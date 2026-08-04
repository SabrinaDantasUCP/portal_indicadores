from datetime import datetime

import streamlit as st

from utils import db_pia
from utils.system_logging import log_exception
from services.data.encuestas import SEDES
from services.etl.encuestas_etl import derivar_parametros_periodo
from services.etl.encuesta_runner import ejecutar_config
from services.etl import vpn_control


TIPO_OPTIONS = [
    ("ALUMNO_DOCENTE", "Alumno → Docente"),
    ("AUTOEVAL_DOCENTE", "Autoevaluación Docente"),
    ("EVALUACION_PARES", "Evaluación de Pares (próximamente)"),
]
TIPO_LABELS = dict(TIPO_OPTIONS)

# scope_mode no se expone en el formulario: es un detalle técnico de cómo se
# resuelve el archivo (ver services/data/encuestas.py) y ya tiene un default
# sensato por tipo, igual al que existía hardcodeado antes de esta pantalla.
SCOPE_MODE_DEFAULT = {
    "ALUMNO_DOCENTE": "SEGUE_VERSION",
    "AUTOEVAL_DOCENTE": "GLOBAL",
    "EVALUACION_PARES": "GLOBAL",
}

_TIPO_SLUG = {
    "ALUMNO_DOCENTE": "encuestas_alumnos_al_docente",
    "AUTOEVAL_DOCENTE": "encuestas_docente_autoeval",
    "EVALUACION_PARES": "encuestas_evaluacion_pares",
}


def _sugerir_dataset_name(tipo, periodo):
    periodo_slug = (periodo or "").replace(".", "").replace(" ", "")
    return f"{_TIPO_SLUG.get(tipo, 'encuesta')}_{periodo_slug}"


def _mostrar_preview_periodo(periodo):
    """Muestra cómo se va a interpretar el periodo (año/subperiodo/semestre
    bio) antes de guardar, y devuelve True si es válido."""
    try:
        parametros = derivar_parametros_periodo(periodo)
        st.caption(
            f"→ Año: {parametros['anho']} · Subperiodo: {parametros['subperiodo']} "
            f"· Semestre (bio): {parametros['semestre_bio']}"
        )
        return True
    except ValueError as e:
        st.caption(f"⚠️ {e}")
        return False


def _registrar_run(config_id, disparado_por, actor_usuario_id=None):
    iniciado_en = datetime.now()
    config = db_pia.get_encuesta_etl_config(config_id)
    resultado = ejecutar_config(config)
    finalizado_en = datetime.now()

    db_pia.registrar_encuesta_etl_run(
        config_id=config_id,
        disparado_por=disparado_por,
        status=resultado["status"],
        iniciado_en=iniciado_en,
        finalizado_en=finalizado_en,
        filas_generadas=resultado["filas"],
        mensaje_error=resultado["mensaje_error"],
        actor_usuario_id=actor_usuario_id,
    )
    return resultado


@st.dialog("Nueva Configuración de ETL de Encuesta")
def modal_crear_config():
    tipo = st.selectbox(
        "Tipo de Encuesta *",
        options=[code for code, _ in TIPO_OPTIONS],
        format_func=lambda c: TIPO_LABELS[c],
    )
    if tipo == "EVALUACION_PARES":
        st.warning(
            "El pipeline de 'Evaluación de Pares' todavía no está implementado. "
            "Puede cadastrar la configuración, pero 'Ejecutar ahora' fallará hasta que se implemente."
        )

    c1, c2 = st.columns(2)
    with c1:
        sede = st.selectbox("Sede *", options=SEDES)
        carrera = st.text_input("Carrera *", value="Medicina")
    with c2:
        periodo = st.text_input("Periodo *", value="2026.1", help="Ej: 2026.1, 2026.2")
        id_encuesta_externa = st.number_input("Id de la Encuesta (Academico.Encuesta) *", min_value=1, value=1, step=1)

    periodo_valido = _mostrar_preview_periodo(periodo)

    dataset_name = st.text_input(
        "Nombre del dataset (identificador interno)",
        value=_sugerir_dataset_name(tipo, periodo),
        help="Se usa para nombrar el archivo generado. Se sugiere automáticamente, pero puede editarlo.",
    )

    if st.button("Crear Configuración", type="primary", use_container_width=True):
        if sede and periodo.strip() and carrera.strip() and dataset_name.strip() and periodo_valido:
            try:
                config_id = db_pia.add_encuesta_etl_config(
                    tipo_encuesta=tipo,
                    sede=sede,
                    periodo=periodo.strip(),
                    carrera=carrera.strip(),
                    id_encuesta_externa=int(id_encuesta_externa),
                    dataset_name=dataset_name.strip(),
                    scope_mode=SCOPE_MODE_DEFAULT[tipo],
                    creado_por=st.session_state.get("user_id"),
                )
                db_pia.log_audit_event(
                    "encuesta_etl_config_created",
                    detalle={"config_id": config_id, "tipo": tipo, "sede": sede, "periodo": periodo, "carrera": carrera},
                )
                st.session_state.temp_msg_encuesta_etl = "Configuración creada exitosamente."
                st.rerun()
            except Exception as e:
                log_exception("Error al crear configuración de ETL de encuesta", e)
                st.error("Error al crear: probablemente ya exista una configuración igual (tipo/sede/periodo/carrera) o el dataset_name ya está en uso.")
        else:
            st.warning("Debe completar todos los campos obligatorios (*).")


@st.dialog("Editar Configuración de ETL de Encuesta")
def modal_editar_config(cfg):
    st.caption(f"Tipo: **{TIPO_LABELS.get(cfg['tipo_encuesta'], cfg['tipo_encuesta'])}** (no editable)")

    c1, c2 = st.columns(2)
    with c1:
        sede = st.selectbox("Sede *", options=SEDES, index=SEDES.index(cfg["sede"]) if cfg["sede"] in SEDES else 0)
        carrera = st.text_input("Carrera *", value=cfg["carrera"])
    with c2:
        periodo = st.text_input("Periodo *", value=cfg["periodo"])
        id_encuesta_externa = st.number_input(
            "Id de la Encuesta (Academico.Encuesta) *", min_value=1, value=int(cfg["id_encuesta_externa"]), step=1
        )

    periodo_valido = _mostrar_preview_periodo(periodo)

    dataset_name = st.text_input("Nombre del dataset (identificador interno)", value=cfg["dataset_name"])

    if st.button("Guardar Cambios", type="primary", use_container_width=True):
        if sede and periodo.strip() and carrera.strip() and dataset_name.strip() and periodo_valido:
            try:
                db_pia.update_encuesta_etl_config(
                    config_id=cfg["id"],
                    sede=sede,
                    periodo=periodo.strip(),
                    carrera=carrera.strip(),
                    id_encuesta_externa=int(id_encuesta_externa),
                    dataset_name=dataset_name.strip(),
                    scope_mode=cfg["scope_mode"],
                )
                db_pia.log_audit_event(
                    "encuesta_etl_config_updated",
                    detalle={"config_id": cfg["id"], "sede": sede, "periodo": periodo, "carrera": carrera},
                )
                st.session_state.temp_msg_encuesta_etl = "Configuración actualizada exitosamente."
                st.rerun()
            except Exception as e:
                log_exception("Error al actualizar configuración de ETL de encuesta", e)
                st.error("Error al actualizar (posiblemente el dataset_name ya está en uso, o ya existe otra config igual).")
        else:
            st.warning("Debe completar todos los campos obligatorios (*).")


def _formatear_fecha(dt):
    if not dt:
        return "-"
    try:
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except AttributeError:
        return str(dt)


def render():
    if st.session_state.get("rol") != "ADMIN":
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return
    st.subheader("Encuestas - Configuración ETL")
    render_body()


def render_body():
    """Cuerpo de la pantalla, sin el chequeo de rol ni el subheader propio —
    pensado para ser embebido dentro de una pestaña (ver modules/config_etl.py),
    que ya hace el chequeo de ADMIN una sola vez para todas las pestañas."""
    st.markdown(
        "Cadastre qué tipo de encuesta, periodo y carrera deben actualizarse "
        "automáticamente (cron 3x al día). El botón **Ejecutar ahora** dispara "
        "la primera carga de datos de inmediato."
    )

    if "temp_msg_encuesta_etl" in st.session_state:
        st.success(st.session_state.temp_msg_encuesta_etl)
        del st.session_state.temp_msg_encuesta_etl

    configs = db_pia.get_encuesta_etl_configs()
    ultimos_runs = db_pia.get_ultimo_run_por_config()

    fallas_activas = [
        c for c in configs
        if c["activo"] and ultimos_runs.get(c["id"], {}).get("status") == "ERROR"
    ]
    if fallas_activas:
        nombres = ", ".join(
            f"{TIPO_LABELS.get(c['tipo_encuesta'], c['tipo_encuesta'])} ({c['sede']}/{c['periodo']}/{c['carrera']})"
            for c in fallas_activas
        )
        st.warning(
            f"⚠️ Hay configuraciones activas cuya última ejecución falló: {nombres}. "
            "Revise el mensaje de error de cada una (probablemente la VPN del ERP esté caída)."
        )

    c_head1, c_head2 = st.columns([3, 1])
    with c_head1:
        st.markdown("### Configuraciones")
    with c_head2:
        if st.button("Nueva Configuración", icon=":material/add:", type="primary", use_container_width=True):
            modal_crear_config()

    st.markdown("---")

    if not configs:
        st.info("Aún no hay configuraciones de ETL de encuestas registradas.")
        return

    for cfg in configs:
        ultimo = ultimos_runs.get(cfg["id"])
        with st.container(border=True):
            c1, c2, c3 = st.columns([2.5, 2, 2])
            with c1:
                st.markdown(f"**{TIPO_LABELS.get(cfg['tipo_encuesta'], cfg['tipo_encuesta'])}**")
                st.caption(f"{cfg['sede']} · {cfg['periodo']} · {cfg['carrera']}")
                st.caption(f"Id encuesta: {cfg['id_encuesta_externa']} · dataset: `{cfg['dataset_name']}`")
            with c2:
                if ultimo:
                    icono = "✅" if ultimo["status"] == "OK" else "❌"
                    st.markdown(f"{icono} Última ejecución: {_formatear_fecha(ultimo['finalizado_en'])}")
                    st.caption(f"Disparado por: {ultimo['disparado_por']}")
                    if ultimo["status"] == "OK":
                        st.caption(f"Filas generadas: {ultimo['filas_generadas']}")
                    else:
                        st.caption(f"Error: {ultimo['mensaje_error']}")
                else:
                    st.caption("Todavía no se ejecutó ninguna vez.")
            with c3:
                activo_actual = bool(cfg["activo"])
                nuevo_estado = st.toggle(
                    "Actualización automática",
                    value=activo_actual,
                    key=f"activo_{cfg['id']}",
                    help="Si está pausada, no se ejecuta en el cron 3x al día, pero los datos ya generados siguen visibles en el dashboard.",
                )
                if nuevo_estado != activo_actual:
                    db_pia.toggle_encuesta_etl_config_activo(cfg["id"], nuevo_estado)
                    db_pia.log_audit_event(
                        "encuesta_etl_config_activo_changed",
                        detalle={"config_id": cfg["id"], "activo": nuevo_estado},
                    )
                    st.rerun()

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("Editar", icon=":material/edit:", key=f"editar_{cfg['id']}", use_container_width=True):
                        modal_editar_config(cfg)
                with bcol2:
                    if st.button("Ejecutar ahora", icon=":material/play_arrow:", key=f"ejecutar_{cfg['id']}", use_container_width=True):
                        try:
                            with st.spinner("Conectando VPN del ERP..."):
                                vpn_control.conectar()
                        except vpn_control.VpnError as e:
                            st.error(str(e))
                        else:
                            try:
                                with st.spinner("Ejecutando ETL (consultando bio + ERP)..."):
                                    resultado = _registrar_run(
                                        cfg["id"], disparado_por="MANUAL", actor_usuario_id=st.session_state.get("user_id")
                                    )
                            finally:
                                vpn_control.desconectar()

                            if resultado["status"] == "OK":
                                st.success(f"Ejecución completada: {resultado['filas']} filas generadas.")
                            else:
                                st.error(f"Falló la ejecución: {resultado['mensaje_error']}")
