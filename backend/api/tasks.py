"""
api/tasks.py
Celery tasks. Scheduled periodically by api/scheduler.py (via Celery beat),
and/or triggered ad-hoc from views.py with .delay()/.apply_async().
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def expire_stale_trip_offers():
    """
    Runs every few seconds. Finds TripOffers whose expiry has passed and are
    still PENDING (i.e. the driver never responded), marks them EXPIRED, and
    immediately tries to ring the next-nearest driver for that trip. If no
    candidates remain, the trip is marked NO_DRIVERS_FOUND.
    """
    from .consumers import push_ride_offer
    from .models import Trip, TripOffer
    from .services import MatchingService

    stale_offers = TripOffer.objects.filter(
        status=TripOffer.Status.PENDING, expires_at__lte=timezone.now()
    ).select_related("trip", "driver")

    count = 0
    for offer in stale_offers:
        offer.status = TripOffer.Status.EXPIRED
        offer.responded_at = timezone.now()
        offer.save(update_fields=["status", "responded_at"])
        count += 1

        trip = offer.trip
        if trip.status != Trip.Status.REQUESTED:
            continue  # someone else already got matched to this trip in the meantime

        next_offer = MatchingService.create_next_offer(trip)
        if next_offer:
            push_ride_offer(next_offer)
        else:
            trip.status = Trip.Status.NO_DRIVERS_FOUND
            trip.save(update_fields=["status"])

    if count:
        logger.info("Expired %s stale trip offers", count)
    return count


@shared_task
def auto_cancel_unmatched_requests(max_wait_minutes=10):
    """
    Safety net: if a trip has sat in REQUESTED for too long (offer pool
    exhausted repeatedly, or a bug elsewhere), auto-cancel it so the rider
    isn't stuck waiting forever with no feedback.
    """
    from .models import Trip
    from .services import NotificationService

    cutoff = timezone.now() - timezone.timedelta(minutes=max_wait_minutes)
    stuck_trips = Trip.objects.filter(status=Trip.Status.REQUESTED, requested_at__lte=cutoff)

    count = 0
    for trip in stuck_trips:
        trip.status = Trip.Status.NO_DRIVERS_FOUND
        trip.cancelled_at = timezone.now()
        trip.cancel_reason = "Auto-cancelled: no driver found in time."
        trip.save(update_fields=["status", "cancelled_at", "cancel_reason"])
        NotificationService.send(
            trip.rider, "No drivers available",
            "We couldn't find a driver nearby. Please try again.", trip,
        )
        count += 1

    if count:
        logger.info("Auto-cancelled %s stuck trip requests", count)
    return count


@shared_task
def mark_idle_drivers_offline(idle_minutes=15):
    """
    Drivers who went ONLINE but stopped sending location pings (app closed,
    connection dropped, etc.) get flipped back to OFFLINE so they stop
    showing up in the matching pool.
    """
    from .models import Driver

    cutoff = timezone.now() - timezone.timedelta(minutes=idle_minutes)
    stale = Driver.objects.filter(status=Driver.Status.ONLINE, location_updated_at__lte=cutoff)
    count = stale.update(status=Driver.Status.OFFLINE)
    if count:
        logger.info("Marked %s idle drivers OFFLINE", count)
    return count


@shared_task
def recompute_surge_pricing_snapshot():
    """
    Lightweight periodic job that just logs current supply/demand — useful
    hook point if you later want to cache per-zone surge multipliers instead
    of computing FareService.get_surge_multiplier() on every estimate call.
    """
    from .models import Driver, Trip

    online = Driver.objects.filter(status=Driver.Status.ONLINE).count()
    pending = Trip.objects.filter(status=Trip.Status.REQUESTED).count()
    logger.info("Surge snapshot — online drivers: %s, pending requests: %s", online, pending)
    return {"online_drivers": online, "pending_requests": pending}


@shared_task
def send_trip_receipt_email(trip_id):
    """Stub: hook up your email/SMS provider here once a trip completes and is paid."""
    from .models import Trip

    trip = Trip.objects.filter(id=trip_id).first()
    if not trip:
        return
    logger.info("Would send receipt for trip %s to %s (%s)", trip.id, trip.rider.email, trip.final_fare)