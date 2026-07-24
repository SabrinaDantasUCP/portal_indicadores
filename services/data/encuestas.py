import pandas as pd
import streamlit as st

from utils.data_loader import get_current_version, get_data_path
from utils.system_logging import log_exception


INDICADOR_GENERAL = "avance_general"
INDICADOR_DETALLE = "avance_por_materia_seccion_grupo"
INDICADOR_ALUMNO = "avance_por_alumno"

TIPO_ALUMNOS_DOCENTE = "ENCUESTA ALUMNOS A DOCENTES"

SEDE_ASUNCION = "Asunción"
SEDE_CIUDAD_DEL_ESTE = "Ciudad del Este"

# Lista fija: se muestran ambas sedes aunque todavía no haya datos cargados
# para alguna de ellas (por ahora sólo Ciudad del Este tiene encuestas).
SEDES = [SEDE_ASUNCION, SEDE_CIUDAD_DEL_ESTE]

# Cada nueva encuesta se agrega acá: sede -> periodo -> carrera -> tipo ->
# {"dataset": nombre registrado en utils/data_config.py bajo "indicadores_v1"
# y "indicadores_v2" (cada versión apunta a su propio parquet), "nombre":
# nombre de la encuesta, "vigencia": rango de fechas mostrado aparte}.
# El archivo real que se lee depende de la versión activa en ese momento
# (utils.data_loader.get_current_version()), fijada por el menú lateral
# antes de entrar a la página.
ENCUESTAS_DATASETS = {
    SEDE_CIUDAD_DEL_ESTE: {
        "2026.1": {
            "Medicina": {
                TIPO_ALUMNOS_DOCENTE: {
                    "dataset": "encuestas_alumnos_al_docente_20261",
                    "nombre": "ENCUESTA ALUMNOS A DOCENTES 2026-1",
                    "vigencia": "22/06/2026 - 25/07/2026",
                },
            },
        },
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

COLUMNAS_ALUMNO = [
    "materia",
    "seccion",
    "grupo",
    "system_id",
    "alumno",
    "planificacion_id",
    "respondio",
]


def listar_sedes_encuestas():
    return SEDES


def listar_periodos_encuestas(sede):
    return sorted(ENCUESTAS_DATASETS.get(sede, {}).keys())


def listar_carreras_encuesta(sede, periodo):
    return sorted(ENCUESTAS_DATASETS.get(sede, {}).get(periodo, {}).keys())


def listar_tipos_encuesta(sede, periodo, carrera):
    """Devuelve [(tipo, label), ...] disponibles para sede/periodo/carrera."""
    tipos = ENCUESTAS_DATASETS.get(sede, {}).get(periodo, {}).get(carrera, {})
    return [
        (tipo, f"{info['nombre']} ({info['vigencia']})")
        for tipo, info in tipos.items()
    ]


def _get_encuesta_info(sede, periodo, carrera, tipo):
    try:
        return ENCUESTAS_DATASETS[sede][periodo][carrera][tipo]
    except KeyError as exc:
        raise KeyError(
            f"Encuesta no configurada para sede={sede} / periodo={periodo} "
            f"/ carrera={carrera} / tipo={tipo}"
        ) from exc


def get_encuesta_nombre(sede, periodo, carrera, tipo):
    return _get_encuesta_info(sede, periodo, carrera, tipo)["nombre"]


def get_encuesta_vigencia(sede, periodo, carrera, tipo):
    return _get_encuesta_info(sede, periodo, carrera, tipo)["vigencia"]


def get_encuestas_dataset(sede, periodo, carrera, tipo):
    return _get_encuesta_info(sede, periodo, carrera, tipo)["dataset"]


@st.cache_data(show_spinner=False)
def _read_encuestas_parquet(dataset_name, version):
    try:
        return pd.read_parquet(get_data_path(dataset_name, version))
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de encuestas: {dataset_name} ({version})", exc)
        return pd.DataFrame()


def load_encuestas_raw(sede, periodo, carrera, tipo):
    dataset_name = get_encuestas_dataset(sede, periodo, carrera, tipo)
    # La versión se pasa explícita como parte de la clave de caché de
    # _read_encuestas_parquet: sin esto, cambiar de V1 a V2 con la misma
    # sede/periodo/carrera/tipo devolvería datos cacheados de la otra versión.
    return _read_encuestas_parquet(dataset_name, get_current_version())


def _compute_general_from_alumnos(df_alu):
    """Calcula el resumen general a partir del detalle por alumno, para
    orígenes que no traen la fila 'avance_general' pre-agregada (p. ej. v2)."""
    if df_alu.empty:
        return None
    esperados = int(df_alu["system_id"].nunique())
    if esperados == 0:
        return None
    respondieron_al_menos_una = int(df_alu.loc[df_alu["respondio"] == True, "system_id"].nunique())
    respondieron_todas = int(df_alu.groupby("system_id")["respondio"].all().sum())
    return {
        "alumnos_unicos_esperados": esperados,
        "alumnos_unicos_que_respondieron_al_menos_una": respondieron_al_menos_una,
        "porcentaje_avance_alumnos": round(respondieron_al_menos_una / esperados * 100, 2),
        "alumnos_unicos_que_respondieron_todas": respondieron_todas,
        "porcentaje_avance_alumnos_todas": round(respondieron_todas / esperados * 100, 2),
    }


def load_encuestas_general(sede, periodo, carrera, tipo):
    """Fila única con los totales generales de avance de la encuesta, o None."""
    df = load_encuestas_raw(sede, periodo, carrera, tipo)
    if df.empty:
        return None
    df_gen = df[df["indicador"] == INDICADOR_GENERAL]
    if not df_gen.empty:
        return df_gen.iloc[0]
    # Algunos orígenes (p. ej. v2) no traen la fila pre-agregada de resumen:
    # se calcula a partir del detalle por alumno.
    return _compute_general_from_alumnos(df[df["indicador"] == INDICADOR_ALUMNO])


def load_encuestas_detalle(sede, periodo, carrera, tipo):
    """Detalle de avance por materia/sección/grupo/docente."""
    df = load_encuestas_raw(sede, periodo, carrera, tipo)
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_DETALLE)
    df_det = df[df["indicador"] == INDICADOR_DETALLE]
    cols = [c for c in COLUMNAS_DETALLE if c in df_det.columns]
    return df_det[cols].reset_index(drop=True)


def load_encuestas_alumnos(sede, periodo, carrera, tipo):
    """Detalle a nivel de alumno (1 fila por alumno x materia/sección/grupo),
    usado para calcular avances por distinct real en vez de sumar conteos
    ya agregados por docente."""
    df = load_encuestas_raw(sede, periodo, carrera, tipo)
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_ALUMNO)
    df_alu = df[df["indicador"] == INDICADOR_ALUMNO]
    cols = [c for c in COLUMNAS_ALUMNO if c in df_alu.columns]
    return df_alu[cols].reset_index(drop=True)
