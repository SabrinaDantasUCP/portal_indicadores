"""
modules/etl_resumen.py

Visión general de TODOS los ETL automatizados (Encuestas, Alumnos,
Asistencias, Índice de Permanencia): qué está activo, a qué hora corre el
cron, cuándo fue la última ejecución y si salió bien o con error. Es de solo
lectura -- para actuar (pausar, editar, ejecutar ahora) hay que ir a la
pantalla propia de cada ETL.

Los horarios de cron están hardcodeados acá porque viven en el crontab del
sistema operativo, no en la base de datos -- si algún día se cambia la hora
de un cron, hay que actualizar también CRON_ENCUESTAS/CRON_ALUMNOS/etc. acá.
"""

import pandas as pd
import streamlit as st

from utils import db_pia
from modules.encuestas_config_etl import TIPO_LABELS


STATUS_TEXTO = {"OK": "✅ OK", "ERROR": "❌ Error", "CANCELADO": "⏹️ Cancelado"}

# Confirmado por los timestamps reales en output/indicadores_encuestas_*.csv
CRON_ENCUESTAS = "04:00, 11:00, 17:00"
CRON_ALUMNOS = "04:00"
CRON_ASISTENCIAS = "03:00"
CRON_PERMANENCIA = "03:30"


def _formatear_fecha(dt):
    if not dt:
        return "-"
    try:
        return dt.strftime("%d/%m/%Y %H:%M")
    except AttributeError:
        return str(dt)


def _estado_txt(ultimo, status_key="status"):
    if not ultimo:
        return "—"
    return STATUS_TEXTO.get(ultimo[status_key], "❓")


ESTADO_FILTRO_OPCIONES = ["OK", "ERROR", "CANCELADO", "NUNCA"]
ESTADO_FILTRO_LABELS = {"OK": "✅ OK", "ERROR": "❌ Error", "CANCELADO": "⏹️ Cancelado", "NUNCA": "— Nunca ejecutado"}


def _filas_encuestas():
    configs = db_pia.get_encuesta_etl_configs()
    ultimos = db_pia.get_ultimo_run_por_config()
    filas = []
    for cfg in configs:
        ultimo = ultimos.get(cfg["id"])
        info = "-"
        if ultimo:
            info = f"{ultimo['filas_generadas']} filas" if ultimo["status"] == "OK" else (ultimo["mensaje_error"] or "-")
        filas.append({
            "ETL": "Encuestas",
            "Detalle": f"{TIPO_LABELS.get(cfg['tipo_encuesta'], cfg['tipo_encuesta'])} · {cfg['sede']} · {cfg['periodo']} · {cfg['carrera']}",
            "Programado": CRON_ENCUESTAS,
            "Activo": "✅ Activo" if cfg["activo"] else "⏸️ Pausado",
            "Última ejecución": _formatear_fecha(ultimo["finalizado_en"]) if ultimo else "Nunca",
            "Estado": _estado_txt(ultimo),
            "Info": info,
            "_activo": bool(cfg["activo"]),
            "_ejecutando": False,
            "_estado_key": ultimo["status"] if ultimo else "NUNCA",
        })
    return filas


def _filas_alumnos():
    cfg = db_pia.get_alumnos_etl_config()
    ultimo = db_pia.get_ultimo_alumnos_etl_run()
    lock = db_pia.get_alumnos_etl_lock_status()

    activo_txt = "✅ Activo" if cfg and cfg["activo"] else "⏸️ Pausado"
    if lock and lock["en_ejecucion"]:
        activo_txt += " · 🔵 Ejecutando"

    info = "-"
    if ultimo:
        info = f"v1={ultimo['filas_v1']}, v2={ultimo['filas_v2']}" if ultimo["status"] == "OK" else (ultimo["mensaje_error"] or "-")

    return [{
        "ETL": "Alumnos",
        "Detalle": f"Años: {', '.join(str(a) for a in cfg['anos'])}" if cfg else "-",
        "Programado": CRON_ALUMNOS,
        "Activo": activo_txt,
        "Última ejecución": _formatear_fecha(ultimo["finalizado_en"]) if ultimo else "Nunca",
        "Estado": _estado_txt(ultimo),
        "Info": info,
        "_activo": bool(cfg["activo"]) if cfg else False,
        "_ejecutando": bool(lock and lock["en_ejecucion"]),
        "_estado_key": ultimo["status"] if ultimo else "NUNCA",
    }]


def _filas_asistencias():
    cfg = db_pia.get_asistencias_etl_config()
    ultimo = db_pia.get_ultimo_asistencias_etl_run()
    lock = db_pia.get_asistencias_etl_lock_status()

    activo_txt = "✅ Activo" if cfg and cfg["activo"] else "⏸️ Pausado"
    if lock and lock["en_ejecucion"]:
        activo_txt += " · 🔵 Ejecutando"

    info = "-"
    if ultimo:
        info = f"v1={ultimo['filas_v1']}, v2={ultimo['filas_v2']}" if ultimo["status"] == "OK" else (ultimo["mensaje_error"] or "-")

    detalle = "-"
    if cfg:
        detalle = f"SysEduca: {', '.join(str(a) for a in cfg['anos_syseduca'])} · Biometría: {', '.join(cfg['periodos_biometria'])}"

    return [{
        "ETL": "Asistencias",
        "Detalle": detalle,
        "Programado": CRON_ASISTENCIAS,
        "Activo": activo_txt,
        "Última ejecución": _formatear_fecha(ultimo["finalizado_en"]) if ultimo else "Nunca",
        "Estado": _estado_txt(ultimo),
        "Info": info,
        "_activo": bool(cfg["activo"]) if cfg else False,
        "_ejecutando": bool(lock and lock["en_ejecucion"]),
        "_estado_key": ultimo["status"] if ultimo else "NUNCA",
    }]


def _filas_permanencia():
    configs = db_pia.get_permanencia_etl_configs()
    lock = db_pia.get_permanencia_etl_lock_status()
    filas = []
    for cfg in configs:
        periodo = cfg["periodo"]
        ultimo = db_pia.get_ultimo_permanencia_etl_run(periodo)

        activo_txt = "✅ Activo" if cfg["activo"] else "⏸️ Pausado"
        if lock and lock["en_ejecucion"] and lock["periodo"] == periodo:
            activo_txt += " · 🔵 Ejecutando"

        info = "-"
        if ultimo:
            info = f"{ultimo['filas']} filas" if ultimo["status"] == "OK" else (ultimo["mensaje_error"] or "-")

        corte_txt = "🧊 Congelado" if cfg["corte_generado"] else "⏳ Pendiente"
        filas.append({
            "ETL": "Índice de Permanencia",
            "Detalle": f"Periodo {periodo} · Corte {corte_txt}",
            "Programado": CRON_PERMANENCIA,
            "Activo": activo_txt,
            "Última ejecución": _formatear_fecha(ultimo["finalizado_en"]) if ultimo else "Nunca",
            "Estado": _estado_txt(ultimo),
            "Info": info,
            "_activo": bool(cfg["activo"]),
            "_ejecutando": bool(lock and lock["en_ejecucion"] and lock["periodo"] == periodo),
            "_estado_key": ultimo["status"] if ultimo else "NUNCA",
        })
    return filas


def render():
    if st.session_state.get("rol") != "ADMIN":
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return
    st.subheader("Configuración ETL - Resumen")
    render_body()


def render_body():
    """Cuerpo de la pantalla, sin el chequeo de rol ni el subheader propio."""
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(
            "Visión general de todos los procesos ETL automatizados: qué está activo, a qué hora "
            "corre, y cómo salió la última ejecución. Para actuar (pausar, editar, ejecutar ahora), "
            "vaya a la pantalla propia de cada ETL."
        )
    with c2:
        if st.button("Actualizar", icon=":material/refresh:", use_container_width=True):
            st.rerun()

    filas = []
    filas += _filas_encuestas()
    filas += _filas_alumnos()
    filas += _filas_asistencias()
    filas += _filas_permanencia()

    if not filas:
        st.info("Todavía no hay ningún ETL configurado.")
        return

    fallando = [f for f in filas if f["_estado_key"] == "ERROR"]
    if fallando:
        st.warning(f"⚠️ {len(fallando)} proceso(s) con la última ejecución en error. Revise la columna 'Info'.")

    fc1, fc2, fc3, fc4 = st.columns([2, 2, 1.5, 1.5])
    with fc1:
        etl_opciones = sorted({f["ETL"] for f in filas})
        etl_sel = st.multiselect("ETL", options=etl_opciones, default=etl_opciones, key="resumen_filtro_etl")
    with fc2:
        estado_sel = st.multiselect(
            "Estado",
            options=ESTADO_FILTRO_OPCIONES,
            default=ESTADO_FILTRO_OPCIONES,
            format_func=lambda k: ESTADO_FILTRO_LABELS[k],
            key="resumen_filtro_estado",
        )
    with fc3:
        activo_sel = st.multiselect(
            "Activo",
            options=["Activo", "Pausado"],
            default=["Activo", "Pausado"],
            key="resumen_filtro_activo",
        )
    with fc4:
        solo_ejecutando = st.checkbox("Solo en ejecución", key="resumen_filtro_ejecutando")

    filas_filtradas = [
        f for f in filas
        if f["ETL"] in etl_sel
        and f["_estado_key"] in estado_sel
        and (("Activo" in activo_sel and f["_activo"]) or ("Pausado" in activo_sel and not f["_activo"]))
        and (not solo_ejecutando or f["_ejecutando"])
    ]

    if not filas_filtradas:
        st.info("Ningún ETL coincide con los filtros seleccionados.")
        return

    columnas_visibles = ["ETL", "Detalle", "Programado", "Activo", "Última ejecución", "Estado", "Info"]
    df = pd.DataFrame(filas_filtradas, columns=columnas_visibles)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(filas_filtradas)} de {len(filas)} proceso(s).")
