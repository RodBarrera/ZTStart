# ZTStart

**Arranca sistemas en modo zero-trust desde el día uno — no los asegures después.**

ZTStart es una herramienta open source que escanea un sistema, lo lleva a un estado
`deny-by-default` (todo cerrado salvo lo esencial), y traduce cada excepción que la
organización necesite a lenguaje simple — para que habilitar permisos sea una decisión
informada y auditada, no un checkbox que nadie entiende.

## El problema que resuelve

La mayoría de los servidores e infraestructura nacen con todo abierto y se van
"asegurando" después, cuando ya hay negocio corriendo encima y cada cambio da miedo.
ZTStart invierte el orden: el sistema nace cerrado, y cada vez que algo lo necesita,
queda registrado el qué, el por qué, y por cuánto tiempo.

No reinventamos el hardening — nos apoyamos en estándares ya maduros:

- **[OpenSCAP](https://www.open-scap.org/) + SCAP Security Guide** para el escaneo y
  los benchmarks CIS/DISA STIG.
- **[Ansible](https://www.ansible.com/) + roles de hardening probados en producción**
  (basados en [dev-sec](https://github.com/dev-sec)) para aplicar los cambios con
  rollback.

Lo que aporta ZTStart es la capa que falta en el ecosistema: el **traductor de
excepciones a lenguaje llano** y el **motor de aprobación auditable**, pensado para
organizaciones (especialmente PyMEs latinoamericanas) que no tienen un equipo de
seguridad dedicado interpretando reportes técnicos de compliance.

## Estado del proyecto

🚧 En desarrollo activo — MVP enfocado en Linux (Debian/Ubuntu server). Ver
[docs/architecture](docs/architecture/) para el diseño y las decisiones tomadas.

## Instalación

```bash
# Aún no publicado en PyPI — instalación desde el repo por ahora
git clone https://github.com/<tu-usuario>/ztstart.git
cd ztstart
pip install -e ".[dev]"
```

## Uso básico (previsto para el MVP)

```bash
# Escanea el sistema sin hacer cambios (modo solo lectura)
ztstart scan

# Cuando algo se bloquea, ZTStart lo explica en lenguaje simple
ztstart explain --resultados ./ztstart-resultados --perfil <perfil-usado-en-scan>

# Aplica el baseline deny-by-default según el perfil de la organización
# (dry-run por defecto — agrega --confirmar para aplicar de verdad)
ztstart apply --profile pyme-basico --resultados ./ztstart-resultados --perfil-xccdf <perfil-usado-en-scan>

# Revisa el historial de excepciones aprobadas (con expiración)
ztstart exceptions list
```

## Filosofía de diseño

1. **Deny-by-default no es opcional ni gradual** — el sistema arranca cerrado.
2. **Ninguna excepción es permanente sin revisión** — todo permiso aprobado tiene
   fecha de expiración y queda auditado.
3. **Lenguaje simple, no jerga de compliance** — quien aprueba una excepción no
   tiene por qué ser experto en seguridad para entender qué está autorizando.
4. **Nos apoyamos en estándares existentes** (CIS, STIG, dev-sec) en vez de
   inventar nuestras propias reglas de qué es "seguro".

## Estado de componentes

Leyenda: ✅ Completo &nbsp;·&nbsp; 🔄 En progreso &nbsp;·&nbsp; ⬜ Pendiente

**Núcleo (scan → explain → apply → exceptions)**
- ✅ `scanner/` — wrapper de OpenSCAP + parser de resultados XCCDF → modelos internos
- ✅ `explainer/` — clasificación por palabras clave + traducción a lenguaje simple (9 categorías, con fallback genérico honesto)
- ✅ `approval_engine/` — solicitud, aprobación, rechazo y expiración de excepciones, persistido en YAML
- ✅ `rules_engine/` — conecta hallazgos fallados con tags de Ansible vía las categorías del `explainer`; distingue hallazgos cubiertos de no cubiertos
- ✅ `ansible_roles/zt_baseline` — aplica los 6 controles CIS de ejemplo del perfil `pyme-basico`, idempotencia validada manualmente
- ✅ CLI completo: `scan`, `explain`, `apply`, `shadow-status`, `exceptions request/approve/reject/list`
- ✅ **Ciclo completo `scan → explain → apply` validado de punta a punta** (dry-run por defecto)
- ✅ Modo `shadow` funcional — `apply --confirmar` no aplica cambios reales mientras el perfil esté en período de prueba (ver ADR-003 y ADR-009)

**Infraestructura del proyecto**
- ✅ Estructura base del repo, `pyproject.toml`, licencia, `CONTRIBUTING.md`
- ✅ CI (ruff, mypy strict, pytest, ansible-lint)
- ✅ Perfil de configuración de ejemplo `pyme-basico`

- ✅ **Pruebas de integración end-to-end contra un servidor real** (VM Debian 12 sobre VMware, no un contenedor) — ciclo `scan → explain → apply` corrido de punta a punta con datos reales: 887 reglas evaluadas, 65.73% de cumplimiento inicial, modo shadow validado en systemd real (ver ADR-010)
- ✅ Categoría `endurecimiento_pila_red` (explainer) + control `cis_3.3` (zt_baseline) — cubre 19 sysctls de hardening de red IPv4/IPv6 (redirecciones ICMP, ruta de origen forzada, rp_filter, syncookies, router advertisements IPv6). Re-corrido contra el mismo servidor real: cobertura del perfil subió de 30/110 a **49/110 hallazgos cubiertos** (ver ADR-012 y ADR-013)
- ✅ Categoría `gestion_paquetes_seguridad` (explainer) + control `cis_paquetes_seguridad` (zt_baseline) — instala `aide`, `apparmor-utils`, `systemd-journal-remote`, `iptables`, `ufw`, `chrony`; remueve `rsync`, `inetutils-telnet`, `rpcbind`. Probado con instalación/remoción real (no solo sintaxis, ver ADR-014). Confirmado contra el mismo servidor real: cobertura del perfil subió de 49/110 a **58/110 hallazgos cubiertos**
- ✅ Corrección de cobertura fantasma en `servicios_innecesarios` — `zt_baseline` ya bloqueaba `freevxfs`/`hfs`/`hfsplus`/`jffs2` desde el principio, pero el explainer no los reconocía y se reportaban como "no cubiertos". Sin cambios en Ansible, solo una palabra clave nueva (ver ADR-015). Confirmado contra el mismo servidor real: cobertura del perfil subió de 58/110 a **62/110 hallazgos cubiertos**

**En progreso**
- 🔄 Ampliar categorías del `explainer/` más allá de las 9 actuales — quedan 48/110 hallazgos sin cubrir (confirmado en la última corrida real); los grupos más grandes restantes son montajes `/tmp` y `/dev/shm`, hardening misceláneo de kernel (ASLR, ptrace_scope, coredumps, suid_dumpable), y `aide_build_database` (dejado fuera a propósito, ver ADR-014)
- 🔄 Ampliar `zt_baseline` más allá de los 6 controles actuales — mismos grupos de arriba, sin tarea de Ansible correspondiente todavía

**Pendiente**
- ⬜ Publicación en PyPI

Detalle de las decisiones detrás de cada módulo en
[docs/architecture/decisiones.md](docs/architecture/decisiones.md).

## Contribuir

Este proyecto recién empieza — toda contribución ayuda, desde código hasta
feedback de gente que administra infraestructura real y quiere probarlo.
Ver `CONTRIBUTING.md` (próximamente) para la guía de contribución.

## Licencia

Apache License 2.0 — ver [LICENSE](LICENSE).

---

**Autor:** Jorge Barrera Espinoza — Ingeniero en Ciberseguridad

