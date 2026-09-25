"""
core/celery.py
Celery application instance. Imported by core/__init__.py so `celery -A core
worker` and `celery -A core beat` both pick it up automatically.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("fastafasta")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()