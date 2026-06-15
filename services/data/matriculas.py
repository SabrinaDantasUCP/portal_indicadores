import pandas as pd
import streamlit as st

from utils.data_loader import get_data_path
from utils.system_logging import log_exception


@st.cache_data
def load_matriculas(data_path):
    try:
        df = pd.read_excel(data_path)
        df.columns = [col.strip().lower() for col in df.columns]
        return df
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de matriculas desde {data_path}", exc)
        return pd.DataFrame()


def load_current_matriculas():
    return load_matriculas(get_data_path("matriculas"))
