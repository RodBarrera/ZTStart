"""Tests para ztstart.approval_engine.motor.

Usan un archivo temporal (tmp_path) como repositorio en cada test, para que
no haya estado compartido entre tests ni se toque el filesystem real.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ztstart.approval_engine import motor
from ztstart.approval_engine.errores import (
    ExcepcionNoEncontradaError,
    TransicionInvalidaError,
)
from ztstart.approval_engine.models import EstadoExcepcion
from ztstart.approval_engine.repositorio import RepositorioExcepciones


@pytest.fixture
def repo(tmp_path: Path) -> RepositorioExcepciones:
    return RepositorioExcepciones(ruta=tmp_path / "excepciones.yaml")


def test_solicitar_crea_excepcion_en_estado_pendiente(repo: RepositorioExcepciones) -> None:
    excepcion = motor.solicitar(
        regla_id="regla_ssh_root",
        host="servidor-01",
        categoria="acceso_remoto_ssh",
        motivo_solicitud="Necesitamos acceso temporal para migración",
        repositorio=repo,
    )

    assert excepcion.estado == EstadoExcepcion.PENDIENTE
    assert excepcion.fecha_expiracion is None
    assert excepcion.esta_vigente is False  # pendiente no es lo mismo que vigente


def test_solicitar_persiste_y_se_puede_recuperar_con_listar(repo: RepositorioExcepciones) -> None:
    motor.solicitar("regla_1", "host-a", "cat_x", "motivo", repositorio=repo)
    motor.solicitar("regla_2", "host-b", "cat_y", "otro motivo", repositorio=repo)

    todas = motor.listar(repositorio=repo)

    assert len(todas) == 2


def test_aprobar_asigna_fecha_expiracion_futura(repo: RepositorioExcepciones) -> None:
    excepcion = motor.solicitar("regla_1", "host-a", "cat_x", "motivo", repositorio=repo)

    aprobada = motor.aprobar(
        excepcion.id, aprobador="jorge", dias_vigencia=30, repositorio=repo
    )

    assert aprobada.estado == EstadoExcepcion.APROBADA
    assert aprobada.fecha_expiracion is not None
    assert aprobada.fecha_expiracion > datetime.now()
    assert aprobada.esta_vigente is True


def test_aprobar_con_dias_vigencia_no_positivo_falla(repo: RepositorioExcepciones) -> None:
    excepcion = motor.solicitar("regla_1", "host-a", "cat_x", "motivo", repositorio=repo)

    with pytest.raises(ValueError, match="dias_vigencia"):
        motor.aprobar(excepcion.id, aprobador="jorge", dias_vigencia=0, repositorio=repo)


def test_no_se_puede_aprobar_dos_veces_la_misma_excepcion(repo: RepositorioExcepciones) -> None:
    excepcion = motor.solicitar("regla_1", "host-a", "cat_x", "motivo", repositorio=repo)
    motor.aprobar(excepcion.id, aprobador="jorge", dias_vigencia=10, repositorio=repo)

    with pytest.raises(TransicionInvalidaError):
        motor.aprobar(excepcion.id, aprobador="jorge", dias_vigencia=10, repositorio=repo)


def test_rechazar_requiere_motivo_y_cambia_estado(repo: RepositorioExcepciones) -> None:
    excepcion = motor.solicitar("regla_1", "host-a", "cat_x", "motivo", repositorio=repo)

    rechazada = motor.rechazar(
        excepcion.id, aprobador="jorge", motivo_decision="Riesgo no aceptable", repositorio=repo
    )

    assert rechazada.estado == EstadoExcepcion.RECHAZADA
    assert rechazada.motivo_decision == "Riesgo no aceptable"
    assert rechazada.esta_vigente is False


def test_aprobar_id_inexistente_lanza_error(repo: RepositorioExcepciones) -> None:
    with pytest.raises(ExcepcionNoEncontradaError):
        motor.aprobar("id-que-no-existe", aprobador="jorge", dias_vigencia=10, repositorio=repo)


def test_revisar_expiradas_marca_solo_las_vencidas(repo: RepositorioExcepciones) -> None:
    vigente = motor.solicitar("regla_vigente", "host-a", "cat_x", "motivo", repositorio=repo)
    vencida = motor.solicitar("regla_vencida", "host-a", "cat_x", "motivo", repositorio=repo)

    motor.aprobar(vigente.id, aprobador="jorge", dias_vigencia=30, repositorio=repo)
    motor.aprobar(vencida.id, aprobador="jorge", dias_vigencia=30, repositorio=repo)

    # Forzamos manualmente que "vencida" ya haya expirado, simulando el paso del tiempo.
    todas = repo.cargar()
    for excepcion in todas:
        if excepcion.id == vencida.id:
            excepcion.fecha_expiracion = datetime.now() - timedelta(days=1)
    repo.guardar(todas)

    recien_expiradas = motor.revisar_expiradas(repositorio=repo)

    assert len(recien_expiradas) == 1
    assert recien_expiradas[0].id == vencida.id

    estado_final = motor.listar(repositorio=repo)
    mapa_estados = {e.id: e.estado for e in estado_final}
    assert mapa_estados[vencida.id] == EstadoExcepcion.EXPIRADA
    assert mapa_estados[vigente.id] == EstadoExcepcion.APROBADA


def test_listar_filtra_por_estado(repo: RepositorioExcepciones) -> None:
    pendiente = motor.solicitar("regla_1", "host-a", "cat_x", "motivo", repositorio=repo)
    a_aprobar = motor.solicitar("regla_2", "host-a", "cat_x", "motivo", repositorio=repo)
    motor.aprobar(a_aprobar.id, aprobador="jorge", dias_vigencia=10, repositorio=repo)

    pendientes = motor.listar(estado=EstadoExcepcion.PENDIENTE, repositorio=repo)
    aprobadas = motor.listar(estado=EstadoExcepcion.APROBADA, repositorio=repo)

    assert [e.id for e in pendientes] == [pendiente.id]
    assert [e.id for e in aprobadas] == [a_aprobar.id]
