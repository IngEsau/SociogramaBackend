# core/views/academic/archivos.py
"""
Endpoints para exportación de datos del sociograma (CSV, PDF).
El tutor puede acceder a cualquier grupo donde sea o haya sido tutor,
sin importar si el periodo está activo o no.
Para los datos del sociograma (JPG) el front usa /api/academic/cuestionarios/{id}/estadisticas/
"""
import csv
import io

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Count, Case, When, IntegerField

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import Cuestionario, CuestionarioEstado, Grupo
from core.utils.decorators import require_tutor
from .cuestionarios import _calcular_nodos_sociograma, _calcular_conexiones_sociograma  # para CSV y PDF


def _get_grupo_tutor(docente, grupo_id):
    """
    Devuelve el grupo si el docente es su tutor (cualquier periodo, activo o no).
    """
    return Grupo.objects.filter(
        id=grupo_id,
        tutor=docente,
    ).select_related('periodo', 'programa').first()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def listar_cuestionarios_historico_view(request):
    """
    Lista todos los pares (cuestionario, grupo) con datos disponibles para el tutor,
    incluyendo periodos pasados. Sin restricción de activo.

    GET /api/academic/archivos/cuestionarios/

    Response:
    {
        "total": 12,
        "archivos": [
            {
                "cuestionario_id": 1,
                "cuestionario_titulo": "Sociograma Enero 2025",
                "grupo_id": 5,
                "grupo_clave": "IDGS-9-A",
                "periodo_codigo": "2025-1",
                "periodo_nombre": "Enero-Junio 2025",
                "fecha_cuestionario": "2025-01-20",
                "total_alumnos": 25,
                "completados": 18
            }
        ]
    }
    """
    # Todos los grupos donde el tutor es (o fue) el tutor asignado
    grupos_tutor = list(
        Grupo.objects.filter(tutor=request.docente)
        .select_related('periodo', 'programa')
    )

    if not grupos_tutor:
        return Response({'total': 0, 'archivos': []}, status=status.HTTP_200_OK)

    grupos_ids = [g.id for g in grupos_tutor]
    grupos_map = {g.id: g for g in grupos_tutor}

    # Pares (cuestionario, grupo) con al menos un estado registrado + conteos
    pares = (
        CuestionarioEstado.objects
        .filter(grupo_id__in=grupos_ids)
        .values('cuestionario_id', 'grupo_id')
        .annotate(
            total=Count('id'),
            completados=Count(
                Case(When(estado='COMPLETADO', then=1), output_field=IntegerField())
            ),
        )
    )

    if not pares:
        return Response({'total': 0, 'archivos': []}, status=status.HTTP_200_OK)

    cuestionario_ids = list({p['cuestionario_id'] for p in pares})
    cuestionarios_map = {
        c.id: c
        for c in Cuestionario.objects.filter(id__in=cuestionario_ids).select_related('periodo')
    }

    archivos = []
    for par in pares:
        cuestionario = cuestionarios_map.get(par['cuestionario_id'])
        grupo = grupos_map.get(par['grupo_id'])
        if not cuestionario or not grupo:
            continue
        archivos.append({
            'cuestionario_id': cuestionario.id,
            'cuestionario_titulo': cuestionario.titulo,
            'grupo_id': grupo.id,
            'grupo_clave': grupo.clave,
            'periodo_codigo': grupo.periodo.codigo,
            'periodo_nombre': grupo.periodo.nombre,
            'fecha_cuestionario': cuestionario.fecha_inicio.date().isoformat(),
            'total_alumnos': par['total'],
            'completados': par['completados'],
        })

    archivos.sort(key=lambda x: x['fecha_cuestionario'], reverse=True)

    return Response({'total': len(archivos), 'archivos': archivos}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def datos_sociograma_view(request, cuestionario_id):
    """
    Datos del sociograma sin restricción de grupo/periodo activo.
    Permite al front generar el JPG de cuestionarios de cualquier periodo.

    GET /api/academic/archivos/cuestionarios/{id}/sociograma/?grupo_id={id}
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    grupo_id = request.query_params.get('grupo_id')

    if not grupo_id:
        return Response(
            {'error': 'El parámetro grupo_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    grupo = _get_grupo_tutor(request.docente, grupo_id)
    if not grupo:
        return Response(
            {'error': 'No tienes acceso a este grupo'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not CuestionarioEstado.objects.filter(cuestionario=cuestionario, grupo=grupo).exists():
        return Response(
            {'error': 'No hay datos de este cuestionario para el grupo indicado'},
            status=status.HTTP_404_NOT_FOUND,
        )

    nodos_data = _calcular_nodos_sociograma(cuestionario, grupo)
    conexiones_data = _calcular_conexiones_sociograma(cuestionario, grupo)

    return Response({
        'cuestionario_id': cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'periodo': grupo.periodo.codigo,
        'grupo_id': grupo.id,
        'grupo_clave': grupo.clave,
        'total_alumnos': nodos_data['total_alumnos'],
        'respuestas_completas': nodos_data['respuestas_completas'],
        'nodos': nodos_data['nodos'],
        'conexiones': conexiones_data,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def exportar_csv_view(request, cuestionario_id):
    """
    Exporta los datos del sociograma en formato CSV (descarga directa).

    GET /api/academic/archivos/cuestionarios/{id}/exportar/csv/?grupo_id={id}

    El CSV incluye:
      - Encabezado con metadatos
      - Sección NODOS: clasificación sociométrica de cada alumno
      - Sección CONEXIONES: elecciones entre alumnos con peso y tipo
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    grupo_id = request.query_params.get('grupo_id')

    if not grupo_id:
        return Response(
            {'error': 'El parámetro grupo_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    grupo = _get_grupo_tutor(request.docente, grupo_id)
    if not grupo:
        return Response(
            {'error': 'No tienes acceso a este grupo'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not CuestionarioEstado.objects.filter(cuestionario=cuestionario, grupo=grupo).exists():
        return Response(
            {'error': 'No hay datos de este cuestionario para el grupo indicado'},
            status=status.HTTP_404_NOT_FOUND,
        )

    nodos_data = _calcular_nodos_sociograma(cuestionario, grupo)
    conexiones_data = _calcular_conexiones_sociograma(cuestionario, grupo)

    filename = f"sociograma_{grupo.clave}_{cuestionario.id}.csv".replace(' ', '_')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    # BOM para que Excel abra correctamente con UTF-8
    response.write('\ufeff')

    writer = csv.writer(response)

    # Metadatos
    writer.writerow(['SOCIOGRAMA', cuestionario.titulo])
    writer.writerow(['Grupo', grupo.clave])
    writer.writerow(['Periodo', grupo.periodo.codigo])
    writer.writerow(['Fecha cuestionario', cuestionario.fecha_inicio.strftime('%d/%m/%Y')])
    writer.writerow(['Total alumnos', nodos_data['total_alumnos']])
    writer.writerow(['Completaron', nodos_data['respuestas_completas']])
    writer.writerow([])

    # Nodos
    writer.writerow(['=== NODOS (ALUMNOS) ==='])
    writer.writerow([
        'N°', 'Matrícula', 'Nombre', 'Clasificación',
        'Puntos Positivos', 'Puntos Negativos', 'Impacto Total',
        'Elecciones Recibidas', 'Elecciones Realizadas', 'Completó',
    ])
    for nodo in nodos_data['nodos']:
        writer.writerow([
            nodo['numero_lista'],
            nodo['matricula'],
            nodo['nombre'],
            nodo['tipo'],
            nodo['puntos_positivos'],
            nodo['puntos_negativos'],
            nodo['impacto_total'],
            nodo['elecciones_recibidas'],
            nodo['elecciones_realizadas'],
            'Sí' if nodo['completo'] else 'No',
        ])

    writer.writerow([])

    # Conexiones
    writer.writerow(['=== CONEXIONES ==='])
    writer.writerow([
        'Origen', 'Destino', 'Peso', 'Tipo Conexión', 'Es Mutua', 'Polaridad', '% Mutuo',
    ])
    for conn in conexiones_data:
        writer.writerow([
            conn['origen_nombre'],
            conn['destino_nombre'],
            conn['peso'],
            conn['tipo_conexion'],
            'Sí' if conn['es_mutua'] else 'No',
            conn['polaridad'],
            conn['porcentaje_mutuo'],
        ])

    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def exportar_pdf_view(request, cuestionario_id):
    """
    Exporta los datos del sociograma en formato PDF (descarga directa).

    GET /api/academic/archivos/cuestionarios/{id}/exportar/pdf/?grupo_id={id}

    Requiere: reportlab (pip install reportlab)
    El PDF incluye tablas de nodos y conexiones en hoja horizontal (A4 landscape).
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
        )
    except ImportError:
        return Response(
            {'error': 'Librería reportlab no disponible. Ejecuta: pip install reportlab'},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    grupo_id = request.query_params.get('grupo_id')

    if not grupo_id:
        return Response(
            {'error': 'El parámetro grupo_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    grupo = _get_grupo_tutor(request.docente, grupo_id)
    if not grupo:
        return Response(
            {'error': 'No tienes acceso a este grupo'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not CuestionarioEstado.objects.filter(cuestionario=cuestionario, grupo=grupo).exists():
        return Response(
            {'error': 'No hay datos de este cuestionario para el grupo indicado'},
            status=status.HTTP_404_NOT_FOUND,
        )

    nodos_data = _calcular_nodos_sociograma(cuestionario, grupo)
    conexiones_data = _calcular_conexiones_sociograma(cuestionario, grupo)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=15, spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        'meta', parent=styles['Normal'], alignment=TA_CENTER, fontSize=9, spaceAfter=2,
    )
    section_style = ParagraphStyle(
        'section', parent=styles['Heading2'], fontSize=11, spaceBefore=10, spaceAfter=4,
    )

    VERDE_OSCURO = colors.HexColor('#1b5e20')
    GRIS_CLARO = colors.HexColor('#f5f5f5')
    COLOR_TIPO = {
        'ACEPTADO': colors.HexColor('#e8f5e9'),
        'RECHAZADO': colors.HexColor('#ffebee'),
        'INVISIBLE': colors.HexColor('#eeeeee'),
    }

    elements = []

    # Encabezado
    elements.append(Paragraph(f"Sociograma — {cuestionario.titulo}", title_style))
    elements.append(Paragraph(
        f"Grupo: {grupo.clave}  |  Periodo: {grupo.periodo.codigo}  |  "
        f"Fecha: {cuestionario.fecha_inicio.strftime('%d/%m/%Y')}",
        meta_style,
    ))
    elements.append(Paragraph(
        f"Total alumnos: {nodos_data['total_alumnos']}  |  "
        f"Completaron: {nodos_data['respuestas_completas']}",
        meta_style,
    ))
    elements.append(Spacer(1, 0.4 * cm))

    # --- Tabla de nodos ---
    elements.append(Paragraph("Nodos (Alumnos)", section_style))

    headers_nodos = [
        'N°', 'Matrícula', 'Nombre', 'Clasificación',
        'Pts+', 'Pts-', 'Impacto', 'Elec.\nRecib.', 'Elec.\nRealiz.', 'Completó',
    ]
    rows_nodos = [headers_nodos]
    for nodo in nodos_data['nodos']:
        rows_nodos.append([
            nodo['numero_lista'],
            nodo['matricula'],
            nodo['nombre'],
            nodo['tipo'],
            nodo['puntos_positivos'],
            nodo['puntos_negativos'],
            nodo['impacto_total'],
            nodo['elecciones_recibidas'],
            nodo['elecciones_realizadas'],
            'Sí' if nodo['completo'] else 'No',
        ])

    col_widths_nodos = [1*cm, 2.5*cm, 5*cm, 2.8*cm, 1.4*cm, 1.4*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm]
    tabla_nodos = Table(rows_nodos, colWidths=col_widths_nodos, repeatRows=1)

    style_nodos = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), VERDE_OSCURO),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ])
    # Colorear celda de clasificación por tipo
    for i, nodo in enumerate(nodos_data['nodos'], start=1):
        color = COLOR_TIPO.get(nodo['tipo'], colors.white)
        style_nodos.add('BACKGROUND', (3, i), (3, i), color)

    tabla_nodos.setStyle(style_nodos)
    elements.append(tabla_nodos)

    # --- Tabla de conexiones ---
    if conexiones_data:
        elements.append(Paragraph("Conexiones", section_style))

        headers_conn = ['Origen', 'Destino', 'Peso', 'Tipo', 'Mutua', 'Polaridad', '% Mutuo']
        rows_conn = [headers_conn]
        for conn in conexiones_data:
            rows_conn.append([
                conn['origen_nombre'],
                conn['destino_nombre'],
                conn['peso'],
                conn['tipo_conexion'].capitalize(),
                'Sí' if conn['es_mutua'] else 'No',
                conn['polaridad'],
                f"{conn['porcentaje_mutuo']}%",
            ])

        col_widths_conn = [4.5*cm, 4.5*cm, 1.4*cm, 2*cm, 1.4*cm, 2.5*cm, 2*cm]
        tabla_conn = Table(rows_conn, colWidths=col_widths_conn, repeatRows=1)
        tabla_conn.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), VERDE_OSCURO),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (1, -1), 'LEFT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(tabla_conn)

    doc.build(elements)
    buffer.seek(0)

    filename = f"sociograma_{grupo.clave}_{cuestionario.id}.pdf".replace(' ', '_')
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
