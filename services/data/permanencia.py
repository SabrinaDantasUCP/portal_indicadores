import pandas as pd
import streamlit as st

from utils.data_loader import get_global_data_path
from utils.system_logging import log_exception


@st.cache_data
def load_permanencia(dataset_name):
    try:
        return pd.read_csv(get_global_data_path(dataset_name), sep=";", low_memory=False)
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de permanencia: {dataset_name}", exc)
        return pd.DataFrame()


def load_permanencia_vision_general():
    return load_permanencia("permanencia_vision_general")


def load_permanencia_fecha_corte():
    return load_permanencia("permanencia_fecha_corte")
