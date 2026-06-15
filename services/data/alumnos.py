import pandas as pd
import streamlit as st

from utils.data_loader import get_data_path
from utils.system_logging import log_exception


@st.cache_data
def load_alumnos(data_path, only_cde=True, only_regular=False):
    try:
        df = pd.read_csv(data_path, low_memory=False)
        df.columns = df.columns.str.strip()

        if only_cde and "filial_periodo_letivo" in df.columns:
            df = df[df["filial_periodo_letivo"].isin(["CDE", "CDE III"])].copy()

        if only_regular and "tipo_disciplina" in df.columns:
            df = df[df["tipo_disciplina"] == "Regular"].copy()

        return df
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de alumnos desde {data_path}", exc)
        return pd.DataFrame()


def load_current_alumnos(only_cde=True, only_regular=False):
    return load_alumnos(
        get_data_path("alumnos"),
        only_cde=only_cde,
        only_regular=only_regular,
    )


def count_current_alumnos_analyzed(only_cde=True):
    df = load_current_alumnos(only_cde=only_cde, only_regular=False)
    if df.empty:
        return 0
    if "usuarios_id" in df.columns:
        return int(df["usuarios_id"].nunique())
    return int(len(df))
