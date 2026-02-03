# core/serializers/importacion.py
"""
Serializers para importación de datos
"""
from rest_framework import serializers


class AnalisisImportacionSerializer(serializers.Serializer):
    """Serializer para análisis inicial del archivo"""
    archivo = serializers.FileField()


class EjecucionImportacionSerializer(serializers.Serializer):
    """Serializer para ejecutar la importación"""
    archivo_id = serializers.CharField(max_length=100)
    periodo_id = serializers.IntegerField(required=False, allow_null=True)
    crear_periodo = serializers.BooleanField(default=False)
    nuevo_periodo_anio = serializers.IntegerField(required=False, allow_null=True)
    nuevo_periodo_numero = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=3)
    desactivar_anteriores = serializers.BooleanField(default=True)
    
    def validate(self, data):
        """Validar que se proporcione periodo_id O crear_periodo"""
        if not data.get('periodo_id') and not data.get('crear_periodo'):
            raise serializers.ValidationError(
                "Debe proporcionar 'periodo_id' o marcar 'crear_periodo' como true"
            )
        
        if data.get('crear_periodo'):
            if not data.get('nuevo_periodo_anio') or not data.get('nuevo_periodo_numero'):
                raise serializers.ValidationError(
                    "Para crear periodo nuevo debe proporcionar 'nuevo_periodo_anio' y 'nuevo_periodo_numero'"
                )
        
        return data