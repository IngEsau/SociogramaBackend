# core/models/surveys.py
"""
Modelos de Cuestionarios Sociométricos
Pregunta, Opcion, Respuesta, Cuestionario, CuestionarioPregunta, CuestionarioEstado
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
    
    POLARIDAD_CHOICES = [
        ('POSITIVA', 'Positiva'),
        ('NEGATIVA', 'Negativa'),
    ]
    
    texto = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    polaridad = models.CharField(
        max_length=20, 
        choices=POLARIDAD_CHOICES, 
        default='POSITIVA',
        help_text='Indica si la pregunta es positiva (¿Con quién harías equipo?) o negativa (¿Con quién NO trabajarías?)'
    )
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


class Cuestionario(models.Model):
    """Cuestionarios sociométricos por periodo"""
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    periodo = models.ForeignKey(
        'Periodo',
        on_delete=models.CASCADE,
        related_name='cuestionarios',
        db_column='periodo_id'
    )
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'cuestionarios'
        managed = True
        verbose_name = 'Cuestionario'
        verbose_name_plural = 'Cuestionarios'
        ordering = ['-creado_en']
    
    def __str__(self):
        return f"{self.titulo} - {self.periodo.nombre}"
    
    @property
    def esta_activo(self):
        """Verificar si está en periodo de aplicación"""
        from django.utils import timezone
        now = timezone.now()
        return self.activo and self.fecha_inicio <= now <= self.fecha_fin
    
    @property
    def total_respuestas(self):
        """Contar respuestas del cuestionario"""
        return self.respuestas.count()
    
    @property
    def total_preguntas(self):
        """Contar preguntas del cuestionario"""
        return self.preguntas.count()
    
    @property
    def total_grupos(self):
        """Contar grupos que tienen estados en este cuestionario"""
        return self.estados.values('grupo').distinct().count()


class CuestionarioPregunta(models.Model):
    """Relación entre cuestionarios y preguntas"""
    cuestionario = models.ForeignKey(
        Cuestionario,
        on_delete=models.CASCADE,
        related_name='preguntas',
        db_column='cuestionario_id'
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name='cuestionarios',
        db_column='pregunta_id'
    )
    orden = models.IntegerField(default=1)
    
    class Meta:
        db_table = 'cuestionario_preguntas'
        managed = True
        unique_together = [['cuestionario', 'pregunta']]
        ordering = ['orden']
        verbose_name = 'Pregunta de Cuestionario'
        verbose_name_plural = 'Preguntas de Cuestionario'
    
    def __str__(self):
        return f"{self.cuestionario.titulo} - Pregunta {self.orden}"


class CuestionarioEstado(models.Model):
    """Estado de completitud del cuestionario por alumno y grupo"""
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROGRESO', 'En Progreso'),
        ('COMPLETADO', 'Completado'),
    ]
    
    cuestionario = models.ForeignKey(
        Cuestionario,
        on_delete=models.CASCADE,
        related_name='estados',
        db_column='cuestionario_id'
    )
    alumno = models.ForeignKey(
        Alumno,
        on_delete=models.CASCADE,
        related_name='cuestionarios_estado',
        db_column='alumno_id'
    )
    grupo = models.ForeignKey(
        'Grupo',
        on_delete=models.CASCADE,
        related_name='cuestionarios_estado',
        db_column='grupo_id'
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_completado = models.DateTimeField(null=True, blank=True)
    progreso = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    class Meta:
        db_table = 'cuestionario_estado'
        managed = True
        unique_together = [['cuestionario', 'alumno', 'grupo']]
        verbose_name = 'Estado de Cuestionario'
        verbose_name_plural = 'Estados de Cuestionario'
    
    def __str__(self):
        return f"{self.alumno.matricula} - {self.grupo.clave} - {self.cuestionario.titulo} ({self.estado})"
    
    def actualizar_progreso(self):
        """Calcular progreso basado en preguntas respondidas"""
        total_preguntas = self.cuestionario.preguntas.count()
        if total_preguntas == 0:
            return 0
        
        respuestas_count = self.cuestionario.respuestas.filter(
            alumno=self.alumno
        ).values('pregunta').distinct().count()
        
        self.progreso = (respuestas_count / total_preguntas) * 100
        
        # Actualizar estado según progreso
        if self.progreso == 0:
            self.estado = 'PENDIENTE'
        elif self.progreso == 100:
            self.estado = 'COMPLETADO'
            if not self.fecha_completado:
                from django.utils import timezone
                self.fecha_completado = timezone.now()
        else:
            self.estado = 'EN_PROGRESO'
            if not self.fecha_inicio:
                from django.utils import timezone
                self.fecha_inicio = timezone.now()
        
        self.save()
        return self.progreso


class Respuesta(models.Model):
    """Respuestas de alumnos a preguntas"""
    alumno = models.ForeignKey(
        Alumno,
        on_delete=models.CASCADE,
        related_name='respuestas',
        db_column='alumno_id'
    )
    cuestionario = models.ForeignKey(
        Cuestionario,
        on_delete=models.CASCADE,
        related_name='respuestas',
        null=True,
        blank=True,
        db_column='cuestionario_id'
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
        unique_together = [['alumno', 'pregunta', 'seleccionado_alumno']]
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