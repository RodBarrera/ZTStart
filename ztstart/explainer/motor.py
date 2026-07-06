"""Motor de clasificación y traducción de hallazgos a lenguaje simple.

El matching es intencionalmente simple (keywords sobre texto en minúsculas),
no un clasificador de ML. Para el propósito de este módulo —agrupar patrones
recurrentes de controles CIS/STIG en categorías legibles— esto es suficiente,
auditable, y no depende de ningún servicio externo. Ver docs/architecture para
la discusión de por qué se eligió este enfoque en vez de un LLM.
"""

from __future__ import annotations

from ztstart.explainer.categorias import CATEGORIAS, PlantillaCategoria
from ztstart.explainer.models import ExplicacionHallazgo
from ztstart.scanner.models import HallazgoRegla

_MENSAJE_GENERICO = (
    "Esta regla de seguridad falló, pero todavía no tenemos una traducción "
    "específica para ella en lenguaje simple."
)
_POR_QUE_IMPORTA_GENERICO = (
    "Aun sin una explicación detallada, un control de seguridad fallado "
    "generalmente indica una configuración que se aparta de las prácticas "
    "recomendadas para este tipo de sistema."
)
_QUE_PASA_GENERICO = (
    "Te recomendamos revisar la descripción técnica original (incluida abajo) "
    "con quien administre la seguridad del sistema antes de decidir si aplicar "
    "una excepción."
)


def _texto_para_matching(hallazgo: HallazgoRegla) -> str:
    """Concatena los campos de texto del hallazgo en minúsculas para el matching."""
    partes = [hallazgo.regla_id, hallazgo.titulo, hallazgo.descripcion or ""]
    return " ".join(partes).lower()


def clasificar(hallazgo: HallazgoRegla) -> PlantillaCategoria | None:
    """Devuelve la categoría que matchea el hallazgo, o None si no hay match.

    Estrategia: la primera categoría cuyo conjunto de palabras clave tenga al
    menos una coincidencia en el texto del hallazgo. El orden de definición en
    categorias.py importa si un hallazgo pudiera matchear más de una — en la
    práctica, con las categorías actuales los solapamientos son mínimos.
    """
    texto = _texto_para_matching(hallazgo)
    for plantilla in CATEGORIAS.values():
        if any(palabra_clave in texto for palabra_clave in plantilla.palabras_clave):
            return plantilla
    return None


def explicar(hallazgo: HallazgoRegla) -> ExplicacionHallazgo:
    """Traduce un HallazgoRegla a una ExplicacionHallazgo en lenguaje simple.

    Si no hay categoría que matchee, devuelve el mensaje genérico de fallback
    con `es_generica=True`, incluyendo siempre la descripción técnica original
    como detalle expandible — nunca se deja al usuario sin ninguna información.
    """
    plantilla = clasificar(hallazgo)

    if plantilla is None:
        return ExplicacionHallazgo(
            regla_id=hallazgo.regla_id,
            categoria="sin_categoria",
            mensaje_simple=_MENSAJE_GENERICO,
            por_que_importa=_POR_QUE_IMPORTA_GENERICO,
            que_pasa_si_se_ignora=_QUE_PASA_GENERICO,
            detalle_tecnico=hallazgo.descripcion or hallazgo.titulo,
            es_generica=True,
        )

    return ExplicacionHallazgo(
        regla_id=hallazgo.regla_id,
        categoria=plantilla.id,
        mensaje_simple=plantilla.mensaje_simple,
        por_que_importa=plantilla.por_que_importa,
        que_pasa_si_se_ignora=plantilla.que_pasa_si_se_ignora,
        detalle_tecnico=hallazgo.descripcion,
        es_generica=False,
    )


def explicar_todos(hallazgos: list[HallazgoRegla]) -> list[ExplicacionHallazgo]:
    """Traduce una lista de hallazgos, preservando el orden de entrada."""
    return [explicar(h) for h in hallazgos]
