"""Modelos de datos del motor de aprobación de excepciones.

Una excepción representa la decisión de permitir algo que el baseline
deny-by-default bloquearía por defecto. Ninguna excepción nace aprobada:
siempre pasa primero por PENDIENTE, y toda aprobación lleva una fecha de
expiración — no existen excepciones permanentes sin revisión periódica
(ver ADR-003 y la filosofía de diseño en el README).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EstadoExcepcion(str, Enum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    EXPIRADA = "expirada"


class SolicitudExcepcion(BaseModel):
    """Una excepción solicitada, con su historial de decisión.

    `regla_id` conecta esta excepción con el hallazgo original del scanner
    (HallazgoRegla.regla_id) — así siempre se puede rastrear qué control
    específico del benchmark se decidió no aplicar, y por qué.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regla_id: str = Field(..., description="ID de la regla del benchmark que se quiere exceptuar")
    host: str = Field(..., description="Sistema al que aplica esta excepción")
    categoria: str = Field(
        ..., description="Categoría del explainer asociada, ej. 'acceso_remoto_ssh'"
    )
    motivo_solicitud: str = Field(
        ..., description="Por qué la organización necesita esta excepción"
    )
    estado: EstadoExcepcion = EstadoExcepcion.PENDIENTE

    fecha_solicitud: datetime = Field(default_factory=datetime.now)
    solicitante: str | None = Field(default=None, description="Quién pidió la excepción")

    aprobador: str | None = Field(
        default=None, description="Quién tomó la decisión (aprobar/rechazar)"
    )
    fecha_decision: datetime | None = None
    motivo_decision: str | None = Field(
        default=None, description="Justificación de por qué se aprobó o rechazó"
    )
    fecha_expiracion: datetime | None = Field(
        default=None,
        description="Fecha límite de validez. Obligatoria si estado == APROBADA — "
        "ninguna excepción queda vigente sin fecha de revisión.",
    )

    @property
    def esta_vigente(self) -> bool:
        """True si la excepción está aprobada y aún no pasó su fecha de expiración."""
        if self.estado != EstadoExcepcion.APROBADA or self.fecha_expiracion is None:
            return False
        return datetime.now() < self.fecha_expiracion
