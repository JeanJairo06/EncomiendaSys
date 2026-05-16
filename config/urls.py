"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from envios import views_auth
from rest_framework_simplejwt.views import (TokenObtainPairView,TokenRefreshView,TokenBlacklistView)
from api.auth import EncomiendaTokenView




admin.site.site_header = 'Sistema de Gestión de Encomiendas'
admin.site.site_title = 'Encomiendas Admin'
admin.site.index_title = 'Panel de Administración'


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('envios.urls')),
    #path('accounts/', include('django.contrib.auth.urls')), # login/logout incluidos

    path('login/', views_auth.login_view, name='login'),
    path('logout/', views_auth.logout_view, name='logout'),
    path('perfil/', views_auth.perfil_view, name='perfil'),

    # API REST
    #path('api/v1/', include('api.urls')),
    path('api/<version>/', include('api.urls')),

    #path('api/v1/auth/token/',TokenObtainPairView.as_view(), name='token_obtain'),
    path('api/v1/auth/token/', EncomiendaTokenView.as_view()),
    path('api/v1/auth/token/refresh/',TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/token/blacklist/',TokenBlacklistView.as_view(), name='token_blacklist'),

    # Documentacion
    #path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    #path('api/docs/', SpectacularSwaggerView.as_view(), name='swagger'),
    #path('api/redoc/', SpectacularRedocView.as_view(), name='redoc'),

    

]

#if settings.DEBUG:
#    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
#    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    from silk import urls as silk_urls
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk')),]
    urlpatterns += static(settings.STATIC_URL,document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
