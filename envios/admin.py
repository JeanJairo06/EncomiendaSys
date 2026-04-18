from django.contrib import admin

# Register your models here.
from .models import Encomienda

@admin.register(Encomienda)
class EncomiendaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'peso_kg', 'estado', 'fecha_envio')
    list_filter = ('estado',)
    search_fields = ('codigo', 'descripcion')