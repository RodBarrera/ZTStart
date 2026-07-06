"""Wrapper sobre el binario `oscap` (OpenSCAP).

Este módulo es la única parte del código que sabe que OpenSCAP existe y cómo
invocarlo. Si en el futuro cambiamos de motor de escaneo, este es el único
archivo que debería tocarse — todo lo demás consume `ResultadoEscaneo`.

Requiere tener instalado `openscap-scanner` y el paquete `ssg-*` correspondiente
a la distro (ej. `ssg-debian` o `ssg-debderived` en sistemas basados en Debian).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class OpenSCAPNoDisponibleError(RuntimeError):
    """El binario `oscap` no está instalado o no es accesible en el PATH."""


class EscaneoFallidoError(RuntimeError):
    """El proceso `oscap` terminó con un error no esperado (no solo hallazgos fallados)."""


@dataclass
class ParametrosEscaneo:
    """Parámetros necesarios para invocar un escaneo XCCDF con oscap."""

    ruta_datastream: Path
    """Ruta al datastream SCAP, ej. /usr/share/xml/scap/ssg/content/ssg-debian12-ds.xml"""

    perfil: str
    """ID del perfil XCCDF a evaluar.

    Ej: 'xccdf_org.ssgproject.content_profile_cis_level1_server'
    """

    directorio_resultados: Path
    """Directorio donde se escribirán los archivos de resultado (XCCDF results + ARF)"""


def verificar_oscap_instalado() -> None:
    """Lanza OpenSCAPNoDisponibleError si `oscap` no está disponible en el sistema."""
    if shutil.which("oscap") is None:
        raise OpenSCAPNoDisponibleError(
            "No se encontró el binario 'oscap'. Instálalo con: "
            "apt install openscap-scanner ssg-debderived (Debian/Ubuntu)"
        )


def ejecutar_escaneo(parametros: ParametrosEscaneo) -> tuple[Path, Path]:
    """Ejecuta `oscap xccdf eval` y devuelve las rutas a los archivos de resultado.

    Devuelve una tupla (ruta_xccdf_results, ruta_arf_results).

    Nota: oscap devuelve código de salida 2 cuando el escaneo corrió bien pero
    hay reglas falladas — eso NO es un error de ejecución, es el resultado
    esperado. Solo tratamos como error los códigos != 0 y != 2.
    """
    verificar_oscap_instalado()
    parametros.directorio_resultados.mkdir(parents=True, exist_ok=True)

    ruta_xccdf_results = parametros.directorio_resultados / "resultados-xccdf.xml"
    ruta_arf_results = parametros.directorio_resultados / "resultados-arf.xml"

    comando = [
        "oscap",
        "xccdf",
        "eval",
        "--profile",
        parametros.perfil,
        "--results",
        str(ruta_xccdf_results),
        "--results-arf",
        str(ruta_arf_results),
        str(parametros.ruta_datastream),
    ]

    proceso = subprocess.run(  # noqa: S603 — comando construido internamente, sin input de usuario en shell
        comando,
        capture_output=True,
        text=True,
        check=False,
    )

    # 0 = todo aprobado, 2 = escaneo ok pero con reglas falladas. Ambos son éxitos de ejecución.
    if proceso.returncode not in (0, 2):
        raise EscaneoFallidoError(
            f"oscap terminó con código {proceso.returncode}.\n"
            f"stdout: {proceso.stdout}\nstderr: {proceso.stderr}"
        )

    return ruta_xccdf_results, ruta_arf_results
