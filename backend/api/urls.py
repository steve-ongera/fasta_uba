"""
api/urls.py
Included by core/urls.py under /api/
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    # --- AUTH ---
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", views.MeView.as_view(), name="me"),

    # --- FARE ---
    path("fare/estimate/", views.FareEstimateView.as_view(), name="fare_estimate"),

    # --- DRIVER ---
    path("driver/status/", views.DriverStatusToggleView.as_view(), name="driver_status"),
    path("driver/location/", views.DriverLocationUpdateView.as_view(), name="driver_location"),
    path("driver/earnings/", views.DriverEarningsView.as_view(), name="driver_earnings"),
    path("driver/offers/pending/", views.PendingOfferView.as_view(), name="pending_offer"),
    path("driver/offers/<uuid:offer_id>/respond/", views.RespondToOfferView.as_view(), name="respond_offer"),

    # --- SAVED PLACES ---
    path("places/", views.SavedPlaceListCreateView.as_view(), name="saved_places"),
    path("places/<uuid:pk>/", views.SavedPlaceDeleteView.as_view(), name="saved_place_delete"),

    # --- TRIP LIFECYCLE ---
    path("trips/request/", views.RequestTripView.as_view(), name="trip_request"),
    path("trips/active/", views.MyActiveTripView.as_view(), name="trip_active"),
    path("trips/history/", views.TripHistoryView.as_view(), name="trip_history"),
    path("trips/<uuid:trip_id>/", views.TripDetailView.as_view(), name="trip_detail"),
    path("trips/<uuid:trip_id>/arrive/", views.TripArriveView.as_view(), name="trip_arrive"),
    path("trips/<uuid:trip_id>/start/", views.TripStartView.as_view(), name="trip_start"),
    path("trips/<uuid:trip_id>/complete/", views.TripCompleteView.as_view(), name="trip_complete"),
    path("trips/<uuid:trip_id>/cancel/", views.TripCancelView.as_view(), name="trip_cancel"),

    # --- PAYMENT ---
    path("trips/<uuid:trip_id>/payment/", views.PaymentDetailView.as_view(), name="payment_detail"),
    path("trips/<uuid:trip_id>/payment/confirm/", views.ConfirmPaymentView.as_view(), name="payment_confirm"),

    # --- RATINGS ---
    path("ratings/", views.RateTripView.as_view(), name="rate_trip"),

    # --- NOTIFICATIONS ---
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/<uuid:notification_id>/read/", views.NotificationMarkReadView.as_view(), name="notification_read"),
]