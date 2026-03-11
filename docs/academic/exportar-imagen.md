# Exportar Sociograma — Imagen PNG y PDF con imagen

## Descripción

Dos endpoints de exportación relacionados con la imagen del sociograma:

- **`/exportar/imagen/`** — descarga directa del sociograma como PNG
- **`/exportar/pdf/`** — PDF con imagen del sociograma en página 1 + tablas de datos en página 2

Ambos replican el renderizado visual del frontend (misma simulación force-directed,
mismos colores, gradientes y flechas).

---

## Endpoints

### PNG

```
GET /api/academic/archivos/cuestionarios/{cuestionario_id}/exportar/imagen/?grupo_id={grupo_id}
```

**Respuesta exitosa:** archivo PNG `1960 × 1400 px` (escala ×2 del viewbox 980×700)

### PDF (con imagen)

```
GET /api/academic/archivos/cuestionarios/{cuestionario_id}/exportar/pdf/?grupo_id={grupo_id}
```

**Respuesta exitosa:** archivo PDF A4 landscape con:
- **Página 1:** encabezado + imagen del sociograma (20cm × ~14.3cm)
- **Página 2+:** tabla de nodos + tabla de conexiones

> Si `cairosvg` no está instalado, el PDF se genera igual pero sin la imagen.

### Parámetros (ambos endpoints)

| Parámetro | Tipo | Descripción |
|---|---|---|
| `cuestionario_id` | path (int) | ID del cuestionario |
| `grupo_id` | query (int) | ID del grupo del tutor |

**Auth:** Bearer Token (tutor)

---

## Archivos involucrados

| Archivo | Rol |
|---|---|
| `core/utils/sociogram_renderer.py` | Simulación de layout + generación SVG |
| `core/views/academic/archivos.py` | `exportar_imagen_view` y `exportar_pdf_view` |
| `core/urls.py` | Rutas registradas |

---

## Dependencia externa requerida

```
cairosvg >= 2.7.0
```

```bash
pip install cairosvg
```

> **Windows:** `cairosvg` necesita la librería Cairo nativa. Si falla con
> `OSError: no library called "cairo-2" was found`, instala primero el
> [GTK3 Runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer)
> y reinicia la terminal.
>
> **Linux/Mac:** `pip install cairosvg` directo, sin pasos extra.

---

## Cómo funciona internamente

### Endpoint PNG

```
Request
  ↓
Validar permisos (tutor del grupo)
  ↓
_calcular_nodos_sociograma()
_calcular_conexiones_sociograma()
  ↓
render_sociogram_svg(nodos, conexiones)
  │
  ├─ _normalize_node_size()          → radio del nodo (18–82 px)
  ├─ _color_from_puntaje()           → color base (verde/rojo/gris)
  ├─ _filter_and_build_graph_edges()
  │     Solo conexiones POSITIVAS
  │     Top 3 por alumno (peso ≥ 33% del total)
  │     Pares A↔B → arista recíproca (doble punta)
  │
  ├─ _build_simulation()
  │     Posicionamiento inicial radial (golden angle)
  │     320 iteraciones: repulsión + resortes + fuerza central
  │     50 pasadas de resolución de colisiones
  │
  └─ Generar SVG string (980×700 px)
       • Fondo #f4f5f6
       • Gradientes radiales: verde / rojo / gris
       • Círculos con número de lista
       • Flechas negras (doble punta = recíproca)
  ↓
cairosvg.svg2png(scale=2)            → PNG 1960×1400 px
  ↓
HttpResponse(content_type='image/png')
```

### Endpoint PDF (imagen incluida)

```
Request
  ↓
Misma validación de permisos
  ↓
_calcular_nodos_sociograma()
_calcular_conexiones_sociograma()
  ↓
[try cairosvg]
  render_sociogram_svg() → PNG bytes en memoria (BytesIO)
  reportlab Image(20cm × 14.3cm)
  PageBreak()            → tablas siempre en página 2
[except ImportError/OSError → omite imagen, PDF se genera igual]
  ↓
Tabla nodos  (página 2)
Tabla conexiones (página 2 o 3 si hay muchas)
  ↓
HttpResponse(content_type='application/pdf')
```

---

## Lógica visual (equivalencias con el frontend)

### Colores de nodos

| Condición | Color | Gradiente |
|---|---|---|
| `impacto_total ≤ 5% del máximo` | Gris | `#7A7F87 → #4A4F56 → #2E3136` |
| `puntos_negativos > puntos_positivos` | Rojo | `#7F2C2A → #5A0D0D → #3A0404` |
| resto | Verde | `#2F8B7E → #0A5B50 → #013D36` |

### Tamaño de nodos

```
radio = clamp(round(18 + (impacto / max_impacto) * 64), 18, 82)
```

### Aristas

- Solo se dibujan conexiones **POSITIVAS**
- Máximo **3 flechas de salida** por alumno
- Umbral mínimo: peso ≥ **33%** del total positivo del alumno origen
- Par recíproco A→B y B→A → **una sola arista con doble punta**
- Color: `#1A1A1A`, grosor: `2px`

### Layout (force-directed determinista)

- Nodo con mayor `(pos - neg) * 0.6 + impacto * 0.4` → centro
- Distribución radial inicial con golden angle (~137.5°)
- 320 iteraciones de física: repulsión (k=14000) + resortes (k=0.025) + gravedad central
- 50 pasadas de resolución de colisiones (gap mínimo 12px)

### Anchos de columna en el PDF

**Tabla nodos** (total ~22.2cm de 26.7cm disponibles):

| N° | Matrícula | Nombre | Clasificación | Pts+ | Pts- | Impacto | Elec.R | Elec.Rz | Completó |
|---|---|---|---|---|---|---|---|---|---|
| 0.8cm | 2.2cm | **8cm** | 2.5cm | 1.2cm | 1.2cm | 1.5cm | 1.7cm | 1.7cm | 1.4cm |

**Tabla conexiones** (total ~22.2cm):

| Origen | Destino | Peso | Tipo | Mutua | Polaridad | % Mutuo |
|---|---|---|---|---|---|---|
| **6.5cm** | **6.5cm** | 1.5cm | 2cm | 1.4cm | 2.5cm | 1.8cm |

---

## Respuestas posibles

### PNG

| HTTP | Cuándo |
|---|---|
| `200 OK` | PNG generado y devuelto |
| `400 Bad Request` | Falta `grupo_id` |
| `403 Forbidden` | Tutor sin acceso al grupo |
| `404 Not Found` | Sin datos del cuestionario para el grupo |
| `501 Not Implemented` | `cairosvg` no instalado o Cairo nativo ausente |

### PDF

| HTTP | Cuándo |
|---|---|
| `200 OK` | PDF generado (con o sin imagen según disponibilidad de Cairo) |
| `400 / 403 / 404` | Mismas condiciones que PNG |
| `501 Not Implemented` | `reportlab` no instalado |

---

## Testing manual con curl

### Obtener token

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "tutor@ejemplo.com", "password": "tu_password"}'
```

### Descargar PNG

```bash
curl -X GET "http://localhost:8000/api/academic/archivos/cuestionarios/1/exportar/imagen/?grupo_id=5" \
  -H "Authorization: Bearer <TOKEN>" \
  --output sociograma.png
```

### Descargar PDF

```bash
curl -X GET "http://localhost:8000/api/academic/archivos/cuestionarios/1/exportar/pdf/?grupo_id=5" \
  -H "Authorization: Bearer <TOKEN>" \
  --output sociograma.pdf
```

### Verificar PNG

```bash
file sociograma.png
# → sociograma.png: PNG image data, 1960 x 1400, 8-bit/color RGBA
```

---

## Testing con Apidog / Postman / Thunder Client

1. **Método:** `GET`
2. **URL:** con el `?grupo_id=` correspondiente
3. **Headers:** solo `Authorization: Bearer <TOKEN>` — no se necesita Content-Type
4. En la respuesta usar **"Save response to file"** → `.png` o `.pdf`

---

## Casos de prueba

### PNG — Caso 1: Éxito básico
**Setup:** tutor con acceso, cuestionario con respuestas
**Expected:** `200`, `image/png`, tamaño > 0 bytes

### PNG — Caso 2: Sin Cairo instalado
**Setup:** Cairo nativo no disponible en el OS
**Expected:** `501`, `{"error": "Librería cairosvg no disponible o Cairo no está instalado..."}`

> Nota: el error se captura como `OSError` (no `ImportError`), por eso
> el endpoint devuelve 501 limpio en vez de 500.

### PNG — Caso 3: Sin grupo_id
**Expected:** `400`, `{"error": "El parámetro grupo_id es requerido"}`

### PNG — Caso 4: Grupo de otro tutor
**Expected:** `403`, `{"error": "No tienes acceso a este grupo"}`

### PNG — Caso 5: Sin datos en el grupo
**Expected:** `404`, `{"error": "No hay datos de este cuestionario para el grupo indicado"}`

### PNG — Caso 6: Sin token
**Expected:** `401 Unauthorized`

### PDF — Caso 7: Con Cairo disponible
**Expected:** PDF de 2+ páginas; página 1 = encabezado + imagen; página 2 = tablas

### PDF — Caso 8: Sin Cairo disponible
**Expected:** PDF de 1+ páginas solo con tablas (sin imagen, sin error)

---

## Notas de rendimiento

- La simulación (320 iteraciones × O(n²) repulsiones) es **síncrona**.
  Para grupos de ≤ 35 alumnos el tiempo es < 1 segundo.
- En el PDF la simulación corre dos veces si se genera también el PNG
  por separado — si ambas se piden en la misma sesión, el resultado es
  idéntico (la simulación es determinista).
- Imagen PNG resultante: **~80–200 KB**.
- PDF con imagen: **~150–350 KB**.
