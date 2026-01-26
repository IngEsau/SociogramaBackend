# core/views/admin/import_alumnos.py
"""
Endpoint para importación de alumnos a grupos existentes
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from datetime import date
import pandas as pd

from core.models import User, Programa, PlanEstudio, Alumno, Grupo, AlumnoGrupo
from core.utils.decorators import require_admin
from .helpers import (
    limpiar_texto,
    generar_username,
    normalizar_genero,
)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
@parser_classes([MultiPartParser, FormParser])
def import_alumnos_view(request):
    """
    Endpoint para importación masiva de ALUMNOS a grupos existentes
    
    POST /api/admin/import-alumnos/
    
    Headers:
        Authorization: Bearer <access_token>
        Content-Type: multipart/form-data
    
    Body (form-data):
        file: archivo CSV con columnas:
            - Matrícula (requerido)
            - Nombres (requerido)
            - A. Paterno
            - A. Materno
            - Sexo
            - NSS
            - Email Institucional
            - Programa (requerido)
            - Clave Grupo (requerido) - Ej: ISC-1-A, INGSOFT-3-B
            - Semestre Actual (opcional, default: 1)
    
    Permisos:
        - Solo usuarios ADMIN
    
    Nota:
        - El grupo debe existir previamente
        - El programa debe existir previamente
        - Se crea el alumno y se inscribe en el grupo especificado
    
    Response:
        {
            "success": true,
            "message": "Importación de alumnos completada",
            "resumen": {
                "alumnos_creados": 10,
                "alumnos_actualizados": 3,
                "relaciones_creadas": 13
            }
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
        columnas_requeridas = ['Matrícula', 'Nombres', 'Programa', 'Clave Grupo']
        
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
                'alumnos_creados': 0,
                'alumnos_actualizados': 0,
                'relaciones_creadas': 0,
            }
            errores = []
            
            # Caches
            programas_cache = {}
            planes_cache = {}
            grupos_cache = {}
            
            # Procesar fila por fila
            for idx, row in df.iterrows():
                try:
                    # Obtener datos básicos
                    matricula = limpiar_texto(row.get('Matrícula'))
                    nombres = limpiar_texto(row.get('Nombres'))
                    a_paterno = limpiar_texto(row.get('A. Paterno', ''))
                    a_materno = limpiar_texto(row.get('A. Materno', ''))
                    sexo = limpiar_texto(row.get('Sexo', ''))
                    nss = limpiar_texto(row.get('NSS', ''))
                    email = limpiar_texto(row.get('Email Institucional') or row.get('Email', ''))
                    programa_nombre = limpiar_texto(row.get('Programa'))
                    clave_grupo = limpiar_texto(row.get('Clave Grupo'))
                    semestre_actual = row.get('Semestre Actual', 1)
                    
                    # Validar datos mínimos
                    if not matricula or not nombres:
                        errores.append(f"Fila {idx+2}: Falta Matrícula o Nombres")
                        continue
                    
                    if not programa_nombre:
                        errores.append(f"Fila {idx+2}: Falta Programa")
                        continue
                    
                    if not clave_grupo:
                        errores.append(f"Fila {idx+2}: Falta Clave Grupo")
                        continue
                    
                    # Buscar Programa
                    programa = None
                    if programa_nombre not in programas_cache:
                        try:
                            programa = Programa.objects.get(nombre=programa_nombre)
                            programas_cache[programa_nombre] = programa
                        except Programa.DoesNotExist:
                            errores.append(f"Fila {idx+2}: Programa '{programa_nombre}' no existe")
                            continue
                    else:
                        programa = programas_cache[programa_nombre]
                    
                    # Buscar o crear Plan de Estudio
                    plan_key = programa_nombre
                    if plan_key not in planes_cache:
                        plan_codigo = f"{programa.codigo}-2020"
                        plan_estudio, _ = PlanEstudio.objects.get_or_create(
                            codigo=plan_codigo,
                            programa=programa,
                            defaults={'nombre': plan_codigo, 'anio_inicio': 2020, 'activo': True}
                        )
                        planes_cache[plan_key] = plan_estudio
                    else:
                        plan_estudio = planes_cache[plan_key]
                    
                    # Buscar Grupo
                    grupo = None
                    if clave_grupo not in grupos_cache:
                        try:
                            grupo = Grupo.objects.get(clave=clave_grupo, activo=True)
                            grupos_cache[clave_grupo] = grupo
                        except Grupo.DoesNotExist:
                            errores.append(f"Fila {idx+2}: Grupo '{clave_grupo}' no existe o no está activo")
                            continue
                        except Grupo.MultipleObjectsReturned:
                            errores.append(f"Fila {idx+2}: Múltiples grupos con clave '{clave_grupo}' - especifique periodo")
                            continue
                    else:
                        grupo = grupos_cache[clave_grupo]
                    
                    # Preparar datos del alumno
                    apellidos = f"{a_paterno or ''} {a_materno or ''}".strip()
                    nombre_completo = f"{nombres} {apellidos}".strip()
                    genero = normalizar_genero(sexo)
                    username = generar_username(matricula)
                    
                    # Crear o actualizar User
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
                    
                    # Si es nuevo, establecer password
                    if user_created:
                        user.set_password(matricula)
                        user.save()
                    else:
                        # Actualizar datos si ya existe
                        user.first_name = nombres
                        user.last_name = apellidos
                        user.nombre_completo = nombre_completo
                        if email:
                            user.email = email
                        if genero:
                            user.genero = genero
                        user.rol = 'ALUMNO'
                        user.save()
                    
                    # Crear o actualizar Alumno
                    alumno, alumno_created = Alumno.objects.get_or_create(
                        matricula=matricula,
                        defaults={
                            'user': user,
                            'nss': nss,
                            'plan_estudio': plan_estudio,
                            'semestre_actual': semestre_actual,
                            'estatus': 'ACTIVO'
                        }
                    )
                    
                    if alumno_created:
                        resumen['alumnos_creados'] += 1
                    else:
                        # Actualizar alumno existente
                        if nss:
                            alumno.nss = nss
                        alumno.plan_estudio = plan_estudio
                        alumno.semestre_actual = semestre_actual
                        alumno.save()
                        resumen['alumnos_actualizados'] += 1
                    
                    # Crear relación Alumno-Grupo (si no existe)
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
                'message': f'Importación de alumnos completada{"" if not errores else " con algunos errores"}',
                'resumen': resumen,
                'errores': errores[:10] if errores else None,
                'estadisticas': {
                    'total_alumnos': Alumno.objects.count(),
                    'total_relaciones': AlumnoGrupo.objects.filter(activo=True).count(),
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