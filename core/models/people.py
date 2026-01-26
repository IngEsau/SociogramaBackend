# core/models/people.py
"""
Modelos de Personas del Sistema
Alumno, Docente
"""
from django.db import models
from .base import User
from .academic import Division, PlanEstudio


class Docente(models.Model):
    """Docentes del sistema"""
    ESTATUS_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
        ('JUBILADO', 'Jubilado'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='docente',
        db_column='user_id'
    )
    profesor_id = models.CharField(max_length=20, unique=True)
    division = models.ForeignKey(
        Division,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='docentes',
        db_column='division_id'
    )
    es_tutor = models.BooleanField(default=False)
    especialidad = models.CharField(max_length=100, null=True, blank=True)
    grado_academico = models.CharField(max_length=50, null=True, blank=True)
    fecha_ingreso = models.DateField(null=True, blank=True)
    estatus = models.CharField(max_length=10, choices=ESTATUS_CHOICES, default='ACTIVO')
    
    class Meta:
        db_table = 'docentes'
        managed = False
        verbose_name = 'Docente'
        verbose_name_plural = 'Docentes'
        ordering = ['profesor_id']
    
    def __str__(self):
        return f"{self.profesor_id} - {self.user.get_full_name()}"
    
    @property
    def grupos_activos(self):
        """Obtener grupos activos donde es tutor"""
        return self.grupos_tutor.filter(activo=True)


class Alumno(models.Model):
    """Alumnos del sistema"""
    ESTATUS_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
        ('EGRESADO', 'Egresado'),
        ('BAJA', 'Baja'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='alumno',
        db_column='user_id'
    )
    matricula = models.CharField(max_length=20, unique=True)
    nss = models.CharField(max_length=20, null=True, blank=True)
    plan_estudio = models.ForeignKey(
        PlanEstudio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alumnos',
        db_column='plan_estudio_id'
    )
    semestre_actual = models.IntegerField(default=1)
    promedio = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    fecha_ingreso = models.DateField(null=True, blank=True)
    estatus = models.CharField(max_length=10, choices=ESTATUS_CHOICES, default='ACTIVO')
    
    class Meta:
        db_table = 'alumnos'
        managed = False
        verbose_name = 'Alumno'
        verbose_name_plural = 'Alumnos'
        ordering = ['matricula']
    
    def __str__(self):
        return f"{self.matricula} - {self.user.get_full_name()}"
    
    @property
    def nombre_completo(self):
        """Obtener nombre completo del alumno"""
        return self.user.get_full_name()
    
    @property
    def grupos_activos(self):
        """Obtener grupos activos del alumno"""
        return self.grupos.filter(activo=True).select_related('grupo')
    
    @property
    def programa(self):
        """Obtener programa del alumno via plan de estudio"""
        return self.plan_estudio.programa if self.plan_estudio else None