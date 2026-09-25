"""
api/consumers.py
Django Channels WebSocket consumers.

Two consumers:

1. TripConsumer  — ws/trip/<trip_id>/
   Joined by BOTH the rider and the matched driver for one specific trip.
   - Driver -> server: {"type": "location_update", "lat", "lng", "heading"}
       -> written to TripLocationPing + Driver.current_lat/lng via
          TripService.record_location_ping(), then rebroadcast to the group
          as {"type": "driver_location", ...} so the rider's map moves live.
   - Server -> group: {"type": "trip_update", "trip": {...}} whenever the
     trip's status changes (called from views.py / tasks.py via
     broadcast_trip_update()).

2. NotificationConsumer — ws/notifications/
   One per logged-in user (rider or driver), group name "user_<id>".
   Used for push events that aren't tied to a single trip's map, e.g.
   "ride_offer" (new TripOffer for a driver) or a Notification created by
   NotificationService.send().

Auth: browsers can't set custom headers on a WebSocket handshake, so the
JWT access token is passed as a query param (?token=...) and verified in
TokenAuthMiddleware (core/asgi.py) which populates scope["user"].
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Trip, TripOffer


class TripConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.trip_id = self.scope["url_route"]["kwargs"]["trip_id"]
        self.group_name = f"trip_{self.trip_id}"
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        allowed = await self._user_is_trip_participant(user, self.trip_id)
        if not allowed:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")

        if msg_type == "location_update":
            await self._handle_location_update(content)

    async def _handle_location_update(self, content):
        lat, lng = content.get("lat"), content.get("lng")
        heading = content.get("heading")
        if lat is None or lng is None:
            return

        await self._save_ping(lat, lng, heading)

        # rebroadcast to everyone in the trip room (i.e. the rider's map)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "driver_location", "lat": lat, "lng": lng, "heading": heading},
        )

    # --- group_send handlers (method name must match the "type" key) ---

    async def driver_location(self, event):
        await self.send_json({"type": "driver_location", "lat": event["lat"], "lng": event["lng"], "heading": event.get("heading")})

    async def trip_update(self, event):
        await self.send_json({"type": "trip_update", "trip": event["trip"]})

    # --- DB helpers ---

    @database_sync_to_async
    def _user_is_trip_participant(self, user, trip_id):
        try:
            trip = Trip.objects.select_related("driver__user").get(id=trip_id)
        except Trip.DoesNotExist:
            return False
        if trip.rider_id == user.id:
            return True
        if trip.driver and trip.driver.user_id == user.id:
            return True
        return False

    @database_sync_to_async
    def _save_ping(self, lat, lng, heading):
        from .services import TripService

        trip = Trip.objects.filter(id=self.trip_id).first()
        if trip:
            TripService.record_location_ping(trip, lat, lng, heading)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # this channel is push-only from the server; ignore client frames
        pass

    # --- group_send handlers ---

    async def notification_push(self, event):
        await self.send_json({
            "type": "notification",
            "title": event["title"],
            "body": event["body"],
            "trip_id": event.get("trip_id"),
        })

    async def ride_offer(self, event):
        """Pushed to a driver's personal channel when MatchingService.create_next_offer() fires for them."""
        await self.send_json({"type": "ride_offer", "offer": event["offer"]})


# ---------------------------------------------------------------------------
# Broadcast helpers — call these from views.py / services.py / tasks.py after
# any state change so connected sockets update immediately, in addition to
# whatever the HTTP response already returned to the caller who made the change.
# ---------------------------------------------------------------------------

def broadcast_trip_update(trip):
    """Push the latest trip state to everyone in that trip's WebSocket room."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from .serializers import TripSerializer

    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"trip_{trip.id}",
        {"type": "trip_update", "trip": TripSerializer(trip).data},
    )


def push_ride_offer(offer):
    """Push a new TripOffer straight to the candidate driver's personal channel."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from .serializers import TripOfferSerializer

    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"user_{offer.driver.user_id}",
        {"type": "ride_offer", "offer": TripOfferSerializer(offer).data},
    )