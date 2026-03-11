# Sociograma UTP - Backend API

Sistema de análisis sociométrico para mapear y analizar las relaciones sociales entre estudiantes de la Universidad Tecnológica de Puebla.

**Equipo de Desarrollo:**
- **Raul Suarez** - Backend Developer
- **Esaú** - Project Manager & UX/UI
- **Brandon** - UX/UI Designer

---

## Tecnologías

- Python 3.8+
- Django 5.2.4
- Django REST Framework
- Simple JWT (Autenticación)
- MySQL 8.0+
- django-cors-headers
- openpyxl / pandas

---

## Instalación Rápida

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/sociograma-utp-backend.git
cd sociograma-utp-backend

# Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# Generar SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Crear base de datos
mysql -u root -p
> CREATE DATABASE sociograma_utp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
> source Dump20260107.sql;
> EXIT;

# Ejecutar migraciones (si usas migraciones en lugar del dump)
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver
```

Servidor: `http://127.0.0.1:8000`

---

## Configuración

### Variables de Entorno (.env)

```bash
# Django
SECRET_KEY=tu-secret-key-generada
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# MySQL
DB_NAME=sociograma_utp
DB_USER=root
DB_PASSWORD=tu_password
DB_HOST=127.0.0.1
DB_PORT=3306

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# JWT (opcional)
JWT_ACCESS_TOKEN_LIFETIME=120
JWT_REFRESH_TOKEN_LIFETIME=7
```

---

## Estructura del Proyecto

```
sociograma_project/
├── core/
│   ├── admin/                         # Admin organizado en módulos
│   │   ├── __init__.py               # Exporta todos los admins
│   │   ├── academic.py               # Admins de catálogos académicos
│   │   ├── base.py                   # UserAdmin
│   │   ├── groups.py                 # GrupoAdmin, AlumnoGrupoAdmin
│   │   ├── people.py                 # DocenteAdmin, AlumnoAdmin
│   │   └── surveys.py                # Admins de encuestas y reportes
│   │
│   ├── management/
│   │   └── commands/
│   │       ├── backup_db.py          # Backup de base de datos
│   │       └── crear_admin.py        # Crear usuario administrador
│   │
│   ├── migrations/
│   │   ├── __init__.py
│   │   ├── 0001_initial.py
│   │   ├── 0002_auditoria.py
│   │   ├── 0003_add_crear_usuario_auditoria_choice.py
│   │   └── 0004_rename_fecha_completado_fecha_fin.py
│   │
│   ├── models/                        # Modelos organizados en módulos
│   │   ├── __init__.py               # Exporta todos los modelos
│   │   ├── academic.py               # División, Programa, PlanEstudio, Periodo
│   │   ├── audit.py                  # Auditoría de acciones
│   │   ├── base.py                   # User extendido
│   │   ├── groups.py                 # Grupo, AlumnoGrupo
│   │   ├── people.py                 # Docente, Alumno
│   │   ├── reports.py                # Reporte
│   │   └── surveys.py                # Pregunta, Opcion, Cuestionario, Respuesta
│   │
│   ├── serializers/
│   │   ├── __init__.py
│   │   ├── alumno.py
│   │   ├── auth.py
│   │   ├── catalogos.py
│   │   ├── cuestionario.py
│   │   ├── docente.py
│   │   ├── grupo.py
│   │   ├── import_excel.py
│   │   └── pregunta.py
│   │
│   ├── templates/
│   │   ├── emails/
│   │   │   └── password_reset.html
│   │   └── imgs/
│   │       ├── Logo_Comite.png
│   │       └── Logo_UTP.png
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_admin_permisos.py
│   │   └── test_comite.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── auth_validators.py
│   │   ├── decorators.py
│   │   ├── email.py
│   │   ├── import_excel_helpers.py
│   │   ├── sociogram_renderer.py     # Renderizado del sociograma (PDF, imágenes)
│   │   ├── sync.py
│   │   └── validators.py
│   │
│   ├── views/                         # Views organizadas por rol
│   │   ├── __init__.py
│   │   ├── auth.py                   # Endpoints de autenticación
│   │   │
│   │   ├── academic/                  # Endpoints para dirección académica
│   │   │   ├── __init__.py
│   │   │   ├── academic.py
│   │   │   ├── archivos.py           # Exportación sociograma (CSV, PDF, imagen)
│   │   │   └── cuestionarios.py      # Estadísticas y progreso de grupos
│   │   │
│   │   ├── admin/                     # Endpoints de administración
│   │   │   ├── __init__.py
│   │   │   ├── asignar_tutor.py
│   │   │   ├── catalogos.py          # CRUD catálogos académicos
│   │   │   ├── cuestionarios.py      # CRUD cuestionarios + activar/desactivar
│   │   │   ├── grupos.py             # CRUD grupos
│   │   │   ├── helpers.py
│   │   │   ├── import_alumnos.py
│   │   │   ├── import_csv.py
│   │   │   ├── import_docentes.py
│   │   │   ├── import_excel.py
│   │   │   ├── periodos.py
│   │   │   ├── preguntas.py          # CRUD banco de preguntas (límite 30)
│   │   │   └── usuarios.py           # CRUD usuarios
│   │   │
│   │   ├── comite/                    # Endpoints para tutores (comité)
│   │   │   ├── __init__.py
│   │   │   ├── cuestionarios.py
│   │   │   ├── dashboard.py
│   │   │   └── helpers.py
│   │   │
│   │   └── student/                   # Endpoints para alumnos
│   │       ├── __init__.py
│   │       └── cuestionarios.py      # Responder cuestionario con validaciones
│   │
│   ├── __init__.py
│   ├── apps.py
│   ├── pagination.py
│   ├── permissions.py
│   └── urls.py
│
├── database/
│   └── backups/                       # Backups locales (no en git)
│
├── docs/                              # Documentación por tema/rol
│   ├── admin/
│   ├── academic/
│   ├── comite/
│   └── student/
│
├── logs/
│   └── django.log
│
├── sociograma_project/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── .env
├── .env.example
├── .gitignore
├── manage.py
├── README.md
└── requirements.txt
```

---

## API Endpoints

**Base URL:** `http://127.0.0.1:8000/api`

### Autenticación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/auth/login/` | Login de usuario |
| POST | `/auth/register/` | Registrar alumno |
| POST | `/auth/logout/` | Cerrar sesión |
| POST | `/auth/token/refresh/` | Refrescar access token |
| POST | `/auth/verify-token/` | Verificar token |
| GET | `/auth/me/` | Perfil del usuario autenticado |
| POST | `/auth/change-password/` | Cambiar contraseña |
| POST | `/auth/first-login-change-password/` | Cambiar contraseña en primer inicio |
| POST | `/auth/password-reset/request/` | Solicitar reset de contraseña |
| POST | `/auth/password-reset/validate/` | Validar código de reset |
| POST | `/auth/password-reset/confirm/` | Confirmar nueva contraseña |
| GET | `/periodos/activo/` | Obtener periodo académico activo |

### Administración — Importaciones

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/admin/import-csv/` | Importar Excel completo (8 hojas) |
| POST | `/admin/import-docentes/` | Importar docentes desde Excel |
| POST | `/admin/import-alumnos/` | Importar alumnos desde Excel |
| POST | `/admin/importacion/analizar/` | Analizar archivo antes de importar |
| POST | `/admin/importacion/ejecutar/` | Ejecutar importación confirmada |

### Administración — Gestión

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/admin/asignar-tutor/` | Asignar tutor a un grupo |
| POST | `/admin/remover-tutor/` | Remover tutor de un grupo |

### Administración — Periodos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/admin/periodos/` | Listar periodos académicos |
| POST | `/admin/periodos/crear/` | Crear periodo académico |
| POST | `/admin/periodos/<id>/activar/` | Activar periodo |
| POST | `/admin/periodos/<id>/desactivar/` | Desactivar periodo |
| PUT | `/admin/periodos/<id>/editar/` | Editar periodo |

### Administración — Usuarios

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/admin/usuarios/` | Listar usuarios |
| POST | `/admin/usuarios/crear/` | Crear usuario |
| PUT | `/admin/usuarios/<id>/editar/` | Editar usuario |
| POST | `/admin/usuarios/<id>/activar/` | Activar usuario |
| POST | `/admin/usuarios/<id>/desactivar/` | Desactivar usuario |

### Administración — Grupos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/admin/grupos/crear/` | Crear grupo |
| PUT | `/admin/grupos/<id>/editar-tutor/` | Editar tutor del grupo |

### Administración — Catálogos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/admin/catalogos/divisiones/` | Listar divisiones |
| POST | `/admin/catalogos/divisiones/crear/` | Crear división |
| PUT | `/admin/catalogos/divisiones/<id>/editar/` | Editar división |
| GET | `/admin/catalogos/programas/` | Listar programas |
| POST | `/admin/catalogos/programas/crear/` | Crear programa |
| PUT | `/admin/catalogos/programas/<id>/editar/` | Editar programa |

### Administración — Cuestionarios

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/admin/cuestionarios/` | Listar cuestionarios |
| POST | `/admin/cuestionarios/crear/` | Crear cuestionario |
| GET | `/admin/cuestionarios/<id>/` | Detalle de cuestionario |
| PUT | `/admin/cuestionarios/<id>/actualizar/` | Actualizar cuestionario |
| DELETE | `/admin/cuestionarios/<id>/eliminar/` | Eliminar cuestionario |
| POST | `/admin/cuestionarios/<id>/activar/` | Activar cuestionario |
| POST | `/admin/cuestionarios/<id>/desactivar/` | Desactivar cuestionario |
| POST | `/admin/cuestionarios/<id>/agregar-pregunta/` | Agregar pregunta al cuestionario |
| DELETE | `/admin/cuestionarios/<id>/remover-pregunta/<pid>/` | Remover pregunta del cuestionario |
| POST | `/admin/cuestionarios/<id>/asociar-pregunta/` | Asociar pregunta existente |

### Administración — Banco de Preguntas

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/admin/preguntas/` | Listar preguntas (límite 30) |
| POST | `/admin/preguntas/crear/` | Crear pregunta |
| GET | `/admin/preguntas/<id>/` | Detalle de pregunta |
| PUT | `/admin/preguntas/<id>/actualizar/` | Actualizar pregunta |
| DELETE | `/admin/preguntas/<id>/eliminar/` | Eliminar pregunta |
| PUT | `/admin/preguntas/<id>/editar-copia/` | Editar copia de pregunta |

### Comité — Cuestionarios

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/comite/cuestionarios/` | Listar cuestionarios |
| GET | `/comite/cuestionarios/<id>/` | Detalle de cuestionario |
| GET | `/comite/cuestionarios/<id>/progreso/` | Progreso de respuestas |
| GET | `/comite/cuestionarios/<id>/estadisticas/` | Estadísticas del cuestionario |

### Comité — Dashboard

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/comite/overview/` | Resumen general |
| GET | `/comite/overview/progreso/` | Progreso general de grupos |
| GET | `/comite/overview/alertas/` | Alertas activas |
| GET | `/comite/overview/centralidad/` | Análisis de centralidad |
| GET | `/comite/graphs/` | Datos para gráficas |

### Académico (Tutores) — Grupos y Cuestionarios

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/academic/my-groups/` | Grupos asignados al tutor |
| GET | `/academic/cuestionarios/` | Listar cuestionarios |
| GET | `/academic/cuestionarios/<id>/` | Detalle de cuestionario |
| GET | `/academic/cuestionarios/<id>/progreso/` | Progreso del grupo |
| GET | `/academic/cuestionarios/<id>/estadisticas/` | Estadísticas del grupo |
| GET | `/academic/cuestionarios/<id>/registro/` | Registro de respuestas |
| GET | `/academic/cuestionarios/<id>/clasificacion-pregunta/` | Clasificación por pregunta |

### Académico (Tutores) — Exportación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/academic/archivos/cuestionarios/` | Historial de cuestionarios |
| GET | `/academic/archivos/cuestionarios/<id>/sociograma/` | Datos del sociograma |
| GET | `/academic/archivos/cuestionarios/<id>/exportar/csv/` | Exportar resultados en CSV |
| GET | `/academic/archivos/cuestionarios/<id>/exportar/pdf/` | Exportar reporte en PDF |
| GET | `/academic/archivos/cuestionarios/<id>/exportar/imagen/` | Exportar imagen del sociograma |

### Estudiantes — Cuestionarios

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/student/cuestionarios/disponibles/` | Cuestionarios disponibles |
| GET | `/student/cuestionarios/<id>/` | Detalle del cuestionario |
| GET | `/student/cuestionarios/<id>/preguntas/` | Preguntas del cuestionario |
| POST | `/student/cuestionarios/<id>/iniciar/` | Iniciar cuestionario |
| POST | `/student/cuestionarios/<id>/responder/` | Enviar respuestas |
| GET | `/student/cuestionarios/<id>/mi-progreso/` | Progreso del alumno |

---

## Autenticación JWT

Todos los endpoints (excepto login/register) requieren autenticación.

**Header:**
```
Authorization: Bearer {access_token}
```

**Login:**
```bash
POST /api/auth/login/
{
  "username": "matricula_o_username",
  "password": "password"
}
```

**Response:**
```json
{
  "access": "token...",
  "refresh": "token...",
  "user": {...},
  "alumno": {...}  // o "docente"
}
```

---

## Importación Masiva

**Endpoint:** `POST /api/admin/import-csv/`
**Rol:** Solo ADMIN

**Formato del Excel (8 hojas):**

1. **Divisiones:** `codigo`, `nombre`, `descripcion`
2. **Programas:** `codigo`, `nombre`, `division_codigo`, `duracion_semestres`
3. **Planes:** `codigo`, `nombre`, `programa_codigo`, `anio_inicio`
4. **Periodos:** `codigo`, `nombre`, `fecha_inicio`, `fecha_fin`
5. **Docentes:** `profesor_id`, `nombre_completo`, `email`, `username`, `division_codigo`, `es_tutor`, `especialidad`
6. **Grupos:** `clave`, `grado`, `grupo`, `turno`, `programa_codigo`, `periodo_codigo`, `tutor_profesor_id`
7. **Alumnos:** `matricula`, `nombre_completo`, `email`, `username`, `nss`, `plan_codigo`, `semestre`, `fecha_ingreso`
8. **Inscripciones:** `alumno_matricula`, `grupo_clave`, `fecha_inscripcion`

**Uso:**
```bash
POST /api/admin/import-csv/
Content-Type: multipart/form-data
Authorization: Bearer {token}

Form-data:
  file: [datos.xlsx]
```

**Manejo de Duplicados:**
- Divisiones, Programas, Periodos: Se reutilizan si ya existen (por código)
- Alumnos: Se actualizan si ya existen (por matrícula)
- Inscripciones: Se omiten si ya existen (alumno-grupo único)
- Password por defecto: `utp2024`

---

## Roles y Permisos

| Rol | Descripción | Acceso |
|-----|-------------|--------|
| **ALUMNO** | Estudiante | Auth, Student |
| **DOCENTE** | Tutor de grupo | Auth, Academic |
| **COMITE** | Comité de tutores | Auth, Comite |
| **ADMIN** | Administrador | Auth, Admin, todo lo anterior |

**Decoradores disponibles:**
```python
@require_admin              # Solo is_staff=True
@require_docente            # Solo DOCENTE activo (tutor o no)
@require_tutor              # Solo DOCENTE activo con es_tutor=True
@require_alumno             # Solo ALUMNO activo con inscripción en el periodo actual
@require_comite             # Solo rol COMITE activo
@require_comite_readonly    # Solo COMITE, bloquea métodos de escritura
@require_admin_or_tutor     # ADMIN o DOCENTE con es_tutor=True activo
@require_admin_or_docente   # ADMIN o DOCENTE activo (tutor o no)
@log_api_call               # Loguea método, ruta y status de la respuesta
```

---

## Comandos Útiles

```bash
# Migraciones
python manage.py makemigrations
python manage.py migrate

# Superusuario
python manage.py createsuperuser

# Shell
python manage.py shell

# Servidor
python manage.py runserver

# Tests
python manage.py test
```

---

## Licencia

Proyecto académico - Universidad Tecnológica de Puebla

**Última actualización:** 03/11/2026
