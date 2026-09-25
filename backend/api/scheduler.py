"""
api/scheduler.py
Registers the periodic ("Celery beat") schedule for api/tasks.py.

Two ways to use this, pick one:

1. Static schedule (simplest — no DB, no admin UI):
   Import CELERY_BEAT_SCHEDULE into core/settings.py:

       from api.scheduler import CELERY_BEAT_SCHEDULE
       CELERY_BEAT_SCHEDULE = CELERY_BEAT_SCHEDULE

   and run: celery -A core beat -l info --scheduler celery.beat:PersistentScheduler

2. Database-backed schedule (recommended — editable from /admin without a
   redeploy, works with settings.CELERY_BEAT_SCHEDULER =
   "django_celery_beat.schedulers:DatabaseScheduler" already set in
   core/settings.py): call `register_periodic_tasks()` once, e.g. from a
   management command or a post-migrate signal, and it upserts the same
   jobs as PeriodicTask rows in the DB.

   Run with: celery -A core beat -l info
"""

from celery.schedules import crontab

# ---------------------------------------------------------------------------
# OPTION 1 — static schedule dict
# ---------------------------------------------------------------------------

CELERY_BEAT_SCHEDULE = {
    "expire-stale-trip-offers": {
        "task": "api.tasks.expire_stale_trip_offers",
        "schedule": 5.0,  # every 5 seconds — offers have a ~15s TTL, so this needs to be tight
    },
    "auto-cancel-unmatched-requests": {
        "task": "api.tasks.auto_cancel_unmatched_requests",
        "schedule": 60.0,  # every minute
        "kwargs": {"max_wait_minutes": 10},
    },
    "mark-idle-drivers-offline": {
        "task": "api.tasks.mark_idle_drivers_offline",
        "schedule": 300.0,  # every 5 minutes
        "kwargs": {"idle_minutes": 15},
    },
    "recompute-surge-pricing-snapshot": {
        "task": "api.tasks.recompute_surge_pricing_snapshot",
        "schedule": crontab(minute="*/2"),  # every 2 minutes
    },
}


# ---------------------------------------------------------------------------
# OPTION 2 — django-celery-beat DatabaseScheduler registration
# ---------------------------------------------------------------------------

def register_periodic_tasks():
    """
    Idempotent upsert of the same jobs as PeriodicTask rows, so they show up
    (and are editable) in Django admin under Periodic Tasks. Safe to call
    multiple times, e.g. from a post_migrate signal or a one-off management
    command (`python manage.py shell -c "from api.scheduler import
    register_periodic_tasks; register_periodic_tasks()"`).
    """
    from django_celery_beat.models import IntervalSchedule, PeriodicTask

    def _every(seconds, name, task, kwargs=None):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=seconds, period=IntervalSchedule.SECONDS
        )
        PeriodicTask.objects.update_or_create(
            name=name,
            defaults={
                "interval": schedule,
                "task": task,
                "kwargs": "{}" if not kwargs else str(kwargs).replace("'", '"'),
                "enabled": True,
            },
        )

    _every(5, "Expire stale trip offers", "api.tasks.expire_stale_trip_offers")
    _every(
        60, "Auto-cancel unmatched requests", "api.tasks.auto_cancel_unmatched_requests",
        kwargs={"max_wait_minutes": 10},
    )
    _every(
        300, "Mark idle drivers offline", "api.tasks.mark_idle_drivers_offline",
        kwargs={"idle_minutes": 15},
    )
    _every(120, "Recompute surge pricing snapshot", "api.tasks.recompute_surge_pricing_snapshot")