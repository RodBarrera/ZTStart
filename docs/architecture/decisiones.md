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
