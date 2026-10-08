#!/bin/bash
set -Eeuo pipefail

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS E ENTORNO
# -----------------------------------------------------------------------------
# Igual que run_alumnos_etl_cron.sh: NO conecta ninguna VPN (MYSQL_HOST_SYS y
# PG_HOST son hosts externos accesibles por red normal), así que va en el
# crontab del usuario normal (biocde), no en el de root.
#
# IMPORTANTE: debe programarse ANTES que run_alumnos_etl_cron.sh,
# run_asistencias_etl_cron.sh y run_etl_cron.sh (encuestas) -- los tres leen
# el archivo que este script genera (usuarios_activos_ids.txt). Sugerido:
#   0 2 * * *  (02:00, los demás corren a las 04:00)
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
VENV_PYTHON="/home/biocde/streamlit/.venv/bin/python3"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/etl_activos_criterios_cron.log"

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
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${PROJECT_DIR}" "${VENV_PYTHON}" "${PROJECT_DIR}/scripts/run_activos_criterios_etl_cron.py"
log "Execução finalizada com sucesso."
