# core/models/surveys.py
"""
Modelos de Cuestionarios Sociométricos
Pregunta, Opcion, Respuesta
"""
from django.db import models
from .people import Alumno


class Pregunta(models.Model):
    """Preguntas del cuestionario sociométrico"""
    TIPO_CHOICES = [
        ('SELECCION_ALUMNO', 'Selección de Alumno'),
        ('OPCION', 'Opción Múltiple'),
        ('TEXTO', 'Texto Libre'),
    ]
    
    texto = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    max_elecciones = models.IntegerField(default=3)
    orden = models.IntegerField()
    activa = models.BooleanField(default=True)
    descripcion = models.TextField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'preguntas'
        managed = False
        verbose_name = 'Pregunta'
        verbose_name_plural = 'Preguntas'
        ordering = ['orden']
    
    def __str__(self):
        return f"P{self.orden}: {self.texto[:50]}..."
    
    @property
    def es_sociometrica(self):
        """Verificar si es pregunta sociométrica"""
        return self.tipo == 'SELECCION_ALUMNO'


class Opcion(models.Model):
    """Opciones de respuesta para preguntas tipo OPCION"""
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name='opciones',
        db_column='pregunta_id'
    )
    texto = models.CharField(max_length=150)
    valor = models.IntegerField(default=1)
    orden = models.IntegerField(default=1)
    
    class Meta:
        db_table = 'opciones'
        managed = False
        verbose_name = 'Opción'
        verbose_name_plural = 'Opciones'
        ordering = ['pregunta', 'orden']
    
    def __str__(self):
        return f"{self.pregunta.orden}.{self.orden}: {self.texto}"


class Respuesta(models.Model):
    """Respuestas de alumnos a preguntas"""
    alumno = models.ForeignKey(
        Alumno,
        on_delete=models.CASCADE,
        related_name='respuestas',
        db_column='alumno_id'
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name='respuestas',
        db_column='pregunta_id'
    )
    opcion = models.ForeignKey(
        Opcion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='opcion_id'
    )
    texto_respuesta = models.CharField(max_length=500, null=True, blank=True)
    seleccionado_alumno = models.ForeignKey(
        Alumno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='elecciones_recibidas',
        db_column='seleccionado_alumno_id'
    )
    orden_eleccion = models.SmallIntegerField(null=True, blank=True)
    puntaje = models.SmallIntegerField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'respuestas'
        managed = False
        unique_together = ['alumno', 'pregunta', 'seleccionado_alumno']
        verbose_name = 'Respuesta'
        verbose_name_plural = 'Respuestas'
    
    def __str__(self):
        return f"{self.alumno.matricula} - Pregunta {self.pregunta.orden}"
    
    def calcular_puntaje(self):
        """
        Calcular puntaje basado en orden de elección
        1ra elección = 3 puntos
        2da elección = 2 puntos  
        3ra elección = 1 punto
        """
        if self.orden_eleccion:
            max_elecciones = self.pregunta.max_elecciones
            self.puntaje = max(1, max_elecciones - self.orden_eleccion + 1)
            return self.puntaje
        return 0