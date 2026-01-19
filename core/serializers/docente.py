from rest_framework import serializers
from core.models import Docente
from .auth import UserSerializer

class DocenteSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    nombre_completo = serializers.CharField(source='user.get_full_name', read_only=True)
    division_nombre = serializers.CharField(source='division.nombre', read_only=True, allow_null=True)
    
    class Meta:
        model = Docente
        fields = [
            'id', 'user', 'profesor_id', 'nombre_completo',
            'division', 'division_nombre', 'es_tutor',
            'especialidad', 'grado_academico', 'fecha_ingreso', 'estatus'
        ]
        read_only_fields = ['id']


class DocenteSimpleSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Docente
        fields = ['id', 'profesor_id', 'nombre_completo', 'es_tutor']