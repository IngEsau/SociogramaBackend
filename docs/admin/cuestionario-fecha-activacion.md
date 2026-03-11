# Cuestionario: Fecha y Hora de Activación

## Estado

**Ya implementado en el backend.** No requiere cambios.

---

## Cómo funciona en el backend

El modelo `Cuestionario` tiene dos campos de fecha/hora que controlan su ventana de aplicación:

| Campo | Tipo | Descripción |
|---|---|---|
| `fecha_inicio` | `DateTimeField` | Fecha y hora desde la que el cuestionario está disponible |
| `fecha_fin` | `DateTimeField` | Fecha y hora en que deja de estar disponible |
| `activo` | `BooleanField` | Flag manual de activación (separado de las fechas) |
| `esta_activo` | property (read-only) | `true` solo si `activo=true` AND `fecha_inicio <= ahora <= fecha_fin` |

### Diferencia entre `activo` y `esta_activo`

- **`activo`**: control manual del admin (encender/apagar el cuestionario).
- **`esta_activo`**: estado real calculado en tiempo real. Un cuestionario puede tener `activo=true` pero `esta_activo=false` si aún no llega la `fecha_inicio` o ya pasó la `fecha_fin`.

> Los alumnos solo ven cuestionarios donde `esta_activo = true`.

---

## Endpoints disponibles

### 1. Crear cuestionario con fechas

```
POST /api/admin/cuestionarios/crear/
```

**Body:**
```json
{
  "titulo": "Cuestionario Sociométrico Feb 2026",
  "descripcion": "Descripción opcional",
  "periodo": 1,
  "fecha_inicio": "2026-02-15T08:00:00Z",
  "fecha_fin": "2026-02-20T23:59:59Z",
  "activo": false,
  "preguntas_ids": [1, 2, 3]
}
```

> Las fechas deben enviarse en formato **ISO 8601 UTC** (`YYYY-MM-DDTHH:MM:SSZ`).

**Validaciones del backend:**
- `fecha_fin` debe ser posterior a `fecha_inicio` (error 400 si no se cumple).
- El periodo debe estar activo.
- Debe incluir al menos una pregunta.

---

### 2. Actualizar fechas de un cuestionario existente

```
PUT /api/admin/cuestionarios/{id}/actualizar/
```

**Body (todos los campos son opcionales):**
```json
{
  "fecha_inicio": "2026-03-01T09:00:00Z",
  "fecha_fin": "2026-03-10T18:00:00Z"
}
```

Se puede enviar solo uno de los dos campos. El backend valida que el rango resultante siga siendo válido.

---

### 3. Activar / desactivar manualmente

```
POST /api/admin/cuestionarios/{id}/activar/
POST /api/admin/cuestionarios/{id}/desactivar/
```

Estos endpoints controlan el flag `activo`. Al activar, el backend:
1. Desactiva automáticamente otros cuestionarios del mismo periodo.
2. Crea estados `PENDIENTE` para todos los alumnos activos del periodo.

---

### 4. Respuesta típica de un cuestionario

```json
{
  "id": 5,
  "titulo": "Cuestionario Sociométrico Feb 2026",
  "periodo": 1,
  "periodo_codigo": "2026-1",
  "fecha_inicio": "2026-02-15T08:00:00Z",
  "fecha_fin": "2026-02-20T23:59:59Z",
  "activo": true,
  "esta_activo": true,
  "total_preguntas": 3,
  "total_respuestas": 0,
  "total_grupos": 12,
  "creado_en": "2026-02-10T10:30:00Z"
}
```

---

## Guía de implementación para el frontend

### Flujo recomendado

```
1. Admin configura título, periodo, fechas y preguntas
        ↓
2. POST /crear/ → cuestionario creado con activo=false (opcional)
        ↓
3. Cuando quiera habilitarlo: POST /{id}/activar/
        ↓
4. El cuestionario aparece a los alumnos solo cuando
   fecha_inicio <= ahora <= fecha_fin  AND  activo=true
```

---

### Componente de selección de fecha/hora

El campo que el admin debe llenar necesita capturar **fecha + hora + zona horaria**.

**Recomendación:** usar un `datetime-local` input o un date-time picker, y enviar siempre en UTC.

```javascript
// Ejemplo: convertir fecha local del usuario a UTC antes de enviar
const fechaLocal = new Date(inputValue); // valor del date-time picker
const fechaUTC = fechaLocal.toISOString(); // "2026-02-15T14:00:00.000Z"
```

---

### Ejemplo de llamada al crear

```javascript
const response = await fetch('/api/admin/cuestionarios/crear/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    titulo: 'Cuestionario Feb 2026',
    descripcion: '',
    periodo: 1,
    fecha_inicio: '2026-02-15T08:00:00Z',
    fecha_fin: '2026-02-20T23:59:59Z',
    activo: false,
    preguntas_ids: [1, 2, 3]
  })
});
```

---

### Ejemplo de actualizar solo las fechas

```javascript
const response = await fetch(`/api/admin/cuestionarios/${id}/actualizar/`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    fecha_inicio: '2026-03-01T09:00:00Z',
    fecha_fin: '2026-03-10T18:00:00Z'
  })
});
```

---

### Mostrar estado en la UI

Usar `esta_activo` (no `activo`) para mostrar si el cuestionario está realmente disponible para los alumnos:

```javascript
// Lógica sugerida para el badge de estado
function getEstado(cuestionario) {
  const ahora = new Date();
  const inicio = new Date(cuestionario.fecha_inicio);
  const fin = new Date(cuestionario.fecha_fin);

  if (!cuestionario.activo) return 'Inactivo';
  if (ahora < inicio) return 'Programado';   // activo=true pero aún no empieza
  if (ahora > fin) return 'Finalizado';       // activo=true pero ya terminó
  return 'En curso';                          // esta_activo=true
}
```

| `activo` | `esta_activo` | Estado sugerido en UI |
|---|---|---|
| `false` | `false` | Inactivo |
| `true` | `false` | Programado / Finalizado |
| `true` | `true` | En curso ✅ |

---

### Errores posibles

| Código | Mensaje | Causa |
|---|---|---|
| 400 | `La fecha de fin debe ser posterior a la fecha de inicio` | `fecha_fin <= fecha_inicio` |
| 400 | `El periodo seleccionado no está activo` | Periodo inactivo |
| 400 | `No se puede activar un cuestionario sin preguntas` | Cero preguntas asociadas |
