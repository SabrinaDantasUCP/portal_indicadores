import os

import pandas as pd
import streamlit as st

from utils.data_loader import get_data_path
from utils.system_logging import log_exception


@st.cache_resource(max_entries=2)
def _load_asistencia_raw(data_path, mtime):
    """Lee el parquet una vez y mantiene el DataFrame compartido en memoria.

    IMPORTANTE: no modificar el objeto devuelto; load_asistencia() entrega una copia.

    `mtime` (fecha de modificación del archivo) forma parte de la clave del
    caché: cuando un ETL reescribe el parquet, la próxima lectura lo vuelve a
    cargar en vez de seguir mostrando la versión que quedó en memoria desde
    que arrancó el servicio. max_entries=2 evita acumular versiones viejas.
    """
    df = pd.read_parquet(data_path)
    df.columns = df.columns.str.strip()
    return df


def load_asistencia(data_path):
    try:
        return _load_asistencia_raw(data_path, os.path.getmtime(data_path)).copy()
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de asistencia desde {data_path}", exc)
        return pd.DataFrame()


def load_current_asistencia():
    return load_asistencia(get_data_path("asistencia"))
