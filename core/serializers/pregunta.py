# core/serializers/pregunta.py
from rest_framework import serializers
from core.models import Pregunta, Opcion, Respuesta

class OpcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Opcion
        fields = ['id', 'texto', 'valor', 'orden']
        read_only_fields = ['id']


class PreguntaSerializer(serializers.ModelSerializer):
    opciones = OpcionSerializer(many=True, read_only=True)
    es_sociometrica = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Pregunta
        fields = [
            'id', 'texto', 'tipo', 'max_elecciones', 'orden',
            'activa', 'descripcion', 'es_sociometrica', 'opciones', 'creado_en'
        ]
        read_only_fields = ['id', 'creado_en']


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