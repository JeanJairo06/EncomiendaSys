from .models import Encomienda

def estadisticas_globales(request):
    """
    Inyecta en TODOS los templates estas variables.
    Visible en el navbar sin tener que pasarlas vista por vista.
    Solo corre si el usuario está autenticado.
    """
    if not request.user.is_authenticated:
        return {}
    
    return {
    'nav_activas': Encomienda.objects.activas().count(),
    'nav_retraso': Encomienda.objects.con_retraso().count(),
    'nav_pendientes': Encomienda.objects.pendientes().count(),
    }