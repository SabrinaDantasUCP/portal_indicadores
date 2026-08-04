"""
services/etl/asistencias_runner.py

Orquesta la ejecución del ETL de asistencias para una config dada
(pia_asistencias_etl_config: años de SysEduca + periodos de Biometría). Arma
asistencia_unificada_v1 (todos los alumnos) y asistencia_unificada_v2 (solo
activos) y los deja listos en assets/data/v1 y assets/data/v2 -- el lugar de
donde services/data/asistencia.py los lee.

Los datos crudos se extraen UNA sola vez (ver services/etl/asistencias_etl.py);
v1 y v2 se calculan ambos a partir de esa misma extracción, sin repetir las
consultas a SysEduca/Biometría.

No toca la base de datos "pia": quien llama (modules/asistencias_config_etl.py
o scripts/run_asistencias_etl_cron.py) es responsable de registrar el
resultado vía utils/db_pia.registrar_asistencias_etl_run.
"""

import os

from services.etl import asistencias_etl as etl
from scripts.csv_to_parquet import BASE_DIR, convert as convertir_a_parquet
from utils.system_logging import get_logger

log = get_logger()

V1_CSV_REL = os.path.join("assets", "data", "v1", "asistencia_unificada_v1.csv")
V2_CSV_REL = os.path.join("assets", "data", "v2", "asistencia_unificada_v2.csv")
ACTIVOS_CSV_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "base_datos_activos.csv")


class SinDatosError(Exception):
    """Ni SysEduca ni Biometría devolvieron datos para los años/periodos configurados."""


def _escribir_dataset(csv_path_rel, df):
    csv_path_abs = os.path.join(BASE_DIR, csv_path_rel)
    os.makedirs(os.path.dirname(csv_path_abs), exist_ok=True)
    df.to_csv(csv_path_abs, index=False, encoding="utf-8-sig")
    convertir_a_parquet(csv_path_rel, ",", True, force=True)
    return csv_path_abs


def _cargar_ids_activos():
    import pandas as pd
    activos = pd.read_csv(ACTIVOS_CSV_PATH, encoding="utf-8-sig")
    return set(activos["ID_Alumno"].dropna().astype("int64"))


def ejecutar_asistencias_etl(anos_syseduca: list, periodos_biometria: list, on_progress=None, cancel_check=None) -> dict:
    """Ejecuta el pipeline completo (SysEduca por año + Biometría por
    periodo -> asistencia_unificada_v1/v2).

    on_progress(indice, total, etiqueta): indice/total son continuos entre
    las dos fases (SysEduca primero, Biometría después); etiqueta es un
    string tipo "SysEduca 2024" o "Biometría 2025.2".
    cancel_check(): se consulta entre cada año/periodo -- ver
    services.etl.asistencias_etl.procesar_anos_syseduca/procesar_periodos_biometria.
    Si se cancela, NO se escribe ningún archivo.

    Retorna {"status": "OK"|"ERROR"|"CANCELADO", "filas_v1": int|None,
    "filas_v2": int|None, "anos_con_error": list, "periodos_con_error": list,
    "mensaje_error": str|None}. Nunca lanza.
    """
    total = len(anos_syseduca) + len(periodos_biometria)
    try:
        df_crudo_sys, anos_con_error, cancelado = etl.procesar_anos_syseduca(
            anos_syseduca, on_progress=on_progress, cancel_check=cancel_check, indice_inicial=0, total=total
        )
        if cancelado:
            return {
                "status": "CANCELADO", "filas_v1": None, "filas_v2": None,
                "anos_con_error": anos_con_error, "periodos_con_error": [],
                "mensaje_error": "Ejecución cancelada por el usuario. No se modificó ningún archivo.",
            }

        df_crudo_bio, periodos_con_error, cancelado = etl.procesar_periodos_biometria(
            periodos_biometria, on_progress=on_progress, cancel_check=cancel_check,
            indice_inicial=len(anos_syseduca), total=total,
        )
        if cancelado:
            return {
                "status": "CANCELADO", "filas_v1": None, "filas_v2": None,
                "anos_con_error": anos_con_error, "periodos_con_error": periodos_con_error,
                "mensaje_error": "Ejecución cancelada por el usuario. No se modificó ningún archivo.",
            }

        if df_crudo_sys.empty and df_crudo_bio.empty:
            raise SinDatosError(
                f"Ni SysEduca (años {anos_syseduca}) ni Biometría (periodos {periodos_biometria}) "
                "devolvieron datos. Revisar la conexión a las fuentes o si hay clases en ese rango."
            )

        df_matriculados = etl.fetch_matriculados()
        detalle_sys = etl.parsear_detalle_syseduca(df_crudo_sys) if not df_crudo_sys.empty else df_crudo_sys

        df_v1_sys = etl.agregar_syseduca(detalle_sys, df_matriculados, ids_activos=None)
        df_v1_bio = etl.agregar_biometria(df_crudo_bio, df_matriculados, ids_activos=None)
        df_v1 = etl.unificar_asistencias(df_v1_sys, df_v1_bio)
        _escribir_dataset(V1_CSV_REL, df_v1)
        filas_v1 = len(df_v1)

        filas_v2 = None
        if os.path.exists(ACTIVOS_CSV_PATH):
            ids_activos = _cargar_ids_activos()
            df_v2_sys = etl.agregar_syseduca(detalle_sys, df_matriculados, ids_activos=ids_activos)
            df_v2_bio = etl.agregar_biometria(df_crudo_bio, df_matriculados, ids_activos=ids_activos)
            df_v2 = etl.unificar_asistencias(df_v2_sys, df_v2_bio)
            _escribir_dataset(V2_CSV_REL, df_v2)
            filas_v2 = len(df_v2)
        else:
            log.warning(
                "No se encontró %s: no se generó asistencia_unificada_v2 (filtrado por activos). "
                "El dashboard sigue mostrando el v2 anterior (si existía).",
                ACTIVOS_CSV_PATH,
            )

        partes_error = []
        if anos_con_error:
            partes_error.append(f"Años SysEduca sin datos: {anos_con_error}")
        if periodos_con_error:
            partes_error.append(f"Periodos Biometría sin datos: {periodos_con_error}")
        mensaje_error = "; ".join(partes_error) if partes_error else None

        return {
            "status": "OK",
            "filas_v1": filas_v1,
            "filas_v2": filas_v2,
            "anos_con_error": anos_con_error,
            "periodos_con_error": periodos_con_error,
            "mensaje_error": mensaje_error,
        }
    except Exception as exc:
        log.exception(
            "Fallo el ETL de asistencias (anos_syseduca=%s, periodos_biometria=%s)",
            anos_syseduca, periodos_biometria,
        )
        return {
            "status": "ERROR",
            "filas_v1": None,
            "filas_v2": None,
            "anos_con_error": anos_syseduca,
            "periodos_con_error": periodos_biometria,
            "mensaje_error": str(exc),
        }
