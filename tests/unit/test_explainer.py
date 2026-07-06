"""Tests para ztstart.explainer.motor."""

from ztstart.explainer.motor import clasificar, explicar, explicar_todos
from ztstart.scanner.models import HallazgoRegla, ResultadoRegla, Severidad


def _hallazgo(regla_id: str, titulo: str, descripcion: str | None = None) -> HallazgoRegla:
    return HallazgoRegla(
        regla_id=regla_id,
        titulo=titulo,
        resultado=ResultadoRegla.FALLADO,
        severidad=Severidad.MEDIA,
        descripcion=descripcion,
    )


def test_clasifica_hallazgo_de_password_correctamente() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_accounts_password_minlen_login_defs",
        titulo="Set Password Minimum Length",
        descripcion="Password length should be configured via pam_pwquality.",
    )

    categoria = clasificar(hallazgo)

    assert categoria is not None
    assert categoria.id == "politica_contrasenas"


def test_hallazgo_sin_match_devuelve_none() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_algo_completamente_inventado_xyz",
        titulo="Regla sin ninguna palabra clave conocida",
        descripcion="Zzzqqqwww nonsense unrelated text.",
    )

    assert clasificar(hallazgo) is None


def test_explicar_con_match_no_es_generica_y_conserva_regla_id() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sshd_disable_root_login",
        titulo="Disable SSH Root Login",
        descripcion="The root user should not be able to log in via SSH directly.",
    )

    explicacion = explicar(hallazgo)

    assert explicacion.es_generica is False
    assert explicacion.categoria == "acceso_remoto_ssh"
    assert explicacion.regla_id == hallazgo.regla_id
    assert explicacion.mensaje_simple  # no vacío


def test_explicar_sin_match_devuelve_fallback_generico_con_detalle_tecnico() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_algo_inventado_xyz",
        titulo="Regla totalmente desconocida",
        descripcion="Descripción técnica original que debe preservarse.",
    )

    explicacion = explicar(hallazgo)

    assert explicacion.es_generica is True
    assert explicacion.categoria == "sin_categoria"
    # El detalle técnico original nunca debe perderse, aunque no haya match.
    assert explicacion.detalle_tecnico == "Descripción técnica original que debe preservarse."


def test_explicar_todos_preserva_orden_y_cantidad() -> None:
    hallazgos = [
        _hallazgo("regla_password_1", "Password rule uno"),
        _hallazgo("regla_ssh_1", "SSH rule uno"),
        _hallazgo("regla_desconocida_1", "Nonsense zzzqqq"),
    ]

    explicaciones = explicar_todos(hallazgos)

    assert len(explicaciones) == 3
    assert [e.regla_id for e in explicaciones] == [h.regla_id for h in hallazgos]
