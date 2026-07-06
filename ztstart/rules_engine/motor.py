"""Motor que decide qué tags de Ansible aplicar, dado un escaneo y un perfil.

La pieza central de este módulo es que reutiliza el clasificador del
explainer (`ztstart.explainer.motor.clasificar`) como puente entre un
hallazgo técnico y su categoría — la misma categoría que ya se usa como tag
en las tareas de Ansible (ver ansible_roles/zt_baseline). Esto evita mantener
una segunda tabla de mapeo por separado: clasificar un hallazgo para
explicarlo y clasificarlo para decidir qué corregir es, a propósito, el mismo
paso.
"""

from __future__ import annotations

from ztstart.explainer.motor import clasificar
from ztstart.rules_engine.models import Perfil, PlanDeAplicacion
from ztstart.scanner.models import HallazgoRegla


def planificar_aplicacion(
    hallazgos_fallados: list[HallazgoRegla], perfil: Perfil
) -> PlanDeAplicacion:
    """Cruza los hallazgos fallados con las categorías habilitadas del perfil.

    Un hallazgo queda "cubierto" si su categoría (según el explainer) está
    entre las categorías que el perfil habilita. Los hallazgos sin categoría
    conocida (clasificar() devuelve None) nunca quedan cubiertos — no existe
    tarea de Ansible para algo que ni siquiera el explainer supo clasificar.
    """
    categorias_habilitadas = perfil.categorias_habilitadas

    cubiertos: list[HallazgoRegla] = []
    no_cubiertos: list[HallazgoRegla] = []
    tags: set[str] = set()

    for hallazgo in hallazgos_fallados:
        plantilla = clasificar(hallazgo)
        if plantilla is not None and plantilla.id in categorias_habilitadas:
            cubiertos.append(hallazgo)
            tags.add(plantilla.id)
        else:
            no_cubiertos.append(hallazgo)

    return PlanDeAplicacion(
        tags_ansible=sorted(tags),
        hallazgos_cubiertos=cubiertos,
        hallazgos_no_cubiertos=no_cubiertos,
    )
