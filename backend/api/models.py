"""
api/models.py
FastaFasta — single 'api' app models.

Design notes:
- Custom User model with a `role` field (rider / driver / admin) so one auth
  system serves both sides of the marketplace.
- Driver / Vehicle are separate from User so a driver profile can carry
  verification + vehicle info without bloating the core User table.
- Location points are stored as plain lat/lng DecimalFields for portability
  (works on SQLite for dev). Swap to django.contrib.gis PointField + PostGIS
  in production for real spatial indexing (see services.py note).
- Trip is the central state-machine model.
- TripLocationPing stores the breadcrumb trail of a driver's live location
  during a trip (written from consumers.py over the WebSocket).
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# ---------------------------------------------------------------------------
# USER
# ---------------------------------------------------------------------------

class User(AbstractUser):
    class Role(models.TextChoices):
        RIDER = "RIDER", "Rider"
        DRIVER = "DRIVER", "Driver"
        ADMIN = "ADMIN", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.RIDER)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True)
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    # live presence — used by matching engine for quick lookups without
    # joining to Driver every time
    last_known_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_known_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "phone_number"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"

    @property
    def is_rider(self):
        return self.role == self.Role.RIDER

    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER


# ---------------------------------------------------------------------------
# DRIVER + VEHICLE
# ---------------------------------------------------------------------------

class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        ECONOMY = "ECONOMY", "Economy"
        COMFORT = "COMFORT", "Comfort"
        XL = "XL", "XL"
        BODA = "BODA", "Boda Boda"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    driver = models.OneToOneField(
        "Driver", on_delete=models.CASCADE, related_name="vehicle"
    )
    vehicle_type = models.CharField(max_length=10, choices=VehicleType.choices, default=VehicleType.ECONOMY)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    color = models.CharField(max_length=30)
    year = models.PositiveIntegerField()
    plate_number = models.CharField(max_length=20, unique=True)
    capacity = models.PositiveSmallIntegerField(default=4)
    photo = models.ImageField(upload_to="vehicle_photos/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.make} {self.model} ({self.plate_number})"


class Driver(models.Model):
    class Status(models.TextChoices):
        OFFLINE = "OFFLINE", "Offline"
        ONLINE = "ONLINE", "Online"          # available for requests
        ON_TRIP = "ON_TRIP", "On Trip"        # currently on a trip

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="driver_profile")
    license_number = models.CharField(max_length=50, unique=True)
    license_expiry = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OFFLINE)

    current_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    heading = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)  # compass degrees
    location_updated_at = models.DateTimeField(null=True, blank=True)

    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    rating_count = models.PositiveIntegerField(default=0)
    total_trips = models.PositiveIntegerField(default=0)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_approved = models.BooleanField(default=False)  # admin verification gate
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["current_lat", "current_lng"]),
        ]

    def __str__(self):
        return f"Driver: {self.user.get_full_name()} [{self.status}]"


# ---------------------------------------------------------------------------
# RIDER PROFILE (extra rider-only fields, optional 1:1 extension of User)
# ---------------------------------------------------------------------------

class RiderProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="rider_profile")
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    rating_count = models.PositiveIntegerField(default=0)
    total_trips = models.PositiveIntegerField(default=0)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    default_payment_method = models.CharField(
        max_length=20,
        choices=[("CASH", "Cash"), ("WALLET", "Wallet"), ("CARD", "Card")],
        default="CASH",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rider: {self.user.get_full_name()}"


class SavedPlace(models.Model):
    """Home / Work / favourites — shown as quick-picks on the booking screen."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_places")
    label = models.CharField(max_length=50)  # "Home", "Work", "Gym"...
    address = models.CharField(max_length=255)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return f"{self.label} - {self.user.username}"


# ---------------------------------------------------------------------------
# TRIP — the core state machine
# ---------------------------------------------------------------------------

class Trip(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"        # rider requested, searching for driver
        ACCEPTED = "ACCEPTED", "Accepted"            # driver matched & accepted
        ARRIVED = "ARRIVED", "Driver Arrived"        # driver at pickup point
        IN_PROGRESS = "IN_PROGRESS", "In Progress"   # trip started, en route to dropoff
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED_BY_RIDER = "CANCELLED_BY_RIDER", "Cancelled by Rider"
        CANCELLED_BY_DRIVER = "CANCELLED_BY_DRIVER", "Cancelled by Driver"
        NO_DRIVERS_FOUND = "NO_DRIVERS_FOUND", "No Drivers Found"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    rider = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trips_as_rider")
    driver = models.ForeignKey(
        Driver, on_delete=models.SET_NULL, related_name="trips_as_driver", null=True, blank=True
    )
    vehicle_type = models.CharField(max_length=10, choices=Vehicle.VehicleType.choices, default=Vehicle.VehicleType.ECONOMY)

    # pickup
    pickup_address = models.CharField(max_length=255)
    pickup_lat = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_lng = models.DecimalField(max_digits=9, decimal_places=6)

    # dropoff
    dropoff_address = models.CharField(max_length=255)
    dropoff_lat = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_lng = models.DecimalField(max_digits=9, decimal_places=6)

    status = models.CharField(max_length=25, choices=Status.choices, default=Status.REQUESTED)

    # route/fare snapshot, computed once at request time then finalised at completion
    estimated_distance_km = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    estimated_duration_min = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    estimated_fare = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    actual_distance_km = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    actual_duration_min = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    final_fare = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    surge_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.00)

    polyline = models.TextField(blank=True, null=True)  # encoded Google polyline for the route

    payment_method = models.CharField(
        max_length=20,
        choices=[("CASH", "Cash"), ("WALLET", "Wallet"), ("CARD", "Card")],
        default="CASH",
    )
    is_paid = models.BooleanField(default=False)

    requested_at = models.DateTimeField(auto_now_add=True)
    matched_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["rider", "status"]),
            models.Index(fields=["driver", "status"]),
        ]

    def __str__(self):
        return f"Trip {self.id} [{self.status}]"


class TripOffer(models.Model):
    """
    A single 'ring' sent to one candidate driver for one trip request.
    The matching engine may create several of these in sequence (nearest
    driver first) until one is accepted or the offer pool is exhausted.
    """
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        DECLINED = "DECLINED", "Declined"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="offers")
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="offers")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    distance_to_pickup_km = models.DecimalField(max_digits=6, decimal_places=2)
    sent_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()  # e.g. sent_at + 15 seconds, checked by scheduler.py

    class Meta:
        ordering = ["sent_at"]


class TripLocationPing(models.Model):
    """Breadcrumb trail written while a trip is IN_PROGRESS / ACCEPTED, for live tracking + audit/ETA recompute."""
    id = models.BigAutoField(primary_key=True)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="pings")
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    heading = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    speed_kmh = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["trip", "recorded_at"])]


# ---------------------------------------------------------------------------
# PAYMENT
# ---------------------------------------------------------------------------

class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        WALLET = "WALLET", "Wallet"
        CARD = "CARD", "Card"
        MPESA = "MPESA", "M-Pesa"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="payment")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    transaction_ref = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.amount} [{self.status}] - Trip {self.trip_id}"


# ---------------------------------------------------------------------------
# RATINGS
# ---------------------------------------------------------------------------

class Rating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="ratings")
    rated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings_given")
    rated_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings_received")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("trip", "rated_by")

    def __str__(self):
        return f"{self.score}★ on trip {self.trip_id}"


# ---------------------------------------------------------------------------
# NOTIFICATIONS (simple in-app feed, pushed also via WebSocket)
# ---------------------------------------------------------------------------

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=100)
    body = models.CharField(max_length=255)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]