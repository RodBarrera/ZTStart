"""Modelos de datos del rules_engine.

`Perfil` es la representación tipada de un archivo como
ztstart/config/perfiles/pyme_basico.yaml. `PlanDeAplicacion` es la salida del
motor: qué tags de Ansible correr, y qué hallazgos quedan cubiertos o no por
el perfil actual — para que nunca se aplique algo "a ciegas".
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ztstart.scanner.models import HallazgoRegla


class ControlPerfil(BaseModel):
    """Un control incluido en un perfil de configuración."""

    id: str = Field(..., description="ID del control en el benchmark, ej. 'cis_5.4.1'")
    categoria: str = Field(
        ..., description="Categoría del explainer / tag de Ansible correspondiente"
    )
    motivo: str = Field(..., description="Por qué este control está incluido en el perfil")


class Perfil(BaseModel):
    """Perfil de configuración de una organización (ej. pyme-basico)."""

    nombre: str
    descripcion: str
    benchmark_base: str
    datastream_sugerido: str | None = None
    modo_inicial: str = "shadow"
    duracion_modo_shadow_dias: int = 14
    controles_incluidos: list[ControlPerfil] = Field(default_factory=list)
    excepciones_pre_aprobadas: list[str] = Field(default_factory=list)
    notificaciones: dict[str, object] = Field(default_factory=dict)

    @property
    def categorias_habilitadas(self) -> set[str]:
        """Categorías (= tags de Ansible) que este perfil autoriza a aplicar."""
        return {control.categoria for control in self.controles_incluidos}


class PlanDeAplicacion(BaseModel):
    """Resultado de cruzar los hallazgos fallados de un escaneo con un perfil.

    La distinción entre cubiertos/no cubiertos es intencional y no debe
    colapsarse: un hallazgo "no cubierto" no es un error, es información
    honesta de que el perfil actual no tiene una tarea de Ansible para
    resolverlo — la organización decide si eso amerita ampliar el perfil.
    """

    tags_ansible: list[str] = Field(
        default_factory=list, description="Tags a pasar a 'ansible-playbook --tags'"
    )
    hallazgos_cubiertos: list[HallazgoRegla] = Field(default_factory=list)
    hallazgos_no_cubiertos: list[HallazgoRegla] = Field(default_factory=list)

    @property
    def hay_algo_que_aplicar(self) -> bool:
        return len(self.tags_ansible) > 0
