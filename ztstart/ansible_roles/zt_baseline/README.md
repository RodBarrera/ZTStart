# zt_baseline

Rol de Ansible que aplica el subconjunto de controles CIS definido en el
perfil `pyme-basico` (ver `ztstart/config/perfiles/pyme_basico.yaml`).

## Por qué un rol y no scripts propios

Ver ADR-002 en `docs/architecture/decisiones.md`: Ansible es idempotente y
declarativo por diseño — aplicar este rol dos veces no debería reportar
cambios la segunda vez. Cada tarea de este rol fue probada manualmente para
confirmar esa idempotencia antes de incluirse (ver ADR-006).

## Instalación de dependencias

```bash
ansible-galaxy collection install -r ../requirements.yml
```

(Requiere acceso a `galaxy.ansible.com`. Alternativa sin ese acceso: instalar
el paquete `ansible` completo vía pip en vez de solo `ansible-core` — el
paquete completo ya incluye `ansible.posix` empaquetado.)

## Uso

```bash
# Aplicar de verdad (pide contraseña de sudo)
ansible-playbook ../playbook.yml --ask-become-pass

# Ver qué cambiaría, sin aplicar nada (dry-run)
ansible-playbook ../playbook.yml --check --diff

# Aplicar solo un control específico, usando su tag
ansible-playbook ../playbook.yml --tags cis_5.4.1 --ask-become-pass
```

## Trazabilidad: control CIS → tarea → categoría del explainer

| Control CIS | Archivo de tarea | Categoría en `explainer/` | Qué hace |
|---|---|---|---|
| `cis_1.1.1.1` | `cis_1_1_1_1_filesystems_no_usados.yml` | `servicios_innecesarios` | Bloquea la carga de módulos de filesystem no usados (cramfs, udf, etc.) |
| `cis_3.1.1` | `cis_3_1_1_ip_forwarding.yml` | `red_reenvio_trafico` | Deshabilita IP forwarding vía sysctl |
| `cis_5.2.1` | `cis_5_2_1_permisos_sshd_config.yml` | `acceso_remoto_ssh` | Restringe permisos de `sshd_config` a 0600, solo root |
| `cis_5.4.1` | `cis_5_4_1_politica_contrasenas.yml` | `politica_contrasenas` | Ajusta `PASS_MAX_DAYS`/`PASS_MIN_DAYS`/`PASS_MIN_LEN` en `login.defs` |

Cada tag de tarea coincide con el ID del control CIS y con el ID de categoría
del `explainer/` — esto es intencional: en el futuro, `rules_engine/` podrá
mapear un hallazgo fallado directamente al tag de Ansible que lo corrige.

## Limitaciones conocidas

- **`cis_5.4.1` solo afecta cuentas nuevas.** Los valores en `/etc/login.defs`
  no cambian retroactivamente la política de cuentas ya existentes — eso
  requeriría `chage` por usuario, fuera del alcance de este rol por ahora.
- **No hay rollback automatizado todavía.** Revertir un control significa,
  por ahora, revertir manualmente el archivo/valor que la tarea tocó (todos
  quedan documentados arriba). Automatizar esto es un buen primer issue para
  quien quiera contribuir.
- **Probado en Ubuntu 24.04 / Debian-like.** No se ha validado aún en RHEL,
  Alpine, ni otras familias de distribución.
