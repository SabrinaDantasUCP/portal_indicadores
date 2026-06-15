import pandas as pd
import streamlit as st

from utils.data_loader import get_data_path
from utils.system_logging import log_exception


@st.cache_data
def load_asistencia(data_path):
    try:
        df = pd.read_csv(data_path, low_memory=False)
        df.columns = df.columns.str.strip()
        return df
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de asistencia desde {data_path}", exc)
        return pd.DataFrame()


def load_current_asistencia():
    return load_asistencia(get_data_path("asistencia"))
