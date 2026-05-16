from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from api.throttles import LoginRateThrottle

class EncomiendaTokenSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['username'] = user.username
        token['email'] = user.email

        try:
            emp = user.empleado

            token['empleado_id'] = emp.id
            token['empleado_codigo'] = emp.codigo
            token['cargo'] = emp.cargo

        except Exception:
            pass

        return token


class EncomiendaTokenView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]
    serializer_class = EncomiendaTokenSerializer