from rest_framework import serializers
from core.models import Division, Programa, PlanEstudio, Periodo, Reporte

class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = ['id', 'codigo', 'nombre', 'descripcion', 'activa']
        read_only_fields = ['id']


class ProgramaSerializer(serializers.ModelSerializer):
    division_nombre = serializers.CharField(source='division.nombre', read_only=True)
    
    class Meta:
        model = Programa
        fields = ['id', 'codigo', 'nombre', 'division', 'division_nombre', 'duracion_semestres', 'activo']
        read_only_fields = ['id']


class PlanEstudioSerializer(serializers.ModelSerializer):
    programa_nombre = serializers.CharField(source='programa.nombre', read_only=True)
    
    class Meta:
        model = PlanEstudio
        fields = ['id', 'codigo', 'nombre', 'programa', 'programa_nombre', 'anio_inicio', 'activo']
        read_only_fields = ['id']


class PeriodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Periodo
        fields = ['id', 'codigo', 'nombre', 'fecha_inicio', 'fecha_fin', 'activo']
        read_only_fields = ['id']


class ReporteSerializer(serializers.ModelSerializer):
    grupo_clave = serializers.CharField(source='grupo.clave', read_only=True)
    generado_por_nombre = serializers.CharField(source='generado_por.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = Reporte
        fields = [
            'id', 'grupo', 'grupo_clave', 'generado_por', 'generado_por_nombre',
            'tipo', 'titulo', 'descripcion', 'data_json', 'archivo_path',
            'creado_en', 'actualizado_en'
        ]
        read_only_fields = ['id', 'creado_en', 'actualizado_en']