"""Modelos de datos para las explicaciones en lenguaje simple.

Estos modelos son el contrato de salida del explainer: lo que consumen la CLI,
el approval_engine, y eventualmente cualquier UI/reporte. La idea es que quien
lea una ExplicacionHallazgo no necesite entender XCCDF, CIS ni jerga de
compliance para tomar una decisión informada.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExplicacionHallazgo(BaseModel):
    """Traducción en lenguaje simple de un HallazgoRegla.

    `es_generica=True` indica que no hubo match con ninguna categoría conocida
    y se usó el fallback — el consumidor de este modelo (CLI, reportes) debería
    dejar claro visualmente que es una explicación genérica, no específica.
    """

    regla_id: str = Field(..., description="ID original de la regla (trazabilidad al benchmark)")
    categoria: str = Field(..., description="Categoría asignada, ej. 'puertos_abiertos'")
    mensaje_simple: str = Field(..., description="Qué es el hallazgo, en una o dos frases simples")
    por_que_importa: str = Field(..., description="Por qué esto representa un riesgo real")
    que_pasa_si_se_ignora: str = Field(
        ..., description="Consecuencia concreta y plausible de no actuar sobre esto"
    )
    detalle_tecnico: str | None = Field(
        default=None,
        description="Descripción técnica original del benchmark, sin traducir — "
        "se muestra como detalle expandible, no como respuesta principal",
    )
    es_generica: bool = Field(
        default=False,
        description="True si no hubo match de categoría y se usó el mensaje de fallback",
    )
