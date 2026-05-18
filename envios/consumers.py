import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

@database_sync_to_async
def obtener_stats_dashboard():
    from .models import Encomienda

    hoy = timezone.now().date()

    return {
        'activas': Encomienda.objects.activas().count(),
        'en_transito': Encomienda.objects.en_transito().count(),
        'con_retraso': Encomienda.objects.con_retraso().count(),
        'entregadas_hoy': Encomienda.objects.filter(
            estado='EN',
            fecha_entrega_real=hoy
        ).count(),
    }

class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']

        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = 'dashboard'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        stats = await obtener_stats_dashboard()

        await self.send(text_data=json.dumps({
            'tipo': 'stats_iniciales',
            'stats': stats,
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Recibe mensajes enviados desde el navegador.

        Soporta:
        - ping: responde pong
        - solicitar_stats: devuelve estadísticas actuales
        """

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'tipo': 'error',
                'mensaje': 'JSON inválido',
            }))
            return

        tipo = data.get('tipo')

        if tipo == 'ping':
            await self.send(text_data=json.dumps({
                'tipo': 'pong',
            }))
            return

        if tipo == 'solicitar_stats':
            stats = await obtener_stats_dashboard()

            await self.send(text_data=json.dumps({
                'tipo': 'stats_actualizado',
                'stats': stats,
            }))
            return

        await self.send(text_data=json.dumps({
            'tipo': 'error',
            'mensaje': f'Tipo de mensaje no soportado: {tipo}',
        }))

    async def dashboard_actualizar(self, event):
        """
        Recibe eventos desde el channel layer y los reenvía al navegador.
        """

        await self.send(text_data=json.dumps({
            'tipo': 'stats_actualizado',
            'stats': event['stats'],
        }))

    async def encomienda_estado_cambio(self, event):
        """
        Recibe el cambio de estado de una encomienda y lo envía al dashboard.
        """

        await self.send(text_data=json.dumps({
            'tipo': 'estado_cambio',
            'encomienda_id': event['encomienda_id'],
            'codigo': event['codigo'],
            'estado_anterior': event['estado_anterior'],
            'estado_nuevo': event['estado_nuevo'],
            'empleado': event['empleado'],
            'timestamp': event['timestamp'],
        }))

        @database_sync_to_async
        def get_stats(self):
            from .models import Encomienda

            hoy = timezone.now().date()

            return {
                'activas': Encomienda.objects.activas().count(),
                'en_transito': Encomienda.objects.en_transito().count(),
                'con_retraso': Encomienda.objects.con_retraso().count(),
                'entregadas_hoy': Encomienda.objects.filter(
                    estado='EN',
                    fecha_entrega_real=hoy
                ).count(),
            }
    
class EncomiendaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']

        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = 'encomiendas_global'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        stats = await obtener_stats_dashboard()

        await self.send(text_data=json.dumps({
            'tipo': 'conectado',
            'mensaje': f'Bienvenido, {user.username}',
            'stats': stats,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    async def receive(self, text_data):
        """
        Procesa mensajes entrantes del WebSocket.

        Siempre usar try/except para evitar que la conexión
        se cierre por errores no controlados.
        """

        try:
            data = json.loads(text_data)

            await self.procesar_mensaje(data)

        except json.JSONDecodeError:

            await self.send(
                text_data=json.dumps({
                    'tipo': 'error',
                    'codigo': 'JSON_INVALIDO',
                    'mensaje': 'El mensaje no es JSON válido',
                })
            )

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(
                f'Error en consumer: {e}',
                exc_info=True
            )

            await self.send(
                text_data=json.dumps({
                    'tipo': 'error',
                    'codigo': 'ERROR_INTERNO',
                    'mensaje': 'Error interno del servidor',
                })
            )

    async def procesar_mensaje(self, data):
        """
        Procesa mensajes recibidos desde el cliente WebSocket.
        """

        tipo = data.get('tipo')

        if tipo == 'ping':

            await self.send(
                text_data=json.dumps({
                    'tipo': 'pong'
                })
            )

        elif tipo == 'solicitar_stats':

            stats = await self.get_estadisticas()

            await self.send(
                text_data=json.dumps({
                    'tipo': 'stats',
                    'stats': stats,
                })
            )

        else:

            await self.send(
                text_data=json.dumps({
                    'tipo': 'error',
                    'mensaje': f'Tipo desconocido: {tipo}',
                })
            )

    async def encomienda_estado_cambio(self, event):
        """
        Recibe eventos del channel layer y los envía al navegador.
        """

        await self.send(text_data=json.dumps({
            'tipo': 'estado_cambio',
            'encomienda_id': event['encomienda_id'],
            'codigo': event['codigo'],
            'estado_anterior': event['estado_anterior'],
            'estado_nuevo': event['estado_nuevo'],
            'empleado': event['empleado'],
            'timestamp': event['timestamp'],
        }))

    @database_sync_to_async
    def get_stats(self):
        from .models import Encomienda

        hoy = timezone.now().date()

        return {
            'activas': Encomienda.objects.activas().count(),
            'en_transito': Encomienda.objects.en_transito().count(),
            'con_retraso': Encomienda.objects.con_retraso().count(),
            'entregadas_hoy': Encomienda.objects.filter(
                estado='EN',
                fecha_entrega_real=hoy
            ).count(),
        }
    

class EncomiendaDetalleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']

        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.enc_pk = self.scope['url_route']['kwargs']['pk']
        self.group_name = f'encomienda_{self.enc_pk}'

        existe = await self.enc_existe(self.enc_pk)

        if not existe:
            await self.close(code=4004)
            return

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        enc_data = await self.get_encomienda(self.enc_pk)

        await self.send(text_data=json.dumps({
            'tipo': 'estado_actual',
            'encomienda': enc_data,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """
        Este consumer solo escucha cambios enviados por el servidor.
        No necesita procesar mensajes del cliente.
        """

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'tipo': 'error',
                'mensaje': 'JSON inválido',
            }))
            return

        if data.get('tipo') == 'ping':
            await self.send(text_data=json.dumps({
                'tipo': 'pong',
            }))
            return

    async def encomienda_estado_cambio(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'estado_cambio',
            'encomienda_id': event['encomienda_id'],
            'codigo': event['codigo'],
            'estado_anterior': event['estado_anterior'],
            'estado_nuevo': event['estado_nuevo'],
            'empleado': event['empleado'],
            'timestamp': event['timestamp'],
        }))

    @database_sync_to_async
    def enc_existe(self, pk):
        from .models import Encomienda

        return Encomienda.objects.filter(pk=pk).exists()

    @database_sync_to_async
    def get_encomienda(self, pk):
        from .models import Encomienda

        try:
            enc = Encomienda.objects.get(pk=pk)

            return {
                'id': enc.pk,
                'codigo': enc.codigo,
                'estado': enc.estado,
                'estado_display': enc.get_estado_display(),
                'fecha_creacion': enc.fecha_creacion.isoformat() if hasattr(enc, 'fecha_creacion') and enc.fecha_creacion else None,
                'fecha_entrega_real': enc.fecha_entrega_real.isoformat() if hasattr(enc, 'fecha_entrega_real') and enc.fecha_entrega_real else None,
            }

        except Encomienda.DoesNotExist:
            return None