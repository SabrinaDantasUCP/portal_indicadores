import pandas as pd
import streamlit as st

from utils.data_loader import get_global_data_path
from utils.system_logging import log_exception


INDICADOR_GENERAL = "avance_general"
INDICADOR_DETALLE = "avance_por_materia_seccion_grupo"

TIPO_ALUMNOS_DOCENTE = "ENCUESTA ALUMNOS A DOCENTES"

# Cada nueva encuesta se agrega acá: "periodo" -> {"tipo" -> nombre del dataset
# registrado en utils/data_config.py (DATASETS["global"]).
ENCUESTAS_DATASETS = {
    "2026.1": {
        TIPO_ALUMNOS_DOCENTE: "encuestas_alumnos_al_docente_20261",
    },
}

COLUMNAS_DETALLE = [
    "materia",
    "seccion",
    "grupo",
    "docente",
    "alumnos_esperados",
    "alumnos_que_respondieron",
    "porcentaje_avance",
]


def listar_periodos_encuestas():
    return sorted(ENCUESTAS_DATASETS.keys())


def listar_tipos_encuesta(periodo):
    return list(ENCUESTAS_DATASETS.get(periodo, {}).keys())


def get_encuestas_dataset(periodo, tipo):
    try:
        return ENCUESTAS_DATASETS[periodo][tipo]
    except KeyError as exc:
        raise KeyError(f"Encuesta no configurada para periodo={periodo} / tipo={tipo}") from exc


@st.cache_data(show_spinner=False)
def load_encuestas_raw(periodo, tipo):
    dataset_name = get_encuestas_dataset(periodo, tipo)
    try:
        return pd.read_parquet(get_global_data_path(dataset_name))
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de encuestas: {dataset_name}", exc)
        return pd.DataFrame()


def load_encuestas_general(periodo, tipo):
    """Fila única con los totales generales de avance de la encuesta, o None."""
    df = load_encuestas_raw(periodo, tipo)
    if df.empty:
        return None
    df_gen = df[df["indicador"] == INDICADOR_GENERAL]
    if df_gen.empty:
        return None
    return df_gen.iloc[0]


def load_encuestas_detalle(periodo, tipo):
    """Detalle de avance por materia/sección/grupo/docente."""
    df = load_encuestas_raw(periodo, tipo)
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_DETALLE)
    df_det = df[df["indicador"] == INDICADOR_DETALLE]
    cols = [c for c in COLUMNAS_DETALLE if c in df_det.columns]
    return df_det[cols].reset_index(drop=True)
