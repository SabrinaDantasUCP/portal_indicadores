import streamlit as st
import pandas as pd
import io
import os
from utils.data_loader import get_global_data_path
from utils.system_logging import log_exception


def _obtener_datos_alumnos_por_id(usuarios_ids):
    """Busca Nombre y Apellido, Documento oficial y Número de Matrícula
    (catraca) directo en SysEduca (ucp.usuarios + ucp.numero_catraca) para
    los usuarios_id dados. La planilla de egresados en su formato actual
    (subida desde Alumnos - Configuración ETL) solo trae usuarios_id -- ya
    no trae estos datos como antes, así que se cruzan acá en el momento de
    exportar."""
    from services.etl.alumnos_etl import obtener_conexion

    ids = ",".join(str(int(i)) for i in pd.unique(usuarios_ids) if pd.notna(i))
    columnas = ["usuarios_id", "Nombre y Apellido", "Documento", "Número de Matrícula"]
    if not ids:
        return pd.DataFrame(columns=columnas)

    query = f"""
        SELECT
            u.id AS usuarios_id,
            u.nome_sobrenome AS `Nombre y Apellido`,
            u.doc_oficial AS `Documento`,
            nc.numero_catraca AS `Número de Matrícula`
        FROM ucp.usuarios u
        LEFT JOIN (
            SELECT usuarios_id, MAX(numero_catraca) AS numero_catraca
            FROM ucp.numero_catraca
            WHERE usuarios_id IS NOT NULL
            GROUP BY usuarios_id
        ) nc ON nc.usuarios_id = u.id
        WHERE u.id IN ({ids})
    """
    conn = obtener_conexion()
    try:
        return pd.read_sql(query, conn)
    finally:
        conn.close()


@st.cache_data
def get_egresados_excel_bytes():
    try:
        file_path = get_global_data_path("egressados")
        copy_path = get_global_data_path("egressados_copy")

        # Intentar leer el original, si hay error de permiso (común en OneDrive), intentar con la copia
        try:
            if os.path.exists(file_path):
                df = pd.read_excel(file_path)
            elif os.path.exists(copy_path):
                df = pd.read_excel(copy_path)
            else:
                return None
        except PermissionError:
            if os.path.exists(copy_path):
                df = pd.read_excel(copy_path)
            else:
                return None

        # Cruce con SysEduca por usuarios_id: la planilla ya no trae nombre,
        # documento ni catraca directamente (ver _obtener_datos_alumnos_por_id).
        if "usuarios_id" in df.columns:
            try:
                df_extra = _obtener_datos_alumnos_por_id(df["usuarios_id"])
                if not df_extra.empty:
                    df = df.merge(df_extra, on="usuarios_id", how="left")
            except Exception as exc:
                log_exception("No se pudo cruzar egresados con nombre/documento/catraca (SysEduca)", exc)

        # Mapeo de nombres y orden solicitado:
        # 1. Número de Matrícula, 2. Documento, 3. Nombre y Apellido,
        # 4. Año de Egreso, 5. Periodo de Egreso, 6. Fecha de titulación, 7. Titulado, 8. Detalle (antiguo detalle)
        rename_map = {"detalle": "Detalle"}
        df = df.rename(columns=rename_map)

        cols_finales = [
            "Número de Matrícula", "Documento", "Nombre y Apellido",
            "Año de Egreso", "Periodo de Egreso", "Fecha de titulación",
            "Titulado", "Detalle"
        ]

        # Filtrar solo las que existen y mantener el orden
        cols_to_keep = [c for c in cols_finales if c in df.columns]
        df = df[cols_to_keep]

        # Formatear "Fecha de titulación" para que no muestre la hora si es datetime
        if "Fecha de titulación" in df.columns:
            try:
                df["Fecha de titulación"] = pd.to_datetime(df["Fecha de titulación"]).dt.strftime('%d/%m/%Y')
            except Exception as exc:
                log_exception("No se pudo formatear la fecha de titulación para exportación", exc)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Egresados')
            worksheet = writer.sheets['Egresados']
            for i, col in enumerate(df.columns):
                col_data = df[col].astype(str)
                if not col_data.empty:
                    max_len = max(col_data.map(len).max(), len(col)) + 2
                else:
                    max_len = len(col) + 2
                worksheet.set_column(i, i, min(max_len, 50))
        return output.getvalue()
    except Exception as exc:
        log_exception("No se pudo generar el Excel de egresados", exc)
        return None
