from rest_framework.views import exception_handler
from rest_framework import status


def encomiendas_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return response

    error_code = 'API_ERROR'
    message = 'Ha ocurrido un error procesando la solicitud.'

    if response.status_code == status.HTTP_400_BAD_REQUEST:
        error_code = 'VALIDATION_ERROR'
        message = 'Los datos enviados contienen errores de validación.'

    elif response.status_code == status.HTTP_401_UNAUTHORIZED:
        error_code = 'AUTHENTICATION_REQUIRED'
        message = 'Se requiere autenticación para acceder a este recurso.'

    elif response.status_code == status.HTTP_403_FORBIDDEN:
        error_code = 'PERMISSION_DENIED'
        message = 'No tienes permisos para realizar esta acción.'

    elif response.status_code == status.HTTP_404_NOT_FOUND:
        error_code = 'NOT_FOUND'
        message = 'El recurso solicitado no existe.'

    elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        error_code = 'THROTTLED'
        message = 'Has realizado demasiadas solicitudes.'

    response.data = {
        'error': True,
        'code': error_code,
        'message': message,
        'detail': response.data,
    }

    return response