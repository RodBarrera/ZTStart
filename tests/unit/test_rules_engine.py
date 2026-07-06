"""Tests para ztstart.rules_engine."""

from __future__ import annotations

import pytest

from ztstart.rules_engine.motor import planificar_aplicacion
from ztstart.rules_engine.perfiles import PerfilNoEncontradoError, cargar_perfil
from ztstart.scanner.models import HallazgoRegla, ResultadoRegla, Severidad


def _hallazgo(regla_id: str, titulo: str, descripcion: str | None = None) -> HallazgoRegla:
    return HallazgoRegla(
        regla_id=regla_id,
        titulo=titulo,
        resultado=ResultadoRegla.FALLADO,
        severidad=Severidad.MEDIA,
        descripcion=descripcion,
    )


def test_cargar_perfil_pyme_basico_real() -> None:
    """Usa el archivo de perfil real del proyecto como test de integración."""
    perfil = cargar_perfil("pyme-basico")

    assert perfil.nombre == "pyme-basico"
    assert len(perfil.controles_incluidos) == 4
    assert "acceso_remoto_ssh" in perfil.categorias_habilitadas
    assert "politica_contrasenas" in perfil.categorias_habilitadas


def test_cargar_perfil_acepta_guion_o_guion_bajo() -> None:
    con_guion = cargar_perfil("pyme-basico")
    con_guion_bajo = cargar_perfil("pyme_basico")

    assert con_guion.nombre == con_guion_bajo.nombre


def test_cargar_perfil_inexistente_lanza_error() -> None:
    with pytest.raises(PerfilNoEncontradoError):
        cargar_perfil("perfil-que-no-existe")


def test_planificar_aplicacion_cubre_hallazgo_de_categoria_habilitada() -> None:
    perfil = cargar_perfil("pyme-basico")
    hallazgos = [
        _hallazgo(
            "xccdf_org.ssgproject.content_rule_sshd_disable_root_login",
            "Disable SSH Root Login",
            "The root user should not log in via SSH directly.",
        )
    ]

    plan = planificar_aplicacion(hallazgos, perfil)

    assert plan.hay_algo_que_aplicar is True
    assert "acceso_remoto_ssh" in plan.tags_ansible
    assert len(plan.hallazgos_cubiertos) == 1
    assert len(plan.hallazgos_no_cubiertos) == 0


def test_planificar_aplicacion_no_cubre_categoria_fuera_del_perfil() -> None:
    perfil = cargar_perfil("pyme-basico")
    # "auditoria_registro" existe como categoría en el explainer, pero el
    # perfil pyme-basico no la incluye — debe quedar como no cubierto.
    hallazgos = [
        _hallazgo(
            "xccdf_org.ssgproject.content_rule_audit_rules",
            "Configure auditd rules",
            "The audit daemon should log security-relevant events.",
        )
    ]

    plan = planificar_aplicacion(hallazgos, perfil)

    assert plan.hay_algo_que_aplicar is False
    assert len(plan.hallazgos_no_cubiertos) == 1
    assert len(plan.hallazgos_cubiertos) == 0


def test_planificar_aplicacion_hallazgo_sin_categoria_queda_no_cubierto() -> None:
    perfil = cargar_perfil("pyme-basico")
    hallazgos = [_hallazgo("regla_desconocida_xyz", "Algo sin keywords conocidas", "zzzqqqwww")]

    plan = planificar_aplicacion(hallazgos, perfil)

    assert plan.hay_algo_que_aplicar is False
    assert len(plan.hallazgos_no_cubiertos) == 1


def test_planificar_aplicacion_deduplica_tags_de_multiples_hallazgos() -> None:
    perfil = cargar_perfil("pyme-basico")
    hallazgos = [
        _hallazgo("regla_ssh_1", "SSH rule uno", "sshd config detail"),
        _hallazgo("regla_ssh_2", "SSH rule dos", "sshd config detail otra vez"),
    ]

    plan = planificar_aplicacion(hallazgos, perfil)

    assert plan.tags_ansible == ["acceso_remoto_ssh"]
    assert len(plan.hallazgos_cubiertos) == 2
