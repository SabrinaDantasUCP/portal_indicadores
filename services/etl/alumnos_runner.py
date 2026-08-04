"""
services/etl/alumnos_runner.py

Orquesta la ejecución del ETL de alumnos para una lista de años dada
(pia_alumnos_etl_config.anos): llama a services/etl/alumnos_etl.py, arma
alumnos_v1/alumnos_v2 y los deja listos en assets/data/v1 y assets/data/v2 —
el lugar de donde services/data/alumnos.py los lee (vía utils/data_config.py).

IMPORTANTE (bug corregido respecto al script original scripts/etl_alumnos.py):
el script original escribía "assets/data/alumnos_v1.csv"/"alumnos_v2.csv"
(sin la subcarpeta v1/v2) y nunca generaba el .parquet, así que el dashboard
(que solo lee los .parquet de assets/data/v1 y assets/data/v2) nunca reflejaba
lo que el ETL generaba. Este runner escribe en la ruta correcta y convierte a
parquet, igual que hace services/etl/encuesta_runner.py.

No toca la base de datos "pia": quien llama (modules/alumnos_config_etl.py o
scripts/run_alumnos_etl_cron.py) es responsable de registrar el resultado en
pia_alumnos_etl_run vía utils/db_pia.registrar_alumnos_etl_run.
"""

import os

from services.etl import alumnos_etl as etl
from scripts.csv_to_parquet import BASE_DIR, convert as convertir_a_parquet
from utils import db_pia
from utils.system_logging import get_logger

log = get_logger()

V1_CSV_REL = os.path.join("assets", "data", "v1", "alumnos_v1.csv")
V2_CSV_REL = os.path.join("assets", "data", "v2", "alumnos_v2.csv")
EGRESADOS_XLSX_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "egressados.xlsx")
ACTIVOS_CSV_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "base_datos_activos.csv")
TEMP_YEARS_DIR = os.path.join(BASE_DIR, "assets", "data", "temp_years")


class SinDatosError(Exception):
    """Ningún año configurado devolvió datos (falla de conexión o consultas vacías)."""


def _escribir_dataset(csv_path_rel, df):
    csv_path_abs = os.path.join(BASE_DIR, csv_path_rel)
    os.makedirs(os.path.dirname(csv_path_abs), exist_ok=True)
    df.to_csv(csv_path_abs, index=False, encoding="utf-8-sig")
    convertir_a_parquet(csv_path_rel, ",", True, force=True)
    return csv_path_abs


def ejecutar_alumnos_etl(anos: list, on_progress=None, cancel_check=None) -> dict:
    """Ejecuta el pipeline completo (matrículas+notas -> alumnos_v1 ->
    alumnos_v2) para los años dados.

    on_progress(indice, total, ano) y cancel_check() se pasan tal cual a
    services.etl.alumnos_etl.procesar_anos — ver ahí el detalle de cuándo se
    llaman. Si se cancela, NO se escribe ningún archivo (la escritura ocurre
    recién después de consolidar todos los años), así que un cancel siempre
    es seguro: los alumnos_v1/v2 existentes quedan intactos.

    Retorna {"status": "OK"|"ERROR"|"CANCELADO", "filas_v1": int|None,
    "filas_v2": int|None, "anos_con_error": list[int], "mensaje_error": str|None}.
    Nunca lanza: cualquier falla (MySQL caído, query rota, etc.) se captura y
    se devuelve como status "ERROR" con un mensaje legible.
    """
    try:
        df_consolidado, anos_con_error, cancelado = etl.procesar_anos(
            anos, pasta_temp=TEMP_YEARS_DIR, on_progress=on_progress, cancel_check=cancel_check
        )
        if cancelado:
            return {
                "status": "CANCELADO",
                "filas_v1": None,
                "filas_v2": None,
                "anos_con_error": anos_con_error,
                "mensaje_error": "Ejecución cancelada por el usuario. No se modificó ningún archivo.",
            }
        if df_consolidado is None:
            raise SinDatosError(
                f"Ningún año devolvió datos (años configurados: {anos}). "
                "Revisar la conexión a MySQL (MYSQL_HOST_SYS) o si hay matrículas para esos años."
            )

        egresados_meta = db_pia.get_egresados_meta()
        fecha_envio_egresados = egresados_meta["fecha_envio"] if egresados_meta else None
        df_v1 = etl.generar_alumnos_v1(
            df_consolidado,
            egresados_xlsx_path=EGRESADOS_XLSX_PATH,
            fecha_envio_egresados=fecha_envio_egresados,
        )
        _escribir_dataset(V1_CSV_REL, df_v1)
        filas_v1 = len(df_v1)

        filas_v2 = None
        if os.path.exists(ACTIVOS_CSV_PATH):
            df_v2 = etl.generar_alumnos_v2(df_v1, ACTIVOS_CSV_PATH)
            _escribir_dataset(V2_CSV_REL, df_v2)
            filas_v2 = len(df_v2)
        else:
            log.warning(
                "No se encontró %s: no se generó alumnos_v2 (filtrado por alumnos activos). "
                "El dashboard sigue mostrando el v2 anterior (si existía).",
                ACTIVOS_CSV_PATH,
            )

        mensaje_error = (
            f"Años sin datos (omitidos): {anos_con_error}" if anos_con_error else None
        )
        return {
            "status": "OK",
            "filas_v1": filas_v1,
            "filas_v2": filas_v2,
            "anos_con_error": anos_con_error,
            "mensaje_error": mensaje_error,
        }
    except Exception as exc:
        log.exception("Fallo el ETL de alumnos (anos=%s)", anos)
        return {
            "status": "ERROR",
            "filas_v1": None,
            "filas_v2": None,
            "anos_con_error": anos,
            "mensaje_error": str(exc),
        }
