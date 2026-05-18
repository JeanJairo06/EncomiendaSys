from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model

from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from urllib.parse import parse_qs

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_string):
    """
    Valida el token JWT y devuelve el usuario.

    Se ejecuta en un hilo separado (database_sync_to_async)
    porque hace consultas a la base de datos.
    """
    try:
        token = AccessToken(token_string)
        user_id = token["user_id"]

        return User.objects.get(pk=user_id)

    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Middleware de Channels que autentica al usuario vía JWT.

    El token llega como parámetro en la URL:
    ws://localhost:8000/ws/encomiendas/?token=eyJhbGci...
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):

        # Solo procesar conexiones WebSocket
        if scope["type"] == "websocket":

            # Extraer el token del query string
            query_string = scope.get("query_string", b"").decode("utf-8")

            params = parse_qs(query_string)
            token_list = params.get("token", [])

            if token_list:
                # Validar token JWT y obtener usuario
                scope["user"] = await get_user_from_token(
                    token_list[0]
                )
            else:
                scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)


# Función auxiliar para usar en asgi.py
def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(
        AuthMiddlewareStack(inner)
    )