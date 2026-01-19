from rest_framework import serializers
from core.models import Alumno, AlumnoGrupo
from .auth import UserSerializer

class AlumnoSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    nombre_completo = serializers.CharField(source='user.get_full_name', read_only=True)
    plan_estudio_nombre = serializers.CharField(source='plan_estudio.nombre', read_only=True, allow_null=True)
    
    class Meta:
        model = Alumno
        fields = [
            'id', 'user', 'matricula', 'nss', 'nombre_completo',
            'plan_estudio', 'plan_estudio_nombre', 'semestre_actual',
            'promedio', 'fecha_ingreso', 'estatus'
        ]
        read_only_fields = ['id']


class AlumnoSimpleSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Alumno
        fields = ['id', 'matricula', 'nombre_completo']


class AlumnoGrupoSerializer(serializers.ModelSerializer):
    alumno_matricula = serializers.CharField(source='alumno.matricula', read_only=True)
    alumno_nombre = serializers.CharField(source='alumno.user.get_full_name', read_only=True)
    grupo_clave = serializers.CharField(source='grupo.clave', read_only=True)
    
    class Meta:
        model = AlumnoGrupo
        fields = [
            'id', 'alumno', 'alumno_matricula', 'alumno_nombre',
            'grupo', 'grupo_clave', 'fecha_inscripcion', 'activo',
            'fecha_baja', 'motivo_baja'
        ]
        read_only_fields = ['id', 'fecha_inscripcion']