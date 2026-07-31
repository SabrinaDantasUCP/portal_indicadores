"""
services/etl/vpn_control.py

Conecta/desconecta la VPN PPTP del ERP desde Python, para el botón
"Ejecutar ahora" del admin (modules/encuestas_config_etl.py). El proceso de
Streamlit corre como un usuario normal (no root), así que toda la lógica de
red vive en scripts/vpn_ctl.sh y se invoca acá vía `sudo -n` (no interactivo:
si la regla sudoers no está instalada, falla de inmediato con un mensaje
claro en vez de colgar la UI esperando una contraseña).

Requiere la regla sudoers de scripts/encuestas_vpn.sudoers.example instalada
en el servidor (no se instala sola — ver instrucciones en ese archivo).
"""

import os
import subprocess

from utils.system_logging import get_logger

log = get_logger()

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_VPN_CTL_SCRIPT = os.path.join(_PROJECT_DIR, "scripts", "vpn_ctl.sh")

CONNECT_TIMEOUT = 60
DISCONNECT_TIMEOUT = 20


class VpnError(Exception):
    """La VPN del ERP no pudo conectarse/desconectarse."""


def conectar():
    log.info("Conectando VPN del ERP (sudo scripts/vpn_ctl.sh connect)")
    try:
        resultado = subprocess.run(
            ["sudo", "-n", _VPN_CTL_SCRIPT, "connect"],
            capture_output=True, text=True, timeout=CONNECT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        log.error("Timeout conectando VPN del ERP")
        raise VpnError("Timeout esperando que la VPN del ERP conecte.") from exc

    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout or "").strip()
        log.error("Fallo al conectar VPN del ERP: %s", detalle)
        raise VpnError(
            "No se pudo conectar la VPN del ERP. Verifique que la regla sudoers "
            "(scripts/encuestas_vpn.sudoers.example) esté instalada y que la VPN "
            f"esté disponible. Detalle: {detalle}"
        )
    log.info("VPN del ERP conectada.")


def desconectar():
    """No lanza: una falla al desconectar no debe tapar el resultado del ETL."""
    try:
        resultado = subprocess.run(
            ["sudo", "-n", _VPN_CTL_SCRIPT, "disconnect"],
            capture_output=True, text=True, timeout=DISCONNECT_TIMEOUT,
        )
        if resultado.returncode != 0:
            log.warning("Fallo al desconectar VPN del ERP (no crítico): %s", resultado.stderr)
    except Exception as exc:
        log.warning("Excepción al desconectar VPN del ERP (no crítico): %s", exc)
