"""
modules/activos_config_etl.py

Pantalla de admin para subir el archivo de "alumnos activos" que se usa
como filtro para generar la variante v2 en los ETL de Alumnos, Asistencias
y Encuestas (Alumno→Docente). Reemplaza el flujo anterior, que requería
subir assets/data/global/base_datos_activos.csv por SCP al servidor.

El archivo subido (.txt, 1 id por línea) se guarda vía
services/etl/activos_ids.guardar_ids_activos, que SIEMPRE sobrescribe el
mismo path (ACTIVOS_TXT_PATH) -- no hay historial de archivos, el último
subido es el único que existe y el que van a usar los próximos runs del
ETL (cron o "Ejecutar ahora").

No dispara ningún ETL por sí sola: los runners (alumnos_runner.py,
asistencias_runner.py, encuesta_runner.py) leen este archivo recién en su
próxima ejecución.
"""

import streamlit as st

from utils import db_pia
from utils.system_logging import log_exception
from services.etl.activos_ids import (
    cargar_ids_activos,
    guardar_ids_activos,
    parsear_ids_activos,
)


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

    st.subheader("Alumnos Activos - Filtro para Indicadores v2")
    st.markdown(
        "Este archivo define quiénes son los \"alumnos activos\" usados para generar la "
        "**Versión 2** de los indicadores en tres ETL: **Alumnos**, **Asistencias** y "
        "**Encuestas** (tipo Alumno→Docente). No afecta la Autoevaluación Docente, que no "
        "tiene versión v1/v2.\n\n"
        "Suba un .txt con **un id de usuario por línea**. Si el archivo tiene más de una "
        "columna por línea (por ejemplo un número de fila adelante), se usa la última "
        "columna. Cada archivo subido **reemplaza** al anterior -- el próximo ETL (cron o "
        "\"Ejecutar ahora\" en cada pantalla) siempre usa el último que fue enviado acá."
    )

    meta = db_pia.get_activos_ids_meta()
    ids_actuales = cargar_ids_activos()
    if meta and ids_actuales:
        st.caption(
            f"Archivo actual: `{meta['nombre_archivo']}` · {meta['cantidad_ids']} ids · "
            f"Subido el {_formatear_fecha(meta['actualizado_en'])}"
        )
    else:
        st.warning(
            "Todavía no se subió ningún archivo. Las variantes v2 de Alumnos, Asistencias y "
            "Encuestas (Alumno→Docente) no se generarán hasta que se suba uno.",
            icon=":material/warning:",
        )

    archivo = st.file_uploader("Nuevo archivo de ids activos (.txt)", type=["txt"], key="activos_ids_uploader")

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

        if st.button("Subir archivo", icon=":material/upload:"):
            try:
                cantidad = guardar_ids_activos(texto)
                db_pia.update_activos_ids_meta(
                    nombre_archivo=archivo.name,
                    cantidad_ids=cantidad,
                    actor_usuario_id=st.session_state.get("user_id"),
                )
                db_pia.log_audit_event(
                    "activos_ids_actualizado",
                    detalle={"nombre_archivo": archivo.name, "cantidad_ids": cantidad},
                )
            except Exception as e:
                log_exception("Error al guardar el nuevo archivo de ids activos", e)
                st.error(f"Error al guardar el archivo: {e}")
                return

            st.success(f"Archivo actualizado: {cantidad} ids activos. Se usará en la próxima ejecución de cada ETL.")
            st.rerun()

    if ids_actuales:
        st.download_button(
            "Descargar archivo actual",
            data="\n".join(str(i) for i in sorted(ids_actuales)),
            file_name="usuarios_activos_ids.txt",
            icon=":material/download:",
        )
