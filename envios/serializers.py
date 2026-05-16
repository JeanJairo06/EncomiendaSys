from rest_framework import serializers
from .models import Encomienda, HistorialEstado, Empleado
from clientes.models import Cliente
from rutas.models import Ruta
from django.utils import timezone

class ClienteSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.ReadOnlyField()
    esta_activo = serializers.ReadOnlyField()

    class Meta:
        model = Cliente
        fields = [
            'id', 'tipo_doc', 'nro_doc',
            'nombres', 'apellidos',
            'nombre_completo', 'telefono',
            'email', 'esta_activo',
        ]

class RutaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ruta
        fields = [
            'id', 'codigo', 'origen', 'destino',
            'precio_base', 'dias_entrega', 'estado',
        ]

class HistorialEstadoSerializer(serializers.ModelSerializer):
    estado_anterior_display = serializers.CharField(
        source='get_estado_anterior_display',
        read_only=True
    )
    estado_nuevo_display = serializers.CharField(
        source='get_estado_nuevo_display',
        read_only=True
    )

    class Meta:
        model = HistorialEstado
        fields = [
            'id',
            'estado_anterior',
            'estado_anterior_display',
            'estado_nuevo',
            'estado_nuevo_display',
            'empleado',
            'observacion',
            'fecha_cambio',
        ]

class EncomiendaBulkSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        encomiendas = [
            Encomienda(**item) for item in validated_data
        ]

        return Encomienda.objects.bulk_create(encomiendas)

    def update(self, instances, validated_data):
        instance_map = {
            encomienda.id: encomienda
            for encomienda in instances
        }

        updated = []

        for item in validated_data:
            encomienda_id = item.pop('id', None)
            encomienda = instance_map.get(encomienda_id)

            if encomienda:
                for campo, valor in item.items():
                    setattr(encomienda, campo, valor)

                updated.append(encomienda)

        if updated:
            Encomienda.objects.bulk_update(
                updated,
                ['estado', 'observaciones', 'costo_envio']
            )

        return updated

class EncomiendaSerializer(serializers.ModelSerializer):
    esta_entregada = serializers.ReadOnlyField()
    tiene_retraso = serializers.ReadOnlyField()
    dias_en_transito = serializers.ReadOnlyField()
    descripcion_corta = serializers.ReadOnlyField()

    estado_display = serializers.SerializerMethodField()

    class Meta:
        model = Encomienda
        fields = [
            'id',
            'codigo',
            'descripcion',
            'descripcion_corta',
            'peso_kg',
            'volumen_cm3',
            'costo_envio',
            'remitente',
            'destinatario',
            'ruta',
            'empleado_registro',
            'estado',
            'estado_display',
            'fecha_registro',
            'fecha_entrega_est',
            'fecha_entrega_real',
            'esta_entregada',
            'tiene_retraso',
            'dias_en_transito',
            'observaciones',
        ]

        read_only_fields = [
            'fecha_registro',
            'fecha_entrega_real',
            'empleado_registro',
        ]
        list_serializer_class = EncomiendaBulkSerializer

    def get_estado_display(self, obj):
        return obj.get_estado_display()
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

        data['ruta_codigo'] = instance.ruta.codigo if instance.ruta else None
        data['ruta_origen'] = instance.ruta.origen if instance.ruta else None
        data['ruta_destino'] = instance.ruta.destino if instance.ruta else None

        data['costo_display'] = f"S/ {instance.costo_envio:.2f}"

        colores = {
            'PE': 'gray',
            'TR': 'blue',
            'RE': 'orange',
            'EN': 'green',
            'CA': 'red',
        }

        data['estado_color'] = colores.get(instance.estado, 'gray')

        request = self.context.get('request')

        if request and not request.user.is_staff:
            data.pop('observaciones', None)
            data.pop('empleado_registro', None)

        return data
    
    def to_internal_value(self, data):
        if hasattr(data, '_mutable'):
            data._mutable = True

        data = data.copy() if hasattr(data, 'copy') else dict(data)

        if 'codigo' in data and data['codigo']:
            data['codigo'] = str(data['codigo']).upper().strip()

        if 'descripcion' in data and data['descripcion']:
            data['descripcion'] = str(data['descripcion']).strip()

        if 'costo_envio' in data and data['costo_envio']:
            data['costo_envio'] = round(float(data['costo_envio']), 2)

        return super().to_internal_value(data)

    def validate_peso_kg(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'El peso debe ser mayor a 0 kg.'
            )

        if value > 500:
            raise serializers.ValidationError(
                'El peso máximo permitido es 500 kg.'
            )

        return value

    def validate_costo_envio(self, value):
        if value < 0:
            raise serializers.ValidationError(
                'El costo no puede ser negativo.'
            )

        return value

    def validate(self, data):
        errors = {}

        if data.get('remitente') == data.get('destinatario'):
            errors['destinatario'] = (
                'El destinatario no puede ser el mismo que el remitente.'
            )

        fecha_est = data.get('fecha_entrega_est')

        if fecha_est and fecha_est < timezone.now().date():
            errors['fecha_entrega_est'] = (
                'La fecha estimada no puede ser en el pasado.'
            )

        ruta = data.get('ruta')
        costo = data.get('costo_envio')

        if ruta and costo and costo < ruta.precio_base:
            errors['costo_envio'] = (
                f'El costo mínimo para esta ruta es S/ {ruta.precio_base}.'
            )

        if errors:
            raise serializers.ValidationError(errors)

        return data

class EncomiendaListSerializer(serializers.ModelSerializer):
    """
    Serializer optimizado para el listado.
    Solo los campos necesarios para mostrar la tabla.
    No incluye descripción larga, observaciones ni historial.
    """

    remitente_nombre = serializers.ReadOnlyField(
        source='remitente.nombre_completo'
    )

    destinatario_nombre = serializers.ReadOnlyField(
        source='destinatario.nombre_completo'
    )

    ruta_destino = serializers.ReadOnlyField(
        source='ruta.destino'
    )

    estado_display = serializers.SerializerMethodField()

    tiene_retraso = serializers.ReadOnlyField()

    class Meta:
        model = Encomienda

        fields = [
            'id',
            'codigo',
            'estado',
            'estado_display',
            'remitente_nombre',
            'destinatario_nombre',
            'ruta_destino',
            'peso_kg',
            'costo_envio',
            'fecha_registro',
            'fecha_entrega_est',
            'tiene_retraso',
        ]

        read_only_fields = ['articulo_id']

    def get_estado_display(self, obj):
        return obj.get_estado_display()

class EncomiendaDetailSerializer(serializers.ModelSerializer):
    """
    Para GET:
        Devuelve objetos anidados completos.

    Para POST/PUT/PATCH:
        Acepta únicamente IDs (write_only).
    """

    # ─────────────────────────────────────────────
    # Campos de solo lectura (objetos completos)
    # ─────────────────────────────────────────────
    remitente = ClienteSerializer(read_only=True)
    destinatario = ClienteSerializer(read_only=True)
    ruta = RutaSerializer(read_only=True)

    # ─────────────────────────────────────────────
    # Campos de solo escritura (IDs)
    # ─────────────────────────────────────────────
    remitente_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.activos(),
        write_only=True,
        source='remitente'
    )

    destinatario_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.activos(),
        write_only=True,
        source='destinatario'
    )

    ruta_id = serializers.PrimaryKeyRelatedField(
        queryset=Ruta.objects.activas(),
        write_only=True,
        source='ruta'
    )

    # ─────────────────────────────────────────────
    # Campos calculados
    # ─────────────────────────────────────────────
    historial = serializers.SerializerMethodField()

    esta_entregada = serializers.ReadOnlyField()
    tiene_retraso = serializers.ReadOnlyField()
    dias_en_transito = serializers.ReadOnlyField()

    # ─────────────────────────────────────────────
    # Configuración Meta
    # ─────────────────────────────────────────────
    class Meta:
        model = Encomienda

        fields = [
            'id',
            'codigo',
            'descripcion',
            'peso_kg',

            'remitente',
            'remitente_id',

            'destinatario',
            'destinatario_id',

            'ruta',
            'ruta_id',

            'estado',
            'costo_envio',

            'fecha_registro',
            'fecha_entrega_est',
            'fecha_entrega_real',

            'esta_entregada',
            'tiene_retraso',
            'dias_en_transito',

            'historial',
            'observaciones',
        ]

    # ─────────────────────────────────────────────
    # Métodos personalizados
    # ─────────────────────────────────────────────
    def get_historial(self, obj):
        """
        Devuelve los últimos 5 cambios de estado.
        """
        return HistorialEstadoSerializer(
            obj.historial.all()[:5],
            many=True
        ).data
    
class EncomiendaV2Serializer(serializers.ModelSerializer):
    """
    Serializer para la API v2.

    Diferencias con v1:
    - remitente y destinatario como objetos anidados completos
    - ruta como objeto anidado
    - Campos de análisis: dias_en_transito, descripcion_corta
    - Campo 'meta' con información de la versión
    """

    # Objetos anidados completos (en v1 son solo IDs)
    remitente = ClienteSerializer(read_only=True)
    destinatario = ClienteSerializer(read_only=True)
    ruta = RutaSerializer(read_only=True)

    # Para escritura: seguir aceptando IDs
    remitente_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.activos(),
        write_only=True,
        source='remitente'
    )

    destinatario_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.activos(),
        write_only=True,
        source='destinatario'
    )

    ruta_id = serializers.PrimaryKeyRelatedField(
        queryset=Ruta.objects.activas(),
        write_only=True,
        source='ruta'
    )

    # Campos nuevos en v2 (propiedades del modelo)
    dias_en_transito = serializers.ReadOnlyField()
    tiene_retraso = serializers.ReadOnlyField()
    esta_entregada = serializers.ReadOnlyField()
    descripcion_corta = serializers.ReadOnlyField()

    # Campo de metadatos de la versión
    meta = serializers.SerializerMethodField()

    class Meta:
        model = Encomienda

        fields = [
            'id',
            'codigo',
            'descripcion',
            'descripcion_corta',
            'peso_kg',
            'volumen_cm3',
            'costo_envio',
            'remitente',
            'remitente_id',
            'destinatario',
            'destinatario_id',
            'ruta',
            'ruta_id',
            'estado',
            'fecha_registro',
            'fecha_entrega_est',
            'dias_en_transito',
            'tiene_retraso',
            'esta_entregada',
            'observaciones',
            'meta',
        ]

        read_only_fields = [
            'codigo',
            'fecha_registro'
        ]

    def get_meta(self, obj):
        """Metadatos útiles para el cliente que consume la API"""
        from django.utils import timezone

        return {
            'version': 'v2',
            'generado': timezone.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'puede_editar': not obj.esta_entregada,
        }
