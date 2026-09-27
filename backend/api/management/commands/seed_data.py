"""
api/management/commands/seed_data.py

Populates the database with demo data so the frontend has something to
show immediately after a fresh `migrate`, without hand-registering users
through the UI every time.

Usage:
    python manage.py seed_data
    python manage.py seed_data --riders 10 --drivers 15
    python manage.py seed_data --flush        # wipe existing demo data first

Creates:
    - N riders (RiderProfile auto-created via signal-less direct create)
    - N drivers, each with a Vehicle, scattered around Nairobi and set ONLINE
      with a current_lat/current_lng so MatchingService.find_nearby_drivers()
      has something to match against immediately
    - A couple of SavedPlace entries per rider (Home / Work)
    - One fully COMPLETED demo trip (with Payment + Rating) between the
      first rider and first driver, so trip history / earnings screens
      aren't empty on first login
    - A fixed demo login for quick manual testing:
        rider:  rider1@example.com  / password123
        driver: driver1@example.com / password123
"""

import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import (
    Driver,
    Payment,
    Rating,
    RiderProfile,
    SavedPlace,
    Trip,
    Vehicle,
)
from api.services import FareService

User = get_user_model()

# Roughly within Nairobi's built-up area, close enough together that
# DRIVER_SEARCH_RADIUS_KM (default 5km) actually finds matches.
NAIROBI_CENTER = (-1.286389, 36.817223)

RIDER_FIRST_NAMES = ["Amina", "Brian", "Cynthia", "David", "Esther", "Faith", "George", "Halima",
                      "Ian", "Joy", "Kevin", "Lilian", "Moses", "Nancy", "Oscar"]
DRIVER_FIRST_NAMES = ["Peter", "Grace", "Samuel", "Mercy", "Daniel", "Ruth", "James", "Alice",
                      "Kennedy", "Winnie", "Felix", "Doreen", "Victor", "Purity", "Erick"]
LAST_NAMES = ["Otieno", "Wanjiru", "Mwangi", "Achieng", "Kariuki", "Njoroge", "Kamau", "Wafula",
              "Cheruiyot", "Nyaga", "Odhiambo", "Mutua", "Kilonzo", "Chege", "Barasa"]

VEHICLE_MAKES_MODELS = [
    ("Toyota", "Axio"), ("Toyota", "Probox"), ("Nissan", "Note"),
    ("Mazda", "Demio"), ("Honda", "Fit"), ("Toyota", "Prado"),
    ("Subaru", "Impreza"), ("Volkswagen", "Golf"),
]
COLORS = ["White", "Silver", "Black", "Blue", "Grey", "Red"]


def jittered_point(center, spread_km=4):
    """Random point within roughly `spread_km` of `center`, for scattering demo drivers."""
    lat, lng = center
    deg_per_km = 1 / 111.0
    d_lat = random.uniform(-spread_km, spread_km) * deg_per_km
    d_lng = random.uniform(-spread_km, spread_km) * deg_per_km
    return round(lat + d_lat, 6), round(lng + d_lng, 6)


class Command(BaseCommand):
    help = "Seed the database with demo riders, drivers, vehicles, and a sample completed trip."

    def add_arguments(self, parser):
        parser.add_argument("--riders", type=int, default=8, help="Number of demo riders to create.")
        parser.add_argument("--drivers", type=int, default=10, help="Number of demo drivers to create.")
        parser.add_argument(
            "--flush", action="store_true",
            help="Delete existing demo users (emails ending in @example.com) before seeding.",
        )

    def handle(self, *args, **options):
        num_riders = options["riders"]
        num_drivers = options["drivers"]

        if options["flush"]:
            self._flush_demo_data()

        riders = self._create_riders(num_riders)
        drivers = self._create_drivers(num_drivers)
        self._create_saved_places(riders)
        self._create_sample_completed_trip(riders[0], drivers[0])

        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded {len(riders)} riders and {len(drivers)} drivers.\n"
            "Demo login:\n"
            "  Rider  -> rider1@example.com  / password123\n"
            "  Driver -> driver1@example.com / password123\n"
        ))

    # ------------------------------------------------------------------
    # FLUSH
    # ------------------------------------------------------------------

    def _flush_demo_data(self):
        deleted, _ = User.objects.filter(email__endswith="@example.com").delete()
        self.stdout.write(self.style.WARNING(f"Flushed {deleted} existing demo records."))

    # ------------------------------------------------------------------
    # RIDERS
    # ------------------------------------------------------------------

    def _create_riders(self, count):
        riders = []
        for i in range(1, count + 1):
            first = RIDER_FIRST_NAMES[(i - 1) % len(RIDER_FIRST_NAMES)]
            last = random.choice(LAST_NAMES)
            email = f"rider{i}@example.com"

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": f"rider{i}",
                    "first_name": first,
                    "last_name": last,
                    "phone_number": f"07{10000000 + i:08d}",
                    "role": User.Role.RIDER,
                    "is_verified": True,
                },
            )
            if created:
                user.set_password("password123")
                user.save(update_fields=["password"])
                RiderProfile.objects.get_or_create(user=user)
                self.stdout.write(f"  + rider {email}")
            riders.append(user)
        return riders

    # ------------------------------------------------------------------
    # DRIVERS
    # ------------------------------------------------------------------

    def _create_drivers(self, count):
        drivers = []
        for i in range(1, count + 1):
            first = DRIVER_FIRST_NAMES[(i - 1) % len(DRIVER_FIRST_NAMES)]
            last = random.choice(LAST_NAMES)
            email = f"driver{i}@example.com"

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": f"driver{i}",
                    "first_name": first,
                    "last_name": last,
                    "phone_number": f"07{20000000 + i:08d}",
                    "role": User.Role.DRIVER,
                    "is_verified": True,
                },
            )
            if created:
                user.set_password("password123")
                user.save(update_fields=["password"])

            lat, lng = jittered_point(NAIROBI_CENTER)

            driver, _ = Driver.objects.get_or_create(
                user=user,
                defaults={
                    "license_number": f"DL{100000 + i}",
                    "license_expiry": timezone.now().date().replace(year=timezone.now().year + 2),
                    "status": Driver.Status.ONLINE,
                    "current_lat": lat,
                    "current_lng": lng,
                    "location_updated_at": timezone.now(),
                    "is_approved": True,
                    "rating_avg": round(random.uniform(4.2, 5.0), 2),
                    "rating_count": random.randint(5, 200),
                    "total_trips": random.randint(5, 400),
                },
            )

            make, model = random.choice(VEHICLE_MAKES_MODELS)
            vehicle_type = random.choice(["ECONOMY", "ECONOMY", "COMFORT", "XL"])  # weight toward ECONOMY
            Vehicle.objects.get_or_create(
                driver=driver,
                defaults={
                    "vehicle_type": vehicle_type,
                    "make": make,
                    "model": model,
                    "color": random.choice(COLORS),
                    "year": random.randint(2012, 2023),
                    "plate_number": f"KD{random.randint(100, 999)}{chr(65 + i % 26)}",
                    "capacity": 6 if vehicle_type == "XL" else 4,
                },
            )

            if _:
                self.stdout.write(f"  + driver {email} ({make} {model}, {vehicle_type})")
            drivers.append(user)
        return drivers

    # ------------------------------------------------------------------
    # SAVED PLACES
    # ------------------------------------------------------------------

    def _create_saved_places(self, riders):
        for rider in riders:
            home_lat, home_lng = jittered_point(NAIROBI_CENTER)
            work_lat, work_lng = jittered_point(NAIROBI_CENTER)
            SavedPlace.objects.get_or_create(
                user=rider, label="Home",
                defaults={"address": "Home address", "lat": home_lat, "lng": home_lng},
            )
            SavedPlace.objects.get_or_create(
                user=rider, label="Work",
                defaults={"address": "Work address", "lat": work_lat, "lng": work_lng},
            )

    # ------------------------------------------------------------------
    # SAMPLE COMPLETED TRIP (so history/earnings screens aren't empty)
    # ------------------------------------------------------------------

    def _create_sample_completed_trip(self, rider, driver_user):
        if Trip.objects.filter(rider=rider, status=Trip.Status.COMPLETED).exists():
            return  # already seeded

        driver = Driver.objects.get(user=driver_user)
        pickup_lat, pickup_lng = jittered_point(NAIROBI_CENTER, spread_km=1)
        dropoff_lat, dropoff_lng = jittered_point(NAIROBI_CENTER, spread_km=3)

        estimate = FareService.estimate(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, "ECONOMY")

        now = timezone.now()
        trip = Trip.objects.create(
            rider=rider,
            driver=driver,
            vehicle_type="ECONOMY",
            pickup_address="Sample Pickup Point, Nairobi",
            pickup_lat=pickup_lat,
            pickup_lng=pickup_lng,
            dropoff_address="Sample Drop-off Point, Nairobi",
            dropoff_lat=dropoff_lat,
            dropoff_lng=dropoff_lng,
            status=Trip.Status.COMPLETED,
            estimated_distance_km=estimate["distance_km"],
            estimated_duration_min=estimate["duration_min"],
            estimated_fare=estimate["estimated_fare"],
            actual_distance_km=estimate["distance_km"],
            actual_duration_min=estimate["duration_min"],
            final_fare=estimate["estimated_fare"],
            surge_multiplier=estimate["surge_multiplier"],
            payment_method="CASH",
            is_paid=True,
            matched_at=now - timezone.timedelta(minutes=40),
            arrived_at=now - timezone.timedelta(minutes=35),
            started_at=now - timezone.timedelta(minutes=30),
            completed_at=now - timezone.timedelta(minutes=10),
        )

        Payment.objects.get_or_create(
            trip=trip,
            defaults={
                "amount": trip.final_fare,
                "method": "CASH",
                "status": Payment.Status.SUCCESS,
                "transaction_ref": "SEED-DEMO-0001",
            },
        )

        Rating.objects.get_or_create(
            trip=trip, rated_by=rider,
            defaults={"rated_user": driver_user, "score": 5, "comment": "Great ride, thanks!"},
        )
        Rating.objects.get_or_create(
            trip=trip, rated_by=driver_user,
            defaults={"rated_user": rider, "score": 5, "comment": "Friendly passenger."},
        )

        driver.total_trips += 1
        driver.save(update_fields=["total_trips"])

        rider_profile, _ = RiderProfile.objects.get_or_create(user=rider)
        rider_profile.total_trips += 1
        rider_profile.save(update_fields=["total_trips"])

        self.stdout.write(f"  + sample completed trip {trip.id} (fare {trip.final_fare})")