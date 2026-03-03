# core/tests/test_admin_permisos.py
"""
Tests de permisos admin para los nuevos endpoints CRUD.
Verifica que:
  - Usuarios no autenticados reciben 401
  - Usuarios no admin reciben 403
  - Usuarios admin acceden correctamente
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.models import User, Division, Programa, Periodo, Docente, Grupo


class BaseAdminTestCase(TestCase):
    """Setup compartido: crea admin, alumno y cliente autenticado."""

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            username='admin_test',
            password='admin1234',
            rol='ADMIN',
            is_staff=True,
            is_active=True,
        )
        self.alumno_user = User.objects.create_user(
            username='alumno_test',
            password='alumno1234',
            rol='ALUMNO',
            is_staff=False,
            is_active=True,
        )

    def auth_admin(self):
        self.client.force_authenticate(user=self.admin)

    def auth_alumno(self):
        self.client.force_authenticate(user=self.alumno_user)

    def no_auth(self):
        self.client.force_authenticate(user=None)


# =============================================================================
# USUARIOS
# =============================================================================

class ListarUsuariosPermisosTest(BaseAdminTestCase):

    def test_sin_autenticar_retorna_401(self):
        self.no_auth()
        r = self.client.get(reverse('core:listar_usuarios'))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_admin_retorna_403(self):
        self.auth_alumno()
        r = self.client.get(reverse('core:listar_usuarios'))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_retorna_200(self):
        self.auth_admin()
        r = self.client.get(reverse('core:listar_usuarios'))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('usuarios', r.data)


class EditarUsuarioPermisosTest(BaseAdminTestCase):

    def test_sin_autenticar_retorna_401(self):
        self.no_auth()
        r = self.client.patch(reverse('core:editar_usuario', args=[self.alumno_user.id]), {})
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_admin_retorna_403(self):
        self.auth_alumno()
        r = self.client.patch(reverse('core:editar_usuario', args=[self.alumno_user.id]), {})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_puede_editar(self):
        self.auth_admin()
        r = self.client.patch(
            reverse('core:editar_usuario', args=[self.alumno_user.id]),
            {'nombre_completo': 'Nuevo Nombre'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['success'])


class ActivarDesactivarUsuarioPermisosTest(BaseAdminTestCase):

    def test_sin_autenticar_activar_retorna_401(self):
        self.no_auth()
        r = self.client.post(reverse('core:activar_usuario', args=[self.alumno_user.id]))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_admin_activar_retorna_403(self):
        self.auth_alumno()
        r = self.client.post(reverse('core:activar_usuario', args=[self.alumno_user.id]))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_puede_desactivar_y_reactivar(self):
        self.auth_admin()
        # Desactivar
        r = self.client.post(reverse('core:desactivar_usuario', args=[self.alumno_user.id]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data['usuario']['is_active'])
        # Reactivar
        r = self.client.post(reverse('core:activar_usuario', args=[self.alumno_user.id]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['usuario']['is_active'])

    def test_admin_no_puede_desactivar_su_propia_cuenta(self):
        self.auth_admin()
        r = self.client.post(reverse('core:desactivar_usuario', args=[self.admin.id]))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


# =============================================================================
# GRUPOS
# =============================================================================

class CrearGrupoPermisosTest(BaseAdminTestCase):

    def setUp(self):
        super().setUp()
        self.division = Division.objects.create(codigo='TI', nombre='Tecnologías de la Información', activa=True)
        self.programa = Programa.objects.create(
            codigo='ISC', nombre='Ingeniería en Sistemas', division=self.division,
            duracion_semestres=9, activo=True,
        )
        self.periodo = Periodo.objects.create(
            codigo='2026-1', nombre='Enero - Abril 2026', activo=True,
        )

    def test_sin_autenticar_retorna_401(self):
        self.no_auth()
        r = self.client.post(reverse('core:crear_grupo'), {})
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_admin_retorna_403(self):
        self.auth_alumno()
        r = self.client.post(reverse('core:crear_grupo'), {})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_puede_crear_grupo(self):
        self.auth_admin()
        r = self.client.post(reverse('core:crear_grupo'), {
            'periodo_id': self.periodo.id,
            'programa_id': self.programa.id,
            'grado': '3',
            'grupo': 'A',
            'turno': 'Matutino',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertTrue(r.data['success'])


class EditarTutorGrupoPermisosTest(BaseAdminTestCase):

    def setUp(self):
        super().setUp()
        division = Division.objects.create(codigo='TI2', nombre='TI', activa=True)
        programa = Programa.objects.create(
            codigo='ISC2', nombre='ISC', division=division, duracion_semestres=9, activo=True,
        )
        periodo = Periodo.objects.create(codigo='2026-2', nombre='Mayo 2026', activo=False)
        self.grupo = Grupo.objects.create(
            clave='ISC2-3-A', periodo=periodo, programa=programa,
            grado='3', grupo='A', turno='Matutino', activo=True,
        )

    def test_sin_autenticar_retorna_401(self):
        self.no_auth()
        r = self.client.patch(reverse('core:editar_tutor_grupo', args=[self.grupo.id]), {})
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_admin_retorna_403(self):
        self.auth_alumno()
        r = self.client.patch(reverse('core:editar_tutor_grupo', args=[self.grupo.id]), {})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_puede_quitar_tutor(self):
        self.auth_admin()
        r = self.client.patch(
            reverse('core:editar_tutor_grupo', args=[self.grupo.id]),
            {'tutor_id': None},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['success'])


# =============================================================================
# CATÁLOGOS - DIVISIONES
# =============================================================================

class DivisionesPermisosTest(BaseAdminTestCase):

    def setUp(self):
        super().setUp()
        self.division = Division.objects.create(codigo='ADM', nombre='Administración', activa=True)

    def test_listar_sin_autenticar_retorna_401(self):
        self.no_auth()
        r = self.client.get(reverse('core:listar_divisiones'))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_listar_no_admin_retorna_403(self):
        self.auth_alumno()
        r = self.client.get(reverse('core:listar_divisiones'))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_listar_admin_retorna_200(self):
        self.auth_admin()
        r = self.client.get(reverse('core:listar_divisiones'))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('divisiones', r.data)

    def test_crear_admin_retorna_201(self):
        self.auth_admin()
        r = self.client.post(reverse('core:crear_division'), {
            'codigo': 'ING', 'nombre': 'Ingeniería',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_editar_no_admin_retorna_403(self):
        self.auth_alumno()
        r = self.client.patch(
            reverse('core:editar_division', args=[self.division.id]),
            {'nombre': 'Nuevo'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_editar_admin_retorna_200(self):
        self.auth_admin()
        r = self.client.patch(
            reverse('core:editar_division', args=[self.division.id]),
            {'nombre': 'Administración y Negocios'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['success'])


# =============================================================================
# CATÁLOGOS - PROGRAMAS
# =============================================================================

class ProgramasPermisosTest(BaseAdminTestCase):

    def setUp(self):
        super().setUp()
        self.division = Division.objects.create(codigo='TI3', nombre='TI Test', activa=True)
        self.programa = Programa.objects.create(
            codigo='PROG1', nombre='Programa Test', division=self.division,
            duracion_semestres=9, activo=True,
        )

    def test_listar_sin_autenticar_retorna_401(self):
        self.no_auth()
        r = self.client.get(reverse('core:listar_programas'))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_listar_no_admin_retorna_403(self):
        self.auth_alumno()
        r = self.client.get(reverse('core:listar_programas'))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_listar_admin_retorna_200(self):
        self.auth_admin()
        r = self.client.get(reverse('core:listar_programas'))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('programas', r.data)

    def test_crear_admin_retorna_201(self):
        self.auth_admin()
        r = self.client.post(reverse('core:crear_programa'), {
            'codigo': 'PROG2',
            'nombre': 'Nuevo Programa',
            'division_id': self.division.id,
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_editar_admin_retorna_200(self):
        self.auth_admin()
        r = self.client.patch(
            reverse('core:editar_programa', args=[self.programa.id]),
            {'nombre': 'Programa Editado'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['success'])


# =============================================================================
# CATÁLOGOS - PERIODOS (editar)
# =============================================================================

class EditarPeriodoPermisosTest(BaseAdminTestCase):

    def setUp(self):
        super().setUp()
        self.periodo = Periodo.objects.create(
            codigo='2025-3', nombre='Septiembre - Diciembre 2025', activo=False,
        )

    def test_sin_autenticar_retorna_401(self):
        self.no_auth()
        r = self.client.patch(reverse('core:editar_periodo', args=[self.periodo.id]), {})
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_admin_retorna_403(self):
        self.auth_alumno()
        r = self.client.patch(reverse('core:editar_periodo', args=[self.periodo.id]), {})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_puede_editar(self):
        self.auth_admin()
        r = self.client.patch(
            reverse('core:editar_periodo', args=[self.periodo.id]),
            {'nombre': 'Sep - Dic 2025'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['success'])
