"""Tests para ztstart.rules_engine.shadow."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ztstart.rules_engine.models import Perfil
from ztstart.rules_engine.shadow import (
    EstadoShadow,
    RepositorioEstadoShadow,
    evaluar_modo_shadow,
)


def _perfil(modo_inicial: str = "shadow", duracion_dias: int = 14) -> Perfil:
    return Perfil(
        nombre="pyme-basico",
        descripcion="Perfil de prueba",
        benchmark_base="cis_level1_server",
        modo_inicial=modo_inicial,
        duracion_modo_shadow_dias=duracion_dias,
    )


def test_estado_shadow_vigente_dentro_del_periodo() -> None:
    estado = EstadoShadow(
        perfil="pyme-basico",
        host="srv1",
        fecha_inicio=datetime.now() - timedelta(days=5),
        duracion_dias=14,
    )

    assert estado.vigente is True
    # dias_restantes trunca hacia abajo (timedelta.days), así que con
    # fecha_inicio hace "5 días" el valor real puede ser 8 u 9 según el
    # instante exacto en que corre el test — no debe ser exacto al segundo.
    assert estado.dias_restantes in (8, 9)


def test_estado_shadow_vencido_fuera_del_periodo() -> None:
    estado = EstadoShadow(
        perfil="pyme-basico",
        host="srv1",
        fecha_inicio=datetime.now() - timedelta(days=20),
        duracion_dias=14,
    )

    assert estado.vigente is False
    assert estado.dias_restantes == 0


def test_evaluar_modo_shadow_perfil_sin_shadow_devuelve_none(tmp_path: Path) -> None:
    perfil = _perfil(modo_inicial="enforce")
    repo = RepositorioEstadoShadow(ruta=tmp_path / "shadow.yaml")

    estado = evaluar_modo_shadow(perfil, "srv1", repo)

    assert estado is None
    assert not (tmp_path / "shadow.yaml").exists()


def test_evaluar_modo_shadow_crea_estado_la_primera_vez(tmp_path: Path) -> None:
    perfil = _perfil(duracion_dias=14)
    repo = RepositorioEstadoShadow(ruta=tmp_path / "shadow.yaml")

    estado = evaluar_modo_shadow(perfil, "srv1", repo)

    assert estado is not None
    assert estado.perfil == "pyme-basico"
    assert estado.host == "srv1"
    assert estado.duracion_dias == 14
    assert estado.vigente is True
    assert (tmp_path / "shadow.yaml").exists()


def test_evaluar_modo_shadow_no_reinicia_el_reloj(tmp_path: Path) -> None:
    perfil = _perfil(duracion_dias=14)
    repo = RepositorioEstadoShadow(ruta=tmp_path / "shadow.yaml")

    primero = evaluar_modo_shadow(perfil, "srv1", repo)
    assert primero is not None

    # Simula que ya pasó bastante tiempo, reescribiendo el archivo a mano —
    # sin pasar por evaluar_modo_shadow(), que es justamente lo que no debería
    # tocar la fecha de inicio en llamadas repetidas.
    estados = repo.cargar()
    estados[0].fecha_inicio = datetime.now() - timedelta(days=20)
    repo.guardar(estados)

    segundo = evaluar_modo_shadow(perfil, "srv1", repo)

    assert segundo is not None
    assert segundo.vigente is False  # si hubiera reiniciado el reloj, seguiría vigente


def test_evaluar_modo_shadow_distingue_hosts(tmp_path: Path) -> None:
    perfil = _perfil(duracion_dias=14)
    repo = RepositorioEstadoShadow(ruta=tmp_path / "shadow.yaml")

    estado_srv1 = evaluar_modo_shadow(perfil, "srv1", repo)
    estados = repo.cargar()
    estados[0].fecha_inicio = datetime.now() - timedelta(days=20)
    repo.guardar(estados)

    estado_srv2 = evaluar_modo_shadow(perfil, "srv2", repo)

    assert estado_srv1 is not None
    assert estado_srv2 is not None
    assert estado_srv2.vigente is True  # srv2 recién empieza su propio período


def test_repositorio_estado_shadow_guarda_y_carga_desde_disco(tmp_path: Path) -> None:
    ruta = tmp_path / "shadow.yaml"
    repo = RepositorioEstadoShadow(ruta=ruta)
    estado = EstadoShadow(perfil="pyme-basico", host="srv1", duracion_dias=14)

    repo.guardar([estado])
    cargados = RepositorioEstadoShadow(ruta=ruta).cargar()

    assert len(cargados) == 1
    assert cargados[0].perfil == "pyme-basico"
    assert cargados[0].host == "srv1"
    assert cargados[0].duracion_dias == 14


def test_repositorio_estado_shadow_archivo_inexistente_devuelve_vacio(tmp_path: Path) -> None:
    repo = RepositorioEstadoShadow(ruta=tmp_path / "no-existe.yaml")

    assert repo.cargar() == []
