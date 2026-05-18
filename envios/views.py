from django.shortcuts import render, redirect, get_object_or_404, get_list_or_404

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import Encomienda, Empleado, HistorialEstado

from clientes.models import Cliente
from rutas.models import Ruta
from config.choices import EstadoEnvio

from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
    Http404,
)

from django.db.models import Q

from django.views.decorators.http import (
    require_http_methods,
    require_GET,
    require_POST,
)
from django.contrib.auth.decorators import (
    permission_required,
    user_passes_test,
)

from django.core.exceptions import PermissionDenied
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from django.views.generic import CreateView

import redis
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import connection
from django.http import JsonResponse

# Condición personalizada para el sistema de encomiendas
def es_empleado_activo(user):
    """True si el user tiene un Empleado activo asociado"""
    return (
        user.is_authenticated and
        Empleado.objects.filter(email=user.email, estado=1).exists()
    )

# ── Vista mínima ─────────────────────────────────────────────
def mi_vista(request):

    # reverse() devuelve la URL como string
    url = reverse('encomienda_detalle', kwargs={'pk': 1})
    # → '/encomiendas/1/'
    return redirect(url)
    '''
    # ── Método HTTP ──────────────────────────────────────────
    request.method
    # 'GET', 'POST', 'PUT', 'DELETE'

    # ── Datos enviados ──────────────────────────────────────
    request.GET
    # parámetros URL (?q=Lima&estado=TR)

    request.POST
    # datos enviados por formulario

    request.FILES
    # archivos subidos

    # ── Usuario autenticado ─────────────────────────────────
    request.user
    # objeto User o AnonymousUser

    request.user.username
    # 'juan.mendoza'

    request.user.is_authenticated
    # True / False

    request.user.email
    # 'juan@encomiendas.pe'

    # ── Sesión ──────────────────────────────────────────────
    request.session

    request.session['ultima_ruta'] = 1
    # guardar valor en sesión

    ruta = request.session.get('ultima_ruta')
    # leer valor

    # ── Meta del request ────────────────────────────────────
    request.path
    # '/encomiendas/1/'

    request.get_full_path()
    # '/encomiendas/1/?page=2'

    request.META['REMOTE_ADDR']
    # IP del cliente

    return HttpResponse('ok')
    '''

class MiView(CreateView):
    success_url = reverse_lazy('encomienda_lista')

# ── Dashboard ───────────────────────────────────────────────
@login_required
def dashboard(request):
    """
    Renderiza el dashboard con estadísticas iniciales.

    Luego, el WebSocket actualizará estos datos en tiempo real.
    """

    hoy = timezone.now().date()

    context = {
        'stats': {
            'activas': Encomienda.objects.activas().count(),
            'en_transito': Encomienda.objects.en_transito().count(),
            'con_retraso': Encomienda.objects.con_retraso().count(),
            'entregadas_hoy': Encomienda.objects.filter(
                estado='EN',
                fecha_entrega_real=hoy
            ).count(),
        }
    }

    return render(request, 'envios/dashboard.html', context)

def encomienda_detalle(request, pk):
    # Si no existe el pk → devuelve 404 automáticamente
    # Nunca más: try/except Encomienda.DoesNotExist
    enc = get_object_or_404(Encomienda, pk=pk)
    # También acepta QuerySets optimizados:
    enc = get_object_or_404(Encomienda.objects.con_relaciones(), pk=pk)
    return render(request, 'envios/detalle.html', {'encomienda': enc})

def encomiendas_por_ruta(request, ruta_pk):
    # Si la lista está vacía → devuelve 404
    encomiendas = get_list_or_404(Encomienda, ruta__pk=ruta_pk)
    return render(request, 'envios/lista.html', {
    'encomiendas': encomiendas,
    })

# ── Crear encomienda ────────────────────────────────────────
@require_http_methods(['GET', 'POST'])
@login_required
@permission_required('envios.add_encomienda', raise_exception=True)
def encomienda_crear(request):
    
    """
    GET  → muestra formulario vacío
    POST → valida, guarda y redirige
    """

    from .forms import EncomiendaForm

    if request.method == 'POST':

        form = EncomiendaForm(request.POST)

        if form.is_valid():

            # Crear objeto sin guardar aún
            enc = form.save(commit=False)

            # Asignar empleado logueado
            enc.empleado_registro = Empleado.objects.get(
                email=request.user.email
            )

            # Guardar en BD
            enc.save()
            # Mensaje éxito
            messages.success(
                request,
                f'Encomienda {enc.codigo} registrada correctamente.'
            )
            # Redirección
            return redirect(
                'encomienda_detalle',
                pk=enc.pk
            )
        
        else:
            messages.error(request, 'Corrige los errores del formulario.')
    else:

        # GET → formulario vacío
        form = EncomiendaForm()

    return render(
        request,
        'envios/form.html',
        {
            'form': form,
            'titulo': 'Nueva Encomienda',
        }
    )

# ── request.GET: filtros por URL ────────────────────────────
# URL:
# /encomiendas/?estado=TR&q=Lima&page=2
@require_GET
@login_required
def encomienda_lista(request):
    estado = request.GET.get('estado', '')
    q = request.GET.get('q', '')
    page = request.GET.get('page', 1)

    qs = Encomienda.objects.con_relaciones()

    # Filtrar por estado
    if estado:
        qs = qs.filter(estado=estado)

    # Búsqueda general
    if q:
        qs = qs.filter(
            Q(codigo__icontains=q) |
            Q(remitente__apellidos__icontains=q) |
            Q(destinatario__apellidos__icontains=q)
        )
    # ── Paginación ────────────────────────────────────────────────
    paginator = Paginator(qs, 15) # 15 por página
    page_number = request.GET.get('page', 1) # página actual
    encomiendas = paginator.get_page(page_number) # objeto Page
    
    #return render(request, 'envios/lista.html', {'enc': qs})
    return render(request, 'envios/lista.html', {
    'encomiendas': encomiendas, # objeto Page (iterable)
    'estados': EstadoEnvio.choices,
    'estado_activo': estado,
    'q': q,
})



# ── request.POST: cambio de estado ──────────────────────────
@require_POST
@login_required
def encomienda_cambiar_estado(request, pk):

    enc = get_object_or_404(
        Encomienda,
        pk=pk
    )

    if request.method == 'POST':

        nuevo_estado = request.POST.get('estado')

        observacion = request.POST.get(
            'observacion',
            ''
        )

        try:

            empleado = Empleado.objects.get(
                email=request.user.email
            )

            enc.cambiar_estado(
                nuevo_estado,
                empleado,
                observacion
            )

            messages.success(
                request,
                f'Estado actualizado a: '
                f'{enc.get_estado_display()}'
            )

        except ValueError as e:

            messages.error(
                request,
                str(e)
            )

    return redirect(
        'encomienda_detalle',
        pk=pk
    )


# ── render() ────────────────────────────────────────────────
# La respuesta más común en Django

def lista_simple(request):

    qs = Encomienda.objects.all()

    return render(
        request,
        'envios/lista.html',
        {
            'enc': qs
        }
    )

# ── redirect() ──────────────────────────────────────────────
# Patrón Post/Redirect/Get

def crear_simple(request):

    if request.method == 'POST':

        # lógica de guardado...
        return redirect(
            'encomienda_detalle',
            pk=1
        )

    return render(
        request,
        'envios/form.html',
        {
            'form': None
        }
    )

# ── JsonResponse() ──────────────────────────────────────────
# Endpoint AJAX/API

def encomienda_estado_json(request, pk):

    enc = get_object_or_404(
        Encomienda,
        pk=pk
    )

    return JsonResponse({

        'codigo': enc.codigo,

        'estado': enc.estado,

        'display': enc.get_estado_display(),

        'retraso': enc.tiene_retraso,

        'dias': enc.dias_en_transito,
    })

# ── Http404 ─────────────────────────────────────────────────
# Recurso no encontrado
def encomienda_por_codigo(request, codigo):

    try:

        enc = Encomienda.objects.get(
            codigo=codigo.upper()
        )

    except Encomienda.DoesNotExist:

        raise Http404(
            f'No existe la encomienda {codigo}'
        )

    return render(
        request,
        'envios/detalle.html',
        {
            'encomienda': enc
        }
    )

@login_required
def eliminar_encomienda(request, pk):
    enc = get_object_or_404(Encomienda, pk=pk)

    # Solo se puede eliminar si está pendiente (lógica de negocio)
    if enc.estado != 'PE':
        raise PermissionDenied # → devuelve 403 Forbidden
    if request.method == 'POST':
        enc.delete()
        messages.success(request, 'Encomienda eliminada.')
        return redirect('encomienda_lista')
    
    return render(request, 'envios/confirmar_eliminar.html', {'enc': enc})

# ── HttpResponse personalizado ──────────────────────────────
def ping(request):

    return HttpResponse(
        'pong',
        status=200,
        content_type='text/plain'
    )


def health_check(request):
    """
    GET /health/

    Verifica el estado general del sistema:
    - PostgreSQL
    - Redis
    - Django Channels
    """

    estado = {
        'postgres': False,
        'redis': False,
        'channels': False,
    }

    # =====================================================
    # PostgreSQL
    # =====================================================

    try:
        connection.ensure_connection()

        estado['postgres'] = True

    except Exception as e:
        estado['postgres_error'] = str(e)

    # =====================================================
    # Redis
    # =====================================================

    try:
        r = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

        r.ping()

        info = r.info()

        estado['redis'] = True
        estado['redis_memoria'] = info.get('used_memory_human')
        estado['redis_clientes'] = info.get('connected_clients')
        estado['redis_version'] = info.get('redis_version')

    except Exception as e:
        estado['redis_error'] = str(e)

    # =====================================================
    # Django Channels
    # =====================================================

    try:
        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            'health_check',
            {
                'type': 'health.ping'
            }
        )

        estado['channels'] = True

    except Exception as e:
        estado['channels_error'] = str(e)

    # =====================================================
    # Usuarios conectados
    # =====================================================

    try:
        r = redis.from_url(settings.REDIS_URL)

        estado['empleados_conectados'] = r.scard(
            'encomiendas:group:encomiendas_global'
        )

    except Exception:
        estado['empleados_conectados'] = None

    # =====================================================
    # Estado global
    # =====================================================

    todo_ok = all([
        estado['postgres'],
        estado['redis'],
        estado['channels'],
    ])

    http_status = 200 if todo_ok else 503

    return JsonResponse(
        estado,
        status=http_status
    )