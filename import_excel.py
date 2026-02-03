"""
Script de importación de datos desde Excel (4 hojas) - VERSIÓN MEJORADA CON GESTIÓN DE PERIODOS
Sistema de Sociograma UTP

MEJORAS:
- Selección inteligente de periodos (usar existente o crear nuevo)
- Desactivación automática de periodos anteriores
- Gestión de bajas automáticas (alumnos que ya no aparecen)
- Reporte detallado de cambios
"""
import os
import sys
import django
from datetime import date, datetime
from collections import defaultdict
import re

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociograma_project.settings')
django.setup()

from core.models import (
    User, Division, Programa, PlanEstudio, Periodo, Docente, Grupo, Alumno, AlumnoGrupo
)
from django.db import transaction
import pandas as pd


# =============================================================================
# SISTEMA DE LOGGING MEJORADO
# =============================================================================

class Logger:
    """Clase para manejar logging dual (consola + archivo) con seguimiento de errores"""
    
    def __init__(self, log_file='importacion.log'):
        self.log_file = log_file
        self.terminal = sys.stdout
        self.errores_por_seccion = defaultdict(list)  # Almacenar errores por sección
        
        with open(self.log_file, 'w', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{'='*70}\n")
            f.write(f"LOG DE IMPORTACIÓN - {timestamp}\n")
            f.write(f"{'='*70}\n\n")
    
    def log(self, message):
        print(message)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            clean_message = re.sub(r'\x1b\[[0-9;]*m', '', str(message))
            f.write(clean_message + '\n')
    
    def log_error(self, message, seccion=None):
        error_msg = f"❌ ERROR: {message}"
        self.log(error_msg)
        if seccion:
            self.errores_por_seccion[seccion].append(message)
    
    def log_success(self, message):
        self.log(f"✅ {message}")
    
    def log_warning(self, message):
        self.log(f"⚠️  {message}")
    
    def log_info(self, message):
        self.log(f"ℹ️  {message}")
    
    def log_progress(self, actual, total, mensaje="Procesando"):
        """Mostrar progreso en tiempo real"""
        porcentaje = (actual / total * 100) if total > 0 else 0
        self.log(f"  📊 {mensaje}: {actual}/{total} ({porcentaje:.1f}%)")
    
    def mostrar_resumen_errores(self):
        """Mostrar resumen consolidado de errores por sección"""
        if not self.errores_por_seccion:
            return
        
        self.log("\n" + "="*70)
        self.log("📋 RESUMEN DETALLADO DE ERRORES")
        self.log("="*70)
        
        for seccion, errores in self.errores_por_seccion.items():
            self.log(f"\n🔴 {seccion.upper()}: {len(errores)} errores")
            self.log("-" * 70)
            
            # Agrupar errores similares
            errores_unicos = {}
            for error in errores:
                if error in errores_unicos:
                    errores_unicos[error] += 1
                else:
                    errores_unicos[error] = 1
            
            # Mostrar primeros 10 errores únicos
            for i, (error, count) in enumerate(list(errores_unicos.items())[:10], 1):
                if count > 1:
                    self.log(f"  {i}. {error} (×{count})")
                else:
                    self.log(f"  {i}. {error}")
            
            if len(errores_unicos) > 10:
                self.log(f"  ... y {len(errores_unicos) - 10} errores más")

logger = Logger()


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def limpiar_texto(texto):
    if pd.isna(texto) or texto == '':
        return None
    return str(texto).strip()


def generar_username(matricula_o_empleado):
    return str(matricula_o_empleado).strip().lower().replace(' ', '')


# =============================================================================
# GESTIÓN DE PERIODOS
# =============================================================================

def seleccionar_periodo():
    """
    Muestra periodos existentes y permite seleccionar uno o crear nuevo
    Retorna: objeto Periodo
    """
    logger.log("\n" + "="*70)
    logger.log("📅 GESTIÓN DE PERIODOS")
    logger.log("="*70)
    
    # Configuración de periodos UTP (3 por año)
    PERIODOS_CONFIG = {
        '1': {
            'nombre': 'Enero - Abril',
            'fecha_inicio_base': (1, 15),  # mes, día
            'fecha_fin_base': (4, 30)
        },
        '2': {
            'nombre': 'Mayo - Agosto',
            'fecha_inicio_base': (5, 1),
            'fecha_fin_base': (8, 31)
        },
        '3': {
            'nombre': 'Septiembre - Diciembre',
            'fecha_inicio_base': (9, 1),
            'fecha_fin_base': (12, 15)
        }
    }
    
    # Mostrar periodos existentes
    periodos_existentes = Periodo.objects.all().order_by('-codigo')
    
    if periodos_existentes.exists():
        logger.log("\nPERIODOS EN LA BASE DE DATOS:")
        for idx, p in enumerate(periodos_existentes, 1):
            estado = "🟢 ACTIVO" if p.activo == 1 else "⚪ INACTIVO"
            logger.log(f"{idx}. {p.codigo} - {p.nombre} {estado}")
        
        usar_existente = input("\n¿Usar un periodo existente? (número) o 'n' para crear nuevo: ").strip()
        
        if usar_existente.isdigit() and 1 <= int(usar_existente) <= len(periodos_existentes):
            periodo = list(periodos_existentes)[int(usar_existente) - 1]
            logger.log_success(f"Usando periodo: {periodo.codigo} - {periodo.nombre}")
            return periodo
    else:
        logger.log_info("No hay periodos en la base de datos")
    
    # Crear nuevo periodo
    logger.log("\n➕ CREAR NUEVO PERIODO")
    año_actual = datetime.now().year
    año_input = input(f"¿Año? [{año_actual}]: ").strip()
    año = int(año_input) if año_input else año_actual
    
    logger.log(f"\nPERIODOS DISPONIBLES PARA {año}:")
    logger.log(f"1. Enero - Abril {año}")
    logger.log(f"2. Mayo - Agosto {año}")
    logger.log(f"3. Septiembre - Diciembre {año}")
    
    periodo_num = input("\nSelecciona periodo (1/2/3): ").strip()
    
    if periodo_num not in ['1', '2', '3']:
        logger.log_error("Periodo inválido. Usando periodo 2 por defecto.")
        periodo_num = '2'
    
    # Generar datos del periodo
    config = PERIODOS_CONFIG[periodo_num]
    codigo = f"{año}-{periodo_num}"
    nombre = f"{config['nombre']} {año}"
    
    fecha_inicio = date(año, config['fecha_inicio_base'][0], config['fecha_inicio_base'][1])
    fecha_fin = date(año, config['fecha_fin_base'][0], config['fecha_fin_base'][1])
    
    # Crear periodo
    with transaction.atomic():
        periodo, created = Periodo.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': nombre,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'activo': 1
            }
        )
        
        if created:
            logger.log_success(f"Creado: {periodo.codigo} - {periodo.nombre}")
        else:
            logger.log_info(f"Ya existía: {periodo.codigo} - {periodo.nombre}")
    
    return periodo


def desactivar_periodo_anterior(periodo_actual):
    """
    Desactiva todos los periodos anteriores y sus grupos/relaciones
    """
    logger.log("\n⚠️  Desactivando periodos anteriores...")
    
    with transaction.atomic():
        # 1. Desactivar periodos anteriores
        periodos_desactivados = Periodo.objects.exclude(id=periodo_actual.id).filter(activo=1).update(activo=0)
        
        # 2. Desactivar grupos de periodos inactivos
        grupos_desactivados = Grupo.objects.filter(periodo__activo=0, activo=1).update(activo=0)
        
        # 3. Desactivar relaciones alumno-grupo de periodos inactivos
        relaciones_desactivadas = AlumnoGrupo.objects.filter(
            grupo__periodo__activo=0,
            activo=1
        ).update(activo=0)
        
        logger.log(f"   Periodos desactivados: {periodos_desactivados}")
        logger.log(f"   Grupos desactivados: {grupos_desactivados}")
        logger.log(f"   Inscripciones desactivadas: {relaciones_desactivadas}")
        
        # Activar el periodo actual por si acaso
        Periodo.objects.filter(id=periodo_actual.id).update(activo=1)
        logger.log_success(f"Periodo activo: {periodo_actual.codigo}")


# =============================================================================
# IMPORTACIÓN DE DATOS
# =============================================================================

def importar_divisiones_programas(df_alumnos, df_grupos):
    """Extrae y crea Divisiones y Programas"""
    logger.log("\n🏢 Creando Divisiones y Programas...")
    
    divisiones_cache = {}
    programas_cache = {}
    
    # Obtener divisiones únicas
    divisiones_unicas = set()
    if 'División' in df_alumnos.columns:
        divisiones_unicas.update(df_alumnos['División'].dropna().unique())
    if 'División' in df_grupos.columns:
        divisiones_unicas.update(df_grupos['División'].dropna().unique())
    
    # Crear divisiones
    for div_nombre in divisiones_unicas:
        div_nombre = limpiar_texto(div_nombre)
        if not div_nombre:
            continue
            
        codigo = re.sub(r'[^A-Z]', '', div_nombre.upper())[:10]
        if not codigo:
            codigo = div_nombre[:10].upper()
        
        division, created = Division.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': div_nombre,
                'activa': 1
            }
        )
        
        divisiones_cache[div_nombre] = division
        status = "✅" if created else "ℹ️"
        logger.log(f"  {status} División: {div_nombre}")
    
    # Obtener programas únicos
    programas_unicos = set()
    if 'Programa' in df_alumnos.columns:
        programas_unicos.update(df_alumnos['Programa'].dropna().unique())
    if 'Programa' in df_grupos.columns:
        programas_unicos.update(df_grupos['Programa'].dropna().unique())
    
    # Crear programas
    for prog_nombre in programas_unicos:
        prog_nombre = limpiar_texto(prog_nombre)
        if not prog_nombre:
            continue
        
        # Buscar división correspondiente
        division = None
        for div_nombre, div_obj in divisiones_cache.items():
            mask_alumnos = (df_alumnos['Programa'] == prog_nombre) if 'Programa' in df_alumnos.columns else pd.Series([False] * len(df_alumnos))
            if mask_alumnos.any():
                div_alumno = df_alumnos.loc[mask_alumnos, 'División'].iloc[0]
                if limpiar_texto(div_alumno) == div_nombre:
                    division = div_obj
                    break
        
        if not division and divisiones_cache:
            division = list(divisiones_cache.values())[0]
        
        # Generar código corto
        nombre_limpio = re.sub(r'\s*-\s*\d{4}', '', prog_nombre)
        palabras = nombre_limpio.split()
        
        if len(palabras) >= 3:
            codigo = ''.join([p[0].upper() for p in palabras if len(p) > 2])[:8]
        elif len(palabras) == 2:
            codigo = ''.join([p[:4].upper() for p in palabras])[:8]
        else:
            codigo = ''.join([c.upper() for c in nombre_limpio if c.isalnum()])[:8]
        
        if not codigo or len(codigo) < 2:
            codigo = nombre_limpio.replace(' ', '')[:20].upper()
        
        programa, created = Programa.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': prog_nombre,
                'division': division,
                'duracion_semestres': 9,
                'activo': 1
            }
        )
        
        programas_cache[prog_nombre] = programa
        status = "✅" if created else "ℹ️"
        logger.log(f"  {status} Programa: {prog_nombre} (Código: {codigo})")
    
    return divisiones_cache, programas_cache


def importar_tutores(df_tutores, divisiones_cache):
    """Importa tutores desde 'Datos Tutores.csv'"""
    SECCION = "tutores"
    logger.log("\n👨‍🏫 Importando Tutores...")
    logger.log(f"   📊 Total de filas en Excel: {len(df_tutores)}")
    
    tutores_cache = {}
    total_creados = 0
    total_omitidos = 0
    errores = 0
    
    with transaction.atomic():
        for idx, row in df_tutores.iterrows():
            try:
                empleado_id = limpiar_texto(row.get('No. de empleado'))
                nombres = limpiar_texto(row.get('Nombres', ''))
                a_paterno = limpiar_texto(row.get('A. Paterno', ''))
                a_materno = limpiar_texto(row.get('A. Materno', ''))
                sexo = limpiar_texto(row.get('Sexo', ''))
                division_nombre = limpiar_texto(row.get('División', ''))
                puesto = limpiar_texto(row.get('Puesto', ''))
                email = limpiar_texto(row.get('Email', ''))
                
                # Validación básica
                if not empleado_id or not nombres:
                    total_omitidos += 1
                    continue
                
                # Construir nombre completo
                apellidos = f"{a_paterno or ''} {a_materno or ''}".strip()
                nombre_completo = f"{nombres} {apellidos}".strip()
                
                # Normalizar género
                genero = None
                if sexo:
                    sexo_lower = sexo.lower()
                    if 'h' in sexo_lower or 'm' == sexo_lower:
                        genero = 'Masculino'
                    elif 'f' in sexo_lower or 'mujer' in sexo_lower:
                        genero = 'Femenino'
                
                username = generar_username(empleado_id)
                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': nombres,
                        'last_name': apellidos,
                        'email': email or f"{username}@utpuebla.edu.mx",
                        'is_staff': True,
                        'is_active': True,
                        'rol': 'DOCENTE',
                        'nombre_completo': nombre_completo,
                        'genero': genero,
                    }
                )
                
                if user_created:
                    user.set_password(empleado_id)
                    user.save()
                
                # Obtener división
                division = divisiones_cache.get(division_nombre)
                
                # Crear docente
                docente, created = Docente.objects.get_or_create(
                    profesor_id=empleado_id,
                    defaults={
                        'user': user,
                        'division': division,
                        'es_tutor': True,
                        'especialidad': puesto,
                        'estatus': 'ACTIVO'
                    }
                )
                
                tutores_cache[empleado_id] = docente
                
                if created:
                    total_creados += 1
                    # Mostrar progreso cada 10
                    if total_creados % 10 == 0:
                        logger.log_progress(total_creados, len(df_tutores), "Tutores creados")
                
            except Exception as e:
                errores += 1
                error_msg = f"Fila {idx+2} (ID: {empleado_id if 'empleado_id' in locals() else 'N/A'}): {str(e)}"
                logger.log_error(error_msg, SECCION)
    
    # Resumen final
    logger.log("\n   " + "-"*60)
    logger.log_success(f"Tutores creados: {total_creados}/{len(df_tutores)}")
    if total_omitidos > 0:
        logger.log_warning(f"Filas omitidas (sin datos): {total_omitidos}")
    if errores > 0:
        logger.log_error(f"Errores encontrados: {errores}", SECCION)
    
    return tutores_cache


def importar_grupos(df_grupos, programas_cache, tutores_cache, periodo):
    """Importa grupos desde 'Datos Grupos.csv'"""
    SECCION = "grupos"
    logger.log("\n🏫 Importando Grupos...")
    logger.log(f"   📊 Total de filas en Excel: {len(df_grupos)}")
    
    grupos_cache = {}
    total_creados = 0
    total_omitidos = 0
    errores = 0
    
    with transaction.atomic():
        for idx, row in df_grupos.iterrows():
            try:
                cuatrimestre_str = limpiar_texto(row.get('Cuatrimestre'))
                grupo_clave = limpiar_texto(row.get('Grupo'))
                division_nombre = limpiar_texto(row.get('División'))
                programa_nombre = limpiar_texto(row.get('Programa'))
                tutor_nombre = limpiar_texto(row.get('Tutor Asignado', ''))
                turno = limpiar_texto(row.get('Turno', 'Matutino'))
                
                if not grupo_clave or not programa_nombre:
                    total_omitidos += 1
                    continue
                
                # Normalizar turno
                if turno and turno.lower() not in ['matutino', 'vespertino', 'nocturno']:
                    turno = 'Matutino'
                elif turno:
                    turno = turno.capitalize()
                
                # Obtener programa
                programa = programas_cache.get(programa_nombre)
                if not programa:
                    error_msg = f"Fila {idx+2}: Programa no encontrado '{programa_nombre}'"
                    logger.log_error(error_msg, SECCION)
                    errores += 1
                    continue
                
                # Buscar tutor
                tutor = None
                if tutor_nombre:
                    for empleado_id, doc in tutores_cache.items():
                        nombre_completo = doc.user.nombre_completo or doc.user.get_full_name()
                        if tutor_nombre.lower() in nombre_completo.lower():
                            tutor = doc
                            break
                
                # Extraer grado
                grado_match = re.match(r'^\d+', str(cuatrimestre_str)) 
                grado_final = grado_match.group(0) if grado_match else 'SG'
                
                # Generar clave única
                clave_unica_bd = f"{programa.codigo}-{grado_final}-{grupo_clave}"

                # Crear grupo
                grupo, created = Grupo.objects.get_or_create(
                    clave=clave_unica_bd,
                    periodo=periodo,
                    defaults={
                        'grado': grado_final, 
                        'grupo': grupo_clave,
                        'turno': turno or 'Matutino',
                        'programa': programa,
                        'tutor': tutor,
                        'activo': 1,  # Cambio: usar 1 en lugar de True
                        'cupo_maximo': 40
                    }
                )
                
                # Cache con tupla
                cache_key = (programa_nombre, cuatrimestre_str, grupo_clave)
                grupos_cache[cache_key] = grupo
                
                if created:
                    total_creados += 1
                    # Mostrar progreso cada 20
                    if total_creados % 20 == 0:
                        logger.log_progress(total_creados, len(df_grupos), "Grupos creados")
                
            except Exception as e:
                errores += 1
                error_msg = f"Fila {idx+2} (Grupo: {grupo_clave if 'grupo_clave' in locals() else 'N/A'}): {str(e)}"
                logger.log_error(error_msg, SECCION)
    
    # Resumen final
    logger.log("\n   " + "-"*60)
    logger.log_success(f"Grupos creados: {total_creados}/{len(df_grupos)}")
    if total_omitidos > 0:
        logger.log_warning(f"Filas omitidas (sin datos): {total_omitidos}")
    if errores > 0:
        logger.log_error(f"Errores encontrados: {errores}", SECCION)
    
    return grupos_cache


def importar_alumnos(df_alumnos, programas_cache):
    """Importa alumnos desde 'Datos Alumnos.csv'"""
    SECCION = "alumnos"
    logger.log("\n👨‍🎓 Importando Alumnos...")
    logger.log(f"   📊 Total de filas en Excel: {len(df_alumnos)}")
    logger.log(f"   📋 Columnas detectadas: {list(df_alumnos.columns)[:8]}...")
    
    alumnos_cache = {}
    total_creados = 0
    total_omitidos = 0
    errores = 0
    
    with transaction.atomic():
        for idx, row in df_alumnos.iterrows():
            try:
                matricula = limpiar_texto(row.get('Matrícula'))
                nombres = limpiar_texto(row.get('Nombres', ''))
                a_paterno = limpiar_texto(row.get('A. Paterno', ''))
                a_materno = limpiar_texto(row.get('A. Materno', ''))
                sexo = limpiar_texto(row.get('Sexo', ''))
                nss = limpiar_texto(row.get('NSS', ''))
                programa_nombre = limpiar_texto(row.get('Programa', ''))
                email = limpiar_texto(row.get('Email Institucional') or row.get('Email', ''))
                
                if not matricula or not nombres:
                    total_omitidos += 1
                    continue
                
                # Construir nombre completo
                apellidos = f"{a_paterno or ''} {a_materno or ''}".strip()
                nombre_completo = f"{nombres} {apellidos}".strip()
                
                # Obtener programa
                programa = programas_cache.get(programa_nombre)
                
                # Crear plan de estudio
                plan_estudio = None
                if programa:
                    plan_codigo = f"{programa.codigo}-2020"
                    
                    plan_estudio, _ = PlanEstudio.objects.get_or_create(
                        codigo=plan_codigo,
                        programa=programa,
                        defaults={
                            'nombre': plan_codigo,
                            'anio_inicio': 2020,
                            'activo': 1
                        }
                    )
                
                # Normalizar género
                genero = None
                if sexo:
                    sexo_lower = sexo.lower()
                    if 'h' in sexo_lower or 'm' == sexo_lower:
                        genero = 'Masculino'
                    elif 'f' in sexo_lower or 'mujer' in sexo_lower:
                        genero = 'Femenino'
                
                username = generar_username(matricula)
                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': nombres,
                        'last_name': apellidos,
                        'email': email or f"{username}@alumno.utpuebla.edu.mx",
                        'is_active': True,
                        'rol': 'ALUMNO',
                        'nombre_completo': nombre_completo,
                        'genero': genero,
                    }
                )
                
                if user_created:
                    user.set_password(matricula)
                    user.save()
                
                # Crear alumno
                alumno, created = Alumno.objects.get_or_create(
                    matricula=matricula,
                    defaults={
                        'user': user,
                        'nss': nss,
                        'plan_estudio': plan_estudio,
                        'semestre_actual': 1,
                        'estatus': 'ACTIVO'
                    }
                )
                
                alumnos_cache[matricula] = alumno
                
                if created:
                    total_creados += 1
                    # Mostrar progreso cada 500
                    if total_creados % 500 == 0:
                        logger.log_progress(total_creados, len(df_alumnos), "Alumnos creados")
                
            except Exception as e:
                errores += 1
                error_msg = f"Fila {idx+2} (Matrícula: {matricula if 'matricula' in locals() else 'N/A'}): {str(e)}"
                logger.log_error(error_msg, SECCION)
                
                # Si hay muchos errores seguidos, pausar y mostrar
                if errores % 100 == 0:
                    logger.log_warning(f"⚠️  Se han detectado {errores} errores hasta ahora...")
    
    # Resumen final
    logger.log("\n   " + "-"*60)
    logger.log_success(f"Alumnos creados: {total_creados}/{len(df_alumnos)}")
    if total_omitidos > 0:
        logger.log_warning(f"Filas omitidas (sin datos): {total_omitidos}")
    if errores > 0:
        logger.log_error(f"Errores encontrados: {errores}", SECCION)
    
    return alumnos_cache


def importar_relaciones_inscritos(df_inscritos, alumnos_cache, grupos_cache):
    """Importa relaciones Alumno-Grupo desde 'Relación Inscritos.csv'"""
    SECCION = "relaciones"
    logger.log("\n🔗 Importando Relaciones Alumno-Grupo...")
    logger.log(f"   📊 Total de filas en Excel: {len(df_inscritos)}")
    
    total_creados = 0
    total_omitidos = 0
    errores = 0
    alumnos_no_encontrados = set()
    grupos_no_encontrados = set()
    
    with transaction.atomic():
        for idx, row in df_inscritos.iterrows():
            try:
                matricula = limpiar_texto(row.get('Matrícula'))
                grupo_clave = limpiar_texto(row.get('Grupo'))
                programa_nombre = limpiar_texto(row.get('Programa'))
                cuatrimestre_str = limpiar_texto(row.get('Cuatrimestre'))
                
                cache_key = (programa_nombre, cuatrimestre_str, grupo_clave)
                
                if not matricula or not all(cache_key):
                    total_omitidos += 1
                    continue
                
                alumno = alumnos_cache.get(matricula)
                grupo = grupos_cache.get(cache_key)
                
                if not alumno:
                    alumnos_no_encontrados.add(matricula)
                    errores += 1
                    continue
                
                if not grupo:
                    grupos_no_encontrados.add(str(cache_key))
                    errores += 1
                    continue
                
                relacion, created = AlumnoGrupo.objects.get_or_create(
                    alumno=alumno,
                    grupo=grupo,
                    defaults={
                        'fecha_inscripcion': date.today(),
                        'activo': 1  # Cambio: usar 1 en lugar de True
                    }
                )
                
                if created:
                    total_creados += 1
                    # Mostrar progreso cada 500
                    if total_creados % 500 == 0:
                        logger.log_progress(total_creados, len(df_inscritos), "Relaciones creadas")
                
            except Exception as e:
                errores += 1
                error_msg = f"Fila {idx+2} (Matrícula: {matricula if 'matricula' in locals() else 'N/A'}): {str(e)}"
                logger.log_error(error_msg, SECCION)

    # Resumen final detallado
    logger.log("\n   " + "-"*60)
    logger.log_success(f"Relaciones creadas: {total_creados}/{len(df_inscritos)}")
    if total_omitidos > 0:
        logger.log_warning(f"Filas omitidas (sin datos): {total_omitidos}")
    
    if alumnos_no_encontrados:
        logger.log_error(f"Alumnos no encontrados: {len(alumnos_no_encontrados)}", SECCION)
        logger.log(f"     Ejemplos: {list(alumnos_no_encontrados)[:5]}")
    
    if grupos_no_encontrados:
        logger.log_error(f"Grupos no encontrados: {len(grupos_no_encontrados)}", SECCION)
        logger.log(f"     Ejemplos: {list(grupos_no_encontrados)[:3]}")
    
    return total_creados


# =============================================================================
# REPORTE DE BAJAS AUTOMÁTICAS
# =============================================================================

def generar_reporte_bajas(periodo_actual, matriculas_nuevas):
    """
    Genera reporte de alumnos nuevos, continuos y dados de baja
    """
    logger.log("\n" + "="*70)
    logger.log("📊 REPORTE DE CAMBIOS EN ALUMNADO")
    logger.log("="*70)
    
    # Obtener alumnos del periodo actual (activos)
    alumnos_actuales = set(
        AlumnoGrupo.objects.filter(
            grupo__periodo=periodo_actual,
            activo=1
        ).values_list('alumno__matricula', flat=True)
    )
    
    # Buscar periodo anterior
    periodo_anterior = Periodo.objects.filter(
        activo=0
    ).order_by('-codigo').first()
    
    if periodo_anterior:
        # Alumnos que estaban en el periodo anterior
        alumnos_anteriores = set(
            AlumnoGrupo.objects.filter(
                grupo__periodo=periodo_anterior,
                activo=0  # Ya fueron desactivados
            ).values_list('alumno__matricula', flat=True)
        )
        
        # Calcular diferencias
        alumnos_nuevos = alumnos_actuales - alumnos_anteriores
        alumnos_continuos = alumnos_actuales & alumnos_anteriores
        alumnos_baja = alumnos_anteriores - alumnos_actuales
        
        logger.log(f"\n📈 Estadísticas:")
        logger.log(f"   Periodo actual: {periodo_actual.codigo}")
        logger.log(f"   Periodo anterior: {periodo_anterior.codigo}")
        logger.log("")
        logger.log_success(f"Alumnos NUEVOS (primera vez): {len(alumnos_nuevos)}")
        logger.log_success(f"Alumnos CONTINUOS (estaban y siguen): {len(alumnos_continuos)}")
        logger.log_warning(f"Alumnos dados de BAJA (ya no aparecen): {len(alumnos_baja)}")
        
        # Guardar detalles en archivo
        if alumnos_baja:
            with open('alumnos_dados_de_baja.txt', 'w', encoding='utf-8') as f:
                f.write(f"ALUMNOS DADOS DE BAJA - {periodo_anterior.codigo} → {periodo_actual.codigo}\n")
                f.write(f"{'='*70}\n\n")
                f.write(f"Total: {len(alumnos_baja)} alumnos\n\n")
                f.write("Matrículas:\n")
                for matricula in sorted(alumnos_baja):
                    alumno = Alumno.objects.filter(matricula=matricula).first()
                    if alumno:
                        nombre = alumno.user.nombre_completo or alumno.user.get_full_name()
                        f.write(f"  - {matricula}: {nombre}\n")
            
            logger.log_info(f"Detalles guardados en: alumnos_dados_de_baja.txt")
    else:
        logger.log_info("No hay periodo anterior para comparar")
        logger.log_success(f"Total de alumnos en {periodo_actual.codigo}: {len(alumnos_actuales)}")


# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    """Función principal"""
    logger.log("="*70)
    logger.log("IMPORTACIÓN DE DATOS DESDE EXCEL (4 HOJAS)")
    logger.log("Sistema de Sociograma UTP - Versión Mejorada")
    logger.log("="*70)
    
    archivo_excel = 'datos.xlsx'
    
    if not os.path.exists(archivo_excel):
        logger.log_error(f"No se encontró el archivo '{archivo_excel}'")
        return
    
    try:
        # Leer Excel
        logger.log(f"\n📂 Leyendo archivo: {archivo_excel}")
        excel_file = pd.ExcelFile(archivo_excel)
        logger.log_success(f"Hojas encontradas: {excel_file.sheet_names}")
        
        # Detectar nombres de hojas
        hojas_map = {
            'alumnos': None,
            'grupos': None,
            'tutores': None,
            'inscritos': None
        }
        
        for nombre_hoja in excel_file.sheet_names:
            nombre_lower = nombre_hoja.lower()
            if 'alumnos' in nombre_lower:
                hojas_map['alumnos'] = nombre_hoja
            elif 'grupos' in nombre_lower:
                hojas_map['grupos'] = nombre_hoja
            elif 'tutores' in nombre_lower:
                hojas_map['tutores'] = nombre_hoja
            elif 'inscritos' in nombre_lower or 'relaci' in nombre_lower:
                hojas_map['inscritos'] = nombre_hoja
        
        # Validar hojas
        logger.log(f"\n📋 Hojas detectadas:")
        for tipo, nombre in hojas_map.items():
            status = "✅" if nombre else "❌"
            logger.log(f"   {status} {tipo.capitalize()}: {nombre or 'NO ENCONTRADA'}")
        
        # Función para leer hojas
        def leer_hoja_inteligente(excel_file, nombre_hoja):
            if not nombre_hoja:
                return pd.DataFrame()
            
            df_preview = pd.read_excel(excel_file, sheet_name=nombre_hoja, nrows=10)
            
            header_row = 0
            for i in range(10):
                try:
                    df_test = pd.read_excel(excel_file, sheet_name=nombre_hoja, header=i, nrows=1)
                    cols_str = ' '.join(str(col).lower() for col in df_test.columns)
                    
                    if 'matricula' in cols_str or 'matrícula' in cols_str:
                        header_row = i
                        break
                    elif 'empleado' in cols_str or 'nombres' in cols_str:
                        header_row = i
                        break
                    elif 'grupo' in cols_str or 'cuatrimestre' in cols_str:
                        header_row = i
                        break
                except:
                    continue
            
            df = pd.read_excel(excel_file, sheet_name=nombre_hoja, header=header_row)
            logger.log_info(f"Hoja '{nombre_hoja}': Header detectado en fila {header_row + 1}")
            logger.log(f"      Columnas: {list(df.columns)[:5]}...")
            return df
        
        df_alumnos = leer_hoja_inteligente(excel_file, hojas_map['alumnos'])
        df_grupos = leer_hoja_inteligente(excel_file, hojas_map['grupos'])
        df_tutores = leer_hoja_inteligente(excel_file, hojas_map['tutores'])
        df_inscritos = leer_hoja_inteligente(excel_file, hojas_map['inscritos'])
        
        # =====================================================================
        # GESTIÓN DE PERIODOS (NUEVO)
        # =====================================================================
        periodo = seleccionar_periodo()
        desactivar_periodo_anterior(periodo)
        
        # =====================================================================
        # IMPORTAR EN ORDEN
        # =====================================================================
        divisiones_cache, programas_cache = importar_divisiones_programas(df_alumnos, df_grupos)
        tutores_cache = importar_tutores(df_tutores, divisiones_cache) if not df_tutores.empty else {}
        grupos_cache = importar_grupos(df_grupos, programas_cache, tutores_cache, periodo) if not df_grupos.empty else {}
        alumnos_cache = importar_alumnos(df_alumnos, programas_cache) if not df_alumnos.empty else {}
        
        matriculas_importadas = set(alumnos_cache.keys())
        
        if not df_inscritos.empty:
            importar_relaciones_inscritos(df_inscritos, alumnos_cache, grupos_cache)
        
        # =====================================================================
        # REPORTE DE BAJAS (NUEVO)
        # =====================================================================
        generar_reporte_bajas(periodo, matriculas_importadas)
        
        # Mostrar resumen de errores
        logger.mostrar_resumen_errores()
        
        # Resumen final
        logger.log("\n" + "="*70)
        logger.log("✅ IMPORTACIÓN COMPLETADA")
        logger.log("="*70)
        logger.log(f"\n📊 RESUMEN FINAL:")
        logger.log(f"   Divisiones: {Division.objects.count()}")
        logger.log(f"   Programas: {Programa.objects.count()}")
        logger.log(f"   Planes de Estudio: {PlanEstudio.objects.count()}")
        logger.log(f"   Periodos: {Periodo.objects.count()}")
        logger.log(f"   Docentes: {Docente.objects.count()}")
        logger.log(f"   Grupos: {Grupo.objects.count()}")
        logger.log(f"   Alumnos: {Alumno.objects.count()}")
        logger.log(f"   Relaciones Alumno-Grupo: {AlumnoGrupo.objects.count()}")
        logger.log(f"   Usuarios totales: {User.objects.count()}")
        
        # Resumen del periodo actual
        grupos_activos = Grupo.objects.filter(periodo=periodo, activo=1).count()
        relaciones_activas = AlumnoGrupo.objects.filter(grupo__periodo=periodo, activo=1).count()
        
        logger.log(f"\n📅 Periodo actual: {periodo.codigo}")
        logger.log(f"   Grupos activos: {grupos_activos}")
        logger.log(f"   Alumnos inscritos: {relaciones_activas}")
        
        # Estado final
        total_errores = sum(len(errores) for errores in logger.errores_por_seccion.values())
        if total_errores == 0:
            logger.log("\n🎉 ¡IMPORTACIÓN EXITOSA SIN ERRORES!")
        else:
            logger.log(f"\n⚠️  Importación completada con {total_errores} errores (ver resumen arriba)")
        
        logger.log(f"\n📄 Log completo guardado en: {logger.log_file}")
        
    except Exception as e:
        logger.log_error(f"Error crítico en la importación: {str(e)}")
        import traceback
        error_detail = traceback.format_exc()
        logger.log("\n" + "="*70)
        logger.log("DETALLE DEL ERROR CRÍTICO:")
        logger.log("="*70)
        logger.log(error_detail)


if __name__ == '__main__':
    main()