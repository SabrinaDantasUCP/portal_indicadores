import os
import shutil
import threading
from datetime import date, datetime

import pandas as pd
import streamlit as st

from utils import db_pia
from utils.system_logging import log_exception
from services.etl.alumnos_etl import validar_egresados_columnas
from services.etl.alumnos_runner import ejecutar_alumnos_etl, EGRESADOS_XLSX_PATH


STATUS_ICONOS = {"OK": "✅", "ERROR": "❌", "CANCELADO": "⏹️"}


ANO_MIN = 2017
ANO_MAX_EXTRA = 2  # cuántos años por delante del actual se ofrecen como opción


def _opciones_anos(extra=None):
    """Rango fijo + cualquier año ya guardado en la config (necesario porque
    accept_new_options permite guardar años fuera del rango fijo -- si no se
    los incluye acá, st.multiselect revienta al usar `default` con un valor
    que no está en `options`)."""
    ano_actual = datetime.now().year
    opciones = set(range(ANO_MIN, ano_actual + ANO_MAX_EXTRA + 1))
    if extra:
        opciones.update(int(a) for a in extra)
    return sorted(opciones)


def _parsear_anos(valores):
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


def _pipeline_worker(anos, progress, cancel_event, disparado_por, actor_usuario_id):
    """Corre en un thread aparte -- NUNCA debe llamar a `st.*` (session_state
    solo se toca de forma segura porque `progress`/`cancel_event` son objetos
    planos pasados por referencia, no accedidos vía st.session_state desde
    este thread). Registra el run y libera el lock siempre, pase lo que pase."""

    def on_progress(index, total, ano):
        progress["index"] = index
        progress["total"] = total
        progress["ano_actual"] = ano

    iniciado_en = datetime.now()
    try:
        resultado = ejecutar_alumnos_etl(anos, on_progress=on_progress, cancel_check=cancel_event.is_set)
    except Exception as exc:
        resultado = {
            "status": "ERROR", "filas_v1": None, "filas_v2": None,
            "anos_con_error": anos, "mensaje_error": str(exc),
        }
    finalizado_en = datetime.now()

    try:
        db_pia.registrar_alumnos_etl_run(
            disparado_por=disparado_por,
            status=resultado["status"],
            iniciado_en=iniciado_en,
            finalizado_en=finalizado_en,
            anos_procesados=anos,
            filas_v1=resultado["filas_v1"],
            filas_v2=resultado["filas_v2"],
            mensaje_error=resultado["mensaje_error"],
            actor_usuario_id=actor_usuario_id,
        )
        db_pia.log_audit_event(
            "alumnos_etl_ejecutado_manual" if disparado_por == "MANUAL" else "alumnos_etl_ejecutado_cron",
            detalle={"anos": anos, "status": resultado["status"]},
            actor_usuario_id=actor_usuario_id,
        )
    finally:
        db_pia.release_alumnos_etl_lock()

    progress["resultado"] = resultado
    progress["done"] = True


@st.dialog("Confirmar ejecución del ETL de Alumnos")
def modal_confirmar_ejecucion(anos):
    st.warning(
        f"Esto va a consultar el MySQL de origen **año por año** ({len(anos)} año(s): "
        f"{', '.join(str(a) for a in sorted(anos))}), lo que puede demorar bastante "
        "(varios minutos, dependiendo de la cantidad de años y del volumen de datos).\n\n"
        "¿Desea ejecutar el ETL ahora de todas formas?"
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()
    with c2:
        if st.button("Sí, ejecutar", type="primary", use_container_width=True):
            actor_usuario_id = st.session_state.get("user_id")
            if not db_pia.try_acquire_alumnos_etl_lock("MANUAL", actor_usuario_id):
                estado = db_pia.get_alumnos_etl_lock_status()
                st.error(
                    f"Ya hay una ejecución en curso (disparado por {estado['disparado_por']} "
                    f"desde {_formatear_fecha(estado['iniciado_en'])}). Espere a que termine."
                )
                return

            progress = {
                "index": 0, "total": len(anos), "ano_actual": None,
                "resultado": None, "done": False,
            }
            cancel_event = threading.Event()
            thread = threading.Thread(
                target=_pipeline_worker,
                args=(anos, progress, cancel_event, "MANUAL", actor_usuario_id),
                daemon=True,
            )
            st.session_state.alumnos_etl_job = {
                "thread": thread, "progress": progress, "cancel_event": cancel_event, "anos": anos,
            }
            thread.start()
            st.rerun()


@st.fragment(run_every=1)
def _render_progreso_ejecucion():
    job = st.session_state.get("alumnos_etl_job")
    if job is None:
        return

    thread = job["thread"]
    progress = job["progress"]
    cancel_event = job["cancel_event"]

    if thread.is_alive():
        total = progress["total"]
        idx = progress["index"]
        ano_actual = progress["ano_actual"]

        if ano_actual is not None:
            st.info(f"Ejecutando ETL de alumnos... Procesando año **{ano_actual}** ({idx}/{total}).")
        else:
            st.info("Ejecutando ETL de alumnos... Iniciando.")
        st.progress(idx / total if total else 0.0)

        if cancel_event.is_set():
            st.caption(
                "Deteniendo — esperando a que termine el año en curso "
                "(no se interrumpe una consulta ya en marcha)."
            )
        else:
            if st.button("Detener", icon=":material/stop:", key="btn_detener_alumnos_etl"):
                cancel_event.set()
        return

    # El thread ya terminó: mostrar mensaje final (vía temp_msg, mismo patrón
    # que el resto de la pantalla) y limpiar el job para volver a la vista normal.
    resultado = progress.get("resultado") or {
        "status": "ERROR", "mensaje_error": "El proceso terminó sin resultado (revise los logs).",
        "filas_v1": None, "filas_v2": None,
    }
    if resultado["status"] == "OK":
        st.session_state.temp_msg_alumnos_etl = (
            f"Ejecución completada: alumnos_v1={resultado['filas_v1']} filas, "
            f"alumnos_v2={resultado['filas_v2']} filas."
        )
    elif resultado["status"] == "CANCELADO":
        st.session_state.temp_msg_alumnos_etl_cancelado = resultado["mensaje_error"]
    else:
        st.session_state.temp_msg_alumnos_etl_error = resultado["mensaje_error"]

    del st.session_state.alumnos_etl_job
    st.rerun()


def _render_egresados_section():
    """Sección para reemplazar assets/data/global/egressados.xlsx desde la UI
    (antes había que subirlo por SCP al servidor). Valida las columnas antes
    de aceptar el archivo y guarda la fecha de envío (fecha en que la
    Secretaría General Académica mandó la planilla, no la de hoy) en
    pia_egresados_meta — esa fecha es la que se muestra en el pie de los
    indicadores que cruzan con egresados (ver utils/ui.render_egresados_fuente_caption)."""
    st.markdown("### Actualizar Egresados (egressados.xlsx)")

    meta = db_pia.get_egresados_meta()
    if meta:
        st.caption(
            f"Archivo actual: enviado por Secretaría el {_formatear_fecha_simple(meta['fecha_envio'])} "
            f"({meta['filas']} filas) · Subido al sistema el {_formatear_fecha(meta['actualizado_en'])}"
        )
    else:
        st.caption("Todavía no se registró ninguna actualización de egresados desde esta pantalla.")

    archivo = st.file_uploader("Nueva planilla de egresados (.xlsx)", type=["xlsx"], key="egresados_uploader")
    fecha_envio = st.date_input(
        "Fecha de envío del archivo *",
        value=date.today(),
        format="DD/MM/YYYY",
        help="Fecha en la que la Secretaría General Académica envió/actualizó esta planilla (no necesariamente hoy).",
        key="egresados_fecha_envio_input",
    )

    if st.button("Subir archivo", icon=":material/upload:", disabled=archivo is None):
        try:
            df_nuevo = pd.read_excel(archivo)
        except Exception as e:
            log_exception("Error al leer el archivo de egresados subido", e)
            st.error(f"No se pudo leer el archivo: {e}")
            return

        faltantes = validar_egresados_columnas(df_nuevo)
        if faltantes:
            st.error(f"El archivo no tiene las columnas esperadas. Faltan: {faltantes}")
            return

        try:
            if os.path.exists(EGRESADOS_XLSX_PATH):
                backup_path = EGRESADOS_XLSX_PATH[:-len(".xlsx")] + f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                shutil.copy2(EGRESADOS_XLSX_PATH, backup_path)

            archivo.seek(0)
            os.makedirs(os.path.dirname(EGRESADOS_XLSX_PATH), exist_ok=True)
            with open(EGRESADOS_XLSX_PATH, "wb") as f:
                f.write(archivo.read())

            db_pia.update_egresados_meta(
                fecha_envio=fecha_envio,
                filas=len(df_nuevo),
                actor_usuario_id=st.session_state.get("user_id"),
            )
            db_pia.log_audit_event(
                "egresados_actualizado",
                detalle={"fecha_envio": str(fecha_envio), "filas": len(df_nuevo)},
            )
        except Exception as e:
            log_exception("Error al guardar el nuevo archivo de egresados", e)
            st.error(f"Error al guardar el archivo: {e}")
            return

        st.success(
            f"Archivo actualizado: {len(df_nuevo)} filas, enviado el {_formatear_fecha_simple(fecha_envio)}. "
            "Se usará en la próxima ejecución del ETL."
        )
        st.rerun()


def render():
    if st.session_state.get("rol") != "ADMIN":
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return
    st.subheader("Alumnos - Configuración ETL")
    render_body()


def render_body():
    """Cuerpo de la pantalla, sin el chequeo de rol ni el subheader propio —
    pensado para ser embebido dentro de una pestaña (ver modules/config_etl.py)."""
    st.markdown(
        "Configure qué años entran en el loop de extracción de matrículas/notas "
        "(cada año es una consulta separada al MySQL de origen). El cron nocturno "
        "(**04:00**) corre automáticamente si está activo. El botón **Ejecutar ahora** "
        "dispara la extracción de inmediato."
    )

    if "temp_msg_alumnos_etl" in st.session_state:
        st.success(st.session_state.temp_msg_alumnos_etl)
        del st.session_state.temp_msg_alumnos_etl
    if "temp_msg_alumnos_etl_error" in st.session_state:
        st.error(f"Falló la ejecución: {st.session_state.temp_msg_alumnos_etl_error}")
        del st.session_state.temp_msg_alumnos_etl_error
    if "temp_msg_alumnos_etl_cancelado" in st.session_state:
        st.warning(f"Ejecución cancelada: {st.session_state.temp_msg_alumnos_etl_cancelado}")
        del st.session_state.temp_msg_alumnos_etl_cancelado

    config = db_pia.get_alumnos_etl_config()
    if not config:
        st.error("No se encontró la configuración de ETL de alumnos (pia_alumnos_etl_config).")
        return

    ultimo = db_pia.get_ultimo_alumnos_etl_run()

    if config["activo"] and ultimo and ultimo["status"] == "ERROR":
        st.warning(
            "⚠️ La última ejecución del ETL de alumnos falló. Revise el mensaje de "
            "error más abajo (probablemente el MySQL de origen esté caído o inaccesible)."
        )

    with st.container(border=True):
        st.markdown("### Configuración")

        anos_seleccionados_raw = st.multiselect(
            "Años a incluir en el loop de extracción *",
            options=_opciones_anos(extra=config["anos"]),
            default=config["anos"],
            accept_new_options=True,
            help="Cada año seleccionado dispara una consulta separada al MySQL de origen (matrículas + notas). "
                 "Puede escribir un año que no esté en la lista y presionar Enter para agregarlo.",
        )
        try:
            anos_seleccionados = _parsear_anos(anos_seleccionados_raw)
        except ValueError as e:
            st.error(str(e))
            anos_seleccionados = []

        activo_actual = bool(config["activo"])
        nuevo_estado = st.toggle(
            "Actualización automática (cron diario 04:00)",
            value=activo_actual,
            help="Si está pausada, el cron nocturno no ejecuta el ETL, pero los datos ya generados siguen visibles en el dashboard.",
        )

        if st.button("Guardar Configuración", type="primary", icon=":material/save:"):
            if not anos_seleccionados:
                st.warning("Debe seleccionar al menos un año.")
            else:
                db_pia.update_alumnos_etl_config(anos_seleccionados, nuevo_estado)
                db_pia.log_audit_event(
                    "alumnos_etl_config_actualizado",
                    detalle={"anos": anos_seleccionados, "activo": nuevo_estado},
                )
                st.success("Configuración guardada.")
                st.rerun()

    st.markdown("---")

    job = st.session_state.get("alumnos_etl_job")
    if job is not None:
        _render_progreso_ejecucion()
    else:
        lock_estado = db_pia.get_alumnos_etl_lock_status()
        bloqueado_por_otro = bool(lock_estado and lock_estado["en_ejecucion"])
        if bloqueado_por_otro:
            st.warning(
                f"⚠️ Ya hay una ejecución del ETL de alumnos en curso, disparada por "
                f"**{lock_estado['disparado_por']}** desde {_formatear_fecha(lock_estado['iniciado_en'])} "
                "(otra pestaña/sesión, o el cron nocturno). Espere a que termine antes de iniciar otra."
            )

        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown("### Última ejecución")
            if ultimo:
                icono = STATUS_ICONOS.get(ultimo["status"], "❓")
                st.markdown(f"{icono} Finalizada: {_formatear_fecha(ultimo['finalizado_en'])}")
                st.caption(f"Disparado por: {ultimo['disparado_por']} · Años procesados: {ultimo['anos_procesados'] or '-'}")
                if ultimo["status"] == "OK":
                    st.caption(f"Filas generadas: alumnos_v1={ultimo['filas_v1']}, alumnos_v2={ultimo['filas_v2']}")
                    if ultimo["mensaje_error"]:
                        st.caption(f"Aviso: {ultimo['mensaje_error']}")
                else:
                    st.caption(f"{'Cancelado' if ultimo['status'] == 'CANCELADO' else 'Error'}: {ultimo['mensaje_error']}")
            else:
                st.info("Todavía no se ejecutó ninguna vez.")
        with c2:
            if st.button(
                "Ejecutar ahora", icon=":material/play_arrow:", type="primary",
                use_container_width=True, disabled=bloqueado_por_otro,
            ):
                if not anos_seleccionados:
                    st.warning("Seleccione al menos un año antes de ejecutar.")
                else:
                    modal_confirmar_ejecucion(anos_seleccionados)

    st.markdown("---")

    with st.container(border=True):
        _render_egresados_section()
