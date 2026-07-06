"""Test de integración: 'ztstart apply' respeta el modo shadow de punta a punta.

Usa el perfil real 'pyme-basico' (modo_inicial=shadow, 14 días) y un archivo
de resultados XCCDF mínimo construido a mano, siguiendo la misma estrategia
que ADR-008 documenta para el resto del proyecto: no depende de que
OpenSCAP esté instalado ni de un escaneo real, pero sí ejecuta el CLI
completo (typer) y solo reemplaza 'ansible-playbook' por un stub para no
requerir Ansible en el entorno de tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ztstart.cli import main as cli_main
from ztstart.rules_engine.shadow import EstadoShadow, RepositorioEstadoShadow

_XCCDF_MINIMO = """<?xml version="1.0" encoding="UTF-8"?>
<TestResult xmlns="http://checklists.nist.gov/xccdf/1.2"
            xmlns:xccdf="http://checklists.nist.gov/xccdf/1.2">
  <rule-result idref="xccdf_org.ssgproject.content_rule_sshd_disable_root_login"
                severity="medium">
    <result>fail</result>
  </rule-result>
</TestResult>
"""

runner = CliRunner()


@pytest.fixture
def _entorno_aislado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Aísla el CLI: cwd temporal + comando ansible-playbook stubeado que no falla."""
    monkeypatch.chdir(tmp_path)

    comandos_ejecutados: list[list[str]] = []

    def _subprocess_run_falso(comando: list[str], cwd: Path, check: bool) -> object:
        comandos_ejecutados.append(comando)

        class _Resultado:
            returncode = 0

        return _Resultado()

    monkeypatch.setattr(cli_main.subprocess, "run", _subprocess_run_falso)
    monkeypatch.setattr(cli_main, "_comandos_ejecutados_test", comandos_ejecutados, raising=False)

    resultados = tmp_path / "resultados"
    resultados.mkdir()
    (resultados / "resultados-xccdf.xml").write_text(_XCCDF_MINIMO, encoding="utf-8")

    return tmp_path


def _argumentos_apply(resultados_dir: Path) -> list[str]:
    return [
        "apply",
        "--profile",
        "pyme-basico",
        "--resultados",
        str(resultados_dir),
        "--perfil-xccdf",
        "xccdf_org.ssgproject.content_profile_cis_level1_server",
        "--confirmar",
    ]


def test_apply_confirmar_se_ignora_durante_shadow(_entorno_aislado: Path) -> None:
    resultado = runner.invoke(
        cli_main.app, _argumentos_apply(_entorno_aislado / "resultados")
    )

    assert resultado.exit_code == 0
    assert "--confirmar fue ignorado" in resultado.stdout
    assert "Modo shadow activo" in resultado.stdout

    comando_ejecutado = cli_main._comandos_ejecutados_test[0]  # type: ignore[attr-defined]
    assert "--check" in comando_ejecutado
    assert "--diff" in comando_ejecutado


def test_apply_confirmar_aplica_de_verdad_tras_vencer_shadow(_entorno_aislado: Path) -> None:
    # Fuerza un estado de shadow ya vencido antes de correr apply, en vez de
    # esperar 14 días reales.
    repo = RepositorioEstadoShadow()
    repo.guardar(
        [
            EstadoShadow(
                perfil="pyme-basico",
                host="localhost",
                fecha_inicio=datetime.now() - timedelta(days=20),
                duracion_dias=14,
            )
        ]
    )

    resultado = runner.invoke(
        cli_main.app, _argumentos_apply(_entorno_aislado / "resultados")
    )

    assert resultado.exit_code == 0
    assert "--confirmar fue ignorado" not in resultado.stdout
    assert "venció" in resultado.stdout

    comando_ejecutado = cli_main._comandos_ejecutados_test[0]  # type: ignore[attr-defined]
    assert "--check" not in comando_ejecutado
    assert "--diff" not in comando_ejecutado
