import asyncio
import httpx
from django.utils import timezone
from .models import Encomienda
from asgiref.sync import sync_to_async

async def verificar_estado_transportista(codigo: str) -> dict:
    """
    Corrutina que consulta la API del transportista.
    Puede pausarse mientras espera la respuesta HTTP.
    """
    url = f'https://api.transportista.pe/v1/track/{codigo}'

    try:
        async with httpx.AsyncClient() as client:
            # await: se pausa aquí mientras el event loop sigue atendiendo otras tareas
            response = await client.get(url, timeout=5.0)
            data = response.json()

            return {
                'codigo': codigo,
                'encontrado': True,
                'estado_ext': data.get('status'),
                'ubicacion': data.get('location'),
                'timestamp': timezone.now().isoformat(),
            }

    except httpx.TimeoutException:
        return {'codigo': codigo, 'encontrado': False, 'error': 'timeout'}

    except httpx.ConnectError:
        return {'codigo': codigo, 'encontrado': False, 'error': 'conexion'}

async def actualizar_estados_en_transito() -> list:
    """
    Actualiza el estado de todas las encomiendas en tránsito
    consultando la API del transportista en paralelo.
    """

    # 1. Obtener encomiendas en tránsito (query async)
    encomiendas = await Encomienda.objects.en_transito().alist()

    if not encomiendas:
        return []

    # 2. Consultar en paralelo
    # Sin async: N encomiendas * latencia HTTP
    # Con async: concurrencia real
    resultados = await asyncio.gather(
        *[
            verificar_estado_transportista(enc.codigo)
            for enc in encomiendas
        ],
        return_exceptions=True
    )

    # 3. Procesar resultados
    actualizadas = []

    for enc, resultado in zip(encomiendas, resultados):

        if isinstance(resultado, Exception):
            continue  # ignorar errores individuales

        if (
            resultado.get('encontrado')
            and resultado.get('estado_ext') == 'DELIVERED'
        ):
            enc.estado = 'EN'
            enc.fecha_entrega_real = timezone.now().date()

            await enc.asave()  # guardado async
            actualizadas.append(enc.codigo)

    return actualizadas

async def verificar_una(session: httpx.AsyncClient, codigo: str) -> dict:
    """Verifica UNA encomienda. Se ejecuta en paralelo con las demás."""
    try:
        r = await session.get(
            f'https://api.transportista.pe/track/{codigo}',
            timeout=5.0
        )

        return {
            'codigo': codigo,
            'ok': True,
            'data': r.json()
        }

    except httpx.TimeoutException:
        return {
            'codigo': codigo,
            'ok': False,
            'error': 'timeout'
        }

    except Exception as e:
        return {
            'codigo': codigo,
            'ok': False,
            'error': str(e)
        }

async def verificar_lote_completo() -> dict:
    """
    Verifica TODAS las encomiendas en tránsito en paralelo.

    SINCRONO: 50 encomiendas * 1s = 50 segundos
    ASINCRONO: todas en paralelo ≈ 1 segundo
    """

    encomiendas = await sync_to_async(lambda: list(Encomienda.objects.en_transito()))()

    if not encomiendas:
        return {
            'verificadas': 0,
            'resultados': []
        }

    print(f'Verificando {len(encomiendas)} encomiendas en paralelo...')

    async with httpx.AsyncClient() as session:

        tareas = [
            verificar_una(session, enc.codigo)
            for enc in encomiendas
        ]

        resultados = await asyncio.gather(
            *tareas,
            return_exceptions=True
        )

    # 4. Separar resultados
    exitosas = [
        r for r in resultados
        if isinstance(r, dict) and r.get('ok')
    ]

    fallidas = [
        r for r in resultados
        if isinstance(r, dict) and not r.get('ok')
    ]

    errores = [
        r for r in resultados
        if isinstance(r, Exception)
    ]

    return {
        'verificadas': len(encomiendas),
        'exitosas': len(exitosas),
        'fallidas': len(fallidas),
        'errores': len(errores),
        'resultados': resultados,
    }

async def enviar_notificacion_email(codigo: str, nuevo_estado: str):
    """
    Simula el envío de una notificación por email.

    Más adelante podrías reemplazar esto por una integración real
    con correo electrónico.
    """

    await asyncio.sleep(0.5)
    print(f'Email simulado enviado: {codigo} -> {nuevo_estado}')

async def registrar_en_log_externo(enc, estado: str):
    """Registra el cambio en un sistema de logs externo."""
    import httpx
    async with httpx.AsyncClient() as client:
        await client.post(
            'https://logs.empresa.pe/api/encomiendas',
            json={'codigo': enc.codigo, 'estado': estado},
            timeout=3.0
        )

async def cambiar_estado_vista(request, pk: int):
    """
    Vista async que cambia el estado y lanza notificaciones
    en background sin hacer esperar al cliente.
    """

    enc = await Encomienda.objects.aget(pk=pk)
    nuevo_estado = request.data.get('estado')

    # Paso 1: cambio crítico (el cliente espera esta parte)
    enc.estado = nuevo_estado
    await enc.asave()

    # Paso 2: tareas en background (no bloqueantes)
    asyncio.create_task(
        enviar_notificacion_email(enc, nuevo_estado)
    )

    asyncio.create_task(
        registrar_en_log_externo(enc, nuevo_estado)
    )

    # Respuesta inmediata al cliente
    return {
        'ok': True,
        'estado': nuevo_estado
    }

async def verificar_con_timeout(codigo: str) -> dict:
    """
    Verifica una encomienda con un timeout máximo.

    Si la API externa demora demasiado, se devuelve una respuesta
    controlada usando la información local.
    """

    try:
        async with httpx.AsyncClient() as session:
            resultado = await asyncio.wait_for(
                verificar_una(session, codigo),
                timeout=3.0
            )

        return resultado

    except asyncio.TimeoutError:
        return {
            'codigo': codigo,
            'ok': False,
            'fuente': 'cache_local',
            'advertencia': 'La API del transportista no respondió a tiempo.',
        }

async def verificar_lote_con_timeout(codigos: list[str]) -> list[dict]:
    """
    Verifica varios códigos de encomienda, cada uno con control de timeout.
    """

    resultados = await asyncio.gather(
        *[
            verificar_con_timeout(codigo)
            for codigo in codigos
        ],
        return_exceptions=True
    )

    return [
        r if not isinstance(r, Exception) else {'ok': False, 'error': str(r)}
        for r in resultados
    ]

