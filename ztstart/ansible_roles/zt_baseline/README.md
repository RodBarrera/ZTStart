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
| `cis_3.3` | `cis_3_3_endurecimiento_pila_red.yml` | `endurecimiento_pila_red` | 19 parámetros sysctl: redirecciones ICMP, ruta de origen forzada, reverse path filtering, SYN cookies, router advertisements IPv6, ICMP bogus/broadcast |
| `cis_paquetes_seguridad` | `cis_paquetes_seguridad.yml` | `gestion_paquetes_seguridad` | Instala `aide`, `apparmor-utils`, `systemd-journal-remote`, `iptables`, `ufw`, `chrony`; remueve `rsync`, `inetutils-telnet`, `rpcbind` |
| `cis_5.2.1` | `cis_5_2_1_permisos_sshd_config.yml` | `acceso_remoto_ssh` | Restringe permisos de `sshd_config` a 0600, solo root |
| `cis_5.4.1` | `cis_5_4_1_politica_contrasenas.yml` | `politica_contrasenas` | Ajusta `PASS_MAX_DAYS`/`PASS_MIN_DAYS`/`PASS_MIN_LEN` en `login.defs` |

Cada tag de tarea coincide con el ID del control CIS y con el ID de categoría
del `explainer/` — esto es intencional: en el futuro, `rules_engine/` podrá
mapear un hallazgo fallado directamente al tag de Ansible que lo corrige.

## Limitaciones conocidas

- **`cis_paquetes_seguridad` no construye la base de datos de AIDE.** Solo
  instala el paquete `aide` (regla `aide_installed`); la regla
  `aide_build_database` sigue sin cobertura a propósito — inicializar la
  base de datos (`aideinit`) es una operación larga que además debería
  correr una sola vez y no en cada `apply`, así que necesita su propio
  control más adelante en vez de forzarla dentro de esta tarea genérica.
- **`cis_paquetes_seguridad` instala `iptables` y `ufw` a la vez.** El
  benchmark CIS evalúa cada paquete de firewall como una regla separada, y
  esta tarea solo instala software (no activa reglas de firewall ni
  deshabilita servicios), así que no hay riesgo de bloquear tráfico por
  accidente — pero vale la pena revisar si instalar dos frontends de
  firewall a la vez tiene sentido para el caso de uso real, o si conviene
  dejar que la organización elija uno.
- **`cis_5.4.1` solo afecta cuentas nuevas.** Los valores en `/etc/login.defs`
  no cambian retroactivamente la política de cuentas ya existentes — eso
  requeriría `chage` por usuario, fuera del alcance de este rol por ahora.
- **No hay rollback automatizado todavía.** Revertir un control significa,
  por ahora, revertir manualmente el archivo/valor que la tarea tocó (todos
  quedan documentados arriba). Automatizar esto es un buen primer issue para
  quien quiera contribuir.
- **Probado en Ubuntu 24.04 / Debian-like.** No se ha validado aún en RHEL,
  Alpine, ni otras familias de distribución.
