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

## ADR-008: rules_engine reutiliza la clasificación del explainer, no un mapeo aparte

**Decisión:** `rules_engine/motor.py` no mantiene una tabla propia de
"regla_id → tag de Ansible". En vez de eso, reutiliza
`explainer.motor.clasificar()` — la misma función que ya clasifica un
hallazgo para explicarlo en lenguaje simple — y usa su `categoria` como el
tag de Ansible a aplicar. El perfil de configuración (ej. `pyme_basico.yaml`)
declara qué categorías tiene habilitadas mediante el campo `categoria` en
cada control incluido.

**Por qué:** mantener dos tablas de mapeo separadas (una para explicar, otra
para aplicar) es una fuente clásica de bugs de sincronización — se actualiza
una y se olvida la otra. Como la convención de nombres ya era la misma
(categoría del explainer = tag de la tarea Ansible, ver ADR-006), unificar
el mapeo en un solo lugar fue directo.

**Consecuencia importante — cobertura honesta:** `PlanDeAplicacion` separa
explícitamente `hallazgos_cubiertos` de `hallazgos_no_cubiertos`. Un hallazgo
no cubierto no es un error silencioso: la CLI (`ztstart apply`) se lo muestra
al usuario y sugiere ampliar el perfil o pedir una excepción — nunca se
aplica algo "a ciegas" ni se ignora en silencio lo que el perfil no cubre.

**`apply` es dry-run por defecto.** Igual que el resto del proyecto,
`ztstart apply` corre `ansible-playbook --check --diff` a menos que se pase
`--confirmar` explícitamente. Esto es coherente con la filosofía
deny-by-default del proyecto: ni siquiera aplicar el propio hardening es
"todo abierto" por defecto.

**Validación end-to-end realizada:** se corrió el pipeline completo
(`scan` real con OpenSCAP contra este entorno de desarrollo → `explain` →
`apply --check`) usando un archivo de resultados XCCDF con hallazgos de
prueba deliberados. Se confirmó que: (1) el motor clasifica correctamente
hallazgos cubiertos vs. no cubiertos por el perfil, (2) los tags calculados
son los correctos, y (3) `ansible-playbook --tags` ejecuta solo las tareas
correspondientes a esos tags, ninguna de más. El escaneo real con OpenSCAP
en este entorno de desarrollo (un contenedor sin systemd) no produjo
hallazgos fallados reales — la mayoría de los controles CIS resultaron
`notapplicable`/`notselected` por tratarse de un contenedor, no un servidor
completo — por lo que la validación de la ruta con fallos usó un archivo de
resultados construido a mano con el mismo esquema XCCDF real.

## ADR-009: Modo shadow — el reloj arranca en el primer `apply`, no en el perfil

**Decisión:** se implementó `rules_engine/shadow.py`. Un perfil con
`modo_inicial: "shadow"` (ver `Perfil.modo_inicial` en `rules_engine/models.py`)
nunca ejecuta cambios reales durante su `duracion_modo_shadow_dias`, sin
importar que `ztstart apply` reciba `--confirmar`. `apply` sigue mostrando el
plan completo (qué se cubre, qué tags se aplicarían) — la única diferencia es
que el comando real a `ansible-playbook` siempre lleva `--check --diff`
mientras el shadow esté vigente.

El estado (`EstadoShadow`: perfil, host, fecha de inicio, duración) se
persiste en `ztstart-shadow.yaml` — un archivo plano nuevo y separado de
`ztstart-excepciones.yaml`, siguiendo el mismo patrón de
`approval_engine/repositorio.py` (ADR-005): sin lógica de negocio en la
capa de persistencia, versionable en git.

**Por qué el reloj arranca en el primer `apply` y no en la fecha del archivo
de perfil:** un perfil YAML puede vivir en el repo de configuración meses
antes de aplicarse por primera vez a un sistema real (o aplicarse primero en
un servidor de staging y semanas después en producción). Si el período de
shadow se contara desde que se escribió el archivo, un perfil "shadow" podría
llegar a un servidor productivo ya vencido el primer día, sin que nadie lo
haya visto en modo prueba de verdad — exactamente la sorpresa que este
proyecto existe para evitar. Por eso `evaluar_modo_shadow()` crea el
`EstadoShadow` la primera vez que se evalúa para un `(perfil, host)` dado, y
llamadas posteriores nunca reinician esa fecha de inicio.

**Por qué es por `(perfil, host)` y no solo por perfil:** el mismo perfil
puede aplicarse primero en un servidor y semanas después en otro. Cada host
necesita su propia ventana de observación antes de bloquear cambios reales
en él — el shadow de un servidor no debería darse por "cumplido" porque otro
servidor ya llevaba dos semanas en shadow.

**Consecuencia en la CLI:** `ztstart apply` muestra un panel explícito
("Modo shadow activo") con cuántos días quedan, y si se pasó `--confirmar`
mientras el shadow sigue vigente, lo dice explícitamente en vez de
aplicarlo en silencio como si nada. Se agregó además `ztstart shadow-status
--profile <perfil> --host <host>` para consultar el estado sin tener que
correr `apply`.

**Validación real hecha:** se corrió el CLI completo (no solo el motor
aislado) con un resultado XCCDF de prueba construido a mano, reemplazando
solo la llamada real a `ansible-playbook` por un stub — se confirmó que (1)
con shadow vigente, `apply --confirmar` sigue ejecutando el comando con
`--check --diff` y avisa que `--confirmar` fue ignorado, y (2) forzando un
`EstadoShadow` ya vencido, `apply --confirmar` ejecuta el comando real, sin
`--check`/`--diff`.

**Pendiente relacionado:** no hay todavía un comando para "saltar" el shadow
manualmente (ej. si una organización quiere aplicar antes de que termine el
período) ni uno para extenderlo — por ahora solo se puede editar
`ztstart-shadow.yaml` a mano, lo cual es intencional en este momento (menos
superficie, y el archivo ya es auditable por git) pero puede necesitar un
comando explícito más adelante.

## ADR-010: VM real (Vagrant + VMware Workstation) como entorno de pruebas de integración

**Decisión:** las pruebas de integración en un sistema real (no contenedor) se
corren en una VM Debian 12 levantada con Vagrant sobre VMware Workstation
(provider `vmware_desktop`), no en KVM/libvirt anidado — porque el entorno de
desarrollo real corre Kali dentro de VMware sin virtualización anidada
expuesta al guest, y crear la VM de prueba como "hermana" (mismo nivel que
Kali, no dentro de él) evita ese problema por completo.

**Por qué no bastaba con el contenedor del ADR-007:** un contenedor no tiene
systemd real ni arranque completo, así que tareas de `zt_baseline` que tocan
`/etc/modprobe.d/`, servicios systemd, o el propio ciclo de vida de Ansible
con `become: true` no se comportan igual que en un servidor real. La VM
resuelve esto sin costo (VMware ya estaba disponible) y sin depender de un
proveedor cloud.

**Contenido SCAP usado:** el paquete `ssg-debian` del repositorio de Debian
12 estable está desactualizado — no incluye datastream para Debian 12 (se
quedó en Debian 11) y, más importante, es anterior a que el proyecto
ComplianceAsCode agregara soporte de perfiles CIS para Debian (eso llegó en
la versión 0.1.78 del proyecto upstream, no antes). Por eso el datastream
real (`ssg-debian12-ds.xml` con el perfil `cis_level1_server`) se descarga
directo del release de GitHub del proyecto (`ComplianceAsCode/content`), no
del `apt install ssg-debian`.

**Procedimiento resumido:**
1. `Vagrantfile` con `config.vm.box = "bento/debian-12"` y provider
   `vmware_desktop`
2. `vagrant up --provider=vmware_desktop`
3. Dentro de la VM: `apt install openscap-scanner ansible`, luego descargar
   `scap-security-guide-<versión>.zip` del release de ComplianceAsCode/content
   y usar el `ssg-debian12-ds.xml` de ahí, no el de apt
4. Ciclo normal: `ztstart scan → explain → apply --confirmar`
5. `vagrant snapshot save limpio` / `vagrant snapshot restore limpio` para
   repetir pruebas desde cero sin reinstalar todo

## ADR-011: Hallazgos de cobertura, medidos en una prueba real (CIS Debian 12, perfil Server L1)

**Contexto:** la primera corrida real de punta a punta (VM Debian 12, ver
ADR-010) contra el perfil CIS Level 1 Server dio 887 reglas evaluadas, 110
fallidas, 65.73% de cumplimiento inicial. Esto permitió medir por primera vez
—con datos reales, no estimados— qué tan completos están hoy el `explainer`
y `zt_baseline`.

**Hallazgo 1 — `explainer`:** de las 110 reglas fallidas, 55 (el 50%) cayeron
en el fallback genérico "sin categoría específica" en vez de una traducción
real. Los grupos más grandes sin cubrir:
- Sysctls de hardening de red IPv4/IPv6 (`accept_redirects`, `rp_filter`,
  `secure_redirects`, `accept_source_route`, `syncookies`, etc.) — el bloque
  más grande, ~25 reglas
- Módulos de kernel deshabilitados (`freevxfs`, `hfs`, `hfsplus`, `jffs2`) —
  llama la atención que `cramfs` y `usb-storage` sí calzan en la categoría
  "software sin uso" pero estos módulos hermanos no, lo que sugiere que el
  matching por keywords actual es más frágil de lo esperado y no generaliza
  bien dentro de la misma familia de reglas
- Paquetes instalados/removidos genéricos (`aide`, `apparmor-utils`,
  `iptables`, `ufw`, `chrony`, `rsync`, `rpcbind`, `inetutils-telnet`)

**Hallazgo 2 — `zt_baseline`:** de las mismas 110 reglas fallidas, solo 30
tenían una tarea de Ansible correspondiente en alguno de los 4 controles
actuales (`acceso_remoto_ssh`, `politica_contrasenas`, `red_reenvio_trafico`,
`servicios_innecesarios`). Las 80 restantes se reportaron como "no cubiertas"
en el plan de `apply`, sin detener la ejecución — que es el comportamiento
esperado (aplicar lo que sí se puede, avisar del resto), pero deja claro que
ampliar `zt_baseline` más allá de los 4 controles de ejemplo es más urgente
de lo que parecía antes de tener este dato.

**Siguiente paso sugerido (no decidido todavía):** priorizar el hallazgo 1
sobre el bloque de sysctls de red antes que los paquetes sueltos, porque es
el grupo más grande y más homogéneo (todas las reglas ahí comparten el mismo
patrón semántico de "hardening de pila de red").

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

## ADR-012: Nueva categoría `endurecimiento_pila_red` (explainer + zt_baseline)

**Decisión:** se agregó la categoría `endurecimiento_pila_red` al explainer
(`explainer/categorias.py`) y su control correspondiente `cis_3.3` en
`zt_baseline` (`cis_3_3_endurecimiento_pila_red.yml`), cubriendo el grupo de
hallazgos más grande que quedó sin clasificar en la primera prueba real
(ADR-011): redirecciones ICMP falsas, paquetes con ruta de origen forzada,
reverse path filtering, SYN cookies, avisos de enrutador IPv6 no confiables,
e ICMP broadcast/bogus. 12 `regla_id` reales de esa prueba, que antes caían
en el fallback genérico, ahora clasifican correctamente (verificado
ejecutando el explainer contra esos mismos IDs, no solo con datos de test
inventados).

**Por qué es una categoría separada de `red_reenvio_trafico` y no la misma:**
son conceptualmente distintas. `red_reenvio_trafico` (`ip_forward`,
`forwarding`) trata de si el sistema actúa como router — una propiedad
binaria de rol. `endurecimiento_pila_red` trata de protegerse de ataques de
red (spoofing, redirección, DoS) sin importar si el sistema enruta tráfico o
no — un servidor que no es router igual necesita estas protecciones.
Colapsarlas en una sola categoría habría hecho el mensaje en lenguaje simple
menos preciso para el que aprueba una excepción.

**Bug real encontrado al probar la tarea de Ansible antes de entregarla (no
solo revisando sintaxis):** los 6 parámetros IPv6 del control fallaban con
`No such file or directory` en cualquier sistema con IPv6 deshabilitado
(rutas de `/proc/sys/net/ipv6/...` no existen ahí) — un caso realista para
una PyME que desactivó IPv6 a propósito. Se corrigió agregando una tarea
previa (`ansible.builtin.stat` sobre `/proc/sys/net/ipv6`) que detecta si
IPv6 está disponible, y condicionando los 6 parámetros IPv6 a ese resultado;
los 13 parámetros IPv4 se aplican siempre. La tarea de detección tiene que
llevar los mismos tags que el resto del control — si queda sin tag, un
`--tags cis_3.3` la excluye del todo y la variable que registra queda
indefinida, rompiendo la condición `when` de las tareas IPv6 (encontrado
también probando, no por inspección).

**Validación real hecha:** `ansible-playbook --syntax-check` sobre el
playbook completo; `ansible-lint` sobre la tarea nueva (sin warnings);
ejecución real de la tarea dos veces seguidas confirmando `changed=0` en la
segunda corrida; y una tercera prueba forzando drift a mano
(`net.ipv4.tcp_syncookies` puesto en `0` directamente en `/proc/sys`) para
confirmar que la tarea sí corrige un valor incorrecto de verdad
(`changed=1`, valor final correcto) y vuelve a quedar idempotente después.

**Efecto en el perfil `pyme-basico`:** pasó de 4 a 5 controles incluidos
(`controles_incluidos`). El test `test_cargar_perfil_pyme_basico_real` se
actualizó para reflejar el conteo real en vez de un número fijo que ya había
quedado obsoleto una vez — vale la pena considerar en el futuro si ese test
debería verificar propiedades (ej. "contiene al menos N controles") en vez
de una igualdad exacta, para no tener que tocarlo cada vez que se agregue un
control.

## ADR-013: Segunda corrida real (post ADR-012) — cobertura sube de 30/110 a 49/110

**Contexto:** tras agregar la categoría `endurecimiento_pila_red` y el
control `cis_3.3` (ADR-012), se corrió de nuevo el ciclo completo
`scan → explain → apply` contra la misma VM Debian 12 del ADR-010, para
medir el efecto real del cambio (no solo confiar en los tests unitarios).

**Resultado:** la cobertura del perfil `pyme-basico` subió de **30/110** a
**49/110** hallazgos cubiertos (61 siguen sin tarea de Ansible). Subió 19,
no exactamente 12 — los 12 `regla_id` que el ADR-012 puntualiza como
verificados por test, más `send_redirects` (all/default, que ya coincidía
con `redirects` como keyword) y el forwarding de IPv6, que ya estaban
cubiertos por categorías existentes pero ahora también entran al plan de
aplicación real por primera vez en esta corrida.

**El control `cis_3.3` se ejecutó de punta a punta en un sistema con IPv6
habilitado** (a diferencia del sandbox de pruebas donde se desarrolló, que
no tenía IPv6): la tarea de detección (`ansible.builtin.stat` sobre
`/proc/sys/net/ipv6`) determinó correctamente que IPv6 estaba disponible, y
las 6 tareas IPv6 corrieron sin error junto con las 13 IPv4 — confirmando
que la corrección del ADR-012 funciona en ambos escenarios (con y sin
IPv6), no solo en el que se detectó el bug originalmente.

**Grupos más grandes que quedan en los 61 no cubiertos**, según el
`explain` de esta corrida — candidatos naturales para la próxima categoría
a agregar:
- Paquetes instalados/removidos genéricos (`aide`, `apparmor-utils`,
  `iptables`, `ufw`, `chrony`, `rsync`, `rpcbind`, `inetutils-telnet`,
  `systemd-journal-remote`)
- Módulos de kernel restantes (`freevxfs`, `hfs`, `hfsplus`, `jffs2`) — el
  mismo patrón señalado en el ADR-011 sigue sin resolverse: `cramfs` y
  `usb-storage` calzan en `servicios_innecesarios` pero sus hermanos no
- Opciones de montaje `/tmp` y `/dev/shm` (`nodev`/`noexec`/`nosuid`)
- Hardening misceláneo de kernel: ASLR (`randomize_va_space`),
  `ptrace_scope`, `suid_dumpable`, deshabilitar coredumps de usuario

Se decide dejar el trabajo aquí por ahora (28-07-2026) — el criterio de
"parar" fue simplemente una decisión de sesión, no una señal de que el
proyecto esté completo en este punto.

