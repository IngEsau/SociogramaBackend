# core/serializers/grupo.py
from rest_framework import serializers
from core.models import Grupo, AlumnoGrupo
from .alumno import AlumnoSimpleSerializer

class GrupoSerializer(serializers.ModelSerializer):
    programa_nombre = serializers.CharField(source='programa.nombre', read_only=True, allow_null=True)
    periodo_nombre = serializers.CharField(source='periodo.nombre', read_only=True, allow_null=True)
    tutor_nombre = serializers.CharField(source='tutor.user.get_full_name', read_only=True, allow_null=True)
    total_alumnos = serializers.SerializerMethodField()
    
    class Meta:
        model = Grupo
        fields = [
            'id', 'clave', 'grado', 'grupo', 'turno',
            'programa', 'programa_nombre', 'periodo', 'periodo_nombre',
            'tutor', 'tutor_nombre', 'activo', 'cupo_maximo',
            'total_alumnos', 'fecha_creacion'
        ]
        read_only_fields = ['id', 'fecha_creacion']
    
    def get_total_alumnos(self, obj):
        return obj.alumnos.filter(activo=True).count()


class AlumnoDetalleSerializer(serializers.ModelSerializer):
    """Serializer para mostrar información completa del alumno en un grupo"""
    matricula = serializers.CharField(source='alumno.matricula', read_only=True)
    nombre_completo = serializers.CharField(source='alumno.user.nombre_completo', read_only=True)
    email = serializers.CharField(source='alumno.user.email', read_only=True)
    semestre = serializers.IntegerField(source='alumno.semestre_actual', read_only=True)
    estatus = serializers.CharField(source='alumno.estatus', read_only=True)
    fecha_inscripcion = serializers.DateField(read_only=True)
    
    class Meta:
        model = AlumnoGrupo
        fields = [
            'id',
            'matricula',
            'nombre_completo',
            'email',
            'semestre',
            'estatus',
            'fecha_inscripcion',
            'activo'
        ]


class GrupoDetalleSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para grupos con lista completa de alumnos inscritos.
    Usado en el endpoint /academic/my-groups/
    """
    programa_nombre = serializers.CharField(source='programa.nombre', read_only=True, allow_null=True)
    programa_codigo = serializers.CharField(source='programa.codigo', read_only=True, allow_null=True)
    division_nombre = serializers.CharField(source='programa.division.nombre', read_only=True, allow_null=True)
    periodo_nombre = serializers.CharField(source='periodo.nombre', read_only=True, allow_null=True)
    periodo_codigo = serializers.CharField(source='periodo.codigo', read_only=True, allow_null=True)
    tutor_nombre = serializers.CharField(source='tutor.user.nombre_completo', read_only=True, allow_null=True)
    total_alumnos = serializers.SerializerMethodField()
    alumnos = serializers.SerializerMethodField()
    
    class Meta:
        model = Grupo
        fields = [
            'id',
            'clave',
            'grado',
            'grupo',
            'turno',
            'programa_codigo',
            'programa_nombre',
            'division_nombre',
            'periodo_codigo',
            'periodo_nombre',
            'tutor_nombre',
            'activo',
            'cupo_maximo',
            'total_alumnos',
            'alumnos',
            'fecha_creacion'
        ]
        read_only_fields = ['id', 'fecha_creacion']
    
    def get_total_alumnos(self, obj):
        """Cuenta alumnos activos en el grupo"""
        return obj.alumnos.filter(activo=True).count()
    
    def get_alumnos(self, obj):
        """Retorna lista completa de alumnos inscritos activos"""
        relaciones = AlumnoGrupo.objects.filter(
            grupo=obj,
            activo=True
        ).select_related(
            'alumno',
            'alumno__user'
        ).order_by('alumno__user__nombre_completo')
        
        return AlumnoDetalleSerializer(relaciones, many=True).data