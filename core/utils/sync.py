# core/utils/sync.py
"""
Utilidades de sincronización de estado entre tablas.
"""
from django.db import connection


def sincronizar_is_active_alumnos():
    """
    Sincroniza is_active de usuarios ALUMNO según su inscripción activa.

    Regla:
      - is_active = 1  →  tiene al menos una inscripción activa en un grupo
                          activo de un periodo activo.
      - is_active = 0  →  no tiene ninguna inscripción activa.

    Solo afecta usuarios con rol = 'ALUMNO'.
    No toca DOCENTE, ADMIN ni COMITE.

    Returns:
        tuple: (activados, desactivados) — filas afectadas en cada operación.
    """
    with connection.cursor() as cursor:

        # 1. Activar alumnos que SÍ tienen inscripción activa en periodo activo
        cursor.execute("""
            UPDATE auth_user u
            INNER JOIN alumnos a ON a.user_id = u.id
            SET u.is_active = 1
            WHERE u.rol = 'ALUMNO'
              AND u.is_active = 0
              AND EXISTS (
                  SELECT 1
                  FROM alumno_grupo ag
                  INNER JOIN grupos g  ON ag.grupo_id  = g.id  AND g.activo  = 1
                  INNER JOIN periodos p ON g.periodo_id = p.id  AND p.activo  = 1
                  WHERE ag.alumno_id = a.id
                    AND ag.activo = 1
              )
        """)
        activados = cursor.rowcount

        # 2. Desactivar alumnos que NO tienen inscripción activa en ningún periodo activo
        cursor.execute("""
            UPDATE auth_user u
            INNER JOIN alumnos a ON a.user_id = u.id
            SET u.is_active = 0
            WHERE u.rol = 'ALUMNO'
              AND u.is_active = 1
              AND NOT EXISTS (
                  SELECT 1
                  FROM alumno_grupo ag
                  INNER JOIN grupos g  ON ag.grupo_id  = g.id  AND g.activo  = 1
                  INNER JOIN periodos p ON g.periodo_id = p.id  AND p.activo  = 1
                  WHERE ag.alumno_id = a.id
                    AND ag.activo = 1
              )
        """)
        desactivados = cursor.rowcount

    return activados, desactivados
