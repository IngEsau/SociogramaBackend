# PR: Exportar sociograma como imagen PNG + imagen en PDF

**Branch:** `raul` → `main`

---

## Resumen

Implementa el endpoint para exportar el sociograma como imagen PNG y mejora
el endpoint PDF existente para incluir la imagen del sociograma en la primera
página junto con correcciones de layout en las tablas.

---

## Cambios

### Nuevo archivo — `core/utils/sociogram_renderer.py`

Módulo Python que traduce 1:1 la lógica de renderizado del frontend
(`SociogramGraph.tsx` + `adapters.ts`) para poder generar el SVG del
sociograma en el backend sin depender del browser.

Incluye:
- `_filter_and_build_graph_edges()` — filtra solo conexiones POSITIVAS, top 3 por alumno, consolida pares recíprocos
- `_build_simulation()` — simulación force-directed determinista: 320 iteraciones de física + 50 pasadas de resolución de colisiones
- `_normalize_node_size()`, `_color_from_puntaje()`, `_gradient_by_color()` — lógica de color y tamaño idéntica al frontend
- `_get_edge_path()` — paths SVG con offsets para puntas de flecha
- `render_sociogram_svg()` — función pública que genera el SVG completo (980×700 px) listo para convertir con `cairosvg`

### Modificado — `core/views/academic/archivos.py`

**Nuevo endpoint `exportar_imagen_view`:**
```
GET /api/academic/archivos/cuestionarios/{id}/exportar/imagen/?grupo_id={id}
```
- Genera PNG de 1960×1400 px (escala ×2) usando `cairosvg`
- Maneja `OSError` además de `ImportError` para cuando Cairo nativo no está instalado en el OS (caso Windows) — devuelve 501 en vez de 500
- Misma lógica de permisos y validaciones que CSV y PDF

**Mejorado `exportar_pdf_view`:**
- Agrega imagen del sociograma (20cm × ~14.3cm) en página 1 antes de las tablas
- `PageBreak` después de la imagen para garantizar que las tablas siempre arranquen en página 2
- Si `cairosvg` no está disponible, el PDF se genera igual sin la imagen
- Columna **Nombre** ampliada: `5cm → 8cm`
- Columnas **Origen/Destino** en tabla de conexiones: `4.5cm → 6.5cm`

### Modificado — `core/urls.py`

Agrega la ruta:
```python
path('academic/archivos/cuestionarios/<int:cuestionario_id>/exportar/imagen/',
     exportar_imagen_view, name='exportar_imagen')
```

### Nuevo archivo — `docs/academic/exportar-imagen.md`

Guía completa de uso, testing y documentación técnica del módulo.

---

## Dependencia nueva

```
cairosvg >= 2.7.0
```

```bash
pip install cairosvg
```

> **Windows:** requiere instalar el
> [GTK3 Runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer)
> para que Cairo esté disponible como librería nativa del sistema.
> En Linux/Mac funciona directo con `pip install cairosvg`.

---

## Endpoints afectados

| Endpoint | Estado |
|---|---|
| `GET .../exportar/imagen/` | **Nuevo** |
| `GET .../exportar/pdf/` | **Mejorado** (imagen + columnas) |
| `GET .../exportar/csv/` | Sin cambios |
| `GET .../archivos/cuestionarios/` | Sin cambios |
| `GET .../sociograma/` | Sin cambios |

---

## Equivalencias frontend → backend

| TypeScript (frontend) | Python (backend) |
|---|---|
| `buildSimulation()` | `_build_simulation()` |
| `calcRelevancia()` | `_calc_relevancia()` |
| `getEdgePath()` | `_get_edge_path()` |
| `filterAndBuildGraphEdges()` | `_filter_and_build_graph_edges()` |
| `normalizeNodeSize()` | `_normalize_node_size()` |
| `colorFromPuntaje()` | `_color_from_puntaje()` |
| `gradientByNode()` | `_gradient_by_color()` |

La simulación es **completamente determinista** — mismo input de nodos y
conexiones produce siempre el mismo layout, idéntico al que renderiza el frontend.

---

## Checklist de testing

- [ ] `GET /exportar/imagen/?grupo_id=X` devuelve 200 con PNG válido
- [ ] PNG tiene dimensiones 1960×1400 px
- [ ] `GET /exportar/pdf/?grupo_id=X` devuelve PDF con imagen en página 1
- [ ] Tablas del PDF arrancan en página 2
- [ ] Columna Nombre del PDF no desborda hacia Clasificación
- [ ] Columnas Origen/Destino del PDF no desbordan hacia Peso
- [ ] Sin `grupo_id` → 400
- [ ] Grupo de otro tutor → 403
- [ ] Sin datos en el grupo → 404
- [ ] Sin token → 401
- [ ] Sin Cairo instalado en `/exportar/imagen/` → 501 (no 500)
- [ ] Sin Cairo instalado en `/exportar/pdf/` → PDF generado sin imagen (no error)
