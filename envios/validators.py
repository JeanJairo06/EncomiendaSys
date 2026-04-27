# envios/validators.py

from django.core.exceptions import ValidationError
from django.utils import timezone


# =====================================================
# VALIDACIÓN: PESO POSITIVO
# =====================================================

def validar_peso_positivo(value):
    """
    Valida que el peso sea mayor a 0.
    """
    if value <= 0:
        raise ValidationError(
            f'El peso debe ser mayor a 0. Recibió: {value} kg'
        )


# =====================================================
# VALIDACIÓN: CÓDIGO DE ENCOMIENDA
# =====================================================

def validar_codigo_encomienda(value):
    """
    Valida que el código comience con 'ENC-'
    Ejemplo válido: ENC-0001
    """
    if not value.startswith('ENC-'):
        raise ValidationError(
            'El código de encomienda debe comenzar con ENC-'
        )


# =====================================================
# VALIDACIÓN: DNI
# =====================================================

def validar_nro_doc_dni(value):
    """
    El DNI debe tener exactamente 8 dígitos numéricos.
    """
    if not value.isdigit() or len(value) != 8:
        raise ValidationError(
            'El DNI debe contener exactamente 8 dígitos numéricos'
        )