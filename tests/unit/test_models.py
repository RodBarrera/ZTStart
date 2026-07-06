"""Tests para ztstart.scanner.models."""

from datetime import datetime

from ztstart.scanner.models import (
    HallazgoRegla,
    ResultadoEscaneo,
    ResultadoRegla,
    Severidad,
)


def _hallazgo(resultado: ResultadoRegla, severidad: Severidad = Severidad.MEDIA) -> HallazgoRegla:
    return HallazgoRegla(
        regla_id="xccdf_org.ssgproject.content_rule_ejemplo",
        titulo="Regla de ejemplo",
        resultado=resultado,
        severidad=severidad,
    )


def test_hallazgos_fallados_filtra_solo_los_fallados() -> None:
    hallazgos = [
        _hallazgo(ResultadoRegla.APROBADO),
        _hallazgo(ResultadoRegla.FALLADO),
        _hallazgo(ResultadoRegla.NO_APLICA),
        _hallazgo(ResultadoRegla.FALLADO),
    ]
    resultado = ResultadoEscaneo(
        host="test-host",
        perfil_benchmark="cis_level1_server",
        fecha_escaneo=datetime.now(),
        hallazgos=hallazgos,
    )

    assert resultado.total_fallados == 2
    assert all(h.resultado == ResultadoRegla.FALLADO for h in resultado.hallazgos_fallados)


def test_resultado_escaneo_sin_hallazgos_no_falla() -> None:
    resultado = ResultadoEscaneo(
        host="test-host",
        perfil_benchmark="cis_level1_server",
        fecha_escaneo=datetime.now(),
        hallazgos=[],
    )

    assert resultado.total_fallados == 0
    assert resultado.hallazgos_fallados == []
