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

# Aplica el baseline deny-by-default según el perfil de la organización
ztstart apply --profile pyme-basico

# Cuando algo se bloquea, ZTStart lo explica y pregunta
ztstart explain --last

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

## Contribuir

Este proyecto recién empieza — toda contribución ayuda, desde código hasta
feedback de gente que administra infraestructura real y quiere probarlo.
Ver `CONTRIBUTING.md` (próximamente) para la guía de contribución.

## Licencia

Apache License 2.0 — ver [LICENSE](LICENSE).
