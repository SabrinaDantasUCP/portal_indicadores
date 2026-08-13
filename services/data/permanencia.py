import pandas as pd
import streamlit as st

from services.calculations.permanencia import (
    PERIODO_DEFAULT,
    get_periodo_config,
    prepare_permanencia_source,
)
from utils import db_pia
from utils.data_loader import get_global_data_path
from utils.system_logging import log_exception


VISTA_VISION_GENERAL = "vision_general"
VISTA_FECHA_CORTE = "fecha_corte"

# Cada periodo tiene dos vistas: la foto actual y la foto de una fecha de corte.
PERMANENCIA_DATASETS = {
    "2025.2": {
        VISTA_VISION_GENERAL: "permanencia_20252_vision_general",
        VISTA_FECHA_CORTE: "permanencia_20252_fecha_corte",
    },
    "2026.1": {
        VISTA_VISION_GENERAL: "permanencia_20261_vision_general",
        VISTA_FECHA_CORTE: "permanencia_20261_fecha_corte",
    },
}


def get_permanencia_dataset(periodo, vista):
    try:
        return PERMANENCIA_DATASETS[periodo][vista]
    except KeyError as exc:
        raise KeyError(f"Dataset de permanencia no configurado: {periodo}/{vista}") from exc


@st.cache_data(ttl=60, show_spinner=False)
def fechas_configuradas():
    """Fechas cargadas desde la pantalla de administración, si la base responde."""
    try:
        return db_pia.get_permanencia_fechas()
    except Exception as exc:
        log_exception("No se pudieron leer las fechas de permanencia; se usan las por defecto", exc)
        return {}


def limpiar_cache_fechas():
    fechas_configuradas.clear()


def get_periodo_config_efectivo(periodo):
    """Config del periodo con las fechas de la base pisando a las del código."""
    config = dict(get_periodo_config(periodo))
    fechas = fechas_configuradas().get(periodo) or {}
    for campo in ("limite_primer_semestre", "limite_otros_semestres"):
        if fechas.get(campo):
            config[campo] = fechas[campo]
    return config


def _sufijo_periodo(periodo):
    """'2025.2' -> '20252', el sufijo con el que vienen las columnas del CSV."""
    return periodo.replace(".", "")


def canonicalizar_columnas(df, periodo):
    """Unifica los nombres de columna al esquema interno _atual/_proximo.

    Los CSV del 2025.2 traen las columnas con el periodo en el nombre
    (semestre_20252, estado_pago_20261...) y los del 2026.1 ya las traen
    genericas (semestre_atual, semestre_proximo). El resto del codigo trabaja
    siempre con _atual/_proximo.
    """
    config = get_periodo_config(periodo)
    sufijos = {
        _sufijo_periodo(periodo): "atual",
        _sufijo_periodo(config["destino"]): "proximo",
    }

    rename_map = {}
    for col in df.columns:
        for sufijo, canonico in sufijos.items():
            if col.endswith(f"_{sufijo}"):
                rename_map[col] = f"{col[: -len(sufijo)]}{canonico}"

    return df.rename(columns=rename_map) if rename_map else df


@st.cache_data(ttl=3600)
def load_permanencia(dataset_name):
    try:
        return pd.read_parquet(get_global_data_path(dataset_name))
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de permanencia: {dataset_name}", exc)
        return pd.DataFrame()


def load_permanencia_periodo(periodo, vista):
    df = load_permanencia(get_permanencia_dataset(periodo, vista))
    if df.empty:
        return df
    return canonicalizar_columnas(df, periodo)


def load_permanencia_vision_general(periodo=PERIODO_DEFAULT):
    return load_permanencia_periodo(periodo, VISTA_VISION_GENERAL)


def load_permanencia_fecha_corte(periodo=PERIODO_DEFAULT):
    return load_permanencia_periodo(periodo, VISTA_FECHA_CORTE)


@st.cache_data(ttl=3600, show_spinner=False, max_entries=8)
def load_permanencia_lista(periodo, vista, limite_primer_semestre, limite_otros_semestres):
    """Datos ya preparados para el indicador.

    Cacheado a propósito: preparar la lista recorre fila por fila y el resultado
    solo depende del parquet y de las fechas de inicio de clases. Sin esto se
    rehacía entero en cada click de cada filtro.
    """
    df = load_permanencia_periodo(periodo, vista)
    if df.empty:
        return df

    config = dict(get_periodo_config(periodo))
    config["limite_primer_semestre"] = limite_primer_semestre
    config["limite_otros_semestres"] = limite_otros_semestres
    return prepare_permanencia_source(df, periodo, config)
