"""
services/etl/activos_criterios_runner.py

Orquesta la ejecución del ETL de "Alumnos Activos por Criterios"
(pia_activos_criterios_config.periodos): llama a
services/etl/activos_criterios_etl.calcular_ids_activos y, si sale OK,
escribe el resultado con services/etl/activos_ids.guardar_ids_activos --
el MISMO archivo (assets/data/global/usuarios_activos_ids.txt) que hoy se
sube a mano en la pantalla de admin "Alumnos Activos".

Por eso este pipeline es independiente de alumnos_runner.py/
asistencias_runner.py/encuesta_runner.py: no los llama ni depende de ellos,
solo alimenta la fuente (`cargar_ids_activos()`) que esos tres ya leen sin
ningún cambio. Para que el filtro v2 de esos tres refleje el cálculo más
reciente, este pipeline debe correr ANTES que ellos (ver el cron horario
sugerido en scripts/run_activos_criterios_etl_cron.sh).

No toca la base de datos "pia" salvo el registro del run: quien llama
(modules/activos_config_etl.py o scripts/run_activos_criterios_etl_cron.py)
es responsable de eso vía utils/db_pia.registrar_activos_criterios_run.
"""

import os

from services.etl import activos_criterios_etl as etl
from services.etl.activos_ids import guardar_ids_activos, guardar_pares_activos
from services.etl.alumnos_runner import EGRESADOS_XLSX_PATH
from scripts.csv_to_parquet import BASE_DIR
from utils.system_logging import get_logger

log = get_logger()

TFG_XLSX_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "tfg.xlsx")
RUES_XLSX_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "rues.xlsx")


def ejecutar_activos_criterios_etl(periodos: list, referencia: dict = None,
                                    on_progress=None, cancel_check=None) -> dict:
    """Ejecuta el cálculo completo de "alumnos activos" para los `periodos`
    dados (lista de strings "AAAA.S") y, si sale OK, sobrescribe
    usuarios_activos_ids.txt con el resultado.

    on_progress(mensaje: str) y cancel_check() se pasan tal cual a
    calcular_ids_activos. Si se cancela o falla, NO se toca el archivo
    existente (los ETL de Alumnos/Asistencias/Encuestas siguen usando el
    último resultado válido).

    Retorna {"status": "OK"|"ERROR"|"CANCELADO", "cantidad_ids": int|None,
    "diagnostico_referencia": list, "faltantes_forzados": list,
    "mensaje_error": str|None}. Nunca lanza.
    """
    try:
        resultado = etl.calcular_ids_activos(
            periodos,
            egresados_path=EGRESADOS_XLSX_PATH,
            tfg_path=TFG_XLSX_PATH,
            rues_path=RUES_XLSX_PATH,
            referencia=referencia,
            on_progress=on_progress,
            cancel_check=cancel_check,
        )

        if resultado.get("cancelado"):
            return {
                "status": "CANCELADO",
                "cantidad_ids": None,
                "diagnostico_referencia": [],
                "faltantes_forzados": [],
                "mensaje_error": "Ejecución cancelada por el usuario. No se modificó ningún archivo.",
            }

        ids_activos = resultado["ids_activos"]
        if not ids_activos:
            raise RuntimeError(
                "El cálculo no arrojó ningún usuario activo -- no se sobrescribe el archivo existente."
            )

        texto = "\n".join(str(i) for i in sorted(ids_activos))
        cantidad = guardar_ids_activos(texto)
        guardar_pares_activos(resultado["pares_activos"])

        partes_aviso = []
        if resultado["faltantes_forzados"]:
            partes_aviso.append(
                f"{len(resultado['faltantes_forzados'])} id(s) de egresados/TFG/RUES no se "
                "encontraron en ningún periodo_letivo."
            )
        shortfalls = [d for d in resultado["diagnostico_referencia"] if d["tipo"] == "shortfall"]
        if shortfalls:
            partes_aviso.append(f"{len(shortfalls)} celda(s) periodo/semestre por debajo del valor de referencia.")

        return {
            "status": "OK",
            "cantidad_ids": cantidad,
            "diagnostico_referencia": resultado["diagnostico_referencia"],
            "faltantes_forzados": resultado["faltantes_forzados"],
            "mensaje_error": "; ".join(partes_aviso) if partes_aviso else None,
        }
    except Exception as exc:
        log.exception("Fallo el ETL de activos por criterios (periodos=%s)", periodos)
        return {
            "status": "ERROR",
            "cantidad_ids": None,
            "diagnostico_referencia": [],
            "faltantes_forzados": [],
            "mensaje_error": str(exc),
        }
