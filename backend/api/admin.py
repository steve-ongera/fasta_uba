from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    Driver,
    Vehicle,
    RiderProfile,
    SavedPlace,
    Trip,
    TripOffer,
    TripLocationPing,
    Payment,
    Rating,
    Notification,
)

# ---------------------------------------------------------------------------
# INLINES
# ---------------------------------------------------------------------------

class VehicleInline(admin.StackedInline):
    model = Vehicle
    can_delete = False
    extra = 0
    show_change_link = True


class RiderProfileInline(admin.StackedInline):
    model = RiderProfile
    can_delete = False
    extra = 0


class DriverProfileInline(admin.StackedInline):
    model = Driver
    can_delete = False
    extra = 0
    show_change_link = True


# ---------------------------------------------------------------------------
# USER ADMIN
# ---------------------------------------------------------------------------

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin handling both riders, drivers, and admins."""
    list_display = (
        "email",
        "username",
        "first_name",
        "last_name",
        "role",
        "phone_number",
        "is_verified",
        "is_staff",
    )
    list_filter = ("role", "is_verified", "is_staff", "is_active", "created_at")
    search_fields = ("email", "username", "first_name", "last_name", "phone_number")
    ordering = ("-created_at",)

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "phone_number", "profile_photo")}),
        ("Role & Permissions", {"fields": ("role", "is_verified", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Live Presence", {"fields": ("last_known_lat", "last_known_lng", "last_seen_at")}),
        ("Important Dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at", "last_login", "date_joined")
    inlines = [DriverProfileInline, RiderProfileInline]


# ---------------------------------------------------------------------------
# DRIVER & VEHICLE ADMIN
# ---------------------------------------------------------------------------

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = (
        "get_full_name",
        "status",
        "license_number",
        "is_approved",
        "rating_avg",
        "total_trips",
        "wallet_balance",
    )
    list_filter = ("status", "is_approved", "license_expiry")
    search_fields = ("user__email", "user__first_name", "user__last_name", "license_number")
    readonly_fields = ("created_at", "updated_at", "rating_avg", "rating_count", "total_trips")
    inlines = [VehicleInline]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = "Driver Name"


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate_number", "make", "model", "color", "vehicle_type", "driver")
    list_filter = ("vehicle_type", "year")
    search_fields = ("plate_number", "make", "model", "driver__user__email")


# ---------------------------------------------------------------------------
# RIDER & PLACES ADMIN
# ---------------------------------------------------------------------------

@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = ("get_full_name", "default_payment_method", "wallet_balance", "total_trips", "rating_avg")
    list_filter = ("default_payment_method",)
    search_fields = ("user__email", "user__first_name", "user__last_name")

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = "Rider Name"


@admin.register(SavedPlace)
class SavedPlaceAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "address")
    search_fields = ("label", "address", "user__email")


# ---------------------------------------------------------------------------
# TRIP & TRACKING ADMIN
# ---------------------------------------------------------------------------

class TripOfferInline(admin.TabularInline):
    model = TripOffer
    extra = 0
    readonly_fields = ("sent_at", "responded_at", "expires_at")


class TripLocationPingInline(admin.TabularInline):
    model = TripLocationPing
    extra = 0
    readonly_fields = ("recorded_at",)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "rider",
        "driver",
        "vehicle_type",
        "estimated_fare",
        "final_fare",
        "requested_at",
    )
    list_filter = ("status", "vehicle_type", "payment_method", "is_paid", "requested_at")
    search_fields = (
        "id",
        "rider__email",
        "driver__user__email",
        "pickup_address",
        "dropoff_address",
    )
    readonly_fields = (
        "requested_at",
        "matched_at",
        "arrived_at",
        "started_at",
        "completed_at",
        "cancelled_at",
    )
    inlines = [TripOfferInline, TripLocationPingInline]


@admin.register(TripOffer)
class TripOfferAdmin(admin.ModelAdmin):
    list_display = ("trip", "driver", "status", "distance_to_pickup_km", "sent_at", "expires_at")
    list_filter = ("status", "sent_at")
    search_fields = ("trip__id", "driver__user__email")


@admin.register(TripLocationPing)
class TripLocationPingAdmin(admin.ModelAdmin):
    list_display = ("trip", "lat", "lng", "speed_kmh", "recorded_at")
    list_filter = ("recorded_at",)
    search_fields = ("trip__id",)


# ---------------------------------------------------------------------------
# PAYMENT, RATINGS & NOTIFICATIONS
# ---------------------------------------------------------------------------

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "trip", "amount", "method", "status", "transaction_ref", "created_at")
    list_filter = ("method", "status", "created_at")
    search_fields = ("id", "transaction_ref", "trip__id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("score", "trip", "rated_by", "rated_user", "created_at")
    list_filter = ("score", "created_at")
    search_fields = ("trip__id", "rated_by__email", "rated_user__email", "comment")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("title", "body", "user__email")