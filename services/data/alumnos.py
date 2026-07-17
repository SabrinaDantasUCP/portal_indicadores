import pandas as pd
import pyarrow.parquet as pq
import streamlit as st

from utils.data_loader import get_data_path
from utils.system_logging import log_exception


# Columnas realmente utilizadas por los modulos (de 56 que trae el parquet).
# Leer solo estas reduce memoria y acelera filtros/copias.
# Si un modulo empieza a usar una columna nueva de alumnos, agregarla aqui.
ALUMNOS_COLUMNS = [
    "usuarios_id",
    "nome_sobrenome",
    "ano_periodo_letivo",
    "periodo_anual_periodo_letivo",
    "semestre_alumno",
    "semestre_disciplina",
    "filial_periodo_letivo",
    "disciplina",
    "turma",
    "docente",
    "calificacion_final",
    "numero_catraca",
    "tipo_disciplina",
    "resultado_final",
    "calificacion_final_1a5",
    "tipo_ingresso",
    "cohorte",
    "ano_inicial_coorte",
    "ano_final_coorte",
    "nombre_status_actual",
    "periodo_egresso",
    "periodo_egresso_format",
    "estado_titulacion",
    "fecha_titulacion",
    "detalle",
]


@st.cache_resource
def _load_alumnos_raw(data_path):
    """Lee el parquet una vez y mantiene el DataFrame compartido en memoria.

    IMPORTANTE: el objeto devuelto es compartido entre todas las sesiones y NO
    debe modificarse. Los consumidores usan load_alumnos(), que siempre devuelve
    una copia (filtrada o completa).
    """
    schema_names = {name.strip() for name in pq.ParquetFile(data_path).schema.names}
    cols = [c for c in ALUMNOS_COLUMNS if c in schema_names]
    df = pd.read_parquet(data_path, columns=cols)
    df.columns = df.columns.str.strip()
    return df


def load_alumnos(data_path, only_cde=True, only_regular=False):
    try:
        df = _load_alumnos_raw(data_path)
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de alumnos desde {data_path}", exc)
        return pd.DataFrame()

    mask = None
    if only_cde and "filial_periodo_letivo" in df.columns:
        mask = df["filial_periodo_letivo"].isin(["CDE", "CDE III"])
    if only_regular and "tipo_disciplina" in df.columns:
        regular_mask = df["tipo_disciplina"] == "Regular"
        mask = regular_mask if mask is None else (mask & regular_mask)

    if mask is None:
        return df.copy()
    return df[mask].copy()


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
