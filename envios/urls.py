from django.urls import path
from . import views
from . import views_cbv


urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('encomiendas/', views.encomienda_lista, name='encomienda_lista'),
    path('encomiendas/nueva/', views.encomienda_crear, name='encomienda_crear'),
    path('encomiendas/<int:pk>/', views.encomienda_detalle, name='encomienda_detalle'),
    path('encomiendas/<int:pk>/estado/', views.encomienda_cambiar_estado, name='encomienda_cambiar_estado'),
    #path('encomiendas/<int:pk>/editar/', views.encomienda_editar, name='encomienda_editar'),
    # Con parámetro texto: <str:codigo>
    #path('encomiendas/buscar/<str:codigo>/', views.buscar_por_codigo, name='buscar_por_codigo'),
    # Con parámetro UUID: <uuid:uuid>
    #path('api/encomiendas/<uuid:uuid>/', views.encomienda_api, name='encomienda_api'),

    # .as_view() convierte la clase en una función vista
    path('', views_cbv.EncomiendaListView.as_view(), name='encomienda_lista'),
    path('<int:pk>/', views_cbv.EncomiendaDetailView.as_view(), name='encomienda_detalle'),
    path('nueva/', views_cbv.EncomiendaCreateView.as_view(), name='encomienda_crear'),
    path('<int:pk>/editar/', views_cbv.EncomiendaUpdateView.as_view(), name='encomienda_editar'),

]