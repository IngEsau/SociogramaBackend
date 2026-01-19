# 🎓 Sociograma UTP - Backend API

Sistema de análisis sociométrico para mapear y analizar las relaciones sociales entre estudiantes de la Universidad Tecnológica de Puebla.

**Equipo de Desarrollo:**
- **Raul Suarez** - Backend Developer
- **Esaú** - Project Manager & UX/UI
- **Gabriel** - Frontend Developer & QA
- **Brandon** - UX/UI Designer

---

## 🚀 Tecnologías

- Python 3.8+
- Django 5.2.4
- Django REST Framework
- Simple JWT (Autenticación)
- MySQL 8.0+
- django-cors-headers
- openpyxl / pandas

---

## 📦 Instalación Rápida

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

## ⚙️ Configuración

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

## 📁 Estructura del Proyecto

```
sociograma_project/
├── core/
│   ├── serializers/
│   │   ├── alumno.py
│   │   ├── auth.py
│   │   ├── catalogos.py
│   │   ├── docente.py
│   │   ├── grupo.py
│   │   ├── pregunta.py
│   │   └── __init__.py
│   ├── utils/
│   │   ├── auth.py
│   │   ├── decorators.py
│   │   ├── validators.py
│   │   └── __init__.py
│   ├── views/
│   │   ├── academic.py
│   │   ├── admin.py
│   │   ├── auth.py
│   │   └── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── pagination.py
│   ├── permissions.py
│   └── urls.py
├── logs/
│   └── django.log
├── sociograma_project/
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── .env
├── .gitignore
├── datos.xlsx
├── import_excel.py
├── manage.py
├── README.md
└── requirements.txt
```

---

## 🔌 API Endpoints

**Base URL:** `http://127.0.0.1:8000/api`

### 🔐 Autenticación

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| POST | `/auth/login/` | Login de usuario | No |
| POST | `/auth/register/` | Registrar alumno | No |
| POST | `/auth/logout/` | Cerrar sesión | Sí |
| POST | `/auth/token/refresh/` | Refrescar access token | No |
| POST | `/auth/verify-token/` | Verificar token | No |
| GET | `/auth/me/` | Perfil del usuario | Sí |
| POST | `/auth/change-password/` | Cambiar contraseña | Sí |

### 👨‍💼 Administración

| Método | Endpoint | Descripción | Rol |
|--------|----------|-------------|-----|
| POST | `/admin/import-csv/` | Importar Excel/CSV masivo | ADMIN |

### 🎓 Académico

| Método | Endpoint | Descripción | Rol |
|--------|----------|-------------|-----|
| GET | `/academic/my-groups/` | Grupos del tutor | DOCENTE (tutor) |

---

## 🔑 Autenticación JWT

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

## 📤 Importación Masiva

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

## 🔒 Roles y Permisos

| Rol | Descripción | Endpoints |
|-----|-------------|-----------|
| **ALUMNO** | Estudiante | Auth |
| **DOCENTE** | Profesor/Tutor | Auth, My Groups |
| **ADMIN** | Administrador | Auth, Import CSV |

**Decoradores disponibles:**
```python
@require_admin          # Solo ADMIN
@require_docente        # Solo DOCENTE
@require_tutor          # Solo DOCENTE con es_tutor=True
@require_alumno         # Solo ALUMNO
@require_role(['ADMIN', 'DOCENTE'])  # Múltiples roles
```

---

## 🧪 Testing

### Credenciales de Prueba

```bash
# Admin
Username: admin
Password: admin123

# Docente (Tutor)
Username: DOC001
Password: utp2024

# Alumno
Username: 2022030001
Password: utp2024
```

### Postman Setup

**Variables:**
```
base_url: http://127.0.0.1:8000/api
access_token: (auto-llenado)
refresh_token: (auto-llenado)
```

**Pre-request Script:**
```javascript
pm.request.headers.add({
    key: 'Authorization',
    value: 'Bearer ' + pm.environment.get('access_token')
});
```

---

## 🚀 Deployment

```python
# settings.py (producción)
DEBUG = False
ALLOWED_HOSTS = ['tu-dominio.com']
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

```bash
# Colectar estáticos
python manage.py collectstatic

# Gunicorn
pip install gunicorn
gunicorn sociograma_project.wsgi:application --bind 0.0.0.0:8000
```

---

## 🐛 Troubleshooting

**Error: "Access denied for user"**
```bash
# Verificar .env
DB_PASSWORD=tu_password_real
```

**Error: Token inválido**
```bash
POST /api/auth/token/refresh/
Body: {"refresh": "tu_refresh_token"}
```

**Error: No module 'mysqlclient'**
```bash
pip install mysqlclient
# Windows: pip install pymysql
```

---

## 📝 Comandos Útiles

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

## 📄 Licencia

Proyecto académico - Universidad Tecnológica de Puebla

**Última actualización:** 01/19/2026