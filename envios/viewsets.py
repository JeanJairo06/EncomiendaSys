from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter

from django_filters.rest_framework import DjangoFilterBackend
from api.throttles import EmpleadoRateThrottle, CambioEstadoThrottle
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from config.settings import CACHE_TTL


from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes

from api.pagination import (
    EncomiendaPagination,
    HistorialPagination,
)
from api.filters import EncomiendaFilter
from api.permissions import (
    EsEmpleadoActivo,
    EsPropietarioOAdmin,
)

from .models import Encomienda, Empleado
from rutas.models import Ruta

from .serializers import (
    EncomiendaSerializer,
    EncomiendaListSerializer,
    EncomiendaDetailSerializer,
    EncomiendaV2Serializer,
    HistorialEstadoSerializer,
    RutaSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary='Listar encomiendas',
        description=(
            'Devuelve la lista paginada de encomiendas. '
            'Soporta filtros por estado, búsqueda y ordenamiento.'
        ),
        tags=['Encomiendas'],
    ),
    create=extend_schema(
        summary='Crear encomienda',
        description='Registra una nueva encomienda en el sistema.',
        tags=['Encomiendas'],
    ),
    retrieve=extend_schema(
        summary='Detalle de encomienda',
        description=(
            'Devuelve los datos completos de una encomienda '
            'con remitente, destinatario, ruta e historial.'
        ),
        tags=['Encomiendas'],
    ),
    update=extend_schema(
        summary='Actualizar encomienda',
        tags=['Encomiendas'],
    ),
    partial_update=extend_schema(
        summary='Actualizar parcial',
        tags=['Encomiendas'],
    ),
    destroy=extend_schema(
        summary='Eliminar encomienda',
        tags=['Encomiendas'],
    ),
)
class EncomiendaViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet genera automáticamente:

    - list()            → GET /encomiendas/
    - create()          → POST /encomiendas/
    - retrieve()        → GET /encomiendas/{pk}/
    - update()          → PUT /encomiendas/{pk}/
    - partial_update()  → PATCH /encomiendas/{pk}/
    - destroy()         → DELETE /encomiendas/{pk}/
    """

    queryset = Encomienda.objects.con_relaciones()
    #queryset = Encomienda.objects.all()
    serializer_class = EncomiendaSerializer
    permission_classes = [EsEmpleadoActivo]
    pagination_class = EncomiendaPagination
    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_class = EncomiendaFilter

    search_fields = [
        'codigo',
        'remitente__apellidos',
        'destinatario__apellidos',
        'descripcion',
    ]

    ordering_fields = [
        'fecha_registro',
        'peso_kg',
        'costo_envio',
    ]

    ordering = ['-fecha_registro']
    throttle_classes = [EmpleadoRateThrottle]

    def get_throttles(self):
        if self.action == 'cambiar_estado':
            return [CambioEstadoThrottle()]
        return super().get_throttles()

    # ─────────────────────────────────────────────
    # Serializer dinámico por versión
    # ─────────────────────────────────────────────
    def get_serializer_class(self):
        """
        Elegir serializer según versión y acción.

        v1:
        - list      -> EncomiendaSerializer
        - retrieve  -> EncomiendaDetailSerializer
        - write     -> EncomiendaSerializer

        v2:
        - todas las acciones -> EncomiendaV2Serializer
        """

        version = getattr(self.request, 'version', 'v1')

        if version == 'v2':
            return 
        
        if self.action == 'list':
            return EncomiendaListSerializer 

        if self.action == 'retrieve':
            return EncomiendaDetailSerializer

        return EncomiendaSerializer

    # ─────────────────────────────────────────────
    # Queryset optimizado
    # ─────────────────────────────────────────────
    def get_queryset(self):
        """
        v1 y v2 usan el mismo queryset optimizado.
        """

        qs = Encomienda.objects.con_relaciones()

        estado = self.request.query_params.get('estado')

        if estado:
            qs = qs.filter(estado=estado)

        q = self.request.query_params.get('search')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(codigo__icontains=q) |
                Q(remitente__apellidos__icontains=q) |
                Q(destinatario__apellidos__icontains=q)
            )

        if self.action == 'list':
            qs = qs.only(
                # Campos propios de encomienda
                'id', 'codigo', 'estado',
                'peso_kg', 'costo_envio',
                'fecha_registro', 'fecha_entrega_est',
                # FK base requeridas por select_related
                'remitente', 'destinatario', 'ruta',
                'empleado_registro',
                # Campos del remitente
                'remitente__nombres', 'remitente__apellidos',
                # Campos del destinatario
                'destinatario__nombres', 'destinatario__apellidos',
                # Campos de la ruta
                'ruta__destino',
            )
        return qs

    # ─────────────────────────────────────────────
    # Cabeceras de versión
    # ─────────────────────────────────────────────
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)

        response['X-API-Version'] = getattr(
            request,
            'version',
            'v1'
        )

        return response

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)

        response['X-API-Version'] = getattr(
            request,
            'version',
            'v1'
        )

        return response

    # ─────────────────────────────────────────────
    # Creación automática
    # ─────────────────────────────────────────────
    def perform_create(self, serializer):
        empleado = Empleado.objects.get(
            email=self.request.user.email
        )

        serializer.save(
            empleado_registro=empleado
        )

    def perform_update(self, serializer):
        """Invalidar caché cuando se actualiza una encomienda."""
        super().perform_update(serializer)

        cache_key = f'estadisticas_empleado_{self.request.user.id}'
        cache.delete(cache_key)

    # ─────────────────────────────────────────────
    # Permisos dinámicos
    # ─────────────────────────────────────────────
    def get_permissions(self):
        if self.action in [
            'update',
            'partial_update',
            'destroy',
        ]:
            return [
                EsEmpleadoActivo(),
                EsPropietarioOAdmin(),
            ]

        return [EsEmpleadoActivo()]

    # ─────────────────────────────────────────────
    # Cambiar estado
    # ─────────────────────────────────────────────
    @extend_schema(
        summary='Cambiar estado de encomienda',
        description='''
        Cambia el estado de una encomienda y registra
        automáticamente el cambio en el historial.

        Estados disponibles:
        - PE: Pendiente
        - TR: En tránsito
        - DE: En destino
        - EN: Entregado
        - DV: Devuelto
        ''',
        request=OpenApiTypes.OBJECT,
        responses={
            200: EncomiendaSerializer,
            400: OpenApiResponse(
                description='Estado inválido'
            ),
        },
        examples=[
            OpenApiExample(
                'Pasar a En tránsito',
                value={
                    'estado': 'TR',
                    'observacion': 'Recogido en agencia Lima',
                },
                request_only=True,
            ),
        ],
        tags=['Encomiendas'],
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='cambiar_estado',
    )
    def cambiar_estado(self, request, pk=None, version=None):
        enc = self.get_object()

        nuevo_estado = request.data.get('estado')

        observacion = request.data.get(
            'observacion',
            ''
        )

        if not nuevo_estado:
            return Response(
                {'error': 'El campo estado es requerido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            empleado = Empleado.objects.get(
                email=request.user.email
            )

            enc.cambiar_estado(
                nuevo_estado,
                empleado,
                observacion,
            )

            serializer = self.get_serializer(enc)

            cache.delete_many([
                f'estadisticas_empleado_{request.user.id}',
                f'encomienda_detalle_{pk}',
            ])

            return Response(serializer.data)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ─────────────────────────────────────────────
    # Encomiendas con retraso
    # ─────────────────────────────────────────────
    @extend_schema(
        summary='Encomiendas con retraso',
        description=(
            'Lista encomiendas cuya fecha estimada '
            'de entrega ya venció.'
        ),
        tags=['Encomiendas'],
    )
    @action(
        detail=False,
        methods=['get'],
        url_path='con_retraso',
    )
    def con_retraso(self, request, version=None):
        qs = (
            Encomienda.objects
            .con_retraso()
            .con_relaciones()
        )

        serializer = self.get_serializer(
            qs,
            many=True
        )

        return Response(serializer.data)

    # ─────────────────────────────────────────────
    # Encomiendas pendientes
    # ─────────────────────────────────────────────
    @extend_schema(
        summary='Encomiendas pendientes',
        description='Lista encomiendas pendientes.',
        tags=['Encomiendas'],
    )
    @action(detail=False, methods=['get'])
    def pendientes(self, request, version=None):
        qs = (
            Encomienda.objects
            .pendientes()
            .con_relaciones()
        )

        serializer = self.get_serializer(
            qs,
            many=True
        )

        return Response(serializer.data)

    # ─────────────────────────────────────────────
    # Historial
    # ─────────────────────────────────────────────
    @extend_schema(
        summary='Historial de estados',
        description=(
            'Devuelve el historial paginado '
            'de cambios de estado.'
        ),
        parameters=[
            OpenApiParameter(
                name='limit',
                type=int,
                description='Cantidad de resultados',
                default=10,
            ),
            OpenApiParameter(
                name='offset',
                type=int,
                description='Posición inicial',
                default=0,
            ),
        ],
        tags=['Encomiendas'],
    )
    @action(
        detail=True,
        methods=['get'],
        url_path='historial',
    )
    def historial(self, request, pk=None, version=None):
        enc = self.get_object()

        qs = (
            enc.historial
            .select_related('empleado')
            .order_by('-fecha_cambio')
        )

        paginator = HistorialPagination()

        page = paginator.paginate_queryset(
            qs,
            request
        )

        if page is not None:
            serializer = HistorialEstadoSerializer(
                page,
                many=True
            )

            return paginator.get_paginated_response(
                serializer.data
            )

        serializer = HistorialEstadoSerializer(
            qs,
            many=True
        )

        return Response(serializer.data)

    # ─────────────────────────────────────────────
    # Estadísticas
    # ─────────────────────────────────────────────
    @extend_schema(
        summary='Estadísticas globales',
        description='Contadores globales del sistema.',
        tags=['Encomiendas'],
    )
    @action(detail=False, methods=['get'])
    def estadisticas(self, request, version=None):
        from django.utils import timezone

        cache_key = f'estadisticas_empleado_{request.user.id}'
        data = cache.get(cache_key)

        if data is None:
            hoy = timezone.now().date()

            total_activas = Encomienda.objects.activas().count()
            pendientes = Encomienda.objects.pendientes().count()
            en_transito = Encomienda.objects.en_transito().count()
            con_retraso = Encomienda.objects.con_retraso().count()
            entregadas = Encomienda.objects.entregadas().count()
            entregadas_hoy = Encomienda.objects.filter(
                estado='EN',
                fecha_entrega_real=hoy,
            ).count()
            entregadas_mes = Encomienda.objects.filter(
                estado='EN',
                fecha_entrega_real__month=timezone.now().month,
            ).count()

            data = {
                'total': Encomienda.objects.count(),
                'pendientes': pendientes,
                'entregadas': entregadas,
                'total_activas': total_activas,
                'activas': total_activas,
                'en_transito': en_transito,
                'con_retraso': con_retraso,
                'entregadas_hoy': entregadas_hoy,
                'entregadas_mes': entregadas_mes,
            }
            cache.set(cache_key, data, CACHE_TTL)

        return Response(data)
    
    @extend_schema(
        summary='Crear múltiples encomiendas',
        description=(
            'Crea varias encomiendas en una sola petición. '
            'El body debe contener una lista de objetos.'
        ),
        tags=['Encomiendas'],
    )
    @action(detail=False, methods=['post'], url_path='bulk_create')


    def bulk_create(self, request, version=None):
        """
        POST /api/v1/encomiendas/bulk_create/

        Body:
        [
            {enc1},
            {enc2},
            {enc3}
        ]

        Crea todas las encomiendas con una sola query SQL.
        """

        # many=True activa EncomiendaBulkSerializer automáticamente
        serializer = self.get_serializer(
            data=request.data,
            many=True
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Asignar el empleado a todas las encomiendas
        empleado = Empleado.objects.get(email=request.user.email)

        encomiendas = serializer.save(
            empleado_registro=empleado
        )

        return Response(
            self.get_serializer(
                encomiendas,
                many=True
            ).data,
            status=status.HTTP_201_CREATED
        )
    

    # ── Bulk estado: cambiar estado a múltiples encomiendas ───────────

    @extend_schema(
        summary='Cambiar estado a múltiples encomiendas',
        description=(
            'Cambia el estado de varias encomiendas y reporta '
            'cuáles tuvieron errores.'
        ),
        tags=['Encomiendas'],
    )
    @action(detail=False, methods=['patch'], url_path='bulk_estado')
    def bulk_estado(self, request, version=None):
        """
        PATCH /api/v1/encomiendas/bulk_estado/

        Body:
        {
            "ids": [1, 2, 3],
            "estado": "TR",
            "observacion": "..."
        }

        Procesa cada encomienda y reporta cuáles tuvieron errores.
        """

        ids = request.data.get('ids', [])
        nuevo_estado = request.data.get('estado')
        observacion = request.data.get('observacion', '')

        # Validar que llegaron los campos requeridos
        if not ids:
            return Response(
                {
                    'error': (
                        'El campo ids es requerido y no puede estar vacío.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not nuevo_estado:
            return Response(
                {
                    'error': 'El campo estado es requerido.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            empleado = Empleado.objects.get(
                email=request.user.email
            )

        except Empleado.DoesNotExist:
            return Response(
                {
                    'error': (
                        'El usuario no tiene un empleado asociado.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN
            )

        encomiendas = Encomienda.objects.filter(
            id__in=ids
        )

        actualizadas = []
        errores = []

        for enc in encomiendas:
            try:
                enc.cambiar_estado(
                    nuevo_estado,
                    empleado,
                    observacion
                )

                actualizadas.append(enc.id)

            except ValueError as e:
                errores.append({
                    'id': enc.id,
                    'error': str(e)
                })

        # IDs que no existen
        ids_procesados = list(
            encomiendas.values_list('id', flat=True)
        )

        no_encontrados = [
            i for i in ids
            if i not in ids_procesados
        ]

        return Response({
            'actualizadas': actualizadas,
            'errores': errores,
            'no_encontrados': no_encontrados,
            'total': len(actualizadas),
        })


class RutaViewSet(viewsets.ReadOnlyModelViewSet):
    """Las rutas cambian poco — cachear el listado 15 minutos"""

    queryset = Ruta.objects.activas()
    serializer_class = RutaSerializer

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_headers('Authorization'))
    def list(self, request, *args, **kwargs):
        """Cache por usuario (vary_on_headers diferencia el token)"""
        return super().list(request, *args, **kwargs)
