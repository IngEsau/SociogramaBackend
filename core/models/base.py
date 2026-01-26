# core/models/base.py
"""
Modelo de Usuario Extendido
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Usuario extendido con campos personalizados
    Extiende el modelo User de Django para incluir campos adicionales en auth_user
    """
    ROL_CHOICES = [
        ('ALUMNO', 'Alumno'),
        ('DOCENTE', 'Docente'),
        ('ADMIN', 'Administrador'),
    ]
    
    GENERO_CHOICES = [
        ('Masculino', 'Masculino'),
        ('Femenino', 'Femenino'),
        ('Otro', 'Otro'),
    ]
    
    rol = models.CharField(
        max_length=10,
        choices=ROL_CHOICES,
        default='ALUMNO',
        verbose_name='Rol'
    )
    nombre_completo = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Nombre Completo'
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Teléfono'
    )
    fecha_nacimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name='Fecha de Nacimiento'
    )
    genero = models.CharField(
        max_length=10,
        choices=GENERO_CHOICES,
        blank=True,
        null=True,
        verbose_name='Género'
    )
    
    class Meta:
        db_table = 'auth_user'
        managed = False
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
    
    def __str__(self):
        return self.nombre_completo or self.get_full_name() or self.username
    
    def save(self, *args, **kwargs):
        # Auto-llenar nombre_completo si está vacío
        if not self.nombre_completo:
            self.nombre_completo = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)