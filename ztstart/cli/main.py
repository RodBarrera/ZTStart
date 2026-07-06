"""CLI principal de ZTStart.

Este módulo solo orquesta — la lógica real vive en scanner/, rules_engine/,
explainer/ y approval_engine/. El CLI no debería crecer con lógica de negocio.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ztstart import __version__
from ztstart.approval_engine import motor as motor_excepciones
from ztstart.approval_engine.errores import (
    ExcepcionNoEncontradaError,
    TransicionInvalidaError,
)
from ztstart.approval_engine.models import EstadoExcepcion
from ztstart.explainer.motor import explicar_todos
from ztstart.rules_engine.motor import planificar_aplicacion
from ztstart.rules_engine.perfiles import PerfilNoEncontradoError, cargar_perfil
from ztstart.rules_engine.shadow import RepositorioEstadoShadow, evaluar_modo_shadow
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
excepciones_app = typer.Typer(
    name="exceptions",
    help="Solicita, aprueba, rechaza y lista excepciones al baseline deny-by-default.",
    no_args_is_help=True,
)
app.add_typer(excepciones_app, name="exceptions")
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


_RUTA_ANSIBLE_ROLES = Path(__file__).resolve().parent.parent / "ansible_roles"


@app.command()
def apply(
    perfil_nombre: str = typer.Option(
        ..., "--profile", help="Nombre del perfil de configuración a aplicar (ej. pyme-basico)"
    ),
    resultados: Path = typer.Option(
        Path("./ztstart-resultados"),
        "--resultados",
        help="Directorio de resultados de 'ztstart scan' a usar para decidir qué aplicar",
    ),
    perfil_xccdf: str = typer.Option(
        ..., "--perfil-xccdf", help="ID del perfil XCCDF usado en el escaneo (el de 'ztstart scan')"
    ),
    host: str = typer.Option("localhost", "--host", help="Identificador del sistema escaneado"),
    confirmar: bool = typer.Option(
        False,
        "--confirmar",
        help="Aplica los cambios de verdad. Sin esta bandera, solo muestra qué cambiaría "
        "(dry-run) — coherente con la filosofía deny-by-default del proyecto.",
    ),
) -> None:
    """Aplica el baseline del perfil indicado, según lo que encontró el último escaneo."""
    try:
        perfil = cargar_perfil(perfil_nombre)
    except PerfilNoEncontradoError as error:
        consola.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error

    ruta_xccdf = resultados / "resultados-xccdf.xml"
    if not ruta_xccdf.exists():
        consola.print(
            f"[bold red]No encontré resultados en '{resultados}'.[/bold red] "
            "Corré 'ztstart scan' primero."
        )
        raise typer.Exit(code=1)

    resultado = parsear_resultados_xccdf(ruta_xccdf, host=host, perfil_benchmark=perfil_xccdf)
    plan = planificar_aplicacion(resultado.hallazgos_fallados, perfil)

    consola.print(f"[bold cyan]Plan de aplicación — perfil '{perfil.nombre}'[/bold cyan]")
    consola.print(
        f"Hallazgos cubiertos por este perfil: [green]{len(plan.hallazgos_cubiertos)}[/green] — "
        f"no cubiertos: [yellow]{len(plan.hallazgos_no_cubiertos)}[/yellow]"
    )

    if plan.hallazgos_no_cubiertos:
        consola.print(
            "[dim]Los hallazgos no cubiertos no tienen una tarea de Ansible en este perfil. "
            "Considera ampliar el perfil o solicitar una excepción con "
            "'ztstart exceptions request'.[/dim]"
        )

    if not plan.hay_algo_que_aplicar:
        consola.print("[dim]Nada que aplicar con este perfil — no se ejecuta Ansible.[/dim]")
        raise typer.Exit(code=0)

    tags = ",".join(plan.tags_ansible)
    consola.print(f"Tags a aplicar: [bold]{tags}[/bold]")

    estado_shadow = evaluar_modo_shadow(perfil, host, RepositorioEstadoShadow())
    en_shadow = estado_shadow is not None and estado_shadow.vigente

    comando = ["ansible-playbook", "playbook.yml", "--tags", tags]

    if en_shadow:
        assert estado_shadow is not None  # para mypy: en_shadow ya lo garantiza
        comando.extend(["--check", "--diff"])
        consola.print(
            Panel(
                f"Este perfil está en período de prueba (modo shadow) desde "
                f"{estado_shadow.fecha_inicio:%Y-%m-%d}. Quedan "
                f"[bold]{estado_shadow.dias_restantes}[/bold] día(s) antes de que "
                "los cambios se puedan aplicar de verdad.\n\n"
                "Mientras tanto, cada corrida de 'apply' solo muestra qué cambiaría "
                "(dry-run) — así se puede revisar el impacto sin riesgo de romper nada.",
                title="Modo shadow activo",
                border_style="magenta",
            )
        )
        if confirmar:
            consola.print(
                "[yellow]--confirmar fue ignorado:[/yellow] el período de shadow de "
                f"este perfil vence el [bold]{estado_shadow.fecha_fin:%Y-%m-%d}[/bold]."
            )
    elif not confirmar:
        comando.extend(["--check", "--diff"])
        consola.print(
            "[yellow]Modo dry-run (no se aplica nada de verdad).[/yellow] "
            "Usa --confirmar para aplicar los cambios."
        )
    elif estado_shadow is not None:
        consola.print(
            f"[dim]El período de shadow de este perfil venció el "
            f"{estado_shadow.fecha_fin:%Y-%m-%d} — aplicando en modo enforce.[/dim]"
        )

    try:
        subprocess.run(comando, cwd=_RUTA_ANSIBLE_ROLES, check=False)  # noqa: S603
    except FileNotFoundError as error:
        consola.print(
            "[bold red]No encontré 'ansible-playbook' instalado.[/bold red] "
            "Instala Ansible para poder aplicar el baseline."
        )
        raise typer.Exit(code=1) from error


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


@excepciones_app.command("request")
def exceptions_request(
    regla_id: str = typer.Option(..., "--regla-id", help="ID de la regla a exceptuar"),
    host: str = typer.Option(..., "--host", help="Sistema al que aplica la excepción"),
    categoria: str = typer.Option(..., "--categoria", help="Categoría del explainer asociada"),
    motivo: str = typer.Option(..., "--motivo", help="Por qué la organización necesita esto"),
    solicitante: str = typer.Option(None, "--solicitante", help="Quién pide la excepción"),
) -> None:
    """Crea una nueva solicitud de excepción en estado pendiente."""
    excepcion = motor_excepciones.solicitar(
        regla_id=regla_id,
        host=host,
        categoria=categoria,
        motivo_solicitud=motivo,
        solicitante=solicitante,
    )
    consola.print(
        f"[bold green]Solicitud creada[/bold green] con ID: [bold]{excepcion.id}[/bold]\n"
        f"Estado: [yellow]{excepcion.estado.value}[/yellow] — "
        f"usa ese ID para aprobarla o rechazarla."
    )


@excepciones_app.command("approve")
def exceptions_approve(
    id_excepcion: str = typer.Argument(..., help="ID de la solicitud a aprobar"),
    aprobador: str = typer.Option(..., "--aprobador", help="Quién aprueba la excepción"),
    dias: int = typer.Option(..., "--dias", help="Días de vigencia antes de que expire"),
    motivo: str = typer.Option(None, "--motivo", help="Justificación de la aprobación"),
) -> None:
    """Aprueba una solicitud pendiente, con fecha de expiración obligatoria."""
    try:
        excepcion = motor_excepciones.aprobar(
            id_excepcion, aprobador=aprobador, dias_vigencia=dias, motivo_decision=motivo
        )
    except ExcepcionNoEncontradaError as error:
        consola.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except TransicionInvalidaError as error:
        consola.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error

    consola.print(
        f"[bold green]Excepción aprobada.[/bold green] "
        f"Expira: [bold]{excepcion.fecha_expiracion}[/bold]"
    )


@excepciones_app.command("reject")
def exceptions_reject(
    id_excepcion: str = typer.Argument(..., help="ID de la solicitud a rechazar"),
    aprobador: str = typer.Option(..., "--aprobador", help="Quién rechaza la excepción"),
    motivo: str = typer.Option(..., "--motivo", help="Por qué se rechaza (obligatorio)"),
) -> None:
    """Rechaza una solicitud pendiente."""
    try:
        motor_excepciones.rechazar(id_excepcion, aprobador=aprobador, motivo_decision=motivo)
    except ExcepcionNoEncontradaError as error:
        consola.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error
    except TransicionInvalidaError as error:
        consola.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error

    consola.print("[bold yellow]Excepción rechazada.[/bold yellow]")


@app.command("shadow-status")
def shadow_status(
    perfil_nombre: str = typer.Option(
        ..., "--profile", help="Nombre del perfil de configuración (ej. pyme-basico)"
    ),
    host: str = typer.Option("localhost", "--host", help="Identificador del sistema"),
) -> None:
    """Muestra si un perfil sigue en modo shadow para un host, y cuánto le queda."""
    try:
        perfil = cargar_perfil(perfil_nombre)
    except PerfilNoEncontradoError as error:
        consola.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(code=1) from error

    estado = evaluar_modo_shadow(perfil, host, RepositorioEstadoShadow())

    if estado is None:
        consola.print(
            f"El perfil '{perfil.nombre}' no usa modo shadow "
            f"(modo_inicial='{perfil.modo_inicial}') — aplica siempre en modo enforce."
        )
        raise typer.Exit(code=0)

    if estado.vigente:
        consola.print(
            f"[bold magenta]En shadow.[/bold magenta] Empezó el "
            f"{estado.fecha_inicio:%Y-%m-%d}, vence el {estado.fecha_fin:%Y-%m-%d} "
            f"— quedan [bold]{estado.dias_restantes}[/bold] día(s)."
        )
    else:
        consola.print(
            f"[bold green]Shadow vencido.[/bold green] Terminó el "
            f"{estado.fecha_fin:%Y-%m-%d} — 'apply --confirmar' ya aplica cambios reales."
        )


@excepciones_app.command("list")
def exceptions_list(
    estado: str = typer.Option(
        None, "--estado", help="Filtrar por estado: pendiente, aprobada, rechazada, expirada"
    ),
) -> None:
    """Lista las excepciones registradas, opcionalmente filtradas por estado."""
    filtro = EstadoExcepcion(estado) if estado else None
    excepciones = motor_excepciones.listar(estado=filtro)

    if not excepciones:
        consola.print("[dim]No hay excepciones registradas.[/dim]")
        raise typer.Exit(code=0)

    tabla = Table(title="Excepciones")
    tabla.add_column("ID", style="dim", max_width=10)
    tabla.add_column("Regla")
    tabla.add_column("Host")
    tabla.add_column("Estado")
    tabla.add_column("Expira")

    for excepcion in excepciones:
        tabla.add_row(
            excepcion.id[:8],
            excepcion.regla_id,
            excepcion.host,
            excepcion.estado.value,
            str(excepcion.fecha_expiracion) if excepcion.fecha_expiracion else "—",
        )

    consola.print(tabla)


if __name__ == "__main__":
    app()
