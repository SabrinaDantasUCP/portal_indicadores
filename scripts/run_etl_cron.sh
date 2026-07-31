#!/bin/bash
set -Eeuo pipefail

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS E ENTORNO
# -----------------------------------------------------------------------------
# La conexión/desconexión de la VPN PPTP vive en scripts/vpn_ctl.sh (usado
# también por el botón "Ejecutar ahora" del admin, vía sudo). Este script
# debe ir en el crontab de ROOT (`sudo crontab -e`), no en el del usuario
# normal — conectar la VPN PPTP requiere privilegios de root.
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
VENV_PYTHON="/home/biocde/streamlit/.venv/bin/python3"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/etl_encuestas_cron.log"
# El ETL corre como este usuario (no como root), para que los CSV/parquet
# generados en assets/data/encuestas/ queden con el mismo dueño que el
# proceso de Streamlit y que "Ejecutar ahora" (admin) pueda sobreescribirlos
# después sin problema de permisos.
PYTHON_RUN_USER="${ENCUESTAS_RUN_USER:-biocde}"

mkdir -p "${LOG_DIR}"
exec >> "${LOG_FILE}" 2>&1

log() {
    printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

run_python_etl() {
    if [[ ! -x "${VENV_PYTHON}" ]]; then
        log "Python do venv compartilhado não encontrado: ${VENV_PYTHON}"
        exit 1
    fi

    if [[ "${EUID}" -eq 0 && -n "${PYTHON_RUN_USER}" && "${PYTHON_RUN_USER}" != "root" ]]; then
        log "Executando ETL como usuário ${PYTHON_RUN_USER}."
        if command -v runuser >/dev/null 2>&1; then
            runuser -u "${PYTHON_RUN_USER}" -- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${PROJECT_DIR}" "${VENV_PYTHON}" "${PROJECT_DIR}/scripts/run_etl_cron.py"
        else
            sudo -u "${PYTHON_RUN_USER}" env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${PROJECT_DIR}" "${VENV_PYTHON}" "${PROJECT_DIR}/scripts/run_etl_cron.py"
        fi
    else
        log "Executando ETL como usuário atual."
        PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${PROJECT_DIR}" "${VENV_PYTHON}" "${PROJECT_DIR}/scripts/run_etl_cron.py"
    fi
}

if [[ "${EUID}" -ne 0 ]]; then
    log "Este script precisa rodar como root (crontab de root) para conectar a VPN PPTP."
    log "Execute: sudo crontab -e (não crontab -e do usuário normal)."
    exit 1
fi

trap '"${SCRIPT_DIR}/vpn_ctl.sh" disconnect' EXIT

log "Inicio da execução."
"${SCRIPT_DIR}/vpn_ctl.sh" connect

cd "${PROJECT_DIR}"
run_python_etl

log "Execução finalizada com sucesso."
