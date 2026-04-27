from django.db import models
# Enums para estados del sistema
from config.choices import EstadoGeneral, EstadoEnvio
#validators
from .validators import validar_peso_positivo, validar_codigo_encomienda
from django.core.validators import MinValueValidator, RegexValidator
# Relaciones con otros módulos
from clientes.models import Cliente
from rutas.models import Ruta
#validaciones cruzadas
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from .querysets import EncomiendaQuerySet



# =====================================================
# MODELO: EMPLEADO
# =====================================================

class Empleado(models.Model):
    """
    Representa a los empleados del sistema.
    Son quienes registran envíos y gestionan cambios de estado.
    """
    codigo = models.CharField(max_length=10, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    cargo = models.CharField(max_length=80)
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    estado = models.IntegerField(choices=EstadoGeneral.choices, default=EstadoGeneral.ACTIVO)
    fecha_ingreso = models.DateField()

    # ==============================
    #REPRESENTACIÓN
    # ==============================

    def __str__(self):
        return f'{self.codigo} - {self.apellidos}, {self.nombres}'

    # ==============================
    # CONFIGURACIÓN
    # ==============================

    class Meta:
        db_table = 'empleados'
        verbose_name = 'Empleado'
        verbose_name_plural = 'Empleados'
        ordering = ['apellidos']


# =====================================================
#  MODELO: ENCOMIENDA
# =====================================================

class Encomienda(models.Model):

    objects = EncomiendaQuerySet.as_manager()

    """
    Representa un envío dentro del sistema.
    Contiene información logística, relaciones y estado.
    """
    codigo = models.CharField(max_length=20, unique=True, validators=[validar_codigo_encomienda])
    descripcion = models.TextField()
    peso_kg = models.DecimalField(max_digits=8, decimal_places=2, validators=[validar_peso_positivo,MinValueValidator(0.01, message='El peso mínimo es 0.01 kg')])
    volumen_cm3 = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    remitente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='envios_como_remitente')
    destinatario = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='envios_como_destinatario')
    ruta = models.ForeignKey(Ruta,on_delete=models.PROTECT,related_name='encomiendas')
    empleado_registro = models.ForeignKey(Empleado, on_delete=models.PROTECT,related_name='encomiendas_registradas' )
    estado = models.CharField(max_length=2, choices=EstadoEnvio.choices, default=EstadoEnvio.PENDIENTE)
    costo_envio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_entrega_est = models.DateField(null=True, blank=True)
    fecha_entrega_real = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    # ==============================
    # VALIDACIONES COMPLEJAS
    # ==============================
    def clean(self):
        """Validaciones cruzadas entre campos del modelo"""
        errors ={} 
        # Regla 1: remitente y destinatario no pueden ser la misma persona
        if self.remitente_id and self.destinatario_id:
            if self.remitente_id == self.destinatario_id:
                errors['destinatario'] = ValidationError('El destinatario no puede ser el mismo que el remitente.')
        
        # Regla 2: la fecha de entrega estimada no puede ser en el pasado
        if self.fecha_entrega_est:
            if self.fecha_entrega_est < timezone.now().date():
                errors['fecha_entrega_est'] = ValidationError('La fecha de entrega estimada no puede ser en el pasado.')

        # Regla 3: la fecha de entrega real no puede ser antes de la estimada
        if self.fecha_entrega_est and self.fecha_entrega_real:
            if self.fecha_entrega_real < self.fecha_entrega_est:
                errors['fecha_entrega_real'] = ValidationError('La fecha de entrega real no puede ser antes de la estimada.' )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """
        Asegura que siempre se validen los datos antes de guardar
        """
        self.full_clean()
        super().save(*args, **kwargs)
        
    
    # ==============================
    # Propiedades
    # ==============================

    @property
    def esta_entregada(self):
        return self.estado == EstadoEnvio.ENTREGADO
    
    @property
    def esta_en_transito(self):
        return self.estado == EstadoEnvio.EN_TRANSITO
    
    @property
    def dias_en_transito(self):
        """Días transcurridos desde el registro"""
        if not self.fecha_registro:
            return 0
        delta = timezone.now().date() - self.fecha_registro.date()
        return delta.days
    
    @property
    def tiene_retraso(self):
        """True si la fecha estimada ya pasó y no está entregada"""
        if not self.fecha_entrega_est or self.esta_entregada:
            return False
        return timezone.now().date() > self.fecha_entrega_est
    
    @property
    def descripcion_corta(self):
        """Primeros 50 caracteres de la descripción"""
        return self.descripcion[:50] + '...' if len(self.descripcion) > 50 else self.descripcion

    # ==============================
    # Métodos de instancias
    # ==============================
    def cambiar_estado(self, nuevo_estado, empleado, observacion=''):
        """
        Cambia el estado de la encomienda y registra el cambio
        en HistorialEstado automáticamente.
        Uso: enc.cambiar_estado(EstadoEnvio.EN_TRANSITO, empleado=e1)
        """
        if nuevo_estado == self.estado:
            raise ValueError(f'La encomienda ya se encuentra en estado {self.get_estado_display()}')
        estado_anterior = self.estado
        self.estado = nuevo_estado
        if nuevo_estado == EstadoEnvio.ENTREGADO:
            from django.utils import timezone
            self.fecha_entrega_real = timezone.now().date()
        self.save()
 
        # Registrar en el historial
        HistorialEstado.objects.create(
            encomienda=self,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            empleado=empleado,
            observacion=observacion
        )
        return self
    
    def calcular_costo(self):
        """
        Calcula el costo del envío basándose en el precio
        base de la ruta y el peso del paquete.
        """
        PRECIO_POR_KG_EXTRA = Decimal('2.50') # soles por kg adicional
        PESO_BASE = Decimal('5.00') # los primeros 5kg están en el precio base
        costo = self.ruta.precio_base
        if self.peso_kg > PESO_BASE:
            costo += (self.peso_kg - PESO_BASE) * PRECIO_POR_KG_EXTRA
        return costo.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


    # ==============================
    # Métodos de clase
    # ==============================

    @classmethod
    def crear_con_costo_calculado(cls,remitente,destinatario,ruta,empleado,descripcion,peso_kg,**kwargs):
        """
        Fábrica: crea una encomienda calculando el costo automáticamente.
        El llamador no necesita conocer la fórmula de precio.
        """
        import uuid
        from django.utils import timezone
        from datetime import timedelta
        # GENERAR CÓDIGO ÚNICO
        codigo = f'ENC-{timezone.now().strftime("%Y%m%d")}-{str(uuid.uuid4())[:6].upper()}'

        # CALCULAR FECHA ESTIMADA
        fecha_est = timezone.now().date() + timedelta(days=ruta.dias_entrega)

        # CREAR INSTANCIA
        encomienda = cls(
            codigo=codigo,
            descripcion=descripcion,
            peso_kg=peso_kg,
            remitente=remitente,
            destinatario=destinatario,
            ruta=ruta,
            empleado_registro=empleado,
            fecha_entrega_est=fecha_est,
            **kwargs
        )
        # CALCULAR COSTO
        encomienda.costo_envio = encomienda.calcular_costo()
        # GUARDAR (CON VALIDACIÓN)
        encomienda.save()
        return encomienda

    # ==============================
    # REPRESENTACIÓN
    # ==============================

    def __str__(self):
        return f'{self.codigo} [{self.get_estado_display()}]'

    # ==============================
    # CONFIGURACIÓN
    # ==============================

    class Meta:
        db_table = 'encomiendas'
        verbose_name = 'Encomienda'
        verbose_name_plural = 'Encomiendas'
        ordering = ['-fecha_registro']
    

# =====================================================
# MODELO: HISTORIAL DE ESTADOS
# =====================================================

class HistorialEstado(models.Model):
    """
    Permite auditar todos los cambios de estado de una encomienda.
    Clave para trazabilidad (muy importante en sistemas reales).
    """
    encomienda = models.ForeignKey(Encomienda, on_delete=models.CASCADE, related_name='historial')
    estado_anterior = models.CharField( max_length=2, choices=EstadoEnvio.choices)
    estado_nuevo = models.CharField(max_length=2, choices=EstadoEnvio.choices)
    observacion = models.TextField(blank=True, null=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, related_name='cambios_estado')
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    # ==============================
    # REPRESENTACIÓN
    # ==============================

    def __str__(self):
        return f'{self.encomienda.codigo}: {self.estado_anterior} → {self.estado_nuevo}'

    # ==============================
    # CONFIGURACIÓN
    # ==============================

    class Meta:
        db_table = 'historial_estados'
        ordering = ['-fecha_cambio']