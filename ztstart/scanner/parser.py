"""Parser de resultados XCCDF (XML) de OpenSCAP hacia los modelos internos.

OpenSCAP produce XML denso y poco amigable (namespaces XCCDF/OVAL anidados).
Este módulo es el único lugar donde se toca ese XML directamente — todo lo
demás en ZTStart trabaja sobre `ResultadoEscaneo` y `HallazgoRegla`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from lxml import etree

from ztstart.scanner.models import (
    HallazgoRegla,
    ResultadoEscaneo,
    ResultadoRegla,
    Severidad,
)

_NS = {
    "xccdf": "http://checklists.nist.gov/xccdf/1.2",
}

_MAPA_RESULTADO = {
    "pass": ResultadoRegla.APROBADO,
    "fail": ResultadoRegla.FALLADO,
    "notapplicable": ResultadoRegla.NO_APLICA,
    "notchecked": ResultadoRegla.NO_VERIFICADO,
    "error": ResultadoRegla.ERROR,
}

_MAPA_SEVERIDAD = {
    "low": Severidad.BAJA,
    "medium": Severidad.MEDIA,
    "high": Severidad.ALTA,
}


def parsear_resultados_xccdf(ruta_xml: Path, host: str, perfil_benchmark: str) -> ResultadoEscaneo:
    """Parsea un archivo de resultados XCCDF hacia un ResultadoEscaneo.

    Args:
        ruta_xml: ruta al archivo de resultados generado por `oscap xccdf eval --results`.
        host: identificador del sistema escaneado (para trazabilidad en el reporte).
        perfil_benchmark: ID del perfil evaluado, tal como se pasó a oscap.

    Nota de implementación: esta es una primera versión funcional pero mínima.
    Casos como CPE platform applicability, multi-check y overrides de severidad
    a nivel de Rule aún no están cubiertos — quedan marcados con TODO abajo y
    son buenos primeros issues para quien quiera contribuir.
    """
    arbol = etree.parse(str(ruta_xml))
    raiz = arbol.getroot()

    hallazgos: list[HallazgoRegla] = []

    for resultado_regla in raiz.findall(".//xccdf:rule-result", namespaces=_NS):
        regla_id = resultado_regla.get("idref", "desconocido")

        elemento_resultado = resultado_regla.find("xccdf:result", namespaces=_NS)
        texto_resultado = elemento_resultado.text if elemento_resultado is not None else "unknown"
        resultado = _MAPA_RESULTADO.get(texto_resultado or "", ResultadoRegla.DESCONOCIDO)

        severidad_attr = resultado_regla.get("severity", "unknown")
        severidad = _MAPA_SEVERIDAD.get(severidad_attr, Severidad.DESCONOCIDA)

        # TODO: el título real de la regla vive en la definición <Rule>, no en <rule-result>.
        # Por ahora usamos el ID como título provisorio; falta cruzar con el benchmark
        # (buscar <xccdf:Rule id="{regla_id}"><xccdf:title>) para el título legible real.
        titulo_provisorio = regla_id.split("_")[-1] if "_" in regla_id else regla_id

        hallazgos.append(
            HallazgoRegla(
                regla_id=regla_id,
                titulo=titulo_provisorio,
                resultado=resultado,
                severidad=severidad,
                descripcion=None,  # TODO: cruzar con la definición de la regla en el benchmark
                referencia_benchmark=perfil_benchmark,
            )
        )

    return ResultadoEscaneo(
        host=host,
        perfil_benchmark=perfil_benchmark,
        fecha_escaneo=datetime.now(),
        hallazgos=hallazgos,
        puntaje_cumplimiento=_calcular_puntaje(hallazgos),
    )


def _calcular_puntaje(hallazgos: list[HallazgoRegla]) -> float | None:
    """Calcula un puntaje simple de cumplimiento (% de reglas aprobadas sobre evaluables).

    Esto es un cálculo propio simplificado, no el <score> oficial que reporta OpenSCAP
    (que usa un método de ponderación distinto). Para el score oficial habría que leer
    el elemento <xccdf:score> del reporte en vez de recalcularlo aquí.
    """
    evaluables = [
        h for h in hallazgos if h.resultado in (ResultadoRegla.APROBADO, ResultadoRegla.FALLADO)
    ]
    if not evaluables:
        return None
    aprobados = sum(1 for h in evaluables if h.resultado == ResultadoRegla.APROBADO)
    return round((aprobados / len(evaluables)) * 100, 2)
