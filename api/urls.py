from django.urls import path, include
from rest_framework.routers import DefaultRouter
from envios.viewsets import EncomiendaViewSet
from envios import api_views

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView, 
)

router = DefaultRouter()
router.register('encomiendas', EncomiendaViewSet, basename='encomienda')


urlpatterns = [
    # Auth JWT
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Docs
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),
    # ReDoc: documentación de solo lectura más limpia
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Endpoints
    #path('encomiendas/', api_views.EncomiendaListCreateView.as_view(), name='api_encomienda_lista'),
    #path('encomiendas/<int:pk>/', api_views.EncomiendaDetailView.as_view(), name='api_encomienda_detalle'),
    path('clientes/', api_views.ClienteListView.as_view(), name='api_cliente_lista'),
    path('rutas/', api_views.RutaListView.as_view(), name='api_ruta_lista'),

    path('', include(router.urls)),
]