"""
utils/ui_uploads.py

Sección de admin reutilizable para reemplazar un archivo .xlsx "de
referencia" (egresados, Defensa de TFG, RUES) desde la UI en vez de subirlo
por SCP al servidor: valida las columnas esperadas, hace backup del archivo
anterior, guarda el nuevo y registra metadatos (fecha de envío del área de
origen + cantidad de filas) en una tabla pia_*_meta.

Extraído de modules/alumnos_config_etl.py (_render_egresados_section, que
fue el primero en implementar este patrón) para reusarlo también en
modules/activos_config_etl.py (Defensa de TFG y RUES).
"""

import os
import shutil
from datetime import date, datetime

import pandas as pd
import streamlit as st

from utils.system_logging import log_exception


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


def render_upload_meta_section(
    *,
    titulo: str,
    file_path: str,
    columnas_requeridas: list,
    get_meta_fn,
    update_meta_fn,
    evento_audit: str,
    key_prefix: str,
    sheet_name=None,
    ayuda: str = None,
    on_saved=None,
    db_pia=None,
    normalizador=None,
):
    """Renderiza la sección de upload. `get_meta_fn`/`update_meta_fn` deben
    tener la misma firma que db_pia.get_egresados_meta/update_egresados_meta
    (fecha_envio, filas, actualizado_por/actor_usuario_id). `db_pia` se pasa
    para poder llamar a log_audit_event sin crear un import circular acá.
    `normalizador`, si se pasa, se aplica al DataFrame leído ANTES de
    validar `columnas_requeridas` -- útil cuando la fuente externa cambia el
    nombre de alguna columna entre versiones de la planilla (ver
    services.etl.alumnos_etl.normalizar_egresados_columnas)."""
    st.markdown(f"### {titulo}")

    meta = get_meta_fn()
    if meta:
        st.caption(
            f"Archivo actual: enviado el {_formatear_fecha_simple(meta['fecha_envio'])} "
            f"({meta['filas']} filas) · Subido al sistema el {_formatear_fecha(meta['actualizado_en'])}"
        )
    else:
        st.caption("Todavía no se registró ninguna actualización desde esta pantalla.")
    if ayuda:
        st.caption(ayuda)

    archivo = st.file_uploader(f"Nueva planilla (.xlsx)", type=["xlsx"], key=f"{key_prefix}_uploader")
    fecha_envio = st.date_input(
        "Fecha de envío del archivo *",
        value=date.today(),
        format="DD/MM/YYYY",
        help="Fecha en la que el área de origen envió/actualizó esta planilla (no necesariamente hoy).",
        key=f"{key_prefix}_fecha_envio_input",
    )

    if st.button("Subir archivo", icon=":material/upload:", disabled=archivo is None, key=f"{key_prefix}_btn_subir"):
        try:
            df_nuevo = pd.read_excel(archivo, sheet_name=sheet_name) if sheet_name else pd.read_excel(archivo)
        except Exception as e:
            log_exception(f"Error al leer el archivo subido ({titulo})", e)
            st.error(f"No se pudo leer el archivo: {e}")
            return

        if normalizador is not None:
            df_nuevo = normalizador(df_nuevo)

        faltantes = [c for c in columnas_requeridas if c not in df_nuevo.columns]
        if faltantes:
            st.error(f"El archivo no tiene las columnas esperadas. Faltan: {faltantes}")
            return

        try:
            if os.path.exists(file_path):
                backup_path = file_path[: -len(".xlsx")] + f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                shutil.copy2(file_path, backup_path)

            archivo.seek(0)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(archivo.read())

            update_meta_fn(
                fecha_envio=fecha_envio,
                filas=len(df_nuevo),
                actor_usuario_id=st.session_state.get("user_id"),
            )
            if db_pia is not None:
                db_pia.log_audit_event(
                    evento_audit,
                    detalle={"fecha_envio": str(fecha_envio), "filas": len(df_nuevo)},
                )
            if on_saved is not None:
                on_saved()
        except Exception as e:
            log_exception(f"Error al guardar el nuevo archivo ({titulo})", e)
            st.error(f"Error al guardar el archivo: {e}")
            return

        st.success(
            f"Archivo actualizado: {len(df_nuevo)} filas, enviado el {_formatear_fecha_simple(fecha_envio)}. "
            "Se usará en la próxima ejecución del ETL."
        )
        st.rerun()
