from django.db import models

# Importación de enum para manejar estados (activo, inactivo, etc.)
from config.choices import EstadoGeneral
from envios.querysets import RutaQuerySet


class Ruta(models.Model):
    objects = RutaQuerySet.as_manager()
    """
    Modelo que representa una ruta de envío.
    Define el trayecto, costo base y tiempo estimado de entrega.
    """

    # ==============================
    # IDENTIFICACIÓN DE LA RUTA
    # ==============================
    codigo = models.CharField(max_length=10, unique=True)
    origen = models.CharField(max_length=100)
    destino = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    precio_base = models.DecimalField(max_digits=10, decimal_places=2)
    dias_entrega = models.PositiveIntegerField(default=1)
    estado = models.IntegerField(choices=EstadoGeneral.choices,default=EstadoGeneral.ACTIVO)

    def __str__(self):
        """
        Representación legible de la ruta
        (útil en admin y debugging)
        """
        return f'{self.codigo}: {self.origen} → {self.destino}'

    # ==============================
    # ⚙️ CONFIGURACIÓN DEL MODELO
    # ==============================

    class Meta:
        # Nombre de la tabla en base de datos
        db_table = 'rutas'

        # Nombre legible en el admin
        verbose_name = 'Ruta'
        verbose_name_plural = 'Rutas'

        # Orden por defecto
        ordering = ['origen', 'destino']