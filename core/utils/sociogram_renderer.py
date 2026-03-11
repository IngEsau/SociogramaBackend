# core/utils/sociogram_renderer.py
"""
Traduce la lógica de renderizado del frontend
a Python puro para generar un SVG del sociograma en el backend.
Constantes y fórmulas copiadas 1:1 del TypeScript para garantizar
que el resultado visual sea idéntico al que renderiza el frontend.
"""

import math
from dataclasses import dataclass

# ============================================================
# Constantes
# ============================================================

MIN_NODE_SIZE = 18
MAX_NODE_SIZE = 82
MAX_OUTGOING_EDGES = 3
MIN_WEIGHT_RATIO = 0.33
NEUTRAL_THRESHOLD_RATIO = 0.05

VIEWBOX_WIDTH = 980
VIEWBOX_HEIGHT = 700
PADDING = 26


# ============================================================
# Tipos internos
# ============================================================

@dataclass
class _GraphEdge:
    id: str
    source: int
    target: int
    reciproco: bool
    weight: float


@dataclass
class _SimNode:
    id: int
    x: float
    y: float
    vx: float
    vy: float
    radius: float


# ============================================================
# Helpers matemáticos
# ============================================================

def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def _r1(value: float) -> float:
    """Redondea a 1 decimal (equivalente a roundTo1 del TS)."""
    return round(value * 10) / 10


# ============================================================
# Adaptadores
# ============================================================

def _normalize_node_size(impacto: float, max_impacto: float) -> int:
    if max_impacto <= 0:
        return MIN_NODE_SIZE
    normalized = impacto / max_impacto
    return int(_clamp(
        round(MIN_NODE_SIZE + normalized * (MAX_NODE_SIZE - MIN_NODE_SIZE)),
        MIN_NODE_SIZE,
        MAX_NODE_SIZE,
    ))


def _color_from_puntaje(puntos_positivos: int, puntos_negativos: int,
                         impacto_total: float, max_impacto: float) -> str:
    umbral_neutro = max_impacto * NEUTRAL_THRESHOLD_RATIO
    if impacto_total <= umbral_neutro:
        return '#4B5563'
    if puntos_negativos > puntos_positivos:
        return '#7A1501'
    return '#0F7E3C'


def _gradient_by_color(color: str) -> str:
    c = color.lower()
    if '7a1501' in c or '5b0d0d' in c or 'ef4444' in c:
        return 'rejected'
    if '4b5563' in c or '6b7280' in c or '9ca3af' in c:
        return 'neutral'
    return 'accepted'


def _filter_and_build_graph_edges(conexiones: list) -> list:
    positivas = [c for c in conexiones if c.get('polaridad') == 'POSITIVA']

    # Peso total positivo por origen
    total_por_origen: dict[int, float] = {}
    for c in positivas:
        oid = c['origen_id']
        total_por_origen[oid] = total_por_origen.get(oid, 0) + c['peso']

    # Top MAX_OUTGOING_EDGES por origen con peso >= 33% del total
    seleccionados: dict[str, dict] = {}
    for origen_id in set(c['origen_id'] for c in positivas):
        total_peso = total_por_origen.get(origen_id, 0)
        umbral = total_peso * MIN_WEIGHT_RATIO
        candidatos = sorted(
            [c for c in positivas if c['origen_id'] == origen_id and c['peso'] >= umbral],
            key=lambda c: c['peso'],
            reverse=True,
        )[:MAX_OUTGOING_EDGES]
        for c in candidatos:
            seleccionados[f"{c['origen_id']}-{c['destino_id']}"] = c

    # Construir aristas finales con reciprocidad
    result: list[_GraphEdge] = []
    procesados: set[str] = set()

    for key, conn in seleccionados.items():
        if key in procesados:
            continue
        reverse_key = f"{conn['destino_id']}-{conn['origen_id']}"
        es_reciproca = reverse_key in seleccionados

        if es_reciproca:
            rev = seleccionados[reverse_key]
            peso_prom = (conn['peso'] + rev['peso']) / 2
            a = min(conn['origen_id'], conn['destino_id'])
            b = max(conn['origen_id'], conn['destino_id'])
            result.append(_GraphEdge(
                id=f"{a}-{b}-pos-mutual",
                source=conn['origen_id'],
                target=conn['destino_id'],
                reciproco=True,
                weight=peso_prom,
            ))
            procesados.add(key)
            procesados.add(reverse_key)
        else:
            result.append(_GraphEdge(
                id=f"{conn['origen_id']}-{conn['destino_id']}-pos",
                source=conn['origen_id'],
                target=conn['destino_id'],
                reciproco=False,
                weight=conn['peso'],
            ))
            procesados.add(key)

    return result


# ============================================================
# Simulación force-directed
# ============================================================

def _calc_relevancia(puntos_positivos: float, puntos_negativos: float,
                     impacto_total: float) -> float:
    return max(0.0, (puntos_positivos - puntos_negativos) * 0.6 + impacto_total * 0.4)


def _build_simulation(nodos: list, edges: list,
                       width: float = VIEWBOX_WIDTH,
                       height: float = VIEWBOX_HEIGHT) -> dict:
    center_x = width / 2
    center_y = height / 2

    # Ordenar por relevancia descendente (mayor relevancia → más cerca al centro)
    seeded = sorted(
        [
            {
                'id': n['alumno_id'],
                'radius': _clamp(n.get('_size', 26), 14, 86),
                'relevancia': _calc_relevancia(
                    n.get('puntos_positivos', 0),
                    n.get('puntos_negativos', 0),
                    n.get('impacto_total', 0),
                ),
            }
            for n in nodos
        ],
        key=lambda x: x['relevancia'],
        reverse=True,
    )

    if not seeded:
        return {}

    max_relevancia = seeded[0]['relevancia'] if seeded[0]['relevancia'] > 0 else 1.0

    # Posicionamiento inicial radial con golden angle (~137.5°)
    golden_angle = math.pi * (3 - math.sqrt(5))
    states: list[_SimNode] = []

    for index, node in enumerate(seeded):
        if index == 0:
            states.append(_SimNode(
                id=node['id'], x=center_x, y=center_y, vx=0, vy=0, radius=node['radius'],
            ))
        else:
            rel_ratio = 1 - node['relevancia'] / max_relevancia if max_relevancia > 0 else 1.0
            min_ring = node['radius'] * 2 + 50
            max_ring = min(width, height) * 0.44
            ring = min_ring + rel_ratio * (max_ring - min_ring)
            angle = index * golden_angle
            wobble = (((index * 7) % 5) - 2) * 8
            states.append(_SimNode(
                id=node['id'],
                x=center_x + math.cos(angle) * (ring + wobble),
                y=center_y + math.sin(angle) * (ring - wobble * 0.5),
                vx=0, vy=0, radius=node['radius'],
            ))

    state_by_id: dict[int, _SimNode] = {s.id: s for s in states}
    relevancia_by_id: dict[int, float] = {s['id']: s['relevancia'] for s in seeded}

    # Parámetros de simulación (exactos del TS)
    repulsion_factor = 14000.0
    spring_factor = 0.025
    center_force_base = 0.003
    center_force_scale = 0.008
    damping = 0.85
    max_step = 10.0

    # Pre-resolver pares de aristas para el loop
    edge_pairs = [
        (state_by_id.get(e.source), state_by_id.get(e.target), e.reciproco)
        for e in edges
    ]

    # 320 iteraciones de física
    for _ in range(320):
        # Repulsión entre todos los pares de nodos
        for i in range(len(states)):
            a = states[i]
            for j in range(i + 1, len(states)):
                b = states[j]
                dx = b.x - a.x
                dy = b.y - a.y
                dist_sq = dx * dx + dy * dy + 0.1
                dist = math.sqrt(dist_sq)
                min_dist = a.radius + b.radius + 50
                force = (repulsion_factor * min_dist * min_dist) / dist_sq
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                a.vx -= fx
                a.vy -= fy
                b.vx += fx
                b.vy += fy

        # Fuerzas de resorte por aristas
        for (source, target, reciproco) in edge_pairs:
            if not source or not target:
                continue
            dx = target.x - source.x
            dy = target.y - source.y
            dist = math.sqrt(dx * dx + dy * dy) or 1.0
            ideal_dist = source.radius + target.radius + (36 if reciproco else 60)
            stretch = dist - ideal_dist
            force = stretch * spring_factor
            fx = (dx / dist) * force
            fy = (dy / dist) * force
            source.vx += fx
            source.vy += fy
            target.vx -= fx
            target.vy -= fy

        # Fuerza central + integración
        for node in states:
            rel = relevancia_by_id.get(node.id, 0)
            rel_ratio = rel / max_relevancia if max_relevancia > 0 else 0
            cf = center_force_base + rel_ratio * center_force_scale
            node.vx += (center_x - node.x) * cf
            node.vy += (center_y - node.y) * cf
            node.vx *= damping
            node.vy *= damping
            node.x += _clamp(node.vx, -max_step, max_step)
            node.y += _clamp(node.vy, -max_step, max_step)
            node.x = _clamp(node.x, PADDING + node.radius, width - PADDING - node.radius)
            node.y = _clamp(node.y, PADDING + node.radius, height - PADDING - node.radius)

    # Resolución de colisiones (50 pasadas)
    min_gap = 12.0
    for _ in range(50):
        resolved = True
        for i in range(len(states)):
            a = states[i]
            for j in range(i + 1, len(states)):
                b = states[j]
                dx = b.x - a.x
                dy = b.y - a.y
                dist = math.sqrt(dx * dx + dy * dy) or 0.1
                required = a.radius + b.radius + min_gap
                if dist < required:
                    resolved = False
                    overlap = (required - dist) / 2 + 1
                    ux = dx / dist
                    uy = dy / dist
                    a.x -= ux * overlap
                    a.y -= uy * overlap
                    b.x += ux * overlap
                    b.y += uy * overlap
                    a.x = _clamp(a.x, PADDING + a.radius, width - PADDING - a.radius)
                    a.y = _clamp(a.y, PADDING + a.radius, height - PADDING - a.radius)
                    b.x = _clamp(b.x, PADDING + b.radius, width - PADDING - b.radius)
                    b.y = _clamp(b.y, PADDING + b.radius, height - PADDING - b.radius)
        if resolved:
            break

    return state_by_id


# ============================================================
# Path de aristas
# ============================================================

def _get_edge_path(source: _SimNode, target: _SimNode, reciprocal: bool) -> str:
    """Línea recta con offsets para las puntas."""
    dx = target.x - source.x
    dy = target.y - source.y
    dist = math.sqrt(dx * dx + dy * dy) or 1.0
    ux = dx / dist
    uy = dy / dist

    arrow_tip_size = 12
    start_offset = source.radius + arrow_tip_size + 2 if reciprocal else source.radius + 2
    end_offset = target.radius + arrow_tip_size + 2

    sx = source.x + ux * start_offset
    sy = source.y + uy * start_offset
    ex = target.x - ux * end_offset
    ey = target.y - uy * end_offset

    return f"M {_r1(sx)} {_r1(sy)} L {_r1(ex)} {_r1(ey)}"


# ============================================================
# Generador SVG principal
# ============================================================

def render_sociogram_svg(nodos_raw: list, conexiones_raw: list) -> str:
    """
    Genera el SVG completo del sociograma, visualmente idéntico al frontend.

    Args:
        nodos_raw:      Lista de dicts de _calcular_nodos_sociograma()['nodos']
        conexiones_raw: Lista de dicts de _calcular_conexiones_sociograma()

    Returns:
        String SVG (980 × 700 px) listo para convertir a PNG/JPG con cairosvg.
    """
    if not nodos_raw:
        return _empty_svg()

    # Calcular tamaño normalizado y color de cada nodo
    max_impacto = max((n.get('impacto_total', 0) for n in nodos_raw), default=0)

    nodos = []
    for n in nodos_raw:
        size = _normalize_node_size(n.get('impacto_total', 0), max_impacto)
        color = _color_from_puntaje(
            n.get('puntos_positivos', 0),
            n.get('puntos_negativos', 0),
            n.get('impacto_total', 0),
            max_impacto,
        )
        nodos.append({**n, '_size': size, '_color': color})

    # Filtrar y construir aristas (solo positivas, top 3, consolidar recíprocos)
    edges = _filter_and_build_graph_edges(conexiones_raw)

    # Layout force-directed (320 iter + 50 collision passes)
    simulation = _build_simulation(nodos, edges)
    if not simulation:
        return _empty_svg()

    # ---- Construir SVG ----
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg viewBox="0 0 {VIEWBOX_WIDTH} {VIEWBOX_HEIGHT}" '
            f'width="{VIEWBOX_WIDTH}" height="{VIEWBOX_HEIGHT}" '
            f'xmlns="http://www.w3.org/2000/svg">'
        ),
        # Fondo
        f'  <rect width="{VIEWBOX_WIDTH}" height="{VIEWBOX_HEIGHT}" fill="#f4f5f6"/>',
        '  <defs>',
        # Gradientes radiales (idénticos a los del TS)
        '    <radialGradient id="node-accepted" cx="30%" cy="25%" r="75%">',
        '      <stop offset="0%" stop-color="#2F8B7E"/>',
        '      <stop offset="62%" stop-color="#0A5B50"/>',
        '      <stop offset="100%" stop-color="#013D36"/>',
        '    </radialGradient>',
        '    <radialGradient id="node-rejected" cx="30%" cy="25%" r="75%">',
        '      <stop offset="0%" stop-color="#7F2C2A"/>',
        '      <stop offset="62%" stop-color="#5A0D0D"/>',
        '      <stop offset="100%" stop-color="#3A0404"/>',
        '    </radialGradient>',
        '    <radialGradient id="node-neutral" cx="30%" cy="25%" r="75%">',
        '      <stop offset="0%" stop-color="#7A7F87"/>',
        '      <stop offset="62%" stop-color="#4A4F56"/>',
        '      <stop offset="100%" stop-color="#2E3136"/>',
        '    </radialGradient>',
        # Markers de flecha (idénticos al TS)
        '    <marker id="arrow-end" markerWidth="6" markerHeight="5" '
        'refX="6" refY="2.5" orient="auto" markerUnits="strokeWidth">',
        '      <polygon points="0 0, 6 2.5, 0 5" fill="#1A1A1A"/>',
        '    </marker>',
        '    <marker id="arrow-start" markerWidth="6" markerHeight="5" '
        'refX="0" refY="2.5" orient="auto-start-reverse" markerUnits="strokeWidth">',
        '      <polygon points="0 0, 6 2.5, 0 5" fill="#1A1A1A"/>',
        '    </marker>',
        '  </defs>',
    ]

    # Aristas
    for edge in edges:
        src = simulation.get(edge.source)
        tgt = simulation.get(edge.target)
        if not src or not tgt:
            continue
        path = _get_edge_path(src, tgt, edge.reciproco)
        marker_start_attr = ' marker-start="url(#arrow-start)"' if edge.reciproco else ''
        parts.append(
            f'  <path d="{path}" stroke="#1A1A1A" stroke-width="2" fill="none"'
            f' marker-end="url(#arrow-end)"{marker_start_attr}/>'
        )

    # Nodos (círculo + número de lista)
    for nodo in nodos:
        alumno_id = nodo['alumno_id']
        sim = simulation.get(alumno_id)
        if not sim:
            continue

        gradient = _gradient_by_color(nodo['_color'])
        fill = f'url(#node-{gradient})'
        cx = _r1(sim.x)
        cy = _r1(sim.y)
        r = _r1(sim.radius)
        font_size = _r1(_clamp(sim.radius * 0.8, 13, 56))
        text_y = _r1(sim.y + font_size * 0.3)
        label = str(nodo.get('numero_lista', alumno_id))

        parts.append(
            f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" '
            f'stroke="#142029" stroke-width="1.2"/>'
        )
        parts.append(
            f'  <text x="{cx}" y="{text_y}" text-anchor="middle" '
            f'fill="#F4F8FB" font-size="{font_size}" font-weight="700" '
            f'font-family="Arial, sans-serif" '
            f'stroke="#0F1217" stroke-opacity="0.45" stroke-width="1.2" '
            f'paint-order="stroke">{label}</text>'
        )

    parts.append('</svg>')
    return '\n'.join(parts)


def _empty_svg() -> str:
    mid_x = VIEWBOX_WIDTH // 2
    mid_y = VIEWBOX_HEIGHT // 2
    return (
        f'<svg viewBox="0 0 {VIEWBOX_WIDTH} {VIEWBOX_HEIGHT}" '
        f'width="{VIEWBOX_WIDTH}" height="{VIEWBOX_HEIGHT}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{VIEWBOX_WIDTH}" height="{VIEWBOX_HEIGHT}" fill="#f4f5f6"/>'
        f'<text x="{mid_x}" y="{mid_y}" text-anchor="middle" '
        f'fill="#6b7280" font-size="18" font-family="Arial, sans-serif">'
        f'Sin datos</text></svg>'
    )
