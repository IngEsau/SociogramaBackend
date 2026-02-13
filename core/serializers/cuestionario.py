# core/serializers/cuestionario.py
"""
Serializers para Sistema de Cuestionarios Sociométricos
Las preguntas se crean INLINE con el cuestionario
ACTUALIZADO: Soporte para polaridad de preguntas
"""
from rest_framework import serializers
from core.models import (
    Cuestionario, 
    CuestionarioPregunta, 
    CuestionarioEstado,
    Pregunta,
    Periodo,
    Alumno,
    Grupo,
    AlumnoGrupo
)


# ============================================
# SERIALIZERS DE LECTURA
# ============================================

class PreguntaInlineSerializer(serializers.ModelSerializer):
    """Serializer para mostrar preguntas dentro de un cuestionario"""
    es_sociometrica = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Pregunta
        fields = ['id', 'texto', 'tipo', 'polaridad', 'max_elecciones', 'descripcion', 'es_sociometrica']
        read_only_fields = ['id']


class CuestionarioPreguntaSerializer(serializers.ModelSerializer):
    """Serializer para la relación cuestionario-pregunta"""
    pregunta = PreguntaInlineSerializer(read_only=True)
    
    class Meta:
        model = CuestionarioPregunta
        fields = ['id', 'pregunta', 'orden']
        read_only_fields = ['id']


class CuestionarioListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados"""
    periodo_codigo = serializers.CharField(source='periodo.codigo', read_only=True)
    periodo_nombre = serializers.CharField(source='periodo.nombre', read_only=True)
    total_preguntas = serializers.IntegerField(read_only=True)
    total_respuestas = serializers.IntegerField(read_only=True)
    total_grupos = serializers.IntegerField(read_only=True)
    esta_activo = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Cuestionario
        fields = [
            'id', 'titulo', 'periodo', 'periodo_codigo', 'periodo_nombre',
            'fecha_inicio', 'fecha_fin', 'activo', 'esta_activo',
            'total_preguntas', 'total_respuestas', 'total_grupos', 'creado_en'
        ]
        read_only_fields = ['id', 'creado_en']


class CuestionarioDetailSerializer(serializers.ModelSerializer):
    """Serializer completo con preguntas"""
    periodo_codigo = serializers.CharField(source='periodo.codigo', read_only=True)
    periodo_nombre = serializers.CharField(source='periodo.nombre', read_only=True)
    preguntas = CuestionarioPreguntaSerializer(many=True, read_only=True)
    total_preguntas = serializers.IntegerField(read_only=True)
    total_respuestas = serializers.IntegerField(read_only=True)
    total_grupos = serializers.IntegerField(read_only=True)
    esta_activo = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Cuestionario
        fields = [
            'id', 'titulo', 'descripcion', 'periodo', 'periodo_codigo', 
            'periodo_nombre', 'fecha_inicio', 'fecha_fin', 'activo',
            'esta_activo', 'preguntas', 'total_preguntas', 
            'total_respuestas', 'total_grupos', 'creado_en'
        ]
        read_only_fields = ['id', 'creado_en']


class CuestionarioEstadoSerializer(serializers.ModelSerializer):
    """Serializer para estado de cuestionarios por alumno"""
    alumno_matricula = serializers.CharField(source='alumno.matricula', read_only=True)
    alumno_nombre = serializers.CharField(source='alumno.user.nombre_completo', read_only=True)
    grupo_clave = serializers.CharField(source='grupo.clave', read_only=True)
    cuestionario_titulo = serializers.CharField(source='cuestionario.titulo', read_only=True)
    
    class Meta:
        model = CuestionarioEstado
        fields = [
            'id', 'cuestionario', 'cuestionario_titulo', 
            'alumno', 'alumno_matricula', 'alumno_nombre',
            'grupo', 'grupo_clave',
            'estado', 'progreso', 'fecha_inicio', 'fecha_completado'
        ]
        read_only_fields = ['id', 'progreso', 'fecha_inicio', 'fecha_completado']


# ============================================
# SERIALIZERS DE ESCRITURA
# ============================================

class PreguntaCreateSerializer(serializers.Serializer):
    """Serializer para crear preguntas inline"""
    texto = serializers.CharField(max_length=255)
    tipo = serializers.ChoiceField(choices=[
        'SELECCION_ALUMNO',
        'OPCION', 
        'TEXTO'
    ])
    polaridad = serializers.ChoiceField(
        choices=['POSITIVA', 'NEGATIVA'],
        default='POSITIVA',
        help_text='Positiva: ¿Con quién harías equipo? | Negativa: ¿Con quién NO trabajarías?'
    )
    max_elecciones = serializers.IntegerField(default=3, min_value=1, max_value=10)
    descripcion = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate_texto(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError('La pregunta debe tener al menos 10 caracteres')
        return value.strip()


class CuestionarioCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear cuestionario con preguntas inline"""
    preguntas = serializers.ListField(
        child=PreguntaCreateSerializer(),
        write_only=True,
        min_length=1,
        help_text="Array de preguntas a crear con el cuestionario"
    )
    
    class Meta:
        model = Cuestionario
        fields = [
            'titulo', 'descripcion', 'periodo', 'fecha_inicio', 
            'fecha_fin', 'activo', 'preguntas'
        ]
    
    def validate(self, data):
        """Validaciones"""
        # Validar fechas
        if data['fecha_inicio'] >= data['fecha_fin']:
            raise serializers.ValidationError({
                'fecha_fin': 'La fecha de fin debe ser posterior a la fecha de inicio'
            })
        
        # Validar periodo
        try:
            periodo = Periodo.objects.get(id=data['periodo'].id)
            if not periodo.activo:
                raise serializers.ValidationError({
                    'periodo': 'El periodo seleccionado no está activo'
                })
        except Periodo.DoesNotExist:
            raise serializers.ValidationError({
                'periodo': 'El periodo seleccionado no existe'
            })
        
        # Validar que al menos haya una pregunta
        if not data.get('preguntas'):
            raise serializers.ValidationError({
                'preguntas': 'Debe incluir al menos una pregunta'
            })
        
        return data
    
    def create(self, validated_data):
        """Crear cuestionario con sus preguntas"""
        from django.db import transaction
        
        preguntas_data = validated_data.pop('preguntas')
        
        with transaction.atomic():
            # 1. Crear cuestionario
            cuestionario = Cuestionario.objects.create(**validated_data)
            
            # 2. Crear preguntas y asociarlas
            for orden, pregunta_data in enumerate(preguntas_data, start=1):
                # Crear pregunta con polaridad
                pregunta = Pregunta.objects.create(
                    texto=pregunta_data['texto'],
                    tipo=pregunta_data['tipo'],
                    polaridad=pregunta_data.get('polaridad', 'POSITIVA'),
                    max_elecciones=pregunta_data.get('max_elecciones', 3),
                    descripcion=pregunta_data.get('descripcion', ''),
                    orden=orden,
                    activa=True
                )
                
                # Asociar pregunta con cuestionario
                CuestionarioPregunta.objects.create(
                    cuestionario=cuestionario,
                    pregunta=pregunta,
                    orden=orden
                )
        
        return cuestionario


class CuestionarioUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar cuestionario (no permite modificar preguntas)"""
    
    class Meta:
        model = Cuestionario
        fields = ['titulo', 'descripcion', 'fecha_inicio', 'fecha_fin', 'activo']
    
    def validate(self, data):
        """Validaciones"""
        instance = self.instance
        
        fecha_inicio = data.get('fecha_inicio', instance.fecha_inicio)
        fecha_fin = data.get('fecha_fin', instance.fecha_fin)
        
        if fecha_inicio >= fecha_fin:
            raise serializers.ValidationError({
                'fecha_fin': 'La fecha de fin debe ser posterior a la fecha de inicio'
            })
        
        # No permitir desactivar si ya tiene respuestas
        if 'activo' in data and not data['activo']:
            if instance.total_respuestas > 0:
                raise serializers.ValidationError({
                    'activo': 'No se puede desactivar un cuestionario que ya tiene respuestas'
                })
        
        return data


class AgregarPreguntaSerializer(serializers.Serializer):
    """Serializer para agregar una pregunta adicional al cuestionario"""
    texto = serializers.CharField(max_length=255)
    tipo = serializers.ChoiceField(choices=['SELECCION_ALUMNO', 'OPCION', 'TEXTO'])
    polaridad = serializers.ChoiceField(
        choices=['POSITIVA', 'NEGATIVA'],
        default='POSITIVA'
    )
    max_elecciones = serializers.IntegerField(default=3, min_value=1, max_value=10)
    descripcion = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate_texto(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError('La pregunta debe tener al menos 10 caracteres')
        return value.strip()


# ============================================
# SERIALIZERS PARA RESPUESTAS
# ============================================

class RespuestaCreateSerializer(serializers.Serializer):
    """Serializer para crear respuestas a cuestionarios"""
    cuestionario_id = serializers.IntegerField()
    pregunta_id = serializers.IntegerField()
    opcion_id = serializers.IntegerField(required=False, allow_null=True)
    texto_respuesta = serializers.CharField(required=False, allow_blank=True, max_length=500)
    seleccionados = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        help_text="[{'alumno_id': 1, 'orden': 1}, {'alumno_id': 2, 'orden': 2}]"
    )
    
    def validate(self, data):
        """Validaciones"""
        cuestionario_id = data.get('cuestionario_id')
        pregunta_id = data.get('pregunta_id')
        
        # Validar cuestionario
        try:
            cuestionario = Cuestionario.objects.get(id=cuestionario_id)
            if not cuestionario.esta_activo:
                raise serializers.ValidationError({
                    'cuestionario_id': 'El cuestionario no está disponible'
                })
        except Cuestionario.DoesNotExist:
            raise serializers.ValidationError({
                'cuestionario_id': 'El cuestionario no existe'
            })
        
        # Validar pregunta
        try:
            pregunta = Pregunta.objects.get(id=pregunta_id)
        except Pregunta.DoesNotExist:
            raise serializers.ValidationError({
                'pregunta_id': 'La pregunta no existe'
            })
        
        if not CuestionarioPregunta.objects.filter(
            cuestionario=cuestionario,
            pregunta=pregunta
        ).exists():
            raise serializers.ValidationError({
                'pregunta_id': 'Esta pregunta no pertenece al cuestionario'
            })
        
        # Validar según tipo de pregunta
        if pregunta.tipo == 'SELECCION_ALUMNO':
            if 'seleccionados' not in data or not data['seleccionados']:
                raise serializers.ValidationError({
                    'seleccionados': 'Debe seleccionar al menos un compañero'
                })
            
            if len(data['seleccionados']) > pregunta.max_elecciones:
                raise serializers.ValidationError({
                    'seleccionados': f'Máximo {pregunta.max_elecciones} compañeros permitidos'
                })
            
            # Validar que no se repitan
            alumnos_ids = [s['alumno_id'] for s in data['seleccionados']]
            if len(alumnos_ids) != len(set(alumnos_ids)):
                raise serializers.ValidationError({
                    'seleccionados': 'No puede seleccionar al mismo compañero más de una vez'
                })
        
        elif pregunta.tipo == 'OPCION':
            if 'opcion_id' not in data:
                raise serializers.ValidationError({
                    'opcion_id': 'Debe seleccionar una opción'
                })
        
        elif pregunta.tipo == 'TEXTO':
            if 'texto_respuesta' not in data or not data['texto_respuesta']:
                raise serializers.ValidationError({
                    'texto_respuesta': 'Debe proporcionar una respuesta'
                })
        
        data['cuestionario'] = cuestionario
        data['pregunta'] = pregunta
        
        return data


class ProgresoAlumnoSerializer(serializers.Serializer):
    """Serializer para progreso del alumno"""
    cuestionario_id = serializers.IntegerField()
    cuestionario_titulo = serializers.CharField()
    grupo_id = serializers.IntegerField()
    grupo_clave = serializers.CharField()
    total_preguntas = serializers.IntegerField()
    preguntas_respondidas = serializers.IntegerField()
    progreso = serializers.DecimalField(max_digits=5, decimal_places=2)
    estado = serializers.CharField()
    fecha_inicio = serializers.DateTimeField(allow_null=True)
    fecha_completado = serializers.DateTimeField(allow_null=True)