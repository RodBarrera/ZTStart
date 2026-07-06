"""Motor de lógica de negocio del flujo de excepciones.

Reglas que este módulo hace cumplir (no son opcionales, ver README - Filosofía
de diseño):

1. Toda excepción nace en estado PENDIENTE — nada queda aprobado por defecto.
2. Aprobar una excepción exige una fecha de expiración — no hay excepciones
   permanentes sin revisión.
3. Solo se puede decidir (aprobar/rechazar) sobre una solicitud PENDIENTE —
   no se puede "re-aprobar" algo ya rechazado ni editar una decisión pasada
   silenciosamente (eso rompería la trazabilidad).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ztstart.approval_engine.errores import (
    ExcepcionNoEncontradaError,
    TransicionInvalidaError,
)
from ztstart.approval_engine.models import EstadoExcepcion, SolicitudExcepcion
from ztstart.approval_engine.repositorio import RepositorioExcepciones


def solicitar(
    regla_id: str,
    host: str,
    categoria: str,
    motivo_solicitud: str,
    solicitante: str | None = None,
    repositorio: RepositorioExcepciones | None = None,
) -> SolicitudExcepcion:
    """Crea una nueva solicitud de excepción en estado PENDIENTE y la persiste."""
    repo = repositorio or RepositorioExcepciones()
    excepciones = repo.cargar()

    nueva = SolicitudExcepcion(
        regla_id=regla_id,
        host=host,
        categoria=categoria,
        motivo_solicitud=motivo_solicitud,
        solicitante=solicitante,
    )
    excepciones.append(nueva)
    repo.guardar(excepciones)
    return nueva


def _buscar_o_fallar(
    excepciones: list[SolicitudExcepcion], id_excepcion: str
) -> SolicitudExcepcion:
    for excepcion in excepciones:
        if excepcion.id == id_excepcion:
            return excepcion
    raise ExcepcionNoEncontradaError(f"No existe ninguna excepción con ID '{id_excepcion}'")


def aprobar(
    id_excepcion: str,
    aprobador: str,
    dias_vigencia: int,
    motivo_decision: str | None = None,
    repositorio: RepositorioExcepciones | None = None,
) -> SolicitudExcepcion:
    """Aprueba una solicitud PENDIENTE, con una fecha de expiración obligatoria.

    `dias_vigencia` debe ser positivo — una excepción no puede aprobarse ya
    expirada, y no puede aprobarse "para siempre" (eso contradice la filosofía
    de diseño del proyecto: ver README, punto 2).
    """
    if dias_vigencia <= 0:
        raise ValueError("dias_vigencia debe ser mayor a 0 — no existen excepciones permanentes")

    repo = repositorio or RepositorioExcepciones()
    excepciones = repo.cargar()
    excepcion = _buscar_o_fallar(excepciones, id_excepcion)

    if excepcion.estado != EstadoExcepcion.PENDIENTE:
        raise TransicionInvalidaError(
            f"Solo se puede aprobar una excepción PENDIENTE (estado actual: {excepcion.estado})"
        )

    ahora = datetime.now()
    excepcion.estado = EstadoExcepcion.APROBADA
    excepcion.aprobador = aprobador
    excepcion.fecha_decision = ahora
    excepcion.motivo_decision = motivo_decision
    excepcion.fecha_expiracion = ahora + timedelta(days=dias_vigencia)

    repo.guardar(excepciones)
    return excepcion


def rechazar(
    id_excepcion: str,
    aprobador: str,
    motivo_decision: str,
    repositorio: RepositorioExcepciones | None = None,
) -> SolicitudExcepcion:
    """Rechaza una solicitud PENDIENTE. El motivo de rechazo es obligatorio."""
    repo = repositorio or RepositorioExcepciones()
    excepciones = repo.cargar()
    excepcion = _buscar_o_fallar(excepciones, id_excepcion)

    if excepcion.estado != EstadoExcepcion.PENDIENTE:
        raise TransicionInvalidaError(
            f"Solo se puede rechazar una excepción PENDIENTE (estado actual: {excepcion.estado})"
        )

    excepcion.estado = EstadoExcepcion.RECHAZADA
    excepcion.aprobador = aprobador
    excepcion.fecha_decision = datetime.now()
    excepcion.motivo_decision = motivo_decision

    repo.guardar(excepciones)
    return excepcion


def revisar_expiradas(
    repositorio: RepositorioExcepciones | None = None,
) -> list[SolicitudExcepcion]:
    """Marca como EXPIRADA toda excepción APROBADA cuya fecha de expiración ya pasó.

    Devuelve solo las que cambiaron de estado en esta llamada (para que quien
    invoque esto pueda, por ejemplo, notificar qué excepciones vencieron).
    Esto debería correr al inicio de cada `ztstart scan` (ver docs/architecture).
    """
    repo = repositorio or RepositorioExcepciones()
    excepciones = repo.cargar()
    ahora = datetime.now()

    recien_expiradas: list[SolicitudExcepcion] = []
    for excepcion in excepciones:
        vencida = (
            excepcion.estado == EstadoExcepcion.APROBADA
            and excepcion.fecha_expiracion is not None
            and excepcion.fecha_expiracion < ahora
        )
        if vencida:
            excepcion.estado = EstadoExcepcion.EXPIRADA
            recien_expiradas.append(excepcion)

    if recien_expiradas:
        repo.guardar(excepciones)

    return recien_expiradas


def listar(
    estado: EstadoExcepcion | None = None,
    repositorio: RepositorioExcepciones | None = None,
) -> list[SolicitudExcepcion]:
    """Lista excepciones, opcionalmente filtradas por estado."""
    repo = repositorio or RepositorioExcepciones()
    excepciones = repo.cargar()
    if estado is None:
        return excepciones
    return [e for e in excepciones if e.estado == estado]
