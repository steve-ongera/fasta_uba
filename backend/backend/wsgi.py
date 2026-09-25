"""
core/wsgi.py
WSGI entrypoint — used for management commands / any plain-HTTP-only
deployment path. The real app (with WebSockets) is served via core/asgi.py.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

application = get_wsgi_application()