"""
modules/activos_config_etl.py

Pantalla de admin de "Alumnos Activos" -- fuente del filtro v2 en los ETL de
Alumnos, Asistencias y Encuestas (Alumno→Docente). La población oficial de
alumnos activos se cierra FUERA del portal (ETL
etl_unico_activos_2018_2_2026_1.py + consolidado "Alumnos Reales Max 2
Recursantes") y se sube aquí como CSV/XLSX
(services/etl/activos_ids.guardar_poblacion). El portal no recalcula
criterios, notas, recortes ni cohortes: el ETL de activos
(services/etl/activos_criterios_runner.py, cron o "Ejecutar ahora") solo
filtra esa población por los periodos configurados y escribe
assets/data/global/usuarios_activos_ids.txt y usuarios_activos_periodos.csv,
que Alumnos, Asistencias y Encuestas siguen leyendo exactamente igual que
antes (cargar_ids_activos / cargar_pares_activos).

Se mantiene, en un expander aparte, el upload manual de .txt como válvula de
escape -- sobrescribe el resultado generado a partir del CSV hasta la
próxima ejecución del ETL.
"""

import os
import threading
from datetime import datetime

import streamlit as st

from utils import db_pia
from utils.system_logging import log_exception
from utils.ui_uploads import render_upload_meta_section
from services.etl.activos_criterios_runner import (
    ejecutar_activos_criterios_etl,
    EGRESADOS_XLSX_PATH,
    TFG_XLSX_PATH,
    RUES_XLSX_PATH,
)
from services.etl.alumnos_etl import EGRESADOS_COLUMNAS_REQUERIDAS, normalizar_egresados_columnas
from services.etl.activos_ids import (
    POBLACION_CSV_PATH,
    cargar_ids_activos,
    cargar_poblacion,
    guardar_ids_activos,
    guardar_poblacion,
    leer_poblacion,
    parsear_ids_activos,
    borrar_pares_activos,
    totales_por_periodo,
)


STATUS_ICONOS = {"OK": "✅", "ERROR": "❌", "CANCELADO": "⏹️"}

PERIODO_MIN = 2018
PERIODO_MAX_EXTRA = 2  # cuántos años por delante del actual se ofrecen como opción


def _opciones_periodos(extra=None):
    """Genera "AAAA.1"/"AAAA.2" desde PERIODO_MIN hasta el año actual +
    PERIODO_MAX_EXTRA, más cualquier periodo ya guardado en la config
    (necesario porque accept_new_options permite valores fuera del rango
    fijo -- si no se los incluye acá, st.multiselect revienta al usar
    `default` con un valor que no está en `options`)."""
    ano_actual = datetime.now().year
    opciones = set()
    for ano in range(PERIODO_MIN, ano_actual + PERIODO_MAX_EXTRA + 1):
        opciones.add(f"{ano}.1")
        opciones.add(f"{ano}.2")
    if extra:
        opciones.update(extra)
    return sorted(opciones, key=lambda p: tuple(int(x) for x in p.split(".")))


def _parsear_periodos(valores):
    periodos = []
    for v in valores:
        v = str(v).strip()
        partes = v.split(".")
        if len(partes) != 2 or not all(p.isdigit() for p in partes) or partes[1] not in ("1", "2"):
            raise ValueError(f"'{v}' no es un periodo válido (formato esperado: 'AAAA.S', ej. 2027.1).")
        periodos.append(v)
    return sorted(set(periodos), key=lambda p: tuple(int(x) for x in p.split(".")))


def _formatear_fecha(dt):
    if not dt:
        return "-"
    try:
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except AttributeError:
        return str(dt)


# ─────────────────────────────────────────────
# EJECUCIÓN (config + cron + "Ejecutar ahora", mismo patrón que
# modules/alumnos_config_etl.py)
# ─────────────────────────────────────────────

def _pipeline_worker(periodos, progress, cancel_event, disparado_por, actor_usuario_id):
    """Corre en un thread aparte -- NUNCA debe llamar a `st.*`."""

    def on_progress(mensaje):
        progress["mensaje"] = mensaje

    iniciado_en = datetime.now()
    try:
        resultado = ejecutar_activos_criterios_etl(
            periodos, on_progress=on_progress, cancel_check=cancel_event.is_set
        )
    except Exception as exc:
        resultado = {
            "status": "ERROR", "cantidad_ids": None,
            "diagnostico_referencia": [], "faltantes_forzados": [], "mensaje_error": str(exc),
        }
    finalizado_en = datetime.now()

    try:
        db_pia.registrar_activos_criterios_run(
            disparado_por=disparado_por,
            status=resultado["status"],
            iniciado_en=iniciado_en,
            finalizado_en=finalizado_en,
            periodos_procesados=periodos,
            cantidad_ids=resultado["cantidad_ids"],
            mensaje_error=resultado["mensaje_error"],
            actor_usuario_id=actor_usuario_id,
        )
        db_pia.log_audit_event(
            "activos_criterios_etl_ejecutado_manual" if disparado_por == "MANUAL" else "activos_criterios_etl_ejecutado_cron",
            detalle={"periodos": periodos, "status": resultado["status"]},
            actor_usuario_id=actor_usuario_id,
        )
    finally:
        db_pia.release_activos_criterios_lock()

    progress["resultado"] = resultado
    progress["done"] = True


@st.dialog("Confirmar ETL de Alumnos Activos")
def modal_confirmar_ejecucion(periodos):
    st.warning(
        f"Esto va a filtrar la población de alumnos activos subida (CSV) por **{len(periodos)} "
        "periodo(s)** y reemplazar el archivo de ids activos (y los pares alumno-periodo) que usan "
        "Alumnos, Asistencias y Encuestas. Tarda unos segundos.\n\nDespués hay que ejecutar los ETL "
        "de Alumnos, Asistencias y Encuestas para regenerar la Versión 2.\n\n¿Desea ejecutar el ETL ahora?"
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", use_container_width=True, key="activos_criterios_modal_cancelar"):
            st.rerun()
    with c2:
        if st.button("Sí, ejecutar", type="primary", use_container_width=True, key="activos_criterios_modal_confirmar"):
            actor_usuario_id = st.session_state.get("user_id")
            if not db_pia.try_acquire_activos_criterios_lock("MANUAL", actor_usuario_id):
                estado = db_pia.get_activos_criterios_lock_status()
                st.error(
                    f"Ya hay una ejecución en curso (disparado por {estado['disparado_por']} "
                    f"desde {_formatear_fecha(estado['iniciado_en'])}). Espere a que termine."
                )
                return

            progress = {"mensaje": None, "resultado": None, "done": False}
            cancel_event = threading.Event()
            thread = threading.Thread(
                target=_pipeline_worker,
                args=(periodos, progress, cancel_event, "MANUAL", actor_usuario_id),
                daemon=True,
            )
            st.session_state.activos_criterios_etl_job = {
                "thread": thread, "progress": progress, "cancel_event": cancel_event, "periodos": periodos,
            }
            thread.start()
            st.rerun()


@st.fragment(run_every=1)
def _render_progreso_ejecucion():
    job = st.session_state.get("activos_criterios_etl_job")
    if job is None:
        return

    thread = job["thread"]
    progress = job["progress"]
    cancel_event = job["cancel_event"]

    if thread.is_alive():
        mensaje = progress.get("mensaje") or "Iniciando..."
        st.info(f"Ejecutando ETL de alumnos activos... {mensaje}")

        if cancel_event.is_set():
            st.caption("Deteniendo — esperando a que termine el paso en curso.")
        else:
            if st.button("Detener", icon=":material/stop:", key="btn_detener_activos_criterios_etl"):
                cancel_event.set()
        return

    resultado = progress.get("resultado") or {
        "status": "ERROR", "mensaje_error": "El proceso terminó sin resultado (revise los logs).",
        "cantidad_ids": None,
    }
    if resultado["status"] == "OK":
        st.session_state.temp_msg_activos_criterios_etl = (
            f"ETL completado: {resultado['cantidad_ids']} ids activos."
            + (f" Aviso: {resultado['mensaje_error']}" if resultado["mensaje_error"] else "")
        )
    elif resultado["status"] == "CANCELADO":
        st.session_state.temp_msg_activos_criterios_etl_cancelado = resultado["mensaje_error"]
    else:
        st.session_state.temp_msg_activos_criterios_etl_error = resultado["mensaje_error"]

    del st.session_state.activos_criterios_etl_job
    st.rerun()


# ─────────────────────────────────────────────
# POBLACIÓN DE ALUMNOS ACTIVOS (CSV cerrado fuera del portal)
# ─────────────────────────────────────────────

def _resumen_poblacion(df):
    return {
        "filas": len(df),
        "alumnos": df["usuarios_id"].nunique(),
        "periodos": df["periodo"].nunique(),
    }


def _render_poblacion_section():
    st.markdown("### Población de alumnos activos (CSV)")
    st.markdown(
        "Lista oficial de alumnos activos, cerrada **fuera del portal** (consolidado \"Alumnos Reales "
        "Max 2 Recursantes\"). Suba la hoja **Alumnos** como .csv/.txt (separador `;`, `,` o tab) o el "
        ".xlsx directo, con las columnas **Año, Periodo, Catraca, ID Usuario, Nombre, Doc. Oficial, "
        "Semestre, Sección, Motivo** (obligatorias: Año, Periodo, ID Usuario, Semestre). El portal no "
        "modifica semestre ni sección; una sección vacía es válida.\n\n"
        "Después de guardar: **\"Ejecutar ahora\"** más abajo (o esperar el cron) y luego los ETL de "
        "**Alumnos**, **Asistencias** y **Encuestas** para regenerar la Versión 2."
    )

    if "temp_msg_activos_poblacion" in st.session_state:
        st.success(st.session_state.temp_msg_activos_poblacion)
        del st.session_state.temp_msg_activos_poblacion

    try:
        poblacion_actual = cargar_poblacion()
    except Exception as e:
        log_exception("Error al leer la población de alumnos activos guardada", e)
        st.error(f"No se pudo leer la población guardada: {e}")
        poblacion_actual = None

    if poblacion_actual is not None:
        resumen = _resumen_poblacion(poblacion_actual)
        modificado = datetime.fromtimestamp(os.path.getmtime(POBLACION_CSV_PATH))
        st.caption(
            f"Población actual: {resumen['filas']} filas · {resumen['alumnos']} alumnos únicos · "
            f"{resumen['periodos']} periodo(s) · Modificada el {_formatear_fecha(modificado)}"
        )
    else:
        st.info("Todavía no se subió ninguna población.")

    archivo = st.file_uploader(
        "Archivo de población (.csv, .txt o .xlsx)", type=["csv", "txt", "xlsx"], key="activos_poblacion_uploader",
    )
    if archivo is not None:
        try:
            df_nuevo = leer_poblacion(archivo.getvalue(), archivo.name)
        except ValueError as e:
            st.error(str(e))
            return

        resumen = _resumen_poblacion(df_nuevo)
        sin_seccion = int((df_nuevo["seccion"] == "").sum())
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Filas", resumen["filas"])
        c2.metric("Alumnos únicos", resumen["alumnos"])
        c3.metric("Periodos", resumen["periodos"])
        c4.metric("Filas sin sección", sin_seccion)
        st.caption("Total de alumnos (ID Usuario únicos) por periodo:")
        st.dataframe(totales_por_periodo(df_nuevo).to_frame().T, use_container_width=True)

        if st.button("Guardar población", type="primary", icon=":material/save:", key="btn_guardar_poblacion"):
            try:
                filas = guardar_poblacion(df_nuevo)
                db_pia.log_audit_event(
                    "activos_poblacion_actualizada",
                    detalle={"nombre_archivo": archivo.name, "filas": filas},
                )
            except Exception as e:
                log_exception("Error al guardar la población de alumnos activos", e)
                st.error(f"Error al guardar la población: {e}")
                return
            st.session_state.temp_msg_activos_poblacion = (
                f"Población guardada: {filas} filas. Ahora ejecute el ETL de activos (\"Ejecutar ahora\")."
            )
            st.rerun()

    if poblacion_actual is not None:
        with open(POBLACION_CSV_PATH, "rb") as f:
            st.download_button(
                "Descargar población actual (CSV)",
                data=f.read(),
                file_name="alumnos_activos_poblacion.csv",
                mime="text/csv",
                icon=":material/download:",
                key="btn_descargar_poblacion",
            )


# ─────────────────────────────────────────────
# UPLOAD MANUAL (válvula de escape, comportamiento anterior sin cambios)
# ─────────────────────────────────────────────

def _render_upload_manual_section():
    st.markdown(
        "Suba un .txt con **un id de usuario por línea**. Si el archivo tiene más de una "
        "columna por línea (por ejemplo un número de fila adelante), se usa la última "
        "columna. Al subir, **sobrescribe** el resultado generado a partir de la población (CSV) "
        "y borra los pares alumno-periodo, así que la Versión 2 pasa a incluir TODO el historial "
        "de esos ids -- la próxima ejecución del ETL (cron o \"Ejecutar ahora\" más arriba) lo "
        "vuelve a reemplazar con la población."
    )

    meta = db_pia.get_activos_ids_meta()
    ids_actuales = cargar_ids_activos()
    if meta and ids_actuales:
        st.caption(
            f"Archivo actual: `{meta['nombre_archivo']}` · {meta['cantidad_ids']} ids · "
            f"Subido el {_formatear_fecha(meta['actualizado_en'])}"
        )

    archivo = st.file_uploader("Archivo de ids activos (.txt)", type=["txt"], key="activos_ids_uploader_manual")

    if archivo is not None:
        try:
            texto = archivo.read().decode("utf-8-sig")
        except UnicodeDecodeError as e:
            log_exception("Error al leer el archivo de ids activos subido", e)
            st.error(f"No se pudo leer el archivo (¿es un .txt de texto plano?): {e}")
            return

        ids_preview = parsear_ids_activos(texto)
        if not ids_preview:
            st.error("No se encontró ningún id válido en el archivo. Revise el formato.")
            return
        st.caption(f"Vista previa: {len(ids_preview)} ids detectados. Primeros 10: {ids_preview[:10]}")

        if st.button("Subir archivo (sobrescribe el resultado del CSV)", icon=":material/upload:", key="btn_subir_manual"):
            try:
                cantidad = guardar_ids_activos(texto)
                borrar_pares_activos()  # invalida los pares alumno-periodo generados desde la población
                db_pia.update_activos_ids_meta(
                    nombre_archivo=archivo.name,
                    cantidad_ids=cantidad,
                    actor_usuario_id=st.session_state.get("user_id"),
                )
                db_pia.log_audit_event(
                    "activos_ids_actualizado_manual",
                    detalle={"nombre_archivo": archivo.name, "cantidad_ids": cantidad},
                )
            except Exception as e:
                log_exception("Error al guardar el nuevo archivo de ids activos", e)
                st.error(f"Error al guardar el archivo: {e}")
                return

            st.success(f"Archivo actualizado: {cantidad} ids activos.")
            st.rerun()

    if ids_actuales:
        st.download_button(
            "Descargar archivo actual",
            data="\n".join(str(i) for i in sorted(ids_actuales)),
            file_name="usuarios_activos_ids.txt",
            icon=":material/download:",
            key="btn_descargar_activos_ids",
        )


# ─────────────────────────────────────────────
# RENDER PRINCIPAL
# ─────────────────────────────────────────────

def render():
    if st.session_state.get("rol") != "ADMIN":
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return

    st.subheader("Alumnos Activos - Configuración ETL")
    st.markdown(
        "Define quiénes son los \"alumnos activos\" usados para generar la **Versión 2** de los "
        "indicadores en tres ETL: **Alumnos**, **Asistencias** y **Encuestas** (tipo "
        "Alumno→Docente). La fuente es la **población oficial (CSV)** cerrada fuera del portal: el "
        "portal no recalcula criterios, notas, recortes ni cohortes, solo filtra esa lista por los "
        "periodos configurados. No afecta la Autoevaluación Docente, que no tiene versión v1/v2."
    )

    if "temp_msg_activos_criterios_etl" in st.session_state:
        st.success(st.session_state.temp_msg_activos_criterios_etl)
        del st.session_state.temp_msg_activos_criterios_etl
    if "temp_msg_activos_criterios_etl_error" in st.session_state:
        st.error(f"Falló la ejecución: {st.session_state.temp_msg_activos_criterios_etl_error}")
        del st.session_state.temp_msg_activos_criterios_etl_error
    if "temp_msg_activos_criterios_etl_cancelado" in st.session_state:
        st.warning(f"Ejecución cancelada: {st.session_state.temp_msg_activos_criterios_etl_cancelado}")
        del st.session_state.temp_msg_activos_criterios_etl_cancelado

    with st.container(border=True):
        _render_poblacion_section()

    st.markdown("---")

    config = db_pia.get_activos_criterios_config()
    if not config:
        st.error("No se encontró la configuración de ETL de activos por criterios (pia_activos_criterios_config).")
        return

    ultimo = db_pia.get_ultimo_activos_criterios_run()
    if config["activo"] and ultimo and ultimo["status"] == "ERROR":
        st.warning(
            "⚠️ La última ejecución del ETL de activos falló. Revise el mensaje de error más "
            "abajo (por ejemplo, población no subida o sin alumnos en los periodos configurados)."
        )

    with st.container(border=True):
        st.markdown("### Configuración")

        periodos_seleccionados_raw = st.multiselect(
            "Periodos a incluir *",
            options=_opciones_periodos(extra=config["periodos"]),
            default=config["periodos"],
            accept_new_options=True,
            help="Solo los alumnos de la población (CSV) en estos periodos pasan a los archivos de ids "
                 "activos; los demás periodos del CSV se ignoran (y se avisa). Puede escribir un periodo "
                 "que no esté en la lista (formato 'AAAA.S') y presionar Enter para agregarlo.",
        )
        try:
            periodos_seleccionados = _parsear_periodos(periodos_seleccionados_raw)
        except ValueError as e:
            st.error(str(e))
            periodos_seleccionados = []

        activo_actual = bool(config["activo"])
        nuevo_estado = st.toggle(
            "Actualización automática (cron diario, antes que Alumnos/Asistencias/Encuestas)",
            value=activo_actual,
            help="Si está pausada, el cron nocturno no ejecuta el ETL, pero el archivo de ids "
                 "activos ya generado sigue siendo usado por los otros ETL.",
        )

        if st.button("Guardar Configuración", type="primary", icon=":material/save:", key="btn_guardar_config_activos"):
            if not periodos_seleccionados:
                st.warning("Debe seleccionar al menos un periodo.")
            else:
                db_pia.update_activos_criterios_config(periodos_seleccionados, nuevo_estado)
                db_pia.log_audit_event(
                    "activos_criterios_config_actualizado",
                    detalle={"periodos": periodos_seleccionados, "activo": nuevo_estado},
                )
                st.success("Configuración guardada.")
                st.rerun()

    st.markdown("---")

    job = st.session_state.get("activos_criterios_etl_job")
    if job is not None:
        _render_progreso_ejecucion()
    else:
        lock_estado = db_pia.get_activos_criterios_lock_status()
        bloqueado_por_otro = bool(lock_estado and lock_estado["en_ejecucion"])
        if bloqueado_por_otro:
            st.warning(
                f"⚠️ Ya hay un ETL de activos en curso, disparado por "
                f"**{lock_estado['disparado_por']}** desde {_formatear_fecha(lock_estado['iniciado_en'])} "
                "(otra pestaña/sesión, o el cron). Espere a que termine antes de iniciar otro."
            )

        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown("### Última ejecución")
            if ultimo:
                icono = STATUS_ICONOS.get(ultimo["status"], "❓")
                st.markdown(f"{icono} Finalizada: {_formatear_fecha(ultimo['finalizado_en'])}")
                st.caption(f"Disparado por: {ultimo['disparado_por']} · Periodos procesados: {ultimo['periodos_procesados'] or '-'}")
                if ultimo["status"] == "OK":
                    st.caption(f"Ids activos generados: {ultimo['cantidad_ids']}")
                    if ultimo["mensaje_error"]:
                        st.caption(f"Aviso: {ultimo['mensaje_error']}")
                else:
                    st.caption(f"{'Cancelado' if ultimo['status'] == 'CANCELADO' else 'Error'}: {ultimo['mensaje_error']}")
            else:
                st.info("Todavía no se ejecutó ninguna vez.")
        with c2:
            if st.button(
                "Ejecutar ahora", icon=":material/play_arrow:", type="primary",
                use_container_width=True, disabled=bloqueado_por_otro, key="btn_ejecutar_activos_criterios",
            ):
                if not periodos_seleccionados:
                    st.warning("Seleccione al menos un periodo antes de ejecutar.")
                else:
                    modal_confirmar_ejecucion(periodos_seleccionados)

    st.markdown("---")

    with st.container(border=True):
        render_upload_meta_section(
            titulo="Actualizar Egresados (egressados.xlsx)",
            file_path=EGRESADOS_XLSX_PATH,
            columnas_requeridas=EGRESADOS_COLUMNAS_REQUERIDAS,
            get_meta_fn=db_pia.get_egresados_meta,
            update_meta_fn=db_pia.update_egresados_meta,
            evento_audit="egresados_actualizado",
            key_prefix="activos_egresados",
            ayuda="Mismo archivo que usa la pantalla de Alumnos. Estos alumnos siempre cuentan como activos.",
            db_pia=db_pia,
            normalizador=normalizar_egresados_columnas,
        )

    with st.container(border=True):
        render_upload_meta_section(
            titulo="Actualizar Defensa de TFG (tfg.xlsx)",
            file_path=TFG_XLSX_PATH,
            columnas_requeridas=["IDs_Solo", "Convocatoria al cual pertenece", "Semestre_BD"],
            get_meta_fn=db_pia.get_tfg_meta,
            update_meta_fn=db_pia.update_tfg_meta,
            evento_audit="tfg_actualizado",
            key_prefix="activos_tfg",
            sheet_name="Todos los Egresados",
            ayuda="Hoja \"Todos los Egresados\". Estos alumnos siempre cuentan como activos.",
            db_pia=db_pia,
        )

    with st.container(border=True):
        render_upload_meta_section(
            titulo="Actualizar RUES (rues.xlsx)",
            file_path=RUES_XLSX_PATH,
            columnas_requeridas=["CRM_INSCRIPCION_ID", "CABECERA_PERIODO_ACADEMICO", "DETALLE_FECHA_MATRICULACION"],
            get_meta_fn=db_pia.get_rues_meta,
            update_meta_fn=db_pia.update_rues_meta,
            evento_audit="rues_actualizado",
            key_prefix="activos_rues",
            sheet_name="Hoja1",
            ayuda="Hoja \"Hoja1\". Estos ingresos (vía convenio) siempre cuentan como activos.",
            db_pia=db_pia,
        )

    st.markdown("---")

    with st.expander("Avanzado: subir lista manualmente (sobrescribe el resultado del CSV)"):
        _render_upload_manual_section()
