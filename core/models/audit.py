# core/models/audit.py
"""
Modelo de Auditoría
Registra acciones relevantes realizadas por usuarios en el sistema
"""
from django.db import models
from .base import User


class Auditoria(models.Model):
    """Registro de auditoría de acciones administrativas"""

    ACCION_CHOICES = [
        ('IMPORTACION', 'Importación masiva Excel'),
        ('CREAR_GRUPO', 'Crear grupo'),
        ('EDITAR_GRUPO', 'Editar grupo'),
        ('CREAR_DIVISION', 'Crear división'),
        ('EDITAR_DIVISION', 'Editar división'),
        ('CREAR_PROGRAMA', 'Crear programa'),
        ('EDITAR_PROGRAMA', 'Editar programa'),
        ('EDITAR_PERIODO', 'Editar periodo'),
        ('CREAR_USUARIO', 'Crear usuario'),
        ('EDITAR_USUARIO', 'Editar usuario'),
        ('ACTIVAR_USUARIO', 'Activar usuario'),
        ('DESACTIVAR_USUARIO', 'Desactivar usuario'),
        ('ASIGNAR_TUTOR', 'Asignar tutor a grupo'),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias',
        db_column='usuario_id',
    )
    accion = models.CharField(max_length=30, choices=ACCION_CHOICES)
    entidad = models.CharField(max_length=50)
    entidad_id = models.IntegerField(null=True, blank=True)
    detalle = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auditorias'
        managed = True
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Auditorías'
        ordering = ['-timestamp']

    def __str__(self):
        usuario_str = self.usuario.username if self.usuario else 'Sistema'
        return f"{self.accion} por {usuario_str} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"
