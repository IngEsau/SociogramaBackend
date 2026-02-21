# core/serializers/pregunta.py
"""
Serializers para Pregunta, Opcion y Respuesta
ACTUALIZADO: polaridad en PreguntaSerializer, soporte escritura para banco de preguntas
"""
from rest_framework import serializers
from core.models import Pregunta, Opcion, Respuesta


class OpcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Opcion
        fields = ['id', 'texto', 'valor', 'orden']
        read_only_fields = ['id']


class PreguntaSerializer(serializers.ModelSerializer):
    """
    Serializer completo para el banco de preguntas.
    Soporta lectura y escritura.
    """
    opciones = OpcionSerializer(many=True, read_only=True)
    es_sociometrica = serializers.BooleanField(read_only=True)

    class Meta:
        model = Pregunta
        fields = [
            'id', 'texto', 'tipo', 'polaridad', 'max_elecciones', 'orden',
            'activa', 'descripcion', 'es_sociometrica', 'opciones', 'creado_en'
        ]
        read_only_fields = ['id', 'creado_en']

    def validate_texto(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                'La pregunta debe tener al menos 10 caracteres.'
            )
        return value.strip()

    def validate_orden(self, value):
        if value < 1:
            raise serializers.ValidationError(
                'El orden debe ser un número positivo.'
            )
        return value

    def validate(self, data):
        # max_elecciones solo aplica a SELECCION_ALUMNO
        tipo = data.get('tipo', getattr(self.instance, 'tipo', None))
        max_elecciones = data.get('max_elecciones', None)

        if tipo != 'SELECCION_ALUMNO' and max_elecciones is not None:
            data['max_elecciones'] = None

        return data


class RespuestaSerializer(serializers.ModelSerializer):
    alumno_matricula = serializers.CharField(source='alumno.matricula', read_only=True)
    seleccionado_nombre = serializers.SerializerMethodField()
    pregunta_texto = serializers.CharField(source='pregunta.texto', read_only=True)
    cuestionario_titulo = serializers.CharField(source='cuestionario.titulo', read_only=True)

    class Meta:
        model = Respuesta
        fields = [
            'id', 'alumno', 'alumno_matricula', 'cuestionario', 'cuestionario_titulo',
            'pregunta', 'pregunta_texto', 'opcion', 'texto_respuesta',
            'seleccionado_alumno', 'seleccionado_nombre',
            'orden_eleccion', 'puntaje', 'creado_en', 'modificado_en'
        ]
        read_only_fields = ['id', 'creado_en', 'modificado_en']

    def get_seleccionado_nombre(self, obj):
        if obj.seleccionado_alumno:
            return obj.seleccionado_alumno.user.nombre_completo
        return None


class RespuestaCreateSerializer(serializers.Serializer):
    pregunta_id = serializers.IntegerField()
    opcion_id = serializers.IntegerField(required=False, allow_null=True)
    texto_respuesta = serializers.CharField(required=False, allow_blank=True, max_length=500)
    seleccionados = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )