import streamlit as st
import pandas as pd
import io
import os
from utils.data_loader import get_global_data_path
from utils.system_logging import log_exception

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
            
        # Mapeo de nombres y orden solicitado:
        # 1. ID Alumno (antiguo usuarios_id), 2. Nro de Documento, 3. Nombre y Apellido, 
        # 4. Año de Egreso, 5. Periodo de Egreso, 6. Fecha de titulación, 7. Titulado, 8. Detalle (antiguo detalle)
        
        rename_map = {
            "usuarios_id": "ID Alumno",
            "detalle": "Detalle"
        }
        
        # Primero renombramos las existentes si están
        df = df.rename(columns=rename_map)
        
        cols_finales = [
            "ID Alumno", "Nombre y Apellido", 
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
        
        # Eliminar explícitamente cualquier columna "documento" extra
        if "documento" in df.columns:
            df = df.drop(columns=["documento"])
            
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
