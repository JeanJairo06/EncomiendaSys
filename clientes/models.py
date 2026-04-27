from django.db import models

# Importación de enums personalizados para reutilizar opciones
from config.choices import EstadoGeneral, TipoDocumento
from envios.querysets import ClienteQuerySet

class Cliente(models.Model):
    objects = ClienteQuerySet.as_manager()
    """
    Modelo que representa a un cliente dentro del sistema.
    Se almacena información personal, de contacto y estado.
    """

    # ==============================
    # INFORMACIÓN DE IDENTIFICACIÓN
    # ==============================
    # Tipo de documento (DNI, RUC, etc.)
    # Usa un enum para evitar valores inválidos
    tipo_doc = models.CharField( max_length=3, choices=TipoDocumento.choices, default=TipoDocumento.DNI)
    nro_doc = models.CharField(max_length=15, unique=True)

    # ==============================
    # DATOS PERSONALES
    # ==============================
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField( max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True )
    direccion = models.TextField(blank=True, null=True )
    estado = models.IntegerField(choices=EstadoGeneral.choices, default=EstadoGeneral.ACTIVO )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    # ==============================
    # Propiedades
    # ==============================

    @property
    def nombre_completo(self):
        """Nombre y apellidos en formato legible"""
        return f'{self.apellidos}, {self.nombres}'
    
    @property
    def esta_activo(self):
        """Devuelve True si el estado es ACTIVO"""
        return self.estado == EstadoGeneral.ACTIVO
    
    @property
    def total_encomiendas_enviadas(self):
        """Número de encomiendas donde este cliente es remitente"""
        return self.envios_como_remitente.count()

    # ==============================
    # REPRESENTACIÓN EN TEXTO
    # ==============================

    def __str__(self):
        """
        Representación legible del cliente
        (útil en el admin de Django y logs)
        """
        return f'{self.nro_doc} - {self.apellidos}, {self.nombres}'

    # ==============================
    #CONFIGURACIÓN DEL MODELO
    # ==============================

    class Meta:
        # Nombre de la tabla en la base de datos
        db_table = 'clientes'

        # Nombre legible en singular
        verbose_name = 'Cliente'

        # Nombre legible en plural
        verbose_name_plural = 'Clientes'

        # Orden por defecto en consultas
        ordering = ['apellidos', 'nombres']
