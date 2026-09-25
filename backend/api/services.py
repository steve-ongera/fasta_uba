"""
api/services.py
Business logic layer — kept out of views.py on purpose so it's testable and
reusable from Celery tasks / WebSocket consumers as well as HTTP views.

Contains:
- Geo helpers (Haversine distance, ETA)
- FareService — fare estimation + finalisation, surge pricing
- MatchingService — finds nearest online driver(s) and manages TripOffer rings
- TripService — orchestrates trip state transitions
- NotificationService — thin wrapper to create + push a Notification
"""

import math
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone

from .models import (
    Driver,
    Notification,
    Payment,
    RiderProfile,
    Trip,
    TripOffer,
    User,
)

# ---------------------------------------------------------------------------
# CONFIG (env-driven, with sane defaults — see backend/.env in README)
# ---------------------------------------------------------------------------

BASE_FARE = Decimal(str(getattr(settings, "BASE_FARE", 100)))
RATE_PER_KM = Decimal(str(getattr(settings, "RATE_PER_KM", 45)))
RATE_PER_MIN = Decimal(str(getattr(settings, "RATE_PER_MIN", 5)))
CANCELLATION_FEE = Decimal(str(getattr(settings, "CANCELLATION_FEE", 50)))
DRIVER_SEARCH_RADIUS_KM = Decimal(str(getattr(settings, "DRIVER_SEARCH_RADIUS_KM", 5)))
OFFER_TIMEOUT_SECONDS = getattr(settings, "OFFER_TIMEOUT_SECONDS", 15)
AVERAGE_CITY_SPEED_KMH = Decimal("28")  # used to estimate duration when no Directions API call is made

EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------------------
# GEO HELPERS
# ---------------------------------------------------------------------------

def haversine_km(lat1, lng1, lat2, lng2) -> Decimal:
    """
    Great-circle distance between two lat/lng points, in km.
    Good enough for matching/estimation; the frontend uses Google's
    Directions/Distance Matrix API for the *displayed* route + ETA, and the
    backend can optionally call the same server-side (see get_route_from_google).
    """
    lat1, lng1, lat2, lng2 = map(lambda v: math.radians(float(v)), [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return Decimal(str(round(EARTH_RADIUS_KM * c, 3)))


def estimate_duration_minutes(distance_km: Decimal) -> Decimal:
    if distance_km <= 0:
        return Decimal("0")
    hours = distance_km / AVERAGE_CITY_SPEED_KMH
    return (hours * 60).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_route_from_google(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng):
    """
    Optional server-side call to Google Directions API using
    settings.GOOGLE_MAPS_SERVER_KEY, returning (distance_km, duration_min, polyline).
    Falls back to Haversine + heuristic ETA if the key isn't configured or the
    call fails, so the app keeps working in dev without billing enabled.
    """
    server_key = getattr(settings, "GOOGLE_MAPS_SERVER_KEY", None)
    if not server_key:
        distance_km = haversine_km(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        return distance_km, estimate_duration_minutes(distance_km), None

    import requests  # local import: keeps this optional dependency out of hot path when unused

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/directions/json",
            params={
                "origin": f"{pickup_lat},{pickup_lng}",
                "destination": f"{dropoff_lat},{dropoff_lng}",
                "key": server_key,
            },
            timeout=5,
        )
        data = resp.json()
        leg = data["routes"][0]["legs"][0]
        distance_km = Decimal(str(round(leg["distance"]["value"] / 1000, 3)))
        duration_min = Decimal(str(round(leg["duration"]["value"] / 60, 2)))
        polyline = data["routes"][0]["overview_polyline"]["points"]
        return distance_km, duration_min, polyline
    except Exception:
        distance_km = haversine_km(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        return distance_km, estimate_duration_minutes(distance_km), None


# ---------------------------------------------------------------------------
# FARE SERVICE
# ---------------------------------------------------------------------------

class FareService:
    @staticmethod
    def get_surge_multiplier(vehicle_type: str) -> Decimal:
        """
        Simple demand-based surge stub: ratio of REQUESTED trips to ONLINE
        drivers in the last few minutes. Swap for a geo-bucketed version
        (H3/geohash cells) for real surge pricing.
        """
        from .models import Driver as DriverModel  # avoid circular import at module load

        online_drivers = DriverModel.objects.filter(status=DriverModel.Status.ONLINE).count()
        pending_requests = Trip.objects.filter(status=Trip.Status.REQUESTED).count()

        if online_drivers == 0:
            return Decimal("1.50") if pending_requests > 0 else Decimal("1.00")

        ratio = Decimal(pending_requests) / Decimal(online_drivers)
        if ratio >= Decimal("2.0"):
            return Decimal("1.80")
        if ratio >= Decimal("1.2"):
            return Decimal("1.40")
        if ratio >= Decimal("0.8"):
            return Decimal("1.15")
        return Decimal("1.00")

    @staticmethod
    def calculate_fare(distance_km: Decimal, duration_min: Decimal, surge_multiplier: Decimal = Decimal("1.00")) -> Decimal:
        raw = BASE_FARE + (RATE_PER_KM * distance_km) + (RATE_PER_MIN * duration_min)
        surged = raw * surge_multiplier
        return surged.quantize(Decimal("1"), rounding=ROUND_HALF_UP)  # round to nearest shilling

    @classmethod
    def estimate(cls, pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, vehicle_type="ECONOMY"):
        distance_km, duration_min, polyline = get_route_from_google(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
        )
        surge = cls.get_surge_multiplier(vehicle_type)
        fare = cls.calculate_fare(distance_km, duration_min, surge)
        return {
            "distance_km": distance_km,
            "duration_min": duration_min,
            "surge_multiplier": surge,
            "estimated_fare": fare,
            "polyline": polyline,
        }

    @classmethod
    def finalize(cls, trip: Trip):
        """Called on trip completion — recompute fare off the actual breadcrumb trail if available."""
        distance_km = trip.actual_distance_km or trip.estimated_distance_km
        duration_min = trip.actual_duration_min or trip.estimated_duration_min
        final_fare = cls.calculate_fare(distance_km, duration_min, trip.surge_multiplier)
        trip.final_fare = final_fare
        trip.save(update_fields=["final_fare"])
        return final_fare


# ---------------------------------------------------------------------------
# MATCHING SERVICE
# ---------------------------------------------------------------------------

class MatchingService:
    @staticmethod
    def find_nearby_drivers(pickup_lat, pickup_lng, vehicle_type="ECONOMY", radius_km=None, exclude_driver_ids=None):
        """
        Naive nearest-driver search: pull ONLINE drivers with a recent
        location fix and rank by Haversine distance in Python.
        For production scale, replace with a PostGIS ST_DWithin query or a
        geospatial index (Redis GEO / Elasticsearch geo_distance) instead of
        scanning all online drivers.
        """
        radius_km = radius_km or DRIVER_SEARCH_RADIUS_KM
        exclude_driver_ids = exclude_driver_ids or []

        qs = Driver.objects.filter(
            status=Driver.Status.ONLINE,
            is_approved=True,
            current_lat__isnull=False,
            current_lng__isnull=False,
        ).exclude(id__in=exclude_driver_ids)

        if hasattr(Driver, "vehicle"):
            qs = qs.filter(vehicle__vehicle_type=vehicle_type)

        candidates = []
        for driver in qs.select_related("vehicle", "user"):
            dist = haversine_km(pickup_lat, pickup_lng, driver.current_lat, driver.current_lng)
            if dist <= radius_km:
                candidates.append((dist, driver))

        candidates.sort(key=lambda pair: pair[0])
        return candidates  # list of (distance_km, Driver)

    @classmethod
    def create_next_offer(cls, trip: Trip):
        """
        Find the nearest driver who has NOT already been offered this trip,
        create a TripOffer with an expiry, and return it (or None if the
        pool is exhausted -> caller should mark trip NO_DRIVERS_FOUND).
        This is called once at request time, and again by the offer-timeout
        handler (scheduler.py / tasks.py) each time an offer expires/declines.
        """
        already_offered_ids = list(trip.offers.values_list("driver_id", flat=True))
        candidates = cls.find_nearby_drivers(
            trip.pickup_lat, trip.pickup_lng, trip.vehicle_type,
            exclude_driver_ids=already_offered_ids,
        )
        if not candidates:
            return None

        distance_km, driver = candidates[0]
        expires_at = timezone.now() + timezone.timedelta(seconds=OFFER_TIMEOUT_SECONDS)
        offer = TripOffer.objects.create(
            trip=trip,
            driver=driver,
            distance_to_pickup_km=distance_km,
            expires_at=expires_at,
        )
        return offer

    @staticmethod
    def accept_offer(offer: TripOffer):
        trip = offer.trip
        offer.status = TripOffer.Status.ACCEPTED
        offer.responded_at = timezone.now()
        offer.save(update_fields=["status", "responded_at"])

        trip.driver = offer.driver
        trip.status = Trip.Status.ACCEPTED
        trip.matched_at = timezone.now()
        trip.save(update_fields=["driver", "status", "matched_at"])

        offer.driver.status = Driver.Status.ON_TRIP
        offer.driver.save(update_fields=["status"])

        # expire any other pending offers for this trip
        trip.offers.filter(status=TripOffer.Status.PENDING).exclude(id=offer.id).update(
            status=TripOffer.Status.EXPIRED, responded_at=timezone.now()
        )
        return trip

    @staticmethod
    def decline_offer(offer: TripOffer):
        offer.status = TripOffer.Status.DECLINED
        offer.responded_at = timezone.now()
        offer.save(update_fields=["status", "responded_at"])
        # caller (view/consumer) should immediately call create_next_offer() again


# ---------------------------------------------------------------------------
# TRIP SERVICE — state machine transitions
# ---------------------------------------------------------------------------

class TripService:
    @staticmethod
    def create_trip_request(rider: User, data: dict) -> Trip:
        estimate = FareService.estimate(
            data["pickup_lat"], data["pickup_lng"],
            data["dropoff_lat"], data["dropoff_lng"],
            data.get("vehicle_type", "ECONOMY"),
        )
        trip = Trip.objects.create(
            rider=rider,
            vehicle_type=data.get("vehicle_type", "ECONOMY"),
            pickup_address=data["pickup_address"],
            pickup_lat=data["pickup_lat"],
            pickup_lng=data["pickup_lng"],
            dropoff_address=data["dropoff_address"],
            dropoff_lat=data["dropoff_lat"],
            dropoff_lng=data["dropoff_lng"],
            estimated_distance_km=estimate["distance_km"],
            estimated_duration_min=estimate["duration_min"],
            estimated_fare=estimate["estimated_fare"],
            surge_multiplier=estimate["surge_multiplier"],
            polyline=estimate["polyline"],
            payment_method=data.get("payment_method", "CASH"),
        )
        return trip

    @staticmethod
    def mark_arrived(trip: Trip):
        trip.status = Trip.Status.ARRIVED
        trip.arrived_at = timezone.now()
        trip.save(update_fields=["status", "arrived_at"])
        return trip

    @staticmethod
    def start_trip(trip: Trip):
        trip.status = Trip.Status.IN_PROGRESS
        trip.started_at = timezone.now()
        trip.save(update_fields=["status", "started_at"])
        return trip

    @staticmethod
    def complete_trip(trip: Trip):
        from django.db.models import Sum

        # actual distance ~ sum of consecutive ping-to-ping haversine legs (cheap approximation)
        pings = list(trip.pings.order_by("recorded_at"))
        actual_distance = Decimal("0")
        for prev, curr in zip(pings, pings[1:]):
            actual_distance += haversine_km(prev.lat, prev.lng, curr.lat, curr.lng)

        trip.actual_distance_km = actual_distance if pings else trip.estimated_distance_km
        if trip.started_at:
            elapsed = timezone.now() - trip.started_at
            trip.actual_duration_min = Decimal(str(round(elapsed.total_seconds() / 60, 2)))
        else:
            trip.actual_duration_min = trip.estimated_duration_min

        trip.status = Trip.Status.COMPLETED
        trip.completed_at = timezone.now()
        trip.save(update_fields=[
            "actual_distance_km", "actual_duration_min", "status", "completed_at",
        ])

        FareService.finalize(trip)

        Payment.objects.get_or_create(
            trip=trip,
            defaults={"amount": trip.final_fare, "method": trip.payment_method},
        )

        if trip.driver:
            trip.driver.status = Driver.Status.ONLINE
            trip.driver.total_trips += 1
            trip.driver.save(update_fields=["status", "total_trips"])

        rider_profile = RiderProfile.objects.filter(user=trip.rider).first()
        if rider_profile:
            rider_profile.total_trips += 1
            rider_profile.save(update_fields=["total_trips"])

        return trip

    @staticmethod
    def cancel_trip(trip: Trip, cancelled_by: User, reason: str = ""):
        if cancelled_by == trip.rider:
            trip.status = Trip.Status.CANCELLED_BY_RIDER
        elif trip.driver and cancelled_by == trip.driver.user:
            trip.status = Trip.Status.CANCELLED_BY_DRIVER
        else:
            raise PermissionError("Only the rider or matched driver can cancel this trip.")

        trip.cancelled_at = timezone.now()
        trip.cancel_reason = reason
        trip.save(update_fields=["status", "cancelled_at", "cancel_reason"])

        if trip.driver:
            trip.driver.status = Driver.Status.ONLINE
            trip.driver.save(update_fields=["status"])

        return trip

    @staticmethod
    def record_location_ping(trip: Trip, lat, lng, heading=None, speed_kmh=None):
        from .models import TripLocationPing

        ping = TripLocationPing.objects.create(
            trip=trip, lat=lat, lng=lng, heading=heading, speed_kmh=speed_kmh,
        )
        if trip.driver:
            trip.driver.current_lat = lat
            trip.driver.current_lng = lng
            trip.driver.heading = heading
            trip.driver.location_updated_at = timezone.now()
            trip.driver.save(update_fields=["current_lat", "current_lng", "heading", "location_updated_at"])
        return ping


# ---------------------------------------------------------------------------
# AUTH HELPER
# ---------------------------------------------------------------------------

def authenticate_by_email(email: str, password: str):
    return authenticate(username=email, password=password)


# ---------------------------------------------------------------------------
# NOTIFICATION SERVICE
# ---------------------------------------------------------------------------

class NotificationService:
    @staticmethod
    def send(user: User, title: str, body: str, trip: Trip = None):
        notif = Notification.objects.create(user=user, title=title, body=body, trip=trip)
        # push over WebSocket too, if a channel layer is configured
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"user_{user.id}",
                    {"type": "notification.push", "title": title, "body": body,
                     "trip_id": str(trip.id) if trip else None},
                )
        except Exception:
            pass  # channel layer not configured (e.g. management command context) — safe to skip
        return notif