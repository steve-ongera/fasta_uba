"""
api/views.py
DRF views for the single 'api' app. Uses SimpleJWT for auth.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Driver,
    Notification,
    Payment,
    Rating,
    RiderProfile,
    SavedPlace,
    Trip,
    TripOffer,
    User,
    Vehicle,
)
from .permissions import IsDriver, IsRider, IsTripParticipant
from .serializers import (
    DriverLocationUpdateSerializer,
    DriverPublicSerializer,
    DriverRegistrationExtraSerializer,
    DriverSerializer,
    FareEstimateRequestSerializer,
    FareEstimateResponseSerializer,
    LoginSerializer,
    NotificationSerializer,
    PaymentSerializer,
    RatingSerializer,
    RegisterSerializer,
    RiderProfileSerializer,
    SavedPlaceSerializer,
    TripCancelSerializer,
    TripListSerializer,
    TripOfferSerializer,
    TripRequestSerializer,
    TripSerializer,
    UserSerializer,
    VehicleSerializer,
)
from .services import FareService, MatchingService, NotificationService, TripService


def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            user = serializer.save()

            # if registering as a driver, expect vehicle/license fields too
            if user.role == User.Role.DRIVER:
                extra = DriverRegistrationExtraSerializer(data=request.data)
                extra.is_valid(raise_exception=True)
                d = extra.validated_data
                driver = Driver.objects.create(
                    user=user,
                    license_number=d["license_number"],
                    license_expiry=d["license_expiry"],
                )
                Vehicle.objects.create(
                    driver=driver,
                    vehicle_type=d["vehicle_type"],
                    make=d["make"],
                    model=d["model"],
                    color=d["color"],
                    year=d["year"],
                    plate_number=d["plate_number"],
                    capacity=d.get("capacity", 4),
                )

        tokens = tokens_for_user(user)
        return Response(
            {"user": UserSerializer(user).data, **tokens},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = tokens_for_user(user)
        return Response({"user": UserSerializer(user).data, **tokens})


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = UserSerializer(request.user).data
        if request.user.is_driver:
            driver = get_object_or_404(Driver, user=request.user)
            data["driver_profile"] = DriverSerializer(driver).data
        elif request.user.is_rider:
            rider_profile, _ = RiderProfile.objects.get_or_create(user=request.user)
            data["rider_profile"] = RiderProfileSerializer(rider_profile).data
        return Response(data)


# ---------------------------------------------------------------------------
# FARE ESTIMATE (public-to-authenticated riders, no trip created yet)
# ---------------------------------------------------------------------------

class FareEstimateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = FareEstimateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        estimate = FareService.estimate(
            v["pickup_lat"], v["pickup_lng"], v["dropoff_lat"], v["dropoff_lng"], v["vehicle_type"],
        )
        return Response(FareEstimateResponseSerializer(estimate).data)


# ---------------------------------------------------------------------------
# DRIVER
# ---------------------------------------------------------------------------

class DriverStatusToggleView(APIView):
    """POST {"status": "ONLINE"|"OFFLINE"} — driver goes on/off duty."""
    permission_classes = [permissions.IsAuthenticated, IsDriver]

    def post(self, request):
        driver = get_object_or_404(Driver, user=request.user)
        new_status = request.data.get("status")
        if new_status not in (Driver.Status.ONLINE, Driver.Status.OFFLINE):
            return Response({"detail": "status must be ONLINE or OFFLINE."}, status=400)
        if driver.status == Driver.Status.ON_TRIP:
            return Response({"detail": "Cannot change status while on a trip."}, status=400)
        driver.status = new_status
        driver.save(update_fields=["status"])
        return Response(DriverSerializer(driver).data)


class DriverLocationUpdateView(APIView):
    """
    POST current lat/lng/heading. Called frequently (every few seconds) by
    the driver app while ONLINE or ON_TRIP. Prefer the WebSocket consumer
    (consumers.py) for high-frequency updates in production; this REST
    endpoint is a simple fallback / used for the initial fix.
    """
    permission_classes = [permissions.IsAuthenticated, IsDriver]

    def post(self, request):
        driver = get_object_or_404(Driver, user=request.user)
        serializer = DriverLocationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        driver.current_lat = v["lat"]
        driver.current_lng = v["lng"]
        driver.heading = v.get("heading")
        driver.location_updated_at = timezone.now()
        driver.save(update_fields=["current_lat", "current_lng", "heading", "location_updated_at"])

        # also log a breadcrumb if attached to an active trip
        active_trip = Trip.objects.filter(
            driver=driver, status__in=[Trip.Status.ACCEPTED, Trip.Status.ARRIVED, Trip.Status.IN_PROGRESS]
        ).first()
        if active_trip:
            TripService.record_location_ping(active_trip, v["lat"], v["lng"], v.get("heading"))

        return Response({"detail": "location updated"})


class DriverEarningsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDriver]

    def get(self, request):
        driver = get_object_or_404(Driver, user=request.user)
        completed = Trip.objects.filter(driver=driver, status=Trip.Status.COMPLETED)
        total_earnings = sum((t.final_fare or 0) for t in completed)
        return Response({
            "total_trips": driver.total_trips,
            "total_earnings": total_earnings,
            "wallet_balance": driver.wallet_balance,
            "rating_avg": driver.rating_avg,
        })


class PendingOfferView(APIView):
    """Driver app polls (or is pushed via WS) — get my current pending offer, if any."""
    permission_classes = [permissions.IsAuthenticated, IsDriver]

    def get(self, request):
        driver = get_object_or_404(Driver, user=request.user)
        offer = TripOffer.objects.filter(driver=driver, status=TripOffer.Status.PENDING).order_by("-sent_at").first()
        if not offer:
            return Response(None)
        return Response(TripOfferSerializer(offer).data)


class RespondToOfferView(APIView):
    """POST {"action": "accept"|"decline"}"""
    permission_classes = [permissions.IsAuthenticated, IsDriver]

    def post(self, request, offer_id):
        driver = get_object_or_404(Driver, user=request.user)
        offer = get_object_or_404(TripOffer, id=offer_id, driver=driver, status=TripOffer.Status.PENDING)
        action = request.data.get("action")

        if action == "accept":
            trip = MatchingService.accept_offer(offer)
            NotificationService.send(
                trip.rider, "Driver matched!", f"{driver.user.get_full_name()} is on the way.", trip,
            )
            return Response(TripSerializer(trip).data)

        elif action == "decline":
            MatchingService.decline_offer(offer)
            next_offer = MatchingService.create_next_offer(offer.trip)
            if not next_offer:
                offer.trip.status = Trip.Status.NO_DRIVERS_FOUND
                offer.trip.save(update_fields=["status"])
            return Response({"detail": "declined"})

        return Response({"detail": "action must be accept or decline."}, status=400)


# ---------------------------------------------------------------------------
# RIDER — SAVED PLACES
# ---------------------------------------------------------------------------

class SavedPlaceListCreateView(generics.ListCreateAPIView):
    serializer_class = SavedPlaceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavedPlace.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SavedPlaceDeleteView(generics.DestroyAPIView):
    serializer_class = SavedPlaceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavedPlace.objects.filter(user=self.request.user)


# ---------------------------------------------------------------------------
# TRIP LIFECYCLE
# ---------------------------------------------------------------------------

class RequestTripView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRider]

    def post(self, request):
        serializer = TripRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        existing = Trip.objects.filter(
            rider=request.user,
            status__in=[Trip.Status.REQUESTED, Trip.Status.ACCEPTED, Trip.Status.ARRIVED, Trip.Status.IN_PROGRESS],
        ).exists()
        if existing:
            return Response({"detail": "You already have an active trip."}, status=400)

        trip = TripService.create_trip_request(request.user, serializer.validated_data)

        offer = MatchingService.create_next_offer(trip)
        if not offer:
            trip.status = Trip.Status.NO_DRIVERS_FOUND
            trip.save(update_fields=["status"])
        else:
            NotificationService.send(
                offer.driver.user, "New ride request",
                f"Pickup {trip.estimated_distance_km} km away.", trip,
            )

        return Response(TripSerializer(trip).data, status=status.HTTP_201_CREATED)


class TripDetailView(generics.RetrieveAPIView):
    serializer_class = TripSerializer
    permission_classes = [permissions.IsAuthenticated, IsTripParticipant]
    queryset = Trip.objects.all()
    lookup_url_kwarg = "trip_id"


class MyActiveTripView(APIView):
    """Convenience endpoint: whichever active trip the logged-in user (rider or driver) currently has."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        active_statuses = [Trip.Status.REQUESTED, Trip.Status.ACCEPTED, Trip.Status.ARRIVED, Trip.Status.IN_PROGRESS]
        if request.user.is_rider:
            trip = Trip.objects.filter(rider=request.user, status__in=active_statuses).first()
        else:
            driver = Driver.objects.filter(user=request.user).first()
            trip = Trip.objects.filter(driver=driver, status__in=active_statuses).first() if driver else None
        if not trip:
            return Response(None)
        return Response(TripSerializer(trip).data)


class TripHistoryView(generics.ListAPIView):
    serializer_class = TripListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_driver:
            driver = Driver.objects.filter(user=user).first()
            return Trip.objects.filter(driver=driver).order_by("-requested_at")
        return Trip.objects.filter(rider=user).order_by("-requested_at")


class TripArriveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDriver]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver__user=request.user, status=Trip.Status.ACCEPTED)
        trip = TripService.mark_arrived(trip)
        NotificationService.send(trip.rider, "Driver has arrived", "Your driver is waiting at pickup.", trip)
        return Response(TripSerializer(trip).data)


class TripStartView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDriver]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver__user=request.user, status=Trip.Status.ARRIVED)
        trip = TripService.start_trip(trip)
        NotificationService.send(trip.rider, "Trip started", "Enjoy your ride!", trip)
        return Response(TripSerializer(trip).data)


class TripCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDriver]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver__user=request.user, status=Trip.Status.IN_PROGRESS)
        trip = TripService.complete_trip(trip)
        NotificationService.send(
            trip.rider, "Trip completed", f"Total fare: {trip.final_fare}. Thanks for riding!", trip,
        )
        return Response(TripSerializer(trip).data)


class TripCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTripParticipant]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id)
        serializer = TripCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            trip = TripService.cancel_trip(trip, request.user, serializer.validated_data.get("reason", ""))
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)

        other_party = trip.driver.user if request.user == trip.rider and trip.driver else trip.rider
        NotificationService.send(other_party, "Trip cancelled", "The trip was cancelled.", trip)
        return Response(TripSerializer(trip).data)


# ---------------------------------------------------------------------------
# PAYMENT
# ---------------------------------------------------------------------------

class PaymentDetailView(generics.RetrieveAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsTripParticipant]
    queryset = Payment.objects.all()

    def get_object(self):
        trip = get_object_or_404(Trip, id=self.kwargs["trip_id"])
        self.check_object_permissions(self.request, trip)
        return get_object_or_404(Payment, trip=trip)


class ConfirmPaymentView(APIView):
    """Mock payment confirmation — swap internals for real M-Pesa/Stripe webhook handling."""
    permission_classes = [permissions.IsAuthenticated, IsTripParticipant]

    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id)
        self.check_object_permissions(request, trip)
        payment = get_object_or_404(Payment, trip=trip)
        payment.status = Payment.Status.SUCCESS
        payment.transaction_ref = request.data.get("transaction_ref", f"MOCK-{payment.id}")
        payment.save(update_fields=["status", "transaction_ref"])
        trip.is_paid = True
        trip.save(update_fields=["is_paid"])
        return Response(PaymentSerializer(payment).data)


# ---------------------------------------------------------------------------
# RATINGS
# ---------------------------------------------------------------------------

class RateTripView(generics.CreateAPIView):
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]
        rated_user = trip.driver.user if self.request.user == trip.rider else trip.rider
        rating = serializer.save(rated_by=self.request.user, rated_user=rated_user)

        # roll up avg rating
        agg = Rating.objects.filter(rated_user=rated_user)
        count = agg.count()
        avg = sum(r.score for r in agg) / count

        if rated_user.is_driver:
            driver = Driver.objects.get(user=rated_user)
            driver.rating_avg = round(avg, 2)
            driver.rating_count = count
            driver.save(update_fields=["rating_avg", "rating_count"])
        else:
            rp, _ = RiderProfile.objects.get_or_create(user=rated_user)
            rp.rating_avg = round(avg, 2)
            rp.rating_count = count
            rp.save(update_fields=["rating_avg", "rating_count"])

        return rating


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, notification_id):
        notif = get_object_or_404(Notification, id=notification_id, user=request.user)
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response({"detail": "ok"})