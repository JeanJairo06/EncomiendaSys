import json

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from config.asgi import application
from .factories import (
    EmpleadoFactory,
    EncomiendaFactory,
    UserFactory,
)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestEncomiendaConsumer:

    async def test_conexion_sin_autenticacion(self):
        """
        Sin autenticar:
        el servidor debe rechazar con código 4001.
        """

        communicator = WebsocketCommunicator(
            application,
            '/ws/encomiendas/'
        )

        connected, code = await communicator.connect()

        assert not connected
        assert code == 4001

        await communicator.disconnect()

    async def test_conexion_autenticada(self):
        """
        Con usuario autenticado:
        el servidor acepta y envía estadísticas.
        """

        user = await database_sync_to_async(UserFactory)()

        communicator = WebsocketCommunicator(
            application,
            '/ws/encomiendas/'
        )

        # Simular usuario autenticado
        communicator.scope['user'] = user

        connected, _ = await communicator.connect()

        assert connected

        # Mensaje inicial
        response = await communicator.receive_json_from(timeout=3)

        assert response['tipo'] == 'conectado'
        assert 'stats' in response
        assert 'activas' in response['stats']

        await communicator.disconnect()

    async def test_ping_pong(self):
        """
        El consumer responde pong al recibir ping.
        """

        user = await database_sync_to_async(UserFactory)()

        communicator = WebsocketCommunicator(
            application,
            '/ws/encomiendas/'
        )

        communicator.scope['user'] = user

        await communicator.connect()

        # Consumir mensaje de bienvenida
        await communicator.receive_json_from(timeout=2)

        # Enviar ping
        await communicator.send_json_to({
            'tipo': 'ping'
        })

        # Esperar pong
        response = await communicator.receive_json_from(timeout=2)

        assert response['tipo'] == 'pong'

        await communicator.disconnect()

    async def test_notificacion_via_channel_layer(self):
        """
        El consumer recibe y reenvía eventos
        provenientes del channel layer.
        """

        user = await database_sync_to_async(UserFactory)()

        communicator = WebsocketCommunicator(
            application,
            '/ws/encomiendas/'
        )

        communicator.scope['user'] = user

        await communicator.connect()

        # Consumir bienvenida
        await communicator.receive_json_from(timeout=2)

        # Simular evento desde el modelo
        channel_layer = get_channel_layer()

        await channel_layer.group_send(
            'encomiendas_global',
            {
                'type': 'encomienda_estado_cambio',
                'encomienda_id': 1,
                'codigo': 'ENC-2026-001',
                'estado_anterior': 'PE',
                'estado_nuevo': 'TR',
                'empleado': 'Mendoza Cruz, Luis',
                'timestamp': '2026-05-14T10:00:00Z',
            }
        )

        # El websocket debe reenviar el evento
        response = await communicator.receive_json_from(timeout=3)

        assert response['tipo'] == 'estado_cambio'
        assert response['codigo'] == 'ENC-2026-001'
        assert response['estado_nuevo'] == 'TR'

        await communicator.disconnect()