"""Categorías de hallazgos y sus plantillas de explicación.

Cada categoría agrupa un patrón recurrente de controles CIS/STIG (no reglas
individuales — serían miles) y define cómo se traduce ese patrón a lenguaje
simple. El match hacia una categoría se hace por palabras clave sobre el
regla_id/título/descripción del hallazgo (ver motor.py).

Agregar una categoría nueva: sumar una entrada a CATEGORIAS con sus keywords
y las tres frases de la plantilla. No hace falta tocar el motor de matching.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlantillaCategoria:
    """Plantilla de explicación para una categoría de hallazgos."""

    id: str
    nombre_legible: str
    palabras_clave: tuple[str, ...]
    mensaje_simple: str
    por_que_importa: str
    que_pasa_si_se_ignora: str


CATEGORIAS: dict[str, PlantillaCategoria] = {}


def _registrar(plantilla: PlantillaCategoria) -> None:
    CATEGORIAS[plantilla.id] = plantilla


_registrar(
    PlantillaCategoria(
        id="puertos_servicios_red",
        nombre_legible="Puertos y servicios de red expuestos",
        palabras_clave=("port", "network", "listen", "service", "daemon", "socket"),
        mensaje_simple=(
            "El sistema tiene un servicio de red activo que podría no ser necesario "
            "para su función actual."
        ),
        por_que_importa=(
            "Cada servicio expuesto a la red es una puerta adicional que alguien "
            "podría intentar forzar. Menos puertas abiertas, menos superficie de ataque."
        ),
        que_pasa_si_se_ignora=(
            "Un atacante que escanee la red puede detectar este servicio y probar "
            "vulnerabilidades conocidas contra él, incluso si nadie lo está usando."
        ),
    )
)

_registrar(
    PlantillaCategoria(
        id="politica_contrasenas",
        nombre_legible="Políticas de contraseña",
        palabras_clave=("password", "passwd", "pwquality", "credential", "authentication"),
        mensaje_simple=(
            "La configuración actual permite contraseñas más débiles de lo recomendado "
            "(muy cortas, sin complejidad, o sin expiración)."
        ),
        por_que_importa=(
            "Las contraseñas débiles son una de las formas más comunes en que los "
            "atacantes obtienen acceso — no hace falta una vulnerabilidad técnica "
            "sofisticada si la contraseña es fácil de adivinar."
        ),
        que_pasa_si_se_ignora=(
            "Una cuenta con contraseña débil puede comprometerse por fuerza bruta "
            "o con listas de contraseñas filtradas de otros sitios."
        ),
    )
)

_registrar(
    PlantillaCategoria(
        id="servicios_innecesarios",
        nombre_legible="Servicios o software innecesario instalado",
        palabras_clave=(
            "unused",
            "unnecessary",
            "remove_package",
            "filesystem",
            "cramfs",
            "usb-storage",
            # Genérico: cubre cualquier regla kernel_module_X_disabled, no
            # solo cramfs/usb-storage. El rol zt_baseline ya bloqueaba
            # freevxfs/hfs/hfsplus/jffs2 en cis_1_1_1_1_filesystems_no_usados
            # desde el principio (misma tarea, mismo bucle) — el explainer
            # simplemente no los reconocía todavía, así que se reportaban
            # como "no cubiertos" pese a que ya se estaban remediando en
            # cada apply. Ver ADR-015 en docs/architecture/decisiones.md.
            "kernel_module",
        ),
        mensaje_simple=(
            "Hay software o funcionalidad instalada que probablemente no se usa "
            "en este sistema."
        ),
        por_que_importa=(
            "Todo lo que está instalado, aunque no se use activamente, puede tener "
            "vulnerabilidades. Software que nadie revisa ni actualiza es un riesgo "
            "silencioso."
        ),
        que_pasa_si_se_ignora=(
            "Si aparece una vulnerabilidad nueva en ese software, el sistema queda "
            "expuesto aunque el equipo no sepa que ese componente estaba instalado."
        ),
    )
)

_registrar(
    PlantillaCategoria(
        id="permisos_archivos",
        nombre_legible="Permisos de archivos y directorios",
        palabras_clave=("permission", "chmod", "owner", "world-writable", "file mode"),
        mensaje_simple=(
            "Un archivo o carpeta del sistema tiene permisos más abiertos de lo "
            "necesario (por ejemplo, cualquier usuario puede modificarlo)."
        ),
        por_que_importa=(
            "Si cualquier usuario o proceso puede escribir en archivos críticos del "
            "sistema, un programa malicioso o una cuenta comprometida puede modificar "
            "configuración sensible sin necesitar privilegios especiales."
        ),
        que_pasa_si_se_ignora=(
            "Una cuenta de bajo privilegio comprometida podría escalar su acceso "
            "modificando estos archivos."
        ),
    )
)

_registrar(
    PlantillaCategoria(
        id="acceso_remoto_ssh",
        nombre_legible="Configuración de acceso remoto (SSH)",
        palabras_clave=("ssh", "sshd", "remote login", "root login"),
        mensaje_simple=(
            "La configuración de acceso remoto (SSH) no sigue las prácticas más "
            "seguras recomendadas — por ejemplo, permitir login directo como "
            "administrador o usar autenticación menos robusta."
        ),
        por_que_importa=(
            "SSH suele ser el principal punto de entrada administrativo a un "
            "servidor. Es de los primeros lugares donde un atacante prueba accesos."
        ),
        que_pasa_si_se_ignora=(
            "Un atacante con las credenciales correctas (o que las adivine) podría "
            "obtener acceso administrativo completo al servidor."
        ),
    )
)

_registrar(
    PlantillaCategoria(
        id="auditoria_registro",
        nombre_legible="Auditoría y registro de eventos",
        palabras_clave=("audit", "logging", "syslog", "journald", "log"),
        mensaje_simple=(
            "El sistema no está registrando ciertos eventos de seguridad que "
            "permitirían detectar un incidente después de que ocurra."
        ),
        por_que_importa=(
            "Sin registros adecuados, si algo sale mal es muy difícil saber qué "
            "pasó, cuándo, y qué se vio afectado."
        ),
        que_pasa_si_se_ignora=(
            "Ante un incidente de seguridad, no habrá evidencia suficiente para "
            "investigar qué ocurrió ni para contenerlo a tiempo."
        ),
    )
)

_registrar(
    PlantillaCategoria(
        id="red_reenvio_trafico",
        nombre_legible="Reenvío de tráfico de red (IP forwarding)",
        palabras_clave=("forward", "routing", "ip_forward", "gateway"),
        mensaje_simple=(
            "El sistema está configurado para reenviar tráfico de red entre "
            "interfaces, como si fuera un router — algo que normalmente un "
            "servidor no necesita hacer."
        ),
        por_que_importa=(
            "Si este sistema no está pensado para enrutar tráfico, tener esta "
            "función activa es una capacidad extra sin uso legítimo que podría "
            "aprovecharse para redirigir tráfico no autorizado."
        ),
        que_pasa_si_se_ignora=(
            "Un atacante que comprometa este sistema podría usarlo como punto "
            "intermedio para acceder a otras partes de la red."
        ),
    )
)

_registrar(
    PlantillaCategoria(
        id="endurecimiento_pila_red",
        nombre_legible="Endurecimiento de la pila de red (parámetros sysctl)",
        palabras_clave=(
            "accept_redirects",
            "accept_source_route",
            "secure_redirects",
            "send_redirects",
            "rp_filter",
            "syncookies",
            "accept_ra",
            "icmp_echo_ignore_broadcasts",
            "bogus_error_responses",
        ),
        mensaje_simple=(
            "El sistema no tiene aplicadas varias protecciones de bajo nivel "
            "contra técnicas de red comunes (redirecciones falsas, paquetes con "
            "ruta de origen forzada, saturación de conexiones, o abuso de ICMP)."
        ),
        por_que_importa=(
            "Estas protecciones del kernel evitan técnicas clásicas de "
            "intercepción y denegación de servicio en la red. Sin ellas, alguien "
            "en la misma red (o que logre interponerse en el camino del tráfico) "
            "tiene herramientas adicionales para redirigir o interrumpir las "
            "comunicaciones del servidor."
        ),
        que_pasa_si_se_ignora=(
            "Un atacante en la red local podría redirigir tráfico hacia sí mismo "
            "(un ataque de intermediario) o saturar el servidor con conexiones "
            "falsas, sin que estas protecciones básicas se lo impidan."
        ),
    )
)


_registrar(
    PlantillaCategoria(
        id="gestion_paquetes_seguridad",
        nombre_legible="Paquetes de seguridad faltantes o innecesarios",
        # Deliberadamente solo "_installed" / "_removed": estas reglas de CIS
        # únicamente verifican el estado de instalación de un paquete (no
        # configuración ni activación), así que "instalar" o "quitar" el
        # paquete correspondiente es una remediación completa y segura — no
        # cambia reglas de firewall, no reinicia servicios de red críticos.
        palabras_clave=("_installed", "_removed"),
        mensaje_simple=(
            "Este control se refiere a un paquete relacionado con la "
            "seguridad del sistema: o falta instalar una herramienta "
            "recomendada, o hay un paquete instalado que debería quitarse "
            "por ser innecesario o inseguro."
        ),
        por_que_importa=(
            "Las herramientas de seguridad recomendadas (integridad de "
            "archivos, sincronización de hora confiable, firewall) no "
            "protegen si no están instaladas. Del otro lado, paquetes de "
            "servicios legados o innecesarios (como telnet o rpcbind) "
            "amplían la superficie de ataque aunque nadie los use "
            "activamente."
        ),
        que_pasa_si_se_ignora=(
            "Si falta una herramienta de seguridad, el sistema pierde esa "
            "capa de protección o detección. Si sobra un paquete inseguro, "
            "queda ahí como una puerta adicional que un atacante podría "
            "aprovechar si algún día se activa por error o se abusa de él."
        ),
    )
)


def categorias_disponibles() -> tuple[str, ...]:
    """IDs de todas las categorías registradas — útil para tests y documentación."""
    return tuple(CATEGORIAS.keys())
