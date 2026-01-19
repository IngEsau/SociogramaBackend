"""
Modelos Django para el Sistema de Sociograma UTP
VERSIÓN CORREGIDA - Con User extendido
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator


# ==================== USER EXTENDIDO ====================

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


# ==================== DIVISIÓN ====================

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


# ==================== PROGRAMA ====================

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


# ==================== PLAN DE ESTUDIO ====================

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


# ==================== PERIODO ====================

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


# ==================== DOCENTE ====================

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


# ==================== ALUMNO ====================

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


# ==================== GRUPO ====================

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


# ==================== ALUMNO-GRUPO ====================

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


# ==================== PREGUNTA ====================

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


# ==================== OPCION ====================

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


# ==================== RESPUESTA ====================

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


# ==================== REPORTE ====================

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