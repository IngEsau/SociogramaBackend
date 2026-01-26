# core/models/groups.py
"""
Modelos de Grupos y Relaciones
Grupo, AlumnoGrupo
"""
from django.db import models
from .academic import Programa, Periodo
from .people import Docente, Alumno


class Grupo(models.Model):
    """Grupos académicos"""
    TURNO_CHOICES = [
        ('Matutino', 'Matutino'),
        ('Vespertino', 'Vespertino'),
        ('Nocturno', 'Nocturno'),
    ]
    
    clave = models.CharField(max_length=50)
    grado = models.CharField(max_length=100, null=True, blank=True)
    grupo = models.CharField(max_length=100, null=True, blank=True)
    turno = models.CharField(max_length=20, choices=TURNO_CHOICES, default='Matutino')
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        related_name='grupos',
        db_column='programa_id'
    )
    periodo = models.ForeignKey(
        Periodo,
        on_delete=models.CASCADE,
        related_name='grupos',
        db_column='periodo_id'
    )
    tutor = models.ForeignKey(
        Docente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grupos_tutor',
        db_column='tutor_id'
    )
    activo = models.BooleanField(default=True)
    cupo_maximo = models.IntegerField(default=40)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'grupos'
        managed = False
        unique_together = ['clave', 'periodo']
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
        ordering = ['clave']
    
    def __str__(self):
        return f"{self.clave} ({self.periodo.codigo})"
    
    @property
    def total_alumnos(self):
        """Contar alumnos activos en el grupo"""
        return self.alumnos.filter(activo=True).count()
    
    @property
    def tiene_cupo(self):
        """Verificar si tiene cupo disponible"""
        return self.total_alumnos < self.cupo_maximo


class AlumnoGrupo(models.Model):
    """Relación muchos a muchos entre Alumnos y Grupos"""
    alumno = models.ForeignKey(
        Alumno,
        on_delete=models.CASCADE,
        related_name='grupos',
        db_column='alumno_id'
    )
    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.CASCADE,
        related_name='alumnos',
        db_column='grupo_id'
    )
    fecha_inscripcion = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    fecha_baja = models.DateField(null=True, blank=True)
    motivo_baja = models.CharField(max_length=200, null=True, blank=True)
    
    class Meta:
        db_table = 'alumno_grupo'
        managed = False
        unique_together = ['alumno', 'grupo']
        verbose_name = 'Alumno-Grupo'
        verbose_name_plural = 'Alumnos-Grupos'
    
    def __str__(self):
        return f"{self.alumno.matricula} → {self.grupo.clave}"
    
    def dar_de_baja(self, motivo=""):
        """Dar de baja al alumno del grupo"""
        from datetime import date
        self.activo = False
        self.fecha_baja = date.today()
        self.motivo_baja = motivo
        self.save()