"""Modo shadow: aplica el perfil "en modo lectura" antes de bloquear de verdad.

Un perfil con `modo_inicial: "shadow"` (ver rules_engine/models.py) no debe
empezar a bloquear/aplicar cambios reales el primer día — eso es exactamente
el tipo de sorpresa que este proyecto quiere evitar (ver la filosofía de
diseño en el README: deny-by-default no significa "sin aviso"). Durante el
período de shadow, `ztstart apply` sigue mostrando el plan de aplicación de
siempre, pero nunca ejecuta cambios reales, incluso si se pasa --confirmar.

Decisión de diseño clave (ver ADR-009 en docs/architecture/decisiones.md):
el reloj del período de shadow arranca la *primera vez* que se corre
`ztstart apply` para un perfil+host dado, no en la fecha en que se escribió
el archivo de perfil. Un perfil puede vivir en git meses antes de aplicarse
por primera vez en un sistema real; contar los días desde el archivo YAML
sería contar días en los que no pasó nada.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ztstart.rules_engine.models import Perfil

RUTA_POR_DEFECTO = Path("./ztstart-shadow.yaml")


class EstadoShadow(BaseModel):
    """Registro de cuándo empezó (y cuándo vence) el período de shadow.

    Una entrada por combinación (perfil, host) — el mismo perfil puede estar
    en shadow en un servidor y ya en modo enforce en otro, si se aplicó
    primero en uno que en otro.
    """

    perfil: str = Field(..., description="Nombre del perfil, ej. 'pyme-basico'")
    host: str = Field(..., description="Sistema al que aplica este período de shadow")
    fecha_inicio: datetime = Field(default_factory=datetime.now)
    duracion_dias: int = Field(..., description="Copiado de Perfil.duracion_modo_shadow_dias")

    @property
    def fecha_fin(self) -> datetime:
        return self.fecha_inicio + timedelta(days=self.duracion_dias)

    @property
    def vigente(self) -> bool:
        """True si el período de shadow sigue activo (todavía bloquea aplicar de verdad)."""
        return datetime.now() < self.fecha_fin

    @property
    def dias_restantes(self) -> int:
        """Días que faltan para que termine el shadow. Nunca negativo."""
        restante = self.fecha_fin - datetime.now()
        return max(0, restante.days)


class RepositorioEstadoShadow:
    """Carga y guarda el estado de shadow de todos los perfiles/hosts en un YAML plano.

    Mismo patrón que approval_engine/repositorio.py (ver ADR-005): un archivo
    versionable en git, sin lógica de negocio propia — solo lee y escribe.
    """

    def __init__(self, ruta: Path = RUTA_POR_DEFECTO) -> None:
        self.ruta = ruta

    def cargar(self) -> list[EstadoShadow]:
        """Devuelve los estados persistidos, o vacío si el archivo no existe."""
        if not self.ruta.exists():
            return []
        contenido = yaml.safe_load(self.ruta.read_text(encoding="utf-8"))
        if not contenido:
            return []
        return [EstadoShadow.model_validate(item) for item in contenido]

    def guardar(self, estados: list[EstadoShadow]) -> None:
        """Sobreescribe el archivo completo con la lista dada (last-write-wins)."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        datos = [estado.model_dump(mode="json") for estado in estados]
        self.ruta.write_text(
            yaml.safe_dump(datos, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def _buscar(estados: list[EstadoShadow], perfil: str, host: str) -> EstadoShadow | None:
    for estado in estados:
        if estado.perfil == perfil and estado.host == host:
            return estado
    return None


def evaluar_modo_shadow(
    perfil: Perfil, host: str, repo: RepositorioEstadoShadow | None = None
) -> EstadoShadow | None:
    """Devuelve el estado de shadow para este perfil+host, iniciándolo si hace falta.

    Devuelve `None` si el perfil no usa modo shadow (`modo_inicial != "shadow"`)
    — en ese caso no hay nada que evaluar, el perfil siempre aplica en modo
    enforce. Si el perfil sí usa shadow y es la primera vez que se evalúa para
    este host, se crea y persiste un nuevo `EstadoShadow` con inicio ahora.
    Si ya existe uno, se devuelve tal cual — llamar esta función varias veces
    nunca reinicia el reloj del período de shadow.
    """
    if perfil.modo_inicial != "shadow":
        return None

    repositorio = repo or RepositorioEstadoShadow()
    estados = repositorio.cargar()
    existente = _buscar(estados, perfil.nombre, host)
    if existente is not None:
        return existente

    nuevo = EstadoShadow(
        perfil=perfil.nombre,
        host=host,
        duracion_dias=perfil.duracion_modo_shadow_dias,
    )
    estados.append(nuevo)
    repositorio.guardar(estados)
    return nuevo
