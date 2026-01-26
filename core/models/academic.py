# core/models/academic.py
"""
Modelos de Catálogos Académicos
División, Programa, Plan de Estudio, Periodo
"""
from django.db import models


class Division(models.Model):
    """División académica (TI, ADM, ING, SALUD)"""
    codigo = models.CharField(max_length=100, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(null=True, blank=True)
    activa = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'divisiones'
        managed = False
        verbose_name = 'División'
        verbose_name_plural = 'Divisiones'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Programa(models.Model):
    """Programa académico (Carrera)"""
    codigo = models.CharField(max_length=1000, unique=True)
    nombre = models.CharField(max_length=150)
    division = models.ForeignKey(
        Division, 
        on_delete=models.CASCADE,
        related_name='programas',
        db_column='division_id'
    )
    duracion_semestres = models.IntegerField(default=9)
    activo = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'programas'
        managed = False
        verbose_name = 'Programa'
        verbose_name_plural = 'Programas'
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class PlanEstudio(models.Model):
    """Plan de estudios por programa"""
    codigo = models.CharField(max_length=100)
    nombre = models.CharField(max_length=100)
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        related_name='planes',
        db_column='programa_id'
    )
    anio_inicio = models.IntegerField()
    activo = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'planes_estudio'
        managed = False
        unique_together = ['codigo', 'programa']
        verbose_name = 'Plan de Estudio'
        verbose_name_plural = 'Planes de Estudio'
        ordering = ['-anio_inicio']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Periodo(models.Model):
    """Periodo académico (cuatrimestre)"""
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=50)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'periodos'
        managed = False
        verbose_name = 'Periodo'
        verbose_name_plural = 'Periodos'
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return self.nombre
    
    @property
    def esta_activo(self):
        """Verificar si el periodo está dentro de las fechas"""
        from datetime import date
        today = date.today()
        if self.fecha_inicio and self.fecha_fin:
            return self.fecha_inicio <= today <= self.fecha_fin
        return self.activo