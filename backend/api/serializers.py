"""
api/serializers.py
DRF serializers for every model in api/models.py.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (
    Driver,
    Notification,
    Payment,
    Rating,
    RiderProfile,
    SavedPlace,
    Trip,
    TripLocationPing,
    TripOffer,
    User,
    Vehicle,
)


# ---------------------------------------------------------------------------
# AUTH / USER
# ---------------------------------------------------------------------------

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "phone_number", "role", "profile_photo", "is_verified",
            "created_at",
        ]
        read_only_fields = ["id", "is_verified", "created_at"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username", "first_name", "last_name", "email", "phone_number",
            "role", "password", "password2",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        if attrs.get("role") == User.Role.ADMIN:
            raise serializers.ValidationError({"role": "Cannot self-register as admin."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # auto-create the matching side profile
        if user.role == User.Role.RIDER:
            RiderProfile.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["email"], password=attrs["password"])
        # NB: our AUTHENTICATION_BACKENDS / USERNAME_FIELD=email handles this;
        # see services.authenticate_by_email in services.py used from views.py
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        attrs["user"] = user
        return attrs


class DriverRegistrationExtraSerializer(serializers.Serializer):
    """Extra fields collected only when role == DRIVER during onboarding."""
    license_number = serializers.CharField(max_length=50)
    license_expiry = serializers.DateField()
    vehicle_type = serializers.ChoiceField(choices=Vehicle.VehicleType.choices)
    make = serializers.CharField(max_length=50)
    model = serializers.CharField(max_length=50)
    color = serializers.CharField(max_length=30)
    year = serializers.IntegerField()
    plate_number = serializers.CharField(max_length=20)
    capacity = serializers.IntegerField(default=4)


# ---------------------------------------------------------------------------
# VEHICLE / DRIVER / RIDER PROFILE
# ---------------------------------------------------------------------------

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id", "vehicle_type", "make", "model", "color", "year",
            "plate_number", "capacity", "photo",
        ]


class DriverSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    vehicle = VehicleSerializer(read_only=True)

    class Meta:
        model = Driver
        fields = [
            "id", "user", "vehicle", "status", "current_lat", "current_lng",
            "heading", "location_updated_at", "rating_avg", "rating_count",
            "total_trips", "wallet_balance", "is_approved",
        ]
        read_only_fields = [
            "rating_avg", "rating_count", "total_trips", "wallet_balance", "is_approved",
        ]


class DriverPublicSerializer(serializers.ModelSerializer):
    """What a rider is allowed to see about the driver matched to their trip."""
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)
    photo = serializers.ImageField(source="user.profile_photo", read_only=True)
    vehicle = VehicleSerializer(read_only=True)

    class Meta:
        model = Driver
        fields = [
            "id", "name", "phone_number", "photo", "vehicle",
            "current_lat", "current_lng", "heading", "rating_avg",
        ]


class DriverLocationUpdateSerializer(serializers.Serializer):
    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    heading = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)


class RiderProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = RiderProfile
        fields = [
            "id", "user", "rating_avg", "rating_count", "total_trips",
            "wallet_balance", "default_payment_method",
        ]
        read_only_fields = ["rating_avg", "rating_count", "total_trips", "wallet_balance"]


class SavedPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedPlace
        fields = ["id", "label", "address", "lat", "lng"]


# ---------------------------------------------------------------------------
# TRIP
# ---------------------------------------------------------------------------

class FareEstimateRequestSerializer(serializers.Serializer):
    pickup_lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    pickup_lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    dropoff_lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    dropoff_lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    vehicle_type = serializers.ChoiceField(choices=Vehicle.VehicleType.choices, default=Vehicle.VehicleType.ECONOMY)


class FareEstimateResponseSerializer(serializers.Serializer):
    distance_km = serializers.DecimalField(max_digits=7, decimal_places=2)
    duration_min = serializers.DecimalField(max_digits=6, decimal_places=2)
    surge_multiplier = serializers.DecimalField(max_digits=3, decimal_places=2)
    estimated_fare = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(default="KES")


class TripRequestSerializer(serializers.Serializer):
    """Payload a rider sends to request a new trip."""
    pickup_address = serializers.CharField(max_length=255)
    pickup_lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    pickup_lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    dropoff_address = serializers.CharField(max_length=255)
    dropoff_lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    dropoff_lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    vehicle_type = serializers.ChoiceField(choices=Vehicle.VehicleType.choices, default=Vehicle.VehicleType.ECONOMY)
    payment_method = serializers.ChoiceField(
        choices=[("CASH", "Cash"), ("WALLET", "Wallet"), ("CARD", "Card")], default="CASH"
    )


class TripSerializer(serializers.ModelSerializer):
    rider = UserSerializer(read_only=True)
    driver = DriverPublicSerializer(read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id", "rider", "driver", "vehicle_type",
            "pickup_address", "pickup_lat", "pickup_lng",
            "dropoff_address", "dropoff_lat", "dropoff_lng",
            "status", "estimated_distance_km", "estimated_duration_min",
            "estimated_fare", "actual_distance_km", "actual_duration_min",
            "final_fare", "surge_multiplier", "polyline",
            "payment_method", "is_paid",
            "requested_at", "matched_at", "arrived_at", "started_at",
            "completed_at", "cancelled_at", "cancel_reason",
        ]
        read_only_fields = fields  # trips are mutated only through service actions, never raw PATCH


class TripListSerializer(serializers.ModelSerializer):
    """Lightweight version for history lists."""
    driver_name = serializers.CharField(source="driver.user.get_full_name", read_only=True, default=None)
    rider_name = serializers.CharField(source="rider.get_full_name", read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id", "status", "pickup_address", "dropoff_address",
            "final_fare", "estimated_fare", "requested_at", "completed_at",
            "driver_name", "rider_name",
        ]


class TripCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class TripOfferSerializer(serializers.ModelSerializer):
    trip = TripSerializer(read_only=True)

    class Meta:
        model = TripOffer
        fields = ["id", "trip", "status", "distance_to_pickup_km", "sent_at", "expires_at"]


class TripLocationPingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripLocationPing
        fields = ["lat", "lng", "heading", "speed_kmh", "recorded_at"]


# ---------------------------------------------------------------------------
# PAYMENT / RATING / NOTIFICATION
# ---------------------------------------------------------------------------

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "trip", "amount", "method", "status", "transaction_ref", "created_at"]
        read_only_fields = ["id", "status", "transaction_ref", "created_at"]


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ["id", "trip", "rated_by", "rated_user", "score", "comment", "created_at"]
        read_only_fields = ["id", "rated_by", "rated_user", "created_at"]

    def validate(self, attrs):
        request = self.context["request"]
        trip = attrs["trip"]
        if trip.status != Trip.Status.COMPLETED:
            raise serializers.ValidationError("You can only rate a completed trip.")
        if request.user not in (trip.rider, getattr(trip.driver, "user", None)):
            raise serializers.ValidationError("You were not part of this trip.")
        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "trip", "is_read", "created_at"]
        read_only_fields = ["id", "created_at"]