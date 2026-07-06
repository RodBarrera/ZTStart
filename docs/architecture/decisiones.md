# Decisiones de arquitectura

## ADR-001: Motor de escaneo = OpenSCAP, no un parser propio

**Decisión:** usar OpenSCAP + SCAP Security Guide (SSG) como motor de escaneo,
en vez de escribir nuestras propias reglas de detección.

**Por qué:** los benchmarks CIS/DISA STIG que trae SSG representan años de
trabajo de la comunidad y son el estándar de facto en la industria. Escribir
nuestras propias reglas de "qué es inseguro" duplicaría ese esfuerzo sin
agregar valor — el aporte de ZTStart está en la capa de traducción y
aprobación, no en redefinir qué es un sistema seguro.

**Consecuencia:** `ztstart/scanner/` es una capa de traducción entre el mundo
XCCDF/XML de OpenSCAP y los modelos internos de Python (`ResultadoEscaneo`,
`HallazgoRegla`). Ningún otro módulo debería importar `lxml` ni saber que
XCCDF existe.

## ADR-002: Ansible para aplicar cambios, no scripts bash propios

**Decisión:** usar Ansible + roles de hardening basados en `dev-sec` para
aplicar el baseline, en vez de escribir scripts de shell/Python que modifiquen
el sistema directamente.

**Por qué:** Ansible es idempotente y declarativo por diseño — aplicar el
mismo playbook dos veces no debería romper nada, y el estado deseado queda
documentado en YAML legible. Los roles de `dev-sec` ya están probados en
producción por muchas organizaciones.

**Estado:** pendiente de implementar (`ztstart/ansible_roles/` existe como
carpeta pero aún no tiene contenido).

## ADR-003: Modo "shadow" antes de "enforce"

**Decisión:** todo perfil de configuración nace con `modo_inicial: shadow` —
el sistema solo registra qué bloquearía, no bloquea de verdad, durante un
período configurable (default 14 días).

**Por qué:** la principal barrera de adopción de zero-trust en organizaciones
sin equipo de seguridad no es técnica, es el miedo a romper producción. El
modo shadow permite validar el impacto real antes de aplicar bloqueos.

**Consecuencia:** el `approval_engine/` necesita distinguir entre "esto se
habría bloqueado" (modo shadow) y "esto se bloqueó y alguien decidió sobre
ello" (modo enforce) — son flujos de datos distintos, no el mismo log con un
flag.

## ADR-004: Explainer basado en reglas + keywords, no LLM

**Decisión:** el módulo `ztstart/explainer/` traduce hallazgos a lenguaje
simple usando un motor de categorías con matching por palabras clave
(`ztstart/explainer/categorias.py` + `ztstart/explainer/motor.py`), no un LLM.

**Por qué:** un usuario de OSS que instala una herramienta de seguridad no
debería depender de una API externa (con su costo y su superficie de riesgo)
para una función central como esta. El enfoque de reglas es 100% auditable —
cualquiera puede leer `categorias.py` y ver exactamente qué explicación se
genera para qué patrón, sin sorpresas de un modelo.

**Manejo de hallazgos sin categoría conocida:** en vez de forzar un match
incorrecto, se usa un mensaje de fallback genérico + la descripción técnica
original del benchmark como detalle expandible (`es_generica=True` en
`ExplicacionHallazgo`). Nunca se le oculta información al usuario, pero
tampoco se inventa una explicación que podría ser incorrecta.

**Riesgo conocido:** palabras clave demasiado genéricas pueden causar falsos
positivos de categorización (ej. la palabra "disable" originalmente en
`servicios_innecesarios` hacía match incorrecto con reglas de SSH como
`sshd_disable_root_login`). Mitigación: los tests en
`tests/unit/test_explainer.py` cubren casos de clasificación específica por
categoría, así que un keyword mal elegido que rompa la categorización de otro
caso real se detecta en CI antes de mergear.

**Pendiente:** un LLM opcional (capa separada, no dependencia core) podría
ofrecerse más adelante para organizaciones que quieran redactar excepciones
personalizadas — pero el motor de reglas seguirá siendo la ruta por defecto.

## ADR-005: Persistencia de excepciones en YAML plano, no en base de datos

**Decisión:** el `approval_engine` persiste todas las excepciones en un único
archivo YAML (`ztstart/approval_engine/repositorio.py`), reescribiéndolo
completo en cada cambio — no se usa SQLite ni ningún motor de base de datos.

**Por qué:** el archivo de excepciones está pensado para vivir junto al resto
de la configuración de la organización, en su propio repositorio git. Esto
significa que el historial de quién aprobó qué y cuándo queda auditado
gratis por `git log`/`git blame`, sin necesitar una base de datos ni
infraestructura adicional — algo valioso para el público objetivo (PyMEs sin
equipo de seguridad dedicado, ver README).

**Limitación conocida:** la estrategia de escritura es "reescribir el archivo
completo" (last-write-wins), adecuada para un solo operador local. Si el
proyecto crece hacia aprobaciones concurrentes de múltiples personas al mismo
tiempo, esto necesitará un backend con bloqueo o control de versiones más
fino — está documentado como limitación en el docstring de
`RepositorioExcepciones.guardar()`.

**Reglas de negocio no negociables que el motor hace cumplir** (ver
`ztstart/approval_engine/motor.py`):
- Toda excepción nace en estado `PENDIENTE`.
- Aprobar exige `dias_vigencia > 0` — no existen excepciones permanentes.
- Solo se puede decidir (aprobar/rechazar) sobre una solicitud `PENDIENTE`;
  intentar re-decidir sobre algo ya decidido lanza `TransicionInvalidaError`,
  para no romper la trazabilidad de la decisión original.

**Pendiente:** integrar `revisar_expiradas()` como parte del flujo de
`ztstart scan`, para que las excepciones vencidas se detecten automáticamente
en cada escaneo en vez de requerir un comando manual aparte.

## ADR-006: Primer rol de Ansible — zt_baseline

**Decisión:** el primer rol implementado (`ztstart/ansible_roles/zt_baseline/`)
cubre exactamente los 4 controles de ejemplo listados en el perfil
`pyme-basico` (`cis_1.1.1.1`, `cis_3.1.1`, `cis_5.2.1`, `cis_5.4.1`), no el
CIS Benchmark completo.

**Por qué:** cubrir el benchmark completo desde el día uno sería trabajo de
meses y no validable a mano. Empezar por los 4 controles que ya estaban
documentados como ejemplo en el perfil permite cerrar el ciclo completo
(scan → explain → aplicar) de punta a punta con algo pequeño y ya probado,
en vez de dejarlo a medias con más cobertura pero sin validar.

**Convención de tags:** cada tarea lleva dos tags — el ID del control CIS
(ej. `cis_5.4.1`) y el ID de la categoría correspondiente en `explainer/`
(ej. `politica_contrasenas`). Esto es intencional: en el futuro,
`rules_engine/` podrá mapear un hallazgo fallado directamente al tag de
Ansible que lo corrige, sin necesitar una tabla de traducción aparte.

**Dependencia externa:** el rol usa el módulo `ansible.posix.sysctl`, que
requiere la colección `ansible.posix` (no viene con `ansible-core`, sí viene
empaquetada si se instala el paquete `ansible` completo). Documentado en
`ztstart/ansible_roles/requirements.yml` y en el README del rol.

## ADR-007: Estrategia de testing — validación real en contenedor desechable

**Decisión:** antes de dar por buena cualquier tarea de Ansible, se ejecuta
de verdad (no solo `--syntax-check`) contra un contenedor Linux desechable,
incluyendo una segunda ejecución para confirmar idempotencia real
(`changed=0` en la segunda corrida).

**Por qué:** un playbook con sintaxis válida puede seguir estando roto en la
práctica. Este mismo proceso encontró un bug real: la tarea de
`cis_1.1.1.1` asumía que `/etc/modprobe.d/` ya existía, lo cual es cierto en
una instalación estándar de Debian/Ubuntu pero no en un contenedor mínimo —
sin la validación real, este bug habría llegado a un usuario real en vez de
detectarse en desarrollo. La corrección fue agregar una tarea explícita que
asegura el directorio antes de escribir en él.

**Consecuencia para CI:** se agregó un job `ansible-lint` en
`.github/workflows/ci.yml` que corre lint (perfil `production`, el más
estricto) y verificación de sintaxis en cada push/PR. La ejecución real con
verificación de idempotencia, por ahora, se hace manualmente durante
desarrollo — automatizarla en CI (ej. con Molecule + Docker) es un buen
próximo paso, documentado como pendiente abajo.

## Pendiente de decidir

- Formato exacto de persistencia de excepciones aprobadas (¿SQLite local?
  ¿archivo YAML versionable en git? — probablemente YAML para que las
  excepciones queden en el repo de configuración de la organización y sean
  auditables vía historial de git).
- Cómo se cruza `regla_id` (XCCDF) con el título/descripción legible real del
  benchmark — actualmente el parser deja esto como TODO (ver
  `ztstart/scanner/parser.py`).
- Mecanismo de expiración de excepciones: ¿un cron/systemd timer que corre
  `ztstart exceptions review`? ¿Verificación al inicio de cada `ztstart scan`?
