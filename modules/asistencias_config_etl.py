import threading
from datetime import datetime

import streamlit as st

from utils import db_pia
from utils.system_logging import log_exception
from services.etl.asistencias_runner import ejecutar_asistencias_etl
from services.etl.encuestas_etl import derivar_parametros_periodo


STATUS_ICONOS = {"OK": "✅", "ERROR": "❌", "CANCELADO": "⏹️"}

ANO_SYSEDUCA_MIN = 2021
ANO_SYSEDUCA_MAX_EXTRA = 0  # SysEduca es la fuente VIEJA (antes de 2025.2); no tiene sentido ofrecer años futuros

PERIODO_BIOMETRIA_MIN_ANHO = 2025  # Biometría arranca en 2025.2
PERIODO_BIOMETRIA_MAX_EXTRA = 1    # cuántos años por delante del actual se ofrecen


def _opciones_anos_syseduca(extra=None):
    """Rango fijo + cualquier año ya guardado en la config (necesario porque
    accept_new_options permite guardar años fuera del rango fijo -- si no se
    los incluye acá, st.multiselect revienta al usar `default` con un valor
    que no está en `options`)."""
    ano_actual = datetime.now().year
    opciones = set(range(ANO_SYSEDUCA_MIN, min(ano_actual, 2025) + 1))
    if extra:
        opciones.update(int(a) for a in extra)
    return sorted(opciones)


def _opciones_periodos_biometria(extra=None):
    ano_actual = datetime.now().year
    opciones = {"2025.2"}
    for anho in range(2026, ano_actual + PERIODO_BIOMETRIA_MAX_EXTRA + 2):
        opciones.update([f"{anho}.1", f"{anho}.2"])
    if extra:
        opciones.update(str(p) for p in extra)
    return sorted(opciones)


def _parsear_anos_syseduca(valores):
    """st.multiselect(accept_new_options=True) devuelve una lista mixta (ints
    de las opciones predefinidas + strings tipeados a mano). Convierte todo a
    una lista limpia de enteros ordenados; lanza ValueError con un mensaje
    legible si algún valor tipeado no es un año válido."""
    anos = []
    for v in valores:
        try:
            anos.append(int(v))
        except (TypeError, ValueError):
            raise ValueError(f"'{v}' no es un año válido (debe ser un número, ej. 2027).")
    return sorted(set(anos))


def _parsear_periodos_biometria(valores):
    """Valida que cada periodo (predefinido o tipeado a mano) tenga el
    formato 'AAAA.S' esperado por derivar_parametros_periodo."""
    periodos = []
    for v in valores:
        v = str(v).strip()
        try:
            derivar_parametros_periodo(v)
        except ValueError as e:
            raise ValueError(f"Periodo '{v}' inválido: {e}")
        periodos.append(v)
    return sorted(set(periodos))


def _formatear_fecha(dt):
    if not dt:
        return "-"
    try:
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except AttributeError:
        return str(dt)


def _pipeline_worker(anos_syseduca, periodos_biometria, progress, cancel_event, disparado_por, actor_usuario_id):
    """Corre en un thread aparte -- ver el mismo comentario en
    modules/alumnos_config_etl.py: NUNCA llamar a `st.*` acá dentro."""

    def on_progress(index, total, etiqueta):
        progress["index"] = index
        progress["total"] = total
        progress["etiqueta"] = etiqueta

    iniciado_en = datetime.now()
    try:
        resultado = ejecutar_asistencias_etl(
            anos_syseduca, periodos_biometria, on_progress=on_progress, cancel_check=cancel_event.is_set
        )
    except Exception as exc:
        resultado = {
            "status": "ERROR", "filas_v1": None, "filas_v2": None,
            "anos_con_error": anos_syseduca, "periodos_con_error": periodos_biometria,
            "mensaje_error": str(exc),
        }
    finalizado_en = datetime.now()

    try:
        db_pia.registrar_asistencias_etl_run(
            disparado_por=disparado_por,
            status=resultado["status"],
            iniciado_en=iniciado_en,
            finalizado_en=finalizado_en,
            anos_syseduca_procesados=anos_syseduca,
            periodos_biometria_procesados=periodos_biometria,
            filas_v1=resultado["filas_v1"],
            filas_v2=resultado["filas_v2"],
            mensaje_error=resultado["mensaje_error"],
            actor_usuario_id=actor_usuario_id,
        )
        db_pia.log_audit_event(
            "asistencias_etl_ejecutado_manual" if disparado_por == "MANUAL" else "asistencias_etl_ejecutado_cron",
            detalle={"anos_syseduca": anos_syseduca, "periodos_biometria": periodos_biometria, "status": resultado["status"]},
            actor_usuario_id=actor_usuario_id,
        )
    finally:
        db_pia.release_asistencias_etl_lock()

    progress["resultado"] = resultado
    progress["done"] = True


@st.dialog("Confirmar ejecución del ETL de Asistencias")
def modal_confirmar_ejecucion(anos_syseduca, periodos_biometria):
    st.warning(
        f"Esto va a consultar SysEduca (MySQL, {len(anos_syseduca)} año(s): "
        f"{', '.join(str(a) for a in sorted(anos_syseduca))}) y Biometría (Postgres, "
        f"{len(periodos_biometria)} periodo(s): {', '.join(sorted(periodos_biometria))}), "
        "lo que puede demorar bastante.\n\n"
        "¿Desea ejecutar el ETL ahora de todas formas?"
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", use_container_width=True, key="asis_cancelar_modal"):
            st.rerun()
    with c2:
        if st.button("Sí, ejecutar", type="primary", use_container_width=True, key="asis_confirmar_modal"):
            actor_usuario_id = st.session_state.get("user_id")
            if not db_pia.try_acquire_asistencias_etl_lock("MANUAL", actor_usuario_id):
                estado = db_pia.get_asistencias_etl_lock_status()
                st.error(
                    f"Ya hay una ejecución en curso (disparado por {estado['disparado_por']} "
                    f"desde {_formatear_fecha(estado['iniciado_en'])}). Espere a que termine."
                )
                return

            progress = {
                "index": 0, "total": len(anos_syseduca) + len(periodos_biometria), "etiqueta": None,
                "resultado": None, "done": False,
            }
            cancel_event = threading.Event()
            thread = threading.Thread(
                target=_pipeline_worker,
                args=(anos_syseduca, periodos_biometria, progress, cancel_event, "MANUAL", actor_usuario_id),
                daemon=True,
            )
            st.session_state.asistencias_etl_job = {
                "thread": thread, "progress": progress, "cancel_event": cancel_event,
                "anos_syseduca": anos_syseduca, "periodos_biometria": periodos_biometria,
            }
            thread.start()
            st.rerun()


@st.fragment(run_every=1)
def _render_progreso_ejecucion():
    job = st.session_state.get("asistencias_etl_job")
    if job is None:
        return

    thread = job["thread"]
    progress = job["progress"]
    cancel_event = job["cancel_event"]

    if thread.is_alive():
        total = progress["total"]
        idx = progress["index"]
        etiqueta = progress["etiqueta"]

        if etiqueta is not None:
            st.info(f"Ejecutando ETL de asistencias... Procesando **{etiqueta}** ({idx}/{total}).")
        else:
            st.info("Ejecutando ETL de asistencias... Iniciando.")
        st.progress(idx / total if total else 0.0)

        if cancel_event.is_set():
            st.caption(
                "Deteniendo — esperando a que termine el año/periodo en curso "
                "(no se interrumpe una consulta ya en marcha)."
            )
        else:
            if st.button("Detener", icon=":material/stop:", key="btn_detener_asistencias_etl"):
                cancel_event.set()
        return

    resultado = progress.get("resultado") or {
        "status": "ERROR", "mensaje_error": "El proceso terminó sin resultado (revise los logs).",
        "filas_v1": None, "filas_v2": None,
    }
    if resultado["status"] == "OK":
        st.session_state.temp_msg_asistencias_etl = (
            f"Ejecución completada: asistencia_unificada_v1={resultado['filas_v1']} filas, "
            f"asistencia_unificada_v2={resultado['filas_v2']} filas."
        )
    elif resultado["status"] == "CANCELADO":
        st.session_state.temp_msg_asistencias_etl_cancelado = resultado["mensaje_error"]
    else:
        st.session_state.temp_msg_asistencias_etl_error = resultado["mensaje_error"]

    del st.session_state.asistencias_etl_job
    st.rerun()


def render():
    if st.session_state.get("rol") != "ADMIN":
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return
    st.subheader("Asistencias - Configuración ETL")
    render_body()


def render_body():
    """Cuerpo de la pantalla, sin el chequeo de rol ni el subheader propio."""
    st.markdown(
        "Configure qué años de **SysEduca** (fuente vieja, antes de 2025.2) y qué "
        "**periodos de Biometría** (fuente nueva, desde 2025.2) entran en la extracción. "
        "El cron nocturno (**03:00**) corre automáticamente si está activo. El botón "
        "**Ejecutar ahora** dispara la extracción de inmediato."
    )

    if "temp_msg_asistencias_etl" in st.session_state:
        st.success(st.session_state.temp_msg_asistencias_etl)
        del st.session_state.temp_msg_asistencias_etl
    if "temp_msg_asistencias_etl_error" in st.session_state:
        st.error(f"Falló la ejecución: {st.session_state.temp_msg_asistencias_etl_error}")
        del st.session_state.temp_msg_asistencias_etl_error
    if "temp_msg_asistencias_etl_cancelado" in st.session_state:
        st.warning(f"Ejecución cancelada: {st.session_state.temp_msg_asistencias_etl_cancelado}")
        del st.session_state.temp_msg_asistencias_etl_cancelado

    config = db_pia.get_asistencias_etl_config()
    if not config:
        st.error("No se encontró la configuración de ETL de asistencias (pia_asistencias_etl_config).")
        return

    ultimo = db_pia.get_ultimo_asistencias_etl_run()

    if config["activo"] and ultimo and ultimo["status"] == "ERROR":
        st.warning(
            "⚠️ La última ejecución del ETL de asistencias falló. Revise el mensaje de "
            "error más abajo (probablemente SysEduca o Biometría estén inaccesibles)."
        )

    with st.container(border=True):
        st.markdown("### Configuración")

        anos_syseduca_raw = st.multiselect(
            "Años a incluir — SysEduca (antes de 2025.2) *",
            options=_opciones_anos_syseduca(extra=config["anos_syseduca"]),
            default=config["anos_syseduca"],
            accept_new_options=True,
            help="Cada año dispara una consulta separada a ucp.coord_aula (MySQL). "
                 "Puede escribir un año que no esté en la lista y presionar Enter para agregarlo.",
        )
        try:
            anos_syseduca_sel = _parsear_anos_syseduca(anos_syseduca_raw)
        except ValueError as e:
            st.error(str(e))
            anos_syseduca_sel = []

        periodos_biometria_raw = st.multiselect(
            "Periodos a incluir — Biometría (desde 2025.2) *",
            options=_opciones_periodos_biometria(extra=config["periodos_biometria"]),
            default=config["periodos_biometria"],
            accept_new_options=True,
            help="Cada periodo (ej. '2025.2') dispara una consulta separada a attendance (Postgres). "
                 "Puede escribir un periodo que no esté en la lista (formato 'AAAA.S') y presionar Enter.",
        )
        try:
            periodos_biometria_sel = _parsear_periodos_biometria(periodos_biometria_raw)
        except ValueError as e:
            st.error(str(e))
            periodos_biometria_sel = []

        activo_actual = bool(config["activo"])
        nuevo_estado = st.toggle(
            "Actualización automática (cron diario 03:00)",
            value=activo_actual,
            help="Si está pausada, el cron nocturno no ejecuta el ETL, pero los datos ya generados siguen visibles en el dashboard.",
        )

        if st.button("Guardar Configuración", type="primary", icon=":material/save:", key="asis_guardar_config"):
            if not anos_syseduca_sel and not periodos_biometria_sel:
                st.warning("Debe seleccionar al menos un año o un periodo.")
            else:
                db_pia.update_asistencias_etl_config(anos_syseduca_sel, periodos_biometria_sel, nuevo_estado)
                db_pia.log_audit_event(
                    "asistencias_etl_config_actualizado",
                    detalle={"anos_syseduca": anos_syseduca_sel, "periodos_biometria": periodos_biometria_sel, "activo": nuevo_estado},
                )
                st.success("Configuración guardada.")
                st.rerun()

    st.markdown("---")

    job = st.session_state.get("asistencias_etl_job")
    if job is not None:
        _render_progreso_ejecucion()
    else:
        lock_estado = db_pia.get_asistencias_etl_lock_status()
        bloqueado_por_otro = bool(lock_estado and lock_estado["en_ejecucion"])
        if bloqueado_por_otro:
            st.warning(
                f"⚠️ Ya hay una ejecución del ETL de asistencias en curso, disparada por "
                f"**{lock_estado['disparado_por']}** desde {_formatear_fecha(lock_estado['iniciado_en'])} "
                "(otra pestaña/sesión, o el cron nocturno). Espere a que termine antes de iniciar otra."
            )

        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown("### Última ejecución")
            if ultimo:
                icono = STATUS_ICONOS.get(ultimo["status"], "❓")
                st.markdown(f"{icono} Finalizada: {_formatear_fecha(ultimo['finalizado_en'])}")
                st.caption(
                    f"Disparado por: {ultimo['disparado_por']} · "
                    f"SysEduca: {ultimo['anos_syseduca_procesados'] or '-'} · "
                    f"Biometría: {ultimo['periodos_biometria_procesados'] or '-'}"
                )
                if ultimo["status"] == "OK":
                    st.caption(f"Filas generadas: v1={ultimo['filas_v1']}, v2={ultimo['filas_v2']}")
                    if ultimo["mensaje_error"]:
                        st.caption(f"Aviso: {ultimo['mensaje_error']}")
                else:
                    st.caption(f"{'Cancelado' if ultimo['status'] == 'CANCELADO' else 'Error'}: {ultimo['mensaje_error']}")
            else:
                st.info("Todavía no se ejecutó ninguna vez.")
        with c2:
            if st.button(
                "Ejecutar ahora", icon=":material/play_arrow:", type="primary",
                use_container_width=True, disabled=bloqueado_por_otro, key="asis_ejecutar_ahora",
            ):
                if not anos_syseduca_sel and not periodos_biometria_sel:
                    st.warning("Seleccione al menos un año o un periodo antes de ejecutar.")
                else:
                    modal_confirmar_ejecucion(anos_syseduca_sel, periodos_biometria_sel)
