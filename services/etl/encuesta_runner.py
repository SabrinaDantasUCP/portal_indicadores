"""
services/etl/encuesta_runner.py

Orquesta la ejecución del ETL de encuestas para una configuración
(pia_encuesta_etl_config) dada: llama a las funciones puras de
services/etl/encuestas_etl.py según el tipo de encuesta, combina los
indicadores resultantes y los deja listos en assets/data/encuestas/ — el
lugar de donde services/data/encuestas.py los lee.

Para ALUMNO_DOCENTE se generan DOS archivos:
  - {dataset_name}_v1: todos los alumnos (según QUERY_CONTACTO).
  - {dataset_name}_v2: igual, pero avance_por_alumno restringido a los ids
    subidos en la pantalla de admin "Alumnos Activos" (ver
    services/etl/activos_ids.py, que reemplazó el antiguo
    assets/data/global/base_datos_activos.csv). Si todavía no se subió
    ningún archivo, se genera solo el v1 y se deja el v2 como estaba (no se
    borra), con un warning en el log.
Para AUTOEVAL_DOCENTE se genera un único archivo {dataset_name} (scope
GLOBAL, no depende del toggle v1/v2).

No toca la base de datos "pia": quien llama (modules/encuestas_config_etl.py
o scripts/run_etl_cron.py) es responsable de registrar el resultado en
pia_encuesta_etl_run vía utils/db_pia.registrar_encuesta_etl_run.
"""

import os

import pandas as pd

from services.etl import encuestas_etl as etl
from services.etl.activos_ids import cargar_ids_activos
from scripts.csv_to_parquet import BASE_DIR, convert as convertir_a_parquet
from utils.system_logging import get_logger

log = get_logger()

TIPO_ALUMNO_DOCENTE = "ALUMNO_DOCENTE"
TIPO_AUTOEVAL_DOCENTE = "AUTOEVAL_DOCENTE"
TIPO_EVALUACION_PARES = "EVALUACION_PARES"

DATASET_DIR_REL = os.path.join("assets", "data", "encuestas")
RAW_OUTPUT_DIR = os.path.join(BASE_DIR, "output")


class PipelineNoImplementado(Exception):
    """El tipo_encuesta es válido pero todavía no tiene pipeline de ETL."""


def _combinar_exports(exports: dict) -> pd.DataFrame:
    return pd.concat(list(exports.values()), ignore_index=True, sort=False)


def _escribir_dataset(nombre_archivo: str, df: pd.DataFrame) -> str:
    """nombre_archivo ya incluye el sufijo _v1/_v2 cuando corresponde, sin extensión."""
    dataset_dir_abs = os.path.join(BASE_DIR, DATASET_DIR_REL)
    os.makedirs(dataset_dir_abs, exist_ok=True)

    csv_path_rel = os.path.join(DATASET_DIR_REL, f"{nombre_archivo}.csv")
    csv_path_abs = os.path.join(BASE_DIR, csv_path_rel)
    df.to_csv(csv_path_abs, index=False, encoding="utf-8-sig")

    convertir_a_parquet(csv_path_rel, ",", False, force=True)
    return csv_path_abs


def _ejecutar_alumno_docente(config: dict) -> int:
    parametros = etl.derivar_parametros_periodo(config["periodo"])
    anho, subperiodo, semestre_bio = parametros["anho"], parametros["subperiodo"], parametros["semestre_bio"]
    dataset_name = config["dataset_name"]

    etl.exportar_planificacion(anho=anho, semestre=semestre_bio, output_dir=RAW_OUTPUT_DIR)
    etl.exportar_respuestas(
        id_encuesta=config["id_encuesta_externa"], anho=anho, subperiodo=subperiodo, output_dir=RAW_OUTPUT_DIR
    )
    exports = etl.generar_indicadores(
        id_encuesta=config["id_encuesta_externa"],
        anho=anho,
        semestre=semestre_bio,
        subperiodo=subperiodo,
        output_dir=RAW_OUTPUT_DIR,
        offline_plan_csv=os.path.join(RAW_OUTPUT_DIR, "planificacion_raw.csv"),
        offline_resp_csv=os.path.join(RAW_OUTPUT_DIR, "respuestas_raw.csv"),
        offline_encuesta_csv=os.path.join(RAW_OUTPUT_DIR, "encuesta_raw.csv"),
        offline_contacto_csv=os.path.join(RAW_OUTPUT_DIR, "contacto_raw.csv"),
    )

    df_v1 = _combinar_exports(exports)
    _escribir_dataset(f"{dataset_name}_v1", df_v1)

    ids_activos = cargar_ids_activos()
    if ids_activos:
        exports_v2 = dict(exports)
        exports_v2["avance_por_alumno"] = etl.filtrar_avance_por_alumno_activos(
            exports["avance_por_alumno"], ids_activos
        )
        df_v2 = _combinar_exports(exports_v2)
        _escribir_dataset(f"{dataset_name}_v2", df_v2)
    else:
        log.warning(
            "No hay ningún archivo de ids activos subido (pantalla admin 'Alumnos Activos'): "
            "no se generó la variante v2 para dataset=%s. El dashboard sigue mostrando el v2 anterior (si existía).",
            dataset_name,
        )

    return len(df_v1)


def _ejecutar_autoeval_docente(config: dict) -> dict:
    parametros = etl.derivar_parametros_periodo(config["periodo"])
    anho, semestre_bio = parametros["anho"], parametros["semestre_bio"]

    etl.exportar_planificacion(anho=anho, semestre=semestre_bio, output_dir=RAW_OUTPUT_DIR)
    etl.exportar_respuestas_docente(
        id_encuesta=config["id_encuesta_externa"], output_dir=RAW_OUTPUT_DIR
    )
    id_encuesta = config["id_encuesta_externa"]
    return etl.generar_indicadores_docente_autoeval(
        id_encuesta=id_encuesta,
        anho=anho,
        semestre=semestre_bio,
        output_dir=RAW_OUTPUT_DIR,
        offline_plan_csv=os.path.join(RAW_OUTPUT_DIR, "planificacion_raw.csv"),
        offline_resp_csv=os.path.join(RAW_OUTPUT_DIR, f"respuestas_docente_raw_{id_encuesta}.csv"),
        offline_encuesta_csv=os.path.join(RAW_OUTPUT_DIR, f"encuesta_docente_raw_{id_encuesta}.csv"),
    )


def ejecutar_config(config: dict) -> dict:
    """Ejecuta el pipeline correspondiente a `config` (una fila de
    pia_encuesta_etl_config) de punta a punta: consulta bio + ERP, calcula
    los indicadores y deja el parquet listo para el dashboard.

    Retorna {"status": "OK"|"ERROR", "filas": int|None, "mensaje_error": str|None}.
    Nunca lanza: cualquier falla (VPN caída, query rota, etc.) se captura y
    se devuelve como status "ERROR" con un mensaje legible.
    """
    tipo = config["tipo_encuesta"]
    dataset_name = config["dataset_name"]

    try:
        if tipo == TIPO_ALUMNO_DOCENTE:
            # Genera v1 y (si hay un archivo de ids activos subido) v2 internamente.
            filas = _ejecutar_alumno_docente(config)
        elif tipo == TIPO_AUTOEVAL_DOCENTE:
            exports = _ejecutar_autoeval_docente(config)
            df_combinado = _combinar_exports(exports)
            _escribir_dataset(dataset_name, df_combinado)
            filas = len(df_combinado)
        elif tipo == TIPO_EVALUACION_PARES:
            raise PipelineNoImplementado(
                "El pipeline de 'Evaluación de pares' todavía no está implementado."
            )
        else:
            raise ValueError(f"tipo_encuesta desconocido: {tipo!r}")

        return {"status": "OK", "filas": filas, "mensaje_error": None}
    except Exception as exc:
        log_exception_msg = f"Fallo el ETL de encuesta config_id={config.get('id')} dataset={dataset_name}"
        log.exception(log_exception_msg)
        return {"status": "ERROR", "filas": None, "mensaje_error": str(exc)}
