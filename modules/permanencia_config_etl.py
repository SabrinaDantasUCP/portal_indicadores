import threading
from datetime import date, datetime

import streamlit as st

from utils import db_pia
from utils.system_logging import log_exception
from services.calculations.permanencia import get_periodo_config
from services.data.permanencia import fechas_configuradas, limpiar_cache_fechas
from services.etl.permanencia_etl import derivar_ids_periodo
from services.etl.permanencia_runner import ejecutar_permanencia_etl


STATUS_ICONOS = {"OK": "✅", "ERROR": "❌", "CANCELADO": "⏹️"}

# Las fechas de "inicio de clases" se siguen guardando en pia_config_permanencia
# (vía db_pia.set_permanencia_fechas / fechas_configuradas), que es lo que ya
# lee en vivo el dashboard (services/data/permanencia.get_periodo_config_efectivo).
# Acá solo se cambia DÓNDE se editan: antes en una pantalla aparte (Fechas de
# Inicio de Clases), ahora dentro del mismo card de cada periodo, junto con la
# fecha de corte.
CAMPOS_INICIO_CLASES = (
    ("limite_primer_semestre", "Inicio de clases · alumnos de 1º semestre"),
    ("limite_otros_semestres", "Inicio de clases · alumnos antiguos"),
)


def _a_fecha(valor):
    return date.fromisoformat(valor) if isinstance(valor, str) else valor


def _fechas_inicio_vigentes(periodo):
    """Fechas de inicio de clases vigentes para `periodo`: las guardadas en
    pia_config_permanencia si existen, si no las por defecto del sistema
    (services.calculations.permanencia.PERMANENCIA_PERIODOS). Si el periodo
    ni siquiera tiene default hardcodeado ahí, cae en hoy (el admin debe
    igual definir las fechas reales)."""
    configurado = fechas_configuradas().get(periodo) or {}
    try:
        por_defecto = get_periodo_config(periodo)
    except KeyError:
        por_defecto = {}

    vigente = {}
    for campo, _ in CAMPOS_INICIO_CLASES:
        valor = configurado.get(campo) or por_defecto.get(campo)
        vigente[campo] = _a_fecha(valor) if valor else date.today()
    return vigente, por_defecto


def _formatear_fecha(dt):
    if not dt:
        return "-"
    try:
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except AttributeError:
        return str(dt)


def _formatear_fecha_simple(d):
    if not d:
        return "-"
    try:
        return d.strftime("%d/%m/%Y")
    except AttributeError:
        return str(d)


def _pipeline_worker(periodo, fecha_corte, corte_generado, progress, cancel_event, disparado_por, actor_usuario_id):
    """Corre en un thread aparte -- ver el mismo comentario en
    modules/alumnos_config_etl.py: NUNCA llamar a `st.*` acá dentro."""

    def on_progress(index, total, etiqueta):
        progress["index"] = index
        progress["total"] = total
        progress["etiqueta"] = etiqueta

    iniciado_en = datetime.now()
    try:
        resultado = ejecutar_permanencia_etl(
            periodo, fecha_corte, corte_generado, on_progress=on_progress, cancel_check=cancel_event.is_set
        )
    except Exception as exc:
        resultado = {
            "status": "ERROR", "filas": None, "corte_generado_ahora": False, "mensaje_error": str(exc),
        }
    finalizado_en = datetime.now()

    try:
        db_pia.registrar_permanencia_etl_run(
            periodo=periodo,
            disparado_por=disparado_por,
            status=resultado["status"],
            iniciado_en=iniciado_en,
            finalizado_en=finalizado_en,
            filas=resultado["filas"],
            corte_generado_en_este_run=resultado["corte_generado_ahora"],
            mensaje_error=resultado["mensaje_error"],
            actor_usuario_id=actor_usuario_id,
        )
        if resultado["corte_generado_ahora"]:
            db_pia.marcar_permanencia_corte_generado(periodo)
        db_pia.log_audit_event(
            "permanencia_etl_ejecutado_manual" if disparado_por == "MANUAL" else "permanencia_etl_ejecutado_cron",
            detalle={"periodo": periodo, "status": resultado["status"], "corte_generado_ahora": resultado["corte_generado_ahora"]},
            actor_usuario_id=actor_usuario_id,
        )
    finally:
        db_pia.release_permanencia_etl_lock()

    progress["resultado"] = resultado
    progress["done"] = True


@st.dialog("Confirmar ejecución del ETL de Permanencia")
def modal_confirmar_ejecucion(periodo, fecha_corte, corte_generado):
    st.warning(
        f"Esto va a consultar matrículas, facturas (con negociaciones recursivas), auditoría y "
        f"notas para el periodo **{periodo}**. Puede demorar varios minutos.\n\n"
        "¿Desea ejecutar el ETL ahora de todas formas?"
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", use_container_width=True, key="perm_cancelar_modal"):
            st.rerun()
    with c2:
        if st.button("Sí, ejecutar", type="primary", use_container_width=True, key="perm_confirmar_modal"):
            actor_usuario_id = st.session_state.get("user_id")
            if not db_pia.try_acquire_permanencia_etl_lock("MANUAL", periodo, actor_usuario_id):
                estado = db_pia.get_permanencia_etl_lock_status()
                st.error(
                    f"Ya hay una ejecución en curso (periodo {estado['periodo']}, disparado por "
                    f"{estado['disparado_por']} desde {_formatear_fecha(estado['iniciado_en'])}). Espere a que termine."
                )
                return

            progress = {"index": 0, "total": 6, "etiqueta": None, "resultado": None, "done": False}
            cancel_event = threading.Event()
            thread = threading.Thread(
                target=_pipeline_worker,
                args=(periodo, fecha_corte, corte_generado, progress, cancel_event, "MANUAL", actor_usuario_id),
                daemon=True,
            )
            st.session_state.permanencia_etl_job = {
                "thread": thread, "progress": progress, "cancel_event": cancel_event, "periodo": periodo,
            }
            thread.start()
            st.rerun()


@st.fragment(run_every=1)
def _render_progreso_ejecucion():
    job = st.session_state.get("permanencia_etl_job")
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
            st.info(f"Ejecutando ETL de permanencia ({job['periodo']})... {etiqueta} ({idx}/{total}).")
        else:
            st.info(f"Ejecutando ETL de permanencia ({job['periodo']})... Iniciando.")
        st.progress(idx / total if total else 0.0)

        if cancel_event.is_set():
            st.caption(
                "Deteniendo — esperando a que termine el paso en curso "
                "(no se interrumpe una consulta ya en marcha)."
            )
        else:
            if st.button("Detener", icon=":material/stop:", key="btn_detener_permanencia_etl"):
                cancel_event.set()
        return

    resultado = progress.get("resultado") or {
        "status": "ERROR", "mensaje_error": "El proceso terminó sin resultado (revise los logs).",
        "filas": None, "corte_generado_ahora": False,
    }
    if resultado["status"] == "OK":
        msg = f"Ejecución completada: {resultado['filas']} filas."
        if resultado["corte_generado_ahora"]:
            msg += " Snapshot de fecha de corte CONGELADO en este run."
        st.session_state.temp_msg_permanencia_etl = msg
    elif resultado["status"] == "CANCELADO":
        st.session_state.temp_msg_permanencia_etl_cancelado = resultado["mensaje_error"]
    else:
        st.session_state.temp_msg_permanencia_etl_error = resultado["mensaje_error"]

    del st.session_state.permanencia_etl_job
    st.rerun()


def _guardar_fechas_inicio_clases(periodo, nuevas):
    db_pia.set_permanencia_fechas(periodo, nuevas["limite_primer_semestre"], nuevas["limite_otros_semestres"])
    limpiar_cache_fechas()


@st.dialog("Nueva Configuración de Permanencia")
def modal_crear_config():
    periodo = st.text_input("Periodo *", value="", help="Formato 'AAAA.S', ej. '2026.2'.")
    fecha_corte = st.date_input("Fecha de corte *", value=date.today(), format="DD/MM/YYYY")
    activo = st.toggle("Actualización automática (cron 03:30)", value=True)

    st.markdown("##### Inicio de clases")
    st.caption(
        "Afecta el cálculo del Índice de Permanencia: una baja antes de esta fecha queda "
        "fuera del indicador."
    )
    nuevas = {}
    cols = st.columns(2)
    for col, (campo, etiqueta) in zip(cols, CAMPOS_INICIO_CLASES):
        with col:
            nuevas[campo] = st.date_input(etiqueta, value=date.today(), format="DD/MM/YYYY", key=f"nuevo_{campo}")

    if st.button("Crear Configuración", type="primary", use_container_width=True):
        periodo = periodo.strip()
        if not periodo:
            st.warning("Debe indicar un periodo.")
            return
        try:
            derivar_ids_periodo(periodo)  # valida formato + rango soportado (ANO_ID_TABLE)
        except ValueError as e:
            st.error(str(e))
            return
        try:
            db_pia.add_permanencia_etl_config(periodo, fecha_corte, activo)
            _guardar_fechas_inicio_clases(periodo, nuevas)
            db_pia.log_audit_event(
                "permanencia_etl_config_created",
                detalle={"periodo": periodo, "fecha_corte": str(fecha_corte), **{c: str(v) for c, v in nuevas.items()}},
            )
            st.session_state.temp_msg_permanencia_etl = f"Periodo {periodo} configurado."
            st.rerun()
        except Exception as e:
            log_exception("Error al crear configuración de permanencia", e)
            st.error("Error al crear: probablemente ya exista una configuración para ese periodo.")


@st.dialog("Editar Configuración de Permanencia")
def modal_editar_config(cfg):
    periodo = cfg["periodo"]
    st.caption(f"Periodo: **{periodo}** (no editable)")
    fecha_corte = st.date_input("Fecha de corte *", value=cfg["fecha_corte"], format="DD/MM/YYYY")
    activo = st.toggle("Actualización automática (cron 03:30)", value=bool(cfg["activo"]))

    if cfg["corte_generado"]:
        st.warning(
            "El snapshot de corte de este periodo YA fue congelado. Cambiar la fecha acá NO lo "
            "regenera solo -- use 'Reabrir corte' más abajo si de verdad quiere forzar una nueva congelación."
        )

    st.markdown("##### Inicio de clases")
    st.caption(
        "Afecta el cálculo del Índice de Permanencia: una baja antes de esta fecha queda "
        "fuera del indicador. Se ve enseguida en Índice de Permanencia → Visión General y Fecha de Corte."
    )
    vigente, por_defecto = _fechas_inicio_vigentes(periodo)
    nuevas = {}
    cols = st.columns(2)
    for col, (campo, etiqueta) in zip(cols, CAMPOS_INICIO_CLASES):
        with col:
            nuevas[campo] = st.date_input(etiqueta, value=vigente[campo], format="DD/MM/YYYY", key=f"editar_{periodo}_{campo}")
            if campo in por_defecto:
                st.caption(f"Por defecto: {_a_fecha(por_defecto[campo]).strftime('%d/%m/%Y')}")

    if st.button("Guardar Cambios", type="primary", use_container_width=True):
        db_pia.update_permanencia_etl_config(periodo, fecha_corte, activo)
        _guardar_fechas_inicio_clases(periodo, nuevas)
        db_pia.log_audit_event(
            "permanencia_etl_config_updated",
            detalle={"periodo": periodo, "fecha_corte": str(fecha_corte), "activo": activo,
                     **{c: str(v) for c, v in nuevas.items()}},
        )
        st.session_state.temp_msg_permanencia_etl = f"Periodo {periodo} actualizado."
        st.rerun()

    if cfg["corte_generado"]:
        st.markdown("---")
        if st.button("Reabrir corte (permitir re-congelar)", icon=":material/lock_open:", use_container_width=True):
            db_pia.resetear_permanencia_corte_generado(periodo)
            db_pia.log_audit_event("permanencia_etl_corte_reabierto", detalle={"periodo": periodo})
            st.session_state.temp_msg_permanencia_etl = (
                f"Corte de {periodo} reabierto: se va a congelar de nuevo en la próxima "
                "ejecución que ocurra en o después de la fecha de corte configurada."
            )
            st.rerun()


def _render_permanencia_config():
    st.markdown(
        "Configure, por periodo: la fecha de corte, las fechas de inicio de clases y si el cron "
        "nocturno (**03:30**) está activo. El cron recalcula la **visión general** todos los días "
        "para los periodos activos, y congela el snapshot de **Fecha de Corte** la primera vez que "
        "la ejecución ocurre en o después de esa fecha (nunca más se sobrescribe después de eso)."
    )

    if "temp_msg_permanencia_etl" in st.session_state:
        st.success(st.session_state.temp_msg_permanencia_etl)
        del st.session_state.temp_msg_permanencia_etl
    if "temp_msg_permanencia_etl_error" in st.session_state:
        st.error(f"Falló la ejecución: {st.session_state.temp_msg_permanencia_etl_error}")
        del st.session_state.temp_msg_permanencia_etl_error
    if "temp_msg_permanencia_etl_cancelado" in st.session_state:
        st.warning(f"Ejecución cancelada: {st.session_state.temp_msg_permanencia_etl_cancelado}")
        del st.session_state.temp_msg_permanencia_etl_cancelado

    job = st.session_state.get("permanencia_etl_job")
    if job is not None:
        _render_progreso_ejecucion()
        return

    lock_estado = db_pia.get_permanencia_etl_lock_status()
    bloqueado_por_otro = bool(lock_estado and lock_estado["en_ejecucion"])
    if bloqueado_por_otro:
        st.warning(
            f"⚠️ Ya hay una ejecución en curso (periodo **{lock_estado['periodo']}**, disparada por "
            f"**{lock_estado['disparado_por']}** desde {_formatear_fecha(lock_estado['iniciado_en'])}). "
            "Espere a que termine antes de iniciar otra."
        )

    c_head1, c_head2 = st.columns([3, 1])
    with c_head1:
        st.markdown("### Periodos configurados")
    with c_head2:
        if st.button("Nueva Configuración", icon=":material/add:", type="primary", use_container_width=True, key="perm_nueva_config"):
            modal_crear_config()

    st.markdown("---")

    configs = db_pia.get_permanencia_etl_configs()
    if not configs:
        st.info("Aún no hay periodos configurados.")
        return

    for cfg in configs:
        periodo = cfg["periodo"]
        ultimo = db_pia.get_ultimo_permanencia_etl_run(periodo)
        with st.container(border=True):
            c1, c2, c3 = st.columns([2.5, 2.5, 2.5])
            with c1:
                st.markdown(f"**Índice de Permanencia {periodo}**")
                corte_badge = "🧊 Congelado" if cfg["corte_generado"] else "⏳ Pendiente"
                st.caption(f"Fecha de corte: {_formatear_fecha_simple(cfg['fecha_corte'])} · {corte_badge}")
                vigente, _ = _fechas_inicio_vigentes(periodo)
                st.caption(
                    f"Inicio de clases: 1º sem. {_formatear_fecha_simple(vigente['limite_primer_semestre'])} · "
                    f"otros sem. {_formatear_fecha_simple(vigente['limite_otros_semestres'])}"
                )
            with c2:
                if ultimo:
                    icono = STATUS_ICONOS.get(ultimo["status"], "❓")
                    st.markdown(f"{icono} Última ejecución: {_formatear_fecha(ultimo['finalizado_en'])}")
                    st.caption(f"Disparado por: {ultimo['disparado_por']}")
                    if ultimo["status"] == "OK":
                        st.caption(f"Filas: {ultimo['filas']}")
                    else:
                        st.caption(f"{ultimo['mensaje_error']}")
                else:
                    st.caption("Todavía no se ejecutó ninguna vez.")
            with c3:
                activo_actual = bool(cfg["activo"])
                nuevo_estado = st.toggle(
                    "Actualización automática (cron 03:30)",
                    value=activo_actual,
                    key=f"perm_activo_{periodo}",
                )
                if nuevo_estado != activo_actual:
                    db_pia.update_permanencia_etl_config(periodo, cfg["fecha_corte"], nuevo_estado)
                    db_pia.log_audit_event(
                        "permanencia_etl_config_activo_changed",
                        detalle={"periodo": periodo, "activo": nuevo_estado},
                    )
                    st.rerun()

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("Editar", icon=":material/edit:", key=f"perm_editar_{periodo}", use_container_width=True):
                        modal_editar_config(cfg)
                with bcol2:
                    if st.button(
                        "Ejecutar ahora", icon=":material/play_arrow:", key=f"perm_ejecutar_{periodo}",
                        use_container_width=True, disabled=bloqueado_por_otro,
                    ):
                        modal_confirmar_ejecucion(periodo, cfg["fecha_corte"], bool(cfg["corte_generado"]))


def render():
    if st.session_state.get("rol") != "ADMIN":
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return
    st.subheader("Índice de Permanencia - Configuración ETL")
    render_body()


def render_body():
    """Cuerpo de la pantalla, sin el chequeo de rol ni el subheader propio."""
    _render_permanencia_config()
