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
- ✅ `explainer/` — clasificación por palabras clave + traducción a lenguaje simple (7 categorías, con fallback genérico honesto)
- ✅ `approval_engine/` — solicitud, aprobación, rechazo y expiración de excepciones, persistido en YAML
- ✅ `rules_engine/` — conecta hallazgos fallados con tags de Ansible vía las categorías del `explainer`; distingue hallazgos cubiertos de no cubiertos
- ✅ `ansible_roles/zt_baseline` — aplica los 4 controles CIS de ejemplo del perfil `pyme-basico`, idempotencia validada manualmente
- ✅ CLI completo: `scan`, `explain`, `apply`, `exceptions request/approve/reject/list`
- ✅ **Ciclo completo `scan → explain → apply` validado de punta a punta** (dry-run por defecto)

**Infraestructura del proyecto**
- ✅ Estructura base del repo, `pyproject.toml`, licencia, `CONTRIBUTING.md`
- ✅ CI (ruff, mypy strict, pytest, ansible-lint)
- ✅ Perfil de configuración de ejemplo `pyme-basico`

**En progreso**
- 🔄 Pruebas de integración end-to-end contra un servidor real (no un contenedor) — el entorno de desarrollo carece de systemd/muchos servicios que el CIS Benchmark evalúa
- 🔄 Ampliar categorías del `explainer/` más allá de las 7 actuales
- 🔄 Ampliar `zt_baseline` más allá de los 4 controles de ejemplo

**Pendiente**
- ⬜ Modo `shadow` funcional (loguear sin bloquear, ver ADR-003)
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

