import os

import pandas as pd
import pyarrow.parquet as pq
import streamlit as st

from utils.data_loader import get_data_path, get_global_data_path
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


@st.cache_resource(max_entries=2)
def _load_alumnos_raw(data_path, mtime):
    """Lee el parquet una vez y mantiene el DataFrame compartido en memoria.

    IMPORTANTE: el objeto devuelto es compartido entre todas las sesiones y NO
    debe modificarse. Los consumidores usan load_alumnos(), que siempre devuelve
    una copia (filtrada o completa).

    `mtime` (fecha de modificación del archivo) forma parte de la clave del
    caché: cuando un ETL reescribe el parquet, la próxima lectura lo vuelve a
    cargar en vez de seguir mostrando la versión que quedó en memoria desde
    que arrancó el servicio. max_entries=2 evita acumular versiones viejas.
    """
    schema_names = {name.strip() for name in pq.ParquetFile(data_path).schema.names}
    cols = [c for c in ALUMNOS_COLUMNS if c in schema_names]
    df = pd.read_parquet(data_path, columns=cols)
    df.columns = df.columns.str.strip()
    return df


@st.cache_data(max_entries=6, show_spinner=False)
def _filtrar_alumnos_cached(data_path, mtime, only_cde=True, only_regular=False):
    """Filtra y almacena en caché la vista de alumnos según los criterios especificados.
    Evita recalcular máscaras booleanas y duplicar DataFrames de gran volumen
    en cada interacción o recarga de la interfaz.
    """
    df = _load_alumnos_raw(data_path, mtime)
    mask = None
    if only_cde and "filial_periodo_letivo" in df.columns:
        mask = df["filial_periodo_letivo"].isin(["CDE", "CDE III"])
    if only_regular and "tipo_disciplina" in df.columns:
        regular_mask = df["tipo_disciplina"] == "Regular"
        mask = regular_mask if mask is None else (mask & regular_mask)

    if mask is None:
        return df.copy()
    return df[mask].copy()


def load_alumnos(data_path, only_cde=True, only_regular=False):
    try:
        mtime = os.path.getmtime(data_path)
        return _filtrar_alumnos_cached(data_path, mtime, only_cde=only_cde, only_regular=only_regular)
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de alumnos desde {data_path}", exc)
        return pd.DataFrame()


def load_current_alumnos(only_cde=True, only_regular=False):
    return load_alumnos(
        get_data_path("alumnos"),
        only_cde=only_cde,
        only_regular=only_regular,
    )


@st.cache_data(max_entries=4, show_spinner=False)
def _count_current_alumnos_cached(version, mtime, only_cde=True):
    """Calcula y cachea la cantidad de alumnos únicos analizados para la versión activa."""
    path = get_data_path("alumnos", version)
    df = load_alumnos(path, only_cde=only_cde, only_regular=False)
    if df.empty:
        return 0
    if "usuarios_id" in df.columns:
        return int(df["usuarios_id"].nunique())
    return int(len(df))


def count_current_alumnos_analyzed(only_cde=True):
    try:
        version = get_current_version()
        path = get_data_path("alumnos", version)
        mtime = os.path.getmtime(path) if os.path.exists(path) else 0
        return _count_current_alumnos_cached(version, mtime, only_cde=only_cde)
    except Exception as exc:
        log_exception("No se pudo contar alumnos analizados", exc)
        return 0


@st.cache_data(ttl=86400, show_spinner=False)
def load_alumnos_documentos():
    """Carga el diccionario {usuarios_id: doc_oficial} directamente del parquet local institucional.
    Si el archivo no existe, lo genera consultando a SysEduca MySQL y lo guarda localmente."""
    try:
        path = get_global_data_path("alumnos_documentos")
        if os.path.exists(path):
            df_docs = pd.read_parquet(path)
            return dict(zip(df_docs["usuarios_id"].astype(int), df_docs["doc_oficial"].astype(str).str.strip()))

        # Fallback de autogeneración desde SysEduca MySQL si no existe en disco
        from services.etl.alumnos_etl import obtener_conexion
        conn = obtener_conexion()
        if conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id AS usuarios_id, doc_oficial FROM ucp.usuarios WHERE doc_oficial IS NOT NULL AND TRIM(doc_oficial) != ''")
            rows = cur.fetchall()
            conn.close()
            if rows:
                df_docs = pd.DataFrame(rows)
                df_docs["usuarios_id"] = df_docs["usuarios_id"].astype(int)
                df_docs["doc_oficial"] = df_docs["doc_oficial"].astype(str).str.strip()
                os.makedirs(os.path.dirname(path), exist_ok=True)
                df_docs.to_parquet(path, index=False)
                return dict(zip(df_docs["usuarios_id"], df_docs["doc_oficial"]))
    except Exception as exc:
        log_exception("No se pudo cargar o generar alumnos_documentos.parquet", exc)
    return {}
