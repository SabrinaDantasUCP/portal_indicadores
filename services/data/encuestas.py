import os

import pandas as pd
import streamlit as st

from utils import data_config, db_pia
from utils.data_loader import get_current_version, get_data_path, data_file_mtime
from utils.system_logging import log_exception


INDICADOR_GENERAL = "avance_general"
INDICADOR_DETALLE = "avance_por_materia_seccion_grupo"
INDICADOR_ALUMNO = "avance_por_alumno"

INDICADOR_GENERAL_DOCENTE = "avance_general_docente"
INDICADOR_DOCENTE_DETALLE = "avance_por_docente"

TIPO_ALUMNOS_DOCENTE = "ENCUESTA ALUMNOS A DOCENTES"
TIPO_AUTOEVALUACION_DOCENTE = "ENCUESTA AUTOEVALUACIÓN DOCENTE"
TIPO_EVALUACION_PARES = "ENCUESTA EVALUACIÓN DE PARES"

SEDE_ASUNCION = "Asunción"
SEDE_CIUDAD_DEL_ESTE = "Ciudad del Este"

# Lista fija: se muestran ambas sedes aunque todavía no haya datos cargados
# para alguna de ellas (por ahora sólo Ciudad del Este tiene encuestas).
SEDES = [SEDE_ASUNCION, SEDE_CIUDAD_DEL_ESTE]

# Traduce el código guardado en pia_encuesta_etl_config.tipo_encuesta (ver
# utils/db_pia.py) a la etiqueta usada acá y en modules/encuestas.py. Se
# mantiene esta capa para no tener que cambiar el resto del módulo (ni
# modules/encuestas.py, que importa estas constantes directamente).
_TIPO_CODE_TO_LABEL = {
    "ALUMNO_DOCENTE": TIPO_ALUMNOS_DOCENTE,
    "AUTOEVAL_DOCENTE": TIPO_AUTOEVALUACION_DOCENTE,
    "EVALUACION_PARES": TIPO_EVALUACION_PARES,
}

DATASETS_DIR = "assets/data/encuestas"


def _dataset_parquet_path(dataset_name):
    return f"{DATASETS_DIR}/{dataset_name}.parquet"


@st.cache_data(ttl=30, show_spinner=False)
def _construir_registro():
    """Arma sede -> periodo -> carrera -> tipo -> {dataset, nombre, scope} a
    partir de pia_encuesta_etl_config (antes era un dict ENCUESTAS_DATASETS
    hardcodeado acá; ahora se cadastra en Administración > Encuestas - ETL).

    De paso, sincroniza utils.data_config.DATASETS (en memoria, no se toca el
    archivo) con el path de cada dataset ya generado, para que
    utils.data_loader.get_data_path/data_file_mtime (usados también por
    app.py para el pie de "última actualización") sigan funcionando sin
    ningún cambio.

    Una config solo aparece acá si ya tiene al menos un parquet generado
    (v1 o v2, según el tipo) — pausar una config (activo=False) no la saca de
    acá; solo deja de recibir actualizaciones automáticas.

    Para scope_mode=GLOBAL hay un único archivo ({dataset_name}.parquet).
    Para SEGUE_VERSION (ALUMNO_DOCENTE) hay dos archivos separados
    ({dataset_name}_v1 / _v2) — v2 es la variante filtrada por
    assets/data/global/base_datos_activos.csv (ver services/etl/encuesta_runner.py).
    Si todavía no existe el v2 (por ej. el CSV de activos no fue subido), la
    config igual aparece acá con solo v1 disponible.
    """
    registro = {}
    for cfg in db_pia.get_encuesta_etl_configs():
        tipo_label = _TIPO_CODE_TO_LABEL.get(cfg["tipo_encuesta"])
        if tipo_label is None:
            continue

        dataset_name = cfg["dataset_name"]

        if cfg["scope_mode"] == "GLOBAL":
            dataset_path = _dataset_parquet_path(dataset_name)
            if not os.path.exists(dataset_path):
                continue
            data_config.DATASETS.setdefault("global", {})[dataset_name] = dataset_path
            scope = "global"
        else:
            path_v1 = _dataset_parquet_path(f"{dataset_name}_v1")
            path_v2 = _dataset_parquet_path(f"{dataset_name}_v2")
            if not os.path.exists(path_v1) and not os.path.exists(path_v2):
                continue
            if os.path.exists(path_v1):
                data_config.DATASETS.setdefault("indicadores_v1", {})[dataset_name] = path_v1
            if os.path.exists(path_v2):
                data_config.DATASETS.setdefault("indicadores_v2", {})[dataset_name] = path_v2
            scope = None

        (
            registro
            .setdefault(cfg["sede"], {})
            .setdefault(cfg["periodo"], {})
            .setdefault(cfg["carrera"], {})
        )[tipo_label] = {
            "dataset": dataset_name,
            "nombre": f"{tipo_label} {cfg['periodo']}",
            "scope": scope,
        }
    return registro


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
    "docente",
    "system_id",
    "alumno",
    "planificacion_id",
    "respondio",
]

COLUMNAS_DOCENTE_DETALLE = [
    "materia",
    "seccion",
    "grupo",
    "docente",
    "docente_id",
    "planificacion_id",
    "respondio",
]


def listar_sedes_encuestas():
    return SEDES


def listar_periodos_encuestas(sede):
    return sorted(_construir_registro().get(sede, {}).keys())


def listar_carreras_encuesta(sede, periodo):
    return sorted(_construir_registro().get(sede, {}).get(periodo, {}).keys())


def listar_tipos_encuesta(sede, periodo, carrera):
    """Devuelve [(tipo, label), ...] disponibles para sede/periodo/carrera."""
    tipos = _construir_registro().get(sede, {}).get(periodo, {}).get(carrera, {})
    resultado = []
    for tipo, info in tipos.items():
        vigencia, _ = load_encuestas_metadata(sede, periodo, carrera, tipo)
        label = f"{info['nombre']} ({vigencia})" if vigencia else info["nombre"]
        resultado.append((tipo, label))
    return resultado


def _get_encuesta_info(sede, periodo, carrera, tipo):
    try:
        return _construir_registro()[sede][periodo][carrera][tipo]
    except KeyError as exc:
        raise KeyError(
            f"Encuesta no configurada para sede={sede} / periodo={periodo} "
            f"/ carrera={carrera} / tipo={tipo}"
        ) from exc


def get_encuesta_nombre(sede, periodo, carrera, tipo):
    return _get_encuesta_info(sede, periodo, carrera, tipo)["nombre"]


def get_encuestas_dataset(sede, periodo, carrera, tipo):
    return _get_encuesta_info(sede, periodo, carrera, tipo)["dataset"]


def get_encuesta_scope(sede, periodo, carrera, tipo):
    """Scope bajo el que vive el dataset en utils/data_config.py: "global"
    si la config tiene scope_mode=GLOBAL, o si no, la versión activa en ese
    momento (indicadores_v1/v2)."""
    info = _get_encuesta_info(sede, periodo, carrera, tipo)
    return info.get("scope") or get_current_version()


@st.cache_data(show_spinner=False)
def _read_encuestas_parquet(dataset_name, version, mtime):
    try:
        return pd.read_parquet(get_data_path(dataset_name, version))
    except Exception as exc:
        log_exception(f"No se pudieron cargar datos de encuestas: {dataset_name} ({version})", exc)
        return pd.DataFrame()


def load_encuestas_raw(sede, periodo, carrera, tipo):
    dataset_name = get_encuestas_dataset(sede, periodo, carrera, tipo)
    # El scope (versión activa o "global") se pasa explícito como parte de la
    # clave de caché de _read_encuestas_parquet: sin esto, cambiar de V1 a V2
    # con la misma sede/periodo/carrera/tipo devolvería datos cacheados de la
    # otra versión. El mtime del archivo también entra en la clave: sin esto,
    # el cron regenerando el parquet mientras el proceso de Streamlit sigue
    # corriendo dejaría el dashboard mostrando datos viejos hasta reiniciar.
    scope = get_encuesta_scope(sede, periodo, carrera, tipo)
    mtime = data_file_mtime(dataset_name, scope)
    return _read_encuestas_parquet(dataset_name, scope, mtime)


def load_encuestas_metadata(sede, periodo, carrera, tipo):
    """(vigencia, semestres_habilitados) tal como vienen en el CSV/parquet de
    origen (columnas "vigencia" y "semestres_habilitados"), no hardcodeados
    en ENCUESTAS_DATASETS, para que reflejen siempre el dato real cargado."""
    df = load_encuestas_raw(sede, periodo, carrera, tipo)
    if df.empty:
        return None, None
    fila = df.iloc[0]
    vigencia = fila.get("vigencia")
    semestres_habilitados = fila.get("semestres_habilitados")
    return (
        vigencia if _valor_valido_metadata(vigencia) else None,
        semestres_habilitados if _valor_valido_metadata(semestres_habilitados) else None,
    )


def _valor_valido_metadata(valor):
    try:
        return valor is not None and not pd.isna(valor)
    except TypeError:
        return valor is not None


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


def load_autoeval_docente_general(sede, periodo, carrera, tipo):
    """Fila única con los totales generales de avance de la autoevaluación
    docente (docentes únicos esperados / que respondieron), o None."""
    df = load_encuestas_raw(sede, periodo, carrera, tipo)
    if df.empty:
        return None
    df_gen = df[df["indicador"] == INDICADOR_GENERAL_DOCENTE]
    return df_gen.iloc[0] if not df_gen.empty else None


def load_autoeval_docente_detalle(sede, periodo, carrera, tipo):
    """Detalle de autoevaluación docente: 1 fila por docente x materia/
    sección/grupo que dicta, con si respondió o no su autoevaluación para
    ese grupo."""
    df = load_encuestas_raw(sede, periodo, carrera, tipo)
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_DOCENTE_DETALLE)
    df_det = df[df["indicador"] == INDICADOR_DOCENTE_DETALLE]
    cols = [c for c in COLUMNAS_DOCENTE_DETALLE if c in df_det.columns]
    return df_det[cols].reset_index(drop=True)
