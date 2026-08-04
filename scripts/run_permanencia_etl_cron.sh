#!/bin/bash
set -Eeuo pipefail

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS E ENTORNO
# -----------------------------------------------------------------------------
# Sin VPN: mismo MYSQL_HOST_SYS que alumnos/asistencias. Va en el crontab del
# usuario normal (biocde), no en el de root.
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
VENV_PYTHON="/home/biocde/streamlit/.venv/bin/python3"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/etl_permanencia_cron.log"

mkdir -p "${LOG_DIR}"
exec >> "${LOG_FILE}" 2>&1

log() {
    printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

if [[ ! -x "${VENV_PYTHON}" ]]; then
    log "Python do venv compartilhado não encontrado: ${VENV_PYTHON}"
    exit 1
fi

log "Inicio da execução."
cd "${PROJECT_DIR}"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${PROJECT_DIR}" "${VENV_PYTHON}" "${PROJECT_DIR}/scripts/run_permanencia_etl_cron.py"
log "Execução finalizada com sucesso."
