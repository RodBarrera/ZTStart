"""Modelos de datos para los resultados de escaneo.

Estos modelos son el contrato entre el scanner (que parsea el output crudo de
OpenSCAP) y el resto de los módulos (rules_engine, explainer, reports). Ningún
otro módulo debería tener que entender XCCDF/XML directamente — todo pasa por
estas estructuras.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ResultadoRegla(str, Enum):
    """Resultado de evaluar una regla individual de un benchmark (CIS/STIG)."""

    APROBADO = "pass"
    FALLADO = "fail"
    NO_APLICA = "notapplicable"
    NO_VERIFICADO = "notchecked"
    ERROR = "error"
    DESCONOCIDO = "unknown"


class Severidad(str, Enum):
    """Severidad declarada por el benchmark de origen (no es un score propio)."""

    BAJA = "low"
    MEDIA = "medium"
    ALTA = "high"
    DESCONOCIDA = "unknown"


class HallazgoRegla(BaseModel):
    """Un hallazgo individual: el resultado de una regla del benchmark aplicada
    al sistema escaneado.

    `regla_id` conserva el identificador original del benchmark (ej. un OVAL/XCCDF
    rule id) para trazabilidad — así siempre se puede volver a la fuente CIS/STIG.
    """

    regla_id: str = Field(..., description="ID original de la regla en el benchmark (XCCDF)")
    titulo: str = Field(..., description="Título de la regla tal como viene del benchmark")
    resultado: ResultadoRegla
    severidad: Severidad
    descripcion: str | None = Field(
        default=None, description="Descripción técnica original, sin traducir"
    )
    referencia_benchmark: str | None = Field(
        default=None, description="Ej: 'CIS Debian 12 Benchmark v1.0.0 - 1.1.1.1'"
    )


class ResultadoEscaneo(BaseModel):
    """Resultado completo de un escaneo a un sistema."""

    host: str = Field(..., description="Hostname o identificador del sistema escaneado")
    perfil_benchmark: str = Field(..., description="Perfil SCAP usado, ej. 'cis_level1_server'")
    fecha_escaneo: datetime
    hallazgos: list[HallazgoRegla] = Field(default_factory=list)
    puntaje_cumplimiento: float | None = Field(
        default=None, description="Score 0-100 reportado por OpenSCAP, si está disponible"
    )

    @property
    def hallazgos_fallados(self) -> list[HallazgoRegla]:
        """Reglas que fallaron — candidatas a hardening o a excepción."""
        return [h for h in self.hallazgos if h.resultado == ResultadoRegla.FALLADO]

    @property
    def total_fallados(self) -> int:
        return len(self.hallazgos_fallados)
