#!/bin/bash
set -Eeuo pipefail

# scripts/vpn_ctl.sh connect|disconnect
#
# Conecta/desconecta la VPN PPTP hacia el ERP — mismo mecanismo que
# /home/biocde/helpdesk_correo/executar_helpdesk.sh (mismo VPN_SERVER/VPN_USER).
#
# Pensado para ser invocado de dos formas:
#   1. Ya como root (scripts/run_etl_cron.sh, que corre en el crontab de root).
#   2. Vía "sudo scripts/vpn_ctl.sh connect|disconnect" desde el proceso de
#      Streamlit (usuario normal, ver services/etl/vpn_control.py), con una
#      regla sudoers restringida EXACTAMENTE a estos dos comandos — ver
#      scripts/encuestas_vpn.sudoers.example.

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/.env"
VENV_PYTHON="/home/biocde/streamlit/.venv/bin/python3"
VPN_NAME="${VPN_NAME:-encuestas_etl_pptp}"
VPN_RUNTIME_DIR="${PROJECT_DIR}/.vpn-runtime"
VPN_PID_FILE="${VPN_RUNTIME_DIR}/${VPN_NAME}.pid"
VPN_IFACE_FILE="${VPN_RUNTIME_DIR}/${VPN_NAME}.iface"
VPN_OPTIONS_FILE="${VPN_RUNTIME_DIR}/${VPN_NAME}.options"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" >&2; }

# Lee UNA clave puntual del .env vía python-dotenv, en vez de hacer
# "source" del archivo entero como bash — el .env tiene otras variables
# (ej. contraseñas de MySQL) con caracteres especiales (&, ), *, etc.) que
# rompen el parser de bash aunque no tengan nada que ver con la VPN.
_env_get() {
    "${VENV_PYTHON}" -c "
import sys
from dotenv import dotenv_values
print(dotenv_values(sys.argv[1]).get(sys.argv[2], ''), end='')
" "${ENV_FILE}" "$1"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        log "Comando obrigatório não encontrado: $1"
        exit 1
    fi
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        log "Precisa rodar como root (use sudo)."
        exit 1
    fi
}

disconnect_vpn() {
    if [[ -s "${VPN_PID_FILE}" ]]; then
        log "Desconectando VPN."
        if kill -0 "$(cat "${VPN_PID_FILE}")" >/dev/null 2>&1; then
            kill "$(cat "${VPN_PID_FILE}")" || log "Aviso: falha ao finalizar processo PPTP."
        fi
        sleep 2
        rm -f "${VPN_PID_FILE}" "${VPN_IFACE_FILE}" "${VPN_OPTIONS_FILE}"
    else
        log "VPN não estava conectada (nada para desconectar)."
    fi
}

wait_for_pptp_iface() {
    local timeout="${VPN_CONNECT_TIMEOUT:-30}"
    local elapsed=0
    local iface
    local iface_addr

    while [[ "${elapsed}" -lt "${timeout}" ]]; do
        iface="$(ip -o link show | awk -F': ' '/ppp[0-9]+/ {print $2; exit}')"
        if [[ -n "${iface}" ]]; then
            iface_addr="$(ip -o -4 addr show dev "${iface}" scope global 2>/dev/null | awk '{print $4; exit}')"
            if [[ -n "${iface_addr}" ]]; then
                printf '%s\n' "${iface}" > "${VPN_IFACE_FILE}"
                log "VPN PPTP conectada na interface ${iface} com IP ${iface_addr}."
                return 0
            fi
        fi

        if [[ -s "${VPN_PID_FILE}" ]] && ! kill -0 "$(cat "${VPN_PID_FILE}")" >/dev/null 2>&1; then
            log "Processo PPTP terminou antes de criar a interface PPP."
            return 1
        fi

        sleep 1
        elapsed=$((elapsed + 1))
    done

    log "Timeout aguardando a interface PPP da VPN PPTP ficar pronta."
    return 1
}

pppd_quote() {
    local value="${1//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '"%s"' "${value}"
}

route_sql_through_vpn() {
    local iface

    if [[ -z "${SQLSRV_ERP_HOST:-}" ]]; then
        log ".env precisa definir SQLSRV_ERP_HOST."
        exit 1
    fi
    if [[ ! -s "${VPN_IFACE_FILE}" ]]; then
        log "Interface da VPN não foi registrada."
        exit 1
    fi

    iface="$(cat "${VPN_IFACE_FILE}")"
    log "Configurando rota para ${SQLSRV_ERP_HOST} via ${iface}."
    ip route replace "${SQLSRV_ERP_HOST}/32" dev "${iface}"
}

validate_sql_connection() {
    local timeout="${SQL_CONNECT_CHECK_TIMEOUT:-10}"

    if [[ -z "${SQLSRV_ERP_HOST:-}" || -z "${SQLSRV_ERP_PORT:-}" ]]; then
        log ".env precisa definir SQLSRV_ERP_HOST e SQLSRV_ERP_PORT."
        exit 1
    fi

    require_command nc
    require_command timeout

    log "Validando acesso TCP ao SQL Server (ERP) em ${SQLSRV_ERP_HOST}:${SQLSRV_ERP_PORT}."
    if ! timeout "${timeout}" nc -z -w "${timeout}" "${SQLSRV_ERP_HOST}" "${SQLSRV_ERP_PORT}"; then
        log "Não foi possível acessar ${SQLSRV_ERP_HOST}:${SQLSRV_ERP_PORT} pela VPN."
        log "Verifique rota da VPN, firewall e se SQLSRV_ERP_HOST é o IP/endereço correto acessível pela VPN."
        exit 1
    fi
}

connect_vpn() {
    require_root

    if [[ ! -f "${ENV_FILE}" ]]; then
        log "Arquivo .env não encontrado. Configure as credenciais antes de executar."
        exit 1
    fi

    VPN_SERVER="$(_env_get VPN_SERVER)"
    VPN_USER="$(_env_get VPN_USER)"
    VPN_PASSWORD="$(_env_get VPN_PASSWORD)"
    SQLSRV_ERP_HOST="$(_env_get SQLSRV_ERP_HOST)"
    SQLSRV_ERP_PORT="$(_env_get SQLSRV_ERP_PORT)"

    if [[ -z "${VPN_SERVER:-}" || -z "${VPN_USER:-}" || -z "${VPN_PASSWORD:-}" ]]; then
        log ".env precisa definir VPN_SERVER, VPN_USER e VPN_PASSWORD."
        exit 1
    fi

    require_command pppd
    require_command pptp
    require_command ip
    require_command awk

    mkdir -p "${VPN_RUNTIME_DIR}"
    chmod 700 "${VPN_RUNTIME_DIR}"

    # Idempotente: si ya está conectada (p. ej. el cron la dejó activa hace
    # segundos), no vuelve a levantar el túnel — solo reconfirma la ruta.
    if [[ -s "${VPN_PID_FILE}" ]] && kill -0 "$(cat "${VPN_PID_FILE}")" >/dev/null 2>&1; then
        log "VPN já estava conectada (pid $(cat "${VPN_PID_FILE}"))."
        route_sql_through_vpn
        validate_sql_connection
        return 0
    fi

    rm -f "${VPN_PID_FILE}" "${VPN_IFACE_FILE}" "${VPN_OPTIONS_FILE}"

    {
        printf 'pty %s\n' "$(pppd_quote "pptp ${VPN_SERVER} --nolaunchpppd")"
        printf 'name %s\n' "$(pppd_quote "${VPN_USER}")"
        printf 'password %s\n' "$(pppd_quote "${VPN_PASSWORD}")"
        printf 'remotename PPTP\n'
        printf 'lock\n'
        printf 'noauth\n'
        printf 'refuse-eap\n'
        printf 'refuse-pap\n'
        printf 'refuse-chap\n'
        printf 'refuse-mschap\n'
        if [[ "${VPN_REQUIRE_MPPE:-0}" == "1" ]]; then
            printf 'require-mppe\n'
        else
            printf 'nomppe\n'
        fi
        printf 'noipdefault\n'
        printf 'nodefaultroute\n'
        printf 'persist\n'
        printf 'maxfail 0\n'
        printf 'holdoff 5\n'
        printf 'nodetach\n'
    } > "${VPN_OPTIONS_FILE}"
    chmod 600 "${VPN_OPTIONS_FILE}"

    log "Conectando VPN PPTP em ${VPN_SERVER}."
    pppd file "${VPN_OPTIONS_FILE}" > "${VPN_RUNTIME_DIR}/${VPN_NAME}.log" 2>&1 &
    printf '%s\n' "$!" > "${VPN_PID_FILE}"

    if ! wait_for_pptp_iface; then
        disconnect_vpn
        exit 1
    fi

    route_sql_through_vpn
    validate_sql_connection
}

case "${1:-}" in
    connect)
        connect_vpn
        ;;
    disconnect)
        require_root
        disconnect_vpn
        ;;
    *)
        echo "Uso: $0 {connect|disconnect}" >&2
        exit 2
        ;;
esac
