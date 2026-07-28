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


# --- endurecimiento_pila_red ---
#
# Estos regla_id son los reales que quedaron sin categoría en la primera
# prueba de integración contra un servidor real (VM Debian 12, ver ADR-010 y
# ADR-011 en docs/architecture/decisiones.md) — no son casos inventados.


def test_clasifica_sysctl_accept_redirects_ipv4_como_endurecimiento_red() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sysctl_net_ipv4_conf_all_accept_redirects",
        titulo="Disable Kernel Parameter for Accepting ICMP Redirects for All IPv4 Interfaces",
    )

    categoria = clasificar(hallazgo)

    assert categoria is not None
    assert categoria.id == "endurecimiento_pila_red"


def test_clasifica_sysctl_accept_source_route_como_endurecimiento_red() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sysctl_net_ipv4_conf_all_accept_source_route",
        titulo="Disable Kernel Parameter for Accepting Source-Routed Packets",
    )

    categoria = clasificar(hallazgo)

    assert categoria is not None
    assert categoria.id == "endurecimiento_pila_red"


def test_clasifica_sysctl_rp_filter_como_endurecimiento_red() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sysctl_net_ipv4_conf_all_rp_filter",
        titulo="Enable Kernel Parameter to Use Reverse Path Filtering",
    )

    categoria = clasificar(hallazgo)

    assert categoria is not None
    assert categoria.id == "endurecimiento_pila_red"


def test_clasifica_sysctl_syncookies_como_endurecimiento_red() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sysctl_net_ipv4_tcp_syncookies",
        titulo="Enable Kernel Parameter to Use TCP Syncookies",
    )

    categoria = clasificar(hallazgo)

    assert categoria is not None
    assert categoria.id == "endurecimiento_pila_red"


def test_clasifica_sysctl_accept_ra_ipv6_como_endurecimiento_red() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sysctl_net_ipv6_conf_all_accept_ra",
        titulo="Disable Accepting IPv6 Router Advertisements on all IPv6 Interfaces",
    )

    categoria = clasificar(hallazgo)

    assert categoria is not None
    assert categoria.id == "endurecimiento_pila_red"


def test_clasifica_sysctl_icmp_broadcasts_como_endurecimiento_red() -> None:
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sysctl_net_ipv4_icmp_echo_ignore_broadcasts",
        titulo="Enable Ignore Broadcast Requests",
    )

    categoria = clasificar(hallazgo)

    assert categoria is not None
    assert categoria.id == "endurecimiento_pila_red"


def test_sysctl_ip_forward_sigue_yendo_a_red_reenvio_trafico_no_a_endurecimiento() -> None:
    """Regresión: ip_forward y forwarding IPv6 deben seguir en su categoría
    original (red_reenvio_trafico), no ser capturados por la nueva categoría
    de endurecimiento — son conceptualmente distintos (una es 'no ser router',
    la otra es 'protegerse de ataques de red aunque no seas router')."""
    hallazgo_ipv4 = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sysctl_net_ipv4_ip_forward",
        titulo="Disable Kernel Parameter for IP Forwarding on IPv4 Interfaces",
    )
    hallazgo_ipv6 = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sysctl_net_ipv6_conf_all_forwarding",
        titulo="Disable Accepting IPv6 Router Advertisements",
    )

    assert clasificar(hallazgo_ipv4).id == "red_reenvio_trafico"  # type: ignore[union-attr]
    assert clasificar(hallazgo_ipv6).id == "red_reenvio_trafico"  # type: ignore[union-attr]


def test_sysctl_log_martians_sigue_yendo_a_auditoria_no_a_endurecimiento() -> None:
    """Regresión: log_martians debe seguir clasificando como auditoría
    (contiene 'log'), no como endurecimiento_pila_red."""
    hallazgo = _hallazgo(
        regla_id="xccdf_org.ssgproject.content_rule_sysctl_net_ipv4_conf_all_log_martians",
        titulo="Enable Kernel Parameter to Log Martian Packets",
    )

    categoria = clasificar(hallazgo)

    assert categoria is not None
    assert categoria.id == "auditoria_registro"
