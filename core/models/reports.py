# core/models/reports.py
"""
Modelos de Reportes y Sociogramas
Reporte
"""
from django.db import models
from .base import User
from .groups import Grupo


class Reporte(models.Model):
    """Reportes y sociogramas generados"""
    TIPO_CHOICES = [
        ('REPORTE', 'Reporte General'),
        ('SOCIOGRAMA', 'Sociograma'),
        ('MATRIZ', 'Matriz Sociométrica'),
        ('ESTADISTICO', 'Estadístico'),
    ]
    
    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.CASCADE,
        related_name='reportes',
        db_column='grupo_id'
    )
    generado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='generado_por'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200, null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    data_json = models.JSONField(null=True, blank=True)
    archivo_path = models.CharField(max_length=500, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reportes'
        managed = False
        verbose_name = 'Reporte'
        verbose_name_plural = 'Reportes'
        ordering = ['-creado_en']
    
    def __str__(self):
        return f"{self.tipo} - {self.grupo.clave} ({self.creado_en.strftime('%Y-%m-%d')})"
    
    @property
    def generador_nombre(self):
        """Nombre de quien generó el reporte"""
        return self.generado_por.get_full_name() if self.generado_por else "Sistema"