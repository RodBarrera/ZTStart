# Contribuir a ZTStart

Gracias por el interés en aportar. El proyecto está en etapa temprana, así que
hay espacio para influir en decisiones grandes, no solo corregir bugs.

## Setup local

```bash
git clone https://github.com/<tu-usuario>/ztstart.git
cd ztstart
pip install -e ".[dev]"
```

## Antes de un PR

```bash
ruff check .        # lint
mypy ztstart        # type-check (el proyecto usa modo strict)
pytest              # tests
```

## Dónde mirar según lo que quieras aportar

- **¿Sabes de OpenSCAP/XCCDF?** → `ztstart/scanner/parser.py` tiene varios
  `TODO` marcados (cruce de reglas con títulos/descripciones reales del
  benchmark, manejo de CPE applicability).
- **¿Sabes de Ansible?** → `ztstart/ansible_roles/` está vacío, es el siguiente
  módulo grande por construir (ver ADR-002 en `docs/architecture/decisiones.md`).
- **¿Te interesa UX/redacción?** → `ztstart/explainer/` (aún no implementado)
  es el módulo que traduce hallazgos técnicos a lenguaje simple — necesita
  criterio de redacción, no solo código.
- **¿Administras infraestructura real?** → el feedback más valioso en esta
  etapa es probar el `scan` en un sistema real y reportar qué falta o qué
  confunde. Abre un issue con el output.

## Convenciones

- Código y nombres de funciones/variables en español (es la convención elegida
  para este proyecto, ver discusión en el README) — comentarios técnicos en
  español también.
- Nombres de tipos SCAP/XCCDF, IDs de reglas, y términos de la industria
  (ej. "deny-by-default", "zero-trust") se mantienen en inglés porque son
  estándares reconocidos.
- Cobertura de tests no es obligatoria al 100% en esta etapa, pero todo módulo
  nuevo debería traer al menos un test de humo.
