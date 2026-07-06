"""Persistencia de excepciones en un archivo YAML plano.

Se eligió YAML sobre una base de datos (ver ADR-005 en
docs/architecture/decisiones.md) para que el archivo de excepciones pueda
vivir junto al resto de la configuración de la organización y su historial
de cambios quede auditado por el propio historial de git — quién aprobó qué
y cuándo queda visible en `git blame`, sin infraestructura adicional.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ztstart.approval_engine.models import SolicitudExcepcion

RUTA_POR_DEFECTO = Path("./ztstart-excepciones.yaml")


class RepositorioExcepciones:
    """Carga y guarda la lista completa de excepciones en un archivo YAML.

    Esta clase no contiene lógica de negocio (aprobar, rechazar, expirar) —
    solo sabe leer y escribir. La lógica vive en approval_engine/motor.py.
    """

    def __init__(self, ruta: Path = RUTA_POR_DEFECTO) -> None:
        self.ruta = ruta

    def cargar(self) -> list[SolicitudExcepcion]:
        """Devuelve la lista de excepciones persistidas, o vacía si el archivo no existe."""
        if not self.ruta.exists():
            return []
        contenido = yaml.safe_load(self.ruta.read_text(encoding="utf-8"))
        if not contenido:
            return []
        return [SolicitudExcepcion.model_validate(item) for item in contenido]

    def guardar(self, excepciones: list[SolicitudExcepcion]) -> None:
        """Sobreescribe el archivo completo con la lista dada.

        Nota: esta es una estrategia "last-write-wins" a nivel de archivo
        completo, adecuada para un solo operador local. Si el proyecto crece
        hacia aprobaciones concurrentes de múltiples personas, esto debería
        migrar a un backend con bloqueo o control de versiones más fino.
        """
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        datos = [excepcion.model_dump(mode="json") for excepcion in excepciones]
        self.ruta.write_text(
            yaml.safe_dump(datos, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
