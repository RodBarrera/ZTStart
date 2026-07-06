"""Carga de perfiles de configuración desde ztstart/config/perfiles/*.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from ztstart.rules_engine.models import Perfil

_DIRECTORIO_PERFILES = Path(__file__).resolve().parent.parent / "config" / "perfiles"


class PerfilNoEncontradoError(FileNotFoundError):
    """No existe un archivo de perfil con el nombre dado."""


def cargar_perfil_desde_ruta(ruta: Path) -> Perfil:
    """Carga un perfil desde una ruta de archivo YAML explícita."""
    if not ruta.exists():
        raise PerfilNoEncontradoError(f"No existe el archivo de perfil: {ruta}")
    contenido = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return Perfil.model_validate(contenido)


def cargar_perfil(nombre: str) -> Perfil:
    """Carga un perfil por nombre, buscándolo en ztstart/config/perfiles/{nombre}.yaml.

    El nombre puede darse con o sin guiones (ej. 'pyme-basico' o 'pyme_basico') —
    se normaliza a guion bajo para coincidir con la convención de nombres de
    archivo del proyecto.
    """
    nombre_archivo = nombre.replace("-", "_")
    ruta = _DIRECTORIO_PERFILES / f"{nombre_archivo}.yaml"
    return cargar_perfil_desde_ruta(ruta)
