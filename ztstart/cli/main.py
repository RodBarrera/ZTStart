"""CLI principal de ZTStart.

Este módulo solo orquesta — la lógica real vive en scanner/, rules_engine/,
explainer/ y approval_engine/. El CLI no debería crecer con lógica de negocio.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ztstart import __version__
from ztstart.explainer.motor import explicar_todos
from ztstart.scanner.openscap_wrapper import (
    EscaneoFallidoError,
    OpenSCAPNoDisponibleError,
    ParametrosEscaneo,
    ejecutar_escaneo,
)
from ztstart.scanner.parser import parsear_resultados_xccdf

app = typer.Typer(
    name="ztstart",
    help="Arranca sistemas en modo zero-trust desde el día uno.",
    no_args_is_help=True,
)
consola = Console()


def _mostrar_version(mostrar: bool) -> None:
    if mostrar:
        consola.print(f"ztstart versión {__version__}")
        raise typer.Exit()


@app.callback()
def principal(
    version: bool = typer.Option(
        False, "--version", callback=_mostrar_version, is_eager=True, help="Muestra la versión."
    ),
) -> None:
    """ZTStart: escaneo, hardening deny-by-default, y excepciones en lenguaje simple."""


@app.command()
def scan(
    datastream: Path = typer.Option(
        ...,
        "--datastream",
        help="Ruta al datastream SCAP (ej. /usr/share/xml/scap/ssg/content/ssg-debian12-ds.xml)",
    ),
    perfil: str = typer.Option(
        "xccdf_org.ssgproject.content_profile_cis_level1_server",
        "--perfil",
        help="ID del perfil XCCDF a evaluar",
    ),
    salida: Path = typer.Option(
        Path("./ztstart-resultados"), "--salida", help="Directorio donde guardar resultados"
    ),
    host: str = typer.Option("localhost", "--host", help="Identificador del sistema escaneado"),
) -> None:
    """Escanea el sistema en modo solo lectura — no aplica ningún cambio."""
    consola.print("[bold cyan]Iniciando escaneo (modo solo lectura, sin cambios)...[/bold cyan]")

    try:
        ruta_xccdf, _ruta_arf = ejecutar_escaneo(
            ParametrosEscaneo(
                ruta_datastream=datastream,
                perfil=perfil,
                directorio_resultados=salida,
            )
        )
    except OpenSCAPNoDisponibleError as error:
        consola.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except EscaneoFallidoError as error:
        consola.print(f"[bold red]El escaneo falló:[/bold red] {error}")
        raise typer.Exit(code=1) from error

    resultado = parsear_resultados_xccdf(ruta_xccdf, host=host, perfil_benchmark=perfil)

    tabla = Table(title=f"Resultado del escaneo — {resultado.host}")
    tabla.add_column("Métrica", style="bold")
    tabla.add_column("Valor")
    tabla.add_row("Perfil evaluado", resultado.perfil_benchmark)
    tabla.add_row("Total de reglas evaluadas", str(len(resultado.hallazgos)))
    tabla.add_row("Reglas falladas", str(resultado.total_fallados))
    puntaje = resultado.puntaje_cumplimiento
    tabla.add_row("Puntaje de cumplimiento", f"{puntaje}%" if puntaje is not None else "N/D")
    consola.print(tabla)

    if resultado.total_fallados > 0:
        consola.print(
            f"\n[yellow]Hay {resultado.total_fallados} reglas falladas.[/yellow] "
            f"Corre: [bold]ztstart explain --resultados {salida} --perfil {perfil}[/bold] "
            "para ver qué significan en lenguaje simple."
        )


@app.command()
def apply(
    perfil: str = typer.Option(
        ..., "--profile", help="Nombre del perfil de configuración a aplicar"
    ),
) -> None:
    """Aplica el baseline deny-by-default del perfil indicado. (Aún no implementado)"""
    consola.print(
        f"[dim]El comando 'apply' para el perfil '{perfil}' está pendiente de implementación. "
        "Depende de rules_engine/ y ansible_roles/ — ver docs/architecture/roadmap.md[/dim]"
    )
    raise typer.Exit(code=0)


@app.command()
def explain(
    resultados: Path = typer.Option(
        Path("./ztstart-resultados"),
        "--resultados",
        help="Directorio de resultados generado por 'ztstart scan' (mismo valor usado en --salida)",
    ),
    perfil: str = typer.Option(
        ...,
        "--perfil",
        help="ID del perfil XCCDF usado en el escaneo (debe coincidir con el de 'ztstart scan')",
    ),
    host: str = typer.Option("localhost", "--host", help="Identificador del sistema escaneado"),
) -> None:
    """Traduce los hallazgos fallados del último escaneo a lenguaje simple."""
    ruta_xccdf = resultados / "resultados-xccdf.xml"
    if not ruta_xccdf.exists():
        consola.print(
            f"[bold red]No encontré resultados en '{resultados}'.[/bold red] "
            "Corré 'ztstart scan' primero, o revisa la ruta con --resultados."
        )
        raise typer.Exit(code=1)

    resultado = parsear_resultados_xccdf(ruta_xccdf, host=host, perfil_benchmark=perfil)

    if resultado.total_fallados == 0:
        consola.print("[bold green]No hay hallazgos fallados que explicar.[/bold green]")
        raise typer.Exit(code=0)

    explicaciones = explicar_todos(resultado.hallazgos_fallados)

    for explicacion in explicaciones:
        cuerpo = (
            f"[bold]{explicacion.mensaje_simple}[/bold]\n\n"
            f"[cyan]Por qué importa:[/cyan] {explicacion.por_que_importa}\n\n"
            f"[yellow]Si se ignora:[/yellow] {explicacion.que_pasa_si_se_ignora}"
        )
        if explicacion.detalle_tecnico:
            cuerpo += f"\n\n[dim]Detalle técnico: {explicacion.detalle_tecnico}[/dim]"

        titulo = explicacion.regla_id
        estilo_borde = "yellow" if explicacion.es_generica else "cyan"
        if explicacion.es_generica:
            titulo += " [dim](sin categoría específica)[/dim]"

        consola.print(Panel(cuerpo, title=titulo, border_style=estilo_borde))


if __name__ == "__main__":
    app()
