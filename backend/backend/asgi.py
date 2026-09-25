"""
core/asgi.py
ASGI entrypoint. Routes HTTP to Django as normal, and WebSocket connections
through a JWT-aware auth middleware into api/routing.py's consumers.

Run with: daphne -b 0.0.0.0 -p 8000 core.asgi:application
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()  # must run before importing anything that touches models/ORM

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.db import database_sync_to_async  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402
from urllib.parse import parse_qs  # noqa: E402

django_asgi_app = get_asgi_application()

import api.routing  # noqa: E402


@database_sync_to_async
def get_user_from_token(token: str):
    from django.contrib.auth.models import AnonymousUser
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    from api.models import User

    try:
        validated = AccessToken(token)
        return User.objects.get(id=validated["user_id"])
    except (TokenError, InvalidToken, User.DoesNotExist, KeyError):
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Reads ?token=<access_token> off the WebSocket connection query string
    (browsers can't send Authorization headers during the WS handshake) and
    populates scope["user"] the same way DRF's JWTAuthentication does for
    HTTP requests.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser

        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]

        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    # layer our JWT middleware inside Channels' AuthMiddlewareStack so session
    # auth still works too (e.g. Django admin websocket tooling, if any)
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(api.routing.websocket_urlpatterns)
    ),
})