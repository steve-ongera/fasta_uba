"""
api/routing.py
WebSocket URL patterns, included by core/asgi.py.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # live trip tracking: driver location + status updates for one specific trip
    re_path(r"^ws/trip/(?P<trip_id>[0-9a-f-]+)/$", consumers.TripConsumer.as_asgi()),

    # user-level channel: ride offers, "driver matched", "trip cancelled", etc.
    re_path(r"^ws/notifications/$", consumers.NotificationConsumer.as_asgi()),
]