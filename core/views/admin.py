# core/views/admin.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from datetime import date
import pandas as pd
import re

from core.models import (
    User, Division, Programa, PlanEstudio, Periodo, 
    Docente, Grupo, Alumno, AlumnoGrupo
)
from core.utils.decorators import require_admin


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def limpiar_texto(texto):
    if pd.isna(texto) or texto == '':
        return None
    return str(texto).strip()

def generar_username(matricula_o_empleado):
    return str(matricula_o_empleado).strip().lower().replace(' ', '')

def normalizar_genero(sexo):
    if not sexo:
        return None
    sexo_lower = str(sexo).lower()
    if 'h' in sexo_lower or 'm' == sexo_lower or 'masc' in sexo_lower:
        return 'Masculino'
    elif 'f' in sexo_lower or 'mujer' in sexo_lower or 'fem' in sexo_lower:
        return 'Femenino'
    return 'Otro'

def crear_o_obtener_periodo():
    periodo, created = Periodo.objects.get_or_create(
        codigo='2025-2',
        defaults={
            'nombre': 'Mayo - Agosto 2025',
            'fecha_inicio': date(2025, 5, 1),
            'fecha_fin': date(2025, 8, 31),
            'activo': True
        }
    )
    return periodo


# =============================================================================
# ENDPOINT PRINCIPAL - UN SOLO CSV
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
@parser_classes([MultiPartParser, FormParser])
def import_csv_view(request):
    """
    Endpoint para importación masiva desde UN SOLO archivo CSV
    
    POST /api/admin/import-csv/
    
    Headers:
        Authorization: Bearer <access_token>
        Content-Type: multipart/form-data
    
    Body (form-data):
        file: archivo CSV con TODAS las columnas:
            - Matrícula, Nombres, A. Paterno, A. Materno, Sexo, NSS, Email Institucional
            - Programa, División
            - Cuatrimestre, Grupo, Turno
            - Tutor No. Empleado, Tutor Nombres, Tutor A. Paterno, Tutor A. Materno,
              Tutor Sexo, Tutor Email, Tutor Puesto
    
    Permisos:
        - Solo usuarios ADMIN
    
    Response:
        {
            "success": true,
            "message": "Importación completada",
            "resumen": {...}
        }
    """
    
    # Verificar archivo
    if 'file' not in request.FILES:
        return Response(
            {'error': 'No se proporcionó ningún archivo. Use el campo "file" en form-data'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    archivo = request.FILES['file']
    
    # Validar extensión
    if not archivo.name.endswith('.csv'):
        return Response(
            {'error': f'El archivo debe ser CSV (.csv), recibido: {archivo.name}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Leer CSV
        df = pd.read_csv(archivo)
        
        # Validar columnas requeridas
        columnas_requeridas = [
            'Matrícula', 'Nombres', 'A. Paterno', 'Programa', 'División',
            'Cuatrimestre', 'Grupo'
        ]
        
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            return Response(
                {
                    'error': f'Faltan las siguientes columnas: {", ".join(columnas_faltantes)}',
                    'columnas_encontradas': list(df.columns),
                    'columnas_requeridas': columnas_requeridas
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if df.empty:
            return Response(
                {'error': 'El archivo CSV está vacío'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Iniciar transacción
        with transaction.atomic():
            resumen = {
                'divisiones_creadas': 0,
                'programas_creados': 0,
                'tutores_creados': 0,
                'grupos_creados': 0,
                'alumnos_creados': 0,
                'relaciones_creadas': 0
            }
            errores = []
            
            # Crear periodo
            periodo = crear_o_obtener_periodo()
            resumen['periodo'] = periodo.codigo
            
            # Caches
            divisiones_cache = {}
            programas_cache = {}
            tutores_cache = {}
            grupos_cache = {}
            alumnos_cache = {}
            
            # Procesar fila por fila
            for idx, row in df.iterrows():
                try:
                    # ===========================================
                    # 1. DIVISIÓN
                    # ===========================================
                    division_nombre = limpiar_texto(row.get('División'))
                    if division_nombre and division_nombre not in divisiones_cache:
                        codigo_div = re.sub(r'[^A-Z]', '', division_nombre.upper())[:10] or division_nombre[:10].upper()
                        division, created = Division.objects.get_or_create(
                            codigo=codigo_div,
                            defaults={'nombre': division_nombre, 'activa': True}
                        )
                        divisiones_cache[division_nombre] = division
                        if created:
                            resumen['divisiones_creadas'] += 1
                    
                    division = divisiones_cache.get(division_nombre)
                    
                    # ===========================================
                    # 2. PROGRAMA
                    # ===========================================
                    programa_nombre = limpiar_texto(row.get('Programa'))
                    if programa_nombre and programa_nombre not in programas_cache:
                        nombre_limpio = re.sub(r'\s*-\s*\d{4}', '', programa_nombre)
                        palabras = nombre_limpio.split()
                        
                        if len(palabras) >= 3:
                            codigo_prog = ''.join([p[0].upper() for p in palabras if len(p) > 2])[:8]
                        elif len(palabras) == 2:
                            codigo_prog = ''.join([p[:4].upper() for p in palabras])[:8]
                        else:
                            codigo_prog = ''.join([c.upper() for c in nombre_limpio if c.isalnum()])[:8]
                        
                        if not codigo_prog or len(codigo_prog) < 2:
                            codigo_prog = nombre_limpio.replace(' ', '')[:20].upper()
                        
                        programa, created = Programa.objects.get_or_create(
                            codigo=codigo_prog,
                            defaults={
                                'nombre': programa_nombre,
                                'division': division,
                                'duracion_semestres': 9,
                                'activo': True
                            }
                        )
                        programas_cache[programa_nombre] = programa
                        if created:
                            resumen['programas_creados'] += 1
                    
                    programa = programas_cache.get(programa_nombre)
                    
                    # ===========================================
                    # 3. PLAN DE ESTUDIO
                    # ===========================================
                    plan_estudio = None
                    if programa:
                        plan_codigo = f"{programa.codigo}-2020"
                        plan_estudio, _ = PlanEstudio.objects.get_or_create(
                            codigo=plan_codigo,
                            programa=programa,
                            defaults={'nombre': plan_codigo, 'anio_inicio': 2020, 'activo': True}
                        )
                    
                    # ===========================================
                    # 4. TUTOR (si existe en el CSV)
                    # ===========================================
                    tutor_empleado = limpiar_texto(row.get('Tutor No. Empleado'))
                    tutor = None
                    
                    if tutor_empleado and tutor_empleado not in tutores_cache:
                        tutor_nombres = limpiar_texto(row.get('Tutor Nombres', ''))
                        tutor_paterno = limpiar_texto(row.get('Tutor A. Paterno', ''))
                        tutor_materno = limpiar_texto(row.get('Tutor A. Materno', ''))
                        tutor_sexo = limpiar_texto(row.get('Tutor Sexo', ''))
                        tutor_email = limpiar_texto(row.get('Tutor Email', ''))
                        tutor_puesto = limpiar_texto(row.get('Tutor Puesto', ''))
                        
                        if tutor_nombres:
                            apellidos_tutor = f"{tutor_paterno or ''} {tutor_materno or ''}".strip()
                            nombre_completo_tutor = f"{tutor_nombres} {apellidos_tutor}".strip()
                            genero_tutor = normalizar_genero(tutor_sexo)
                            
                            username_tutor = generar_username(tutor_empleado)
                            user_tutor, user_created = User.objects.get_or_create(
                                username=username_tutor,
                                defaults={
                                    'first_name': tutor_nombres,
                                    'last_name': apellidos_tutor,
                                    'email': tutor_email or f"{username_tutor}@utpuebla.edu.mx",
                                    'is_staff': True,
                                    'is_active': True,
                                    'rol': 'DOCENTE',
                                    'nombre_completo': nombre_completo_tutor,
                                    'genero': genero_tutor,
                                }
                            )
                            
                            if user_created:
                                user_tutor.set_password(tutor_empleado)
                                user_tutor.save()
                            
                            docente, created = Docente.objects.get_or_create(
                                profesor_id=tutor_empleado,
                                defaults={
                                    'user': user_tutor,
                                    'division': division,
                                    'es_tutor': True,
                                    'especialidad': tutor_puesto,
                                    'estatus': 'ACTIVO'
                                }
                            )
                            
                            tutores_cache[tutor_empleado] = docente
                            if created:
                                resumen['tutores_creados'] += 1
                    
                    if tutor_empleado:
                        tutor = tutores_cache.get(tutor_empleado)
                    
                    # ===========================================
                    # 5. GRUPO
                    # ===========================================
                    cuatrimestre = limpiar_texto(row.get('Cuatrimestre'))
                    grupo_letra = limpiar_texto(row.get('Grupo'))
                    turno = limpiar_texto(row.get('Turno', 'Matutino'))
                    
                    if turno and turno.lower() not in ['matutino', 'vespertino', 'nocturno']:
                        turno = 'Matutino'
                    elif turno:
                        turno = turno.capitalize()
                    
                    grupo_key = (programa_nombre, cuatrimestre, grupo_letra)
                    
                    if all(grupo_key) and grupo_key not in grupos_cache:
                        grado_match = re.match(r'^\d+', str(cuatrimestre))
                        grado = grado_match.group(0) if grado_match else 'SG'
                        
                        clave_grupo = f"{programa.codigo}-{grado}-{grupo_letra}"
                        
                        grupo, created = Grupo.objects.get_or_create(
                            clave=clave_grupo,
                            periodo=periodo,
                            defaults={
                                'grado': grado,
                                'grupo': grupo_letra,
                                'turno': turno or 'Matutino',
                                'programa': programa,
                                'tutor': tutor,
                                'activo': True,
                                'cupo_maximo': 40
                            }
                        )
                        
                        grupos_cache[grupo_key] = grupo
                        if created:
                            resumen['grupos_creados'] += 1
                    
                    grupo = grupos_cache.get(grupo_key)
                    
                    # ===========================================
                    # 6. ALUMNO
                    # ===========================================
                    matricula = limpiar_texto(row.get('Matrícula'))
                    nombres = limpiar_texto(row.get('Nombres'))
                    a_paterno = limpiar_texto(row.get('A. Paterno', ''))
                    a_materno = limpiar_texto(row.get('A. Materno', ''))
                    sexo = limpiar_texto(row.get('Sexo', ''))
                    nss = limpiar_texto(row.get('NSS', ''))
                    email = limpiar_texto(row.get('Email Institucional') or row.get('Email', ''))
                    
                    if not matricula or not nombres:
                        continue
                    
                    if matricula not in alumnos_cache:
                        apellidos = f"{a_paterno or ''} {a_materno or ''}".strip()
                        nombre_completo = f"{nombres} {apellidos}".strip()
                        genero = normalizar_genero(sexo)
                        
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
                            resumen['alumnos_creados'] += 1
                    
                    alumno = alumnos_cache.get(matricula)
                    
                    # ===========================================
                    # 7. RELACIÓN ALUMNO-GRUPO
                    # ===========================================
                    if alumno and grupo:
                        relacion, created = AlumnoGrupo.objects.get_or_create(
                            alumno=alumno,
                            grupo=grupo,
                            defaults={'fecha_inscripcion': date.today(), 'activo': True}
                        )
                        
                        if created:
                            resumen['relaciones_creadas'] += 1
                
                except Exception as e:
                    errores.append(f"Fila {idx+2}: {str(e)}")
            
            # Respuesta
            return Response({
                'success': True,
                'message': f'Importación completada{"" if not errores else " con algunos errores"}',
                'resumen': resumen,
                'errores': errores[:10] if errores else None,
                'estadisticas_bd': {
                    'total_divisiones': Division.objects.count(),
                    'total_programas': Programa.objects.count(),
                    'total_docentes': Docente.objects.count(),
                    'total_grupos': Grupo.objects.count(),
                    'total_alumnos': Alumno.objects.count(),
                    'total_relaciones': AlumnoGrupo.objects.count()
                }
            }, status=status.HTTP_200_OK)
        
    except pd.errors.EmptyDataError:
        return Response(
            {'error': 'El archivo CSV está vacío o corrupto'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Error al procesar el archivo CSV', 'detalle': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )