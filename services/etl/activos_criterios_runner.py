"""
services/etl/activos_criterios_runner.py

Orquesta el ETL de "Alumnos Activos" (pia_activos_criterios_config.periodos).
La población oficial de alumnos activos se cierra FUERA del portal (ETL
etl_unico_activos_2018_2_2026_1.py + consolidado "Alumnos Reales Max 2
Recursantes") y se sube en la pantalla de admin "Alumnos Activos"
(services/etl/activos_ids.guardar_poblacion -> POBLACION_CSV_PATH). Este
runner NO recalcula criterios, notas, recortes ni cohortes: solo filtra esa
población por los periodos configurados y escribe los dos archivos que leen
los demás ETL:

- usuarios_activos_ids.txt (guardar_ids_activos): ids únicos.
- usuarios_activos_periodos.csv (guardar_pares_activos):
  {(usuarios_id, periodo): semestre}, con el semestre tal cual viene en la
  población.

Por eso este pipeline es independiente de alumnos_runner.py/
asistencias_runner.py/encuesta_runner.py: no los llama ni depende de ellos,
solo alimenta la fuente (`cargar_ids_activos()`/`cargar_pares_activos()`)
que esos tres ya leen sin ningún cambio. Para que el filtro v2 de esos tres
refleje la población más reciente, este pipeline debe correr ANTES que ellos
(ver el cron sugerido en scripts/run_activos_criterios_etl_cron.sh).

services/etl/activos_criterios_etl.py (el cálculo por criterios anterior)
se conserva en el repo pero ya no se usa desde aquí.

No toca la base de datos "pia" salvo el registro del run: quien llama
(modules/activos_config_etl.py o scripts/run_activos_criterios_etl_cron.py)
es responsable de eso vía utils/db_pia.registrar_activos_criterios_run.
"""

import os

from services.etl.activos_ids import (
    cargar_poblacion,
    guardar_ids_activos,
    guardar_pares_activos,
    totales_por_periodo,
)
from services.etl.alumnos_runner import EGRESADOS_XLSX_PATH  # noqa: F401 -- re-exportado para modules/activos_config_etl.py
from scripts.csv_to_parquet import BASE_DIR
from utils.system_logging import get_logger

log = get_logger()

TFG_XLSX_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "tfg.xlsx")
RUES_XLSX_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "rues.xlsx")


def _resultado(status, cantidad_ids=None, mensaje_error=None) -> dict:
    return {
        "status": status,
        "cantidad_ids": cantidad_ids,
        "diagnostico_referencia": [],
        "faltantes_forzados": [],
        "mensaje_error": mensaje_error,
    }


def ejecutar_activos_criterios_etl(periodos: list, referencia: dict = None,
                                    on_progress=None, cancel_check=None) -> dict:
    """Filtra la población oficial (cargar_poblacion) por los `periodos`
    dados (lista de strings "AAAA.S") y, si queda algún alumno, sobrescribe
    usuarios_activos_ids.txt y usuarios_activos_periodos.csv.

    `referencia` se ignora (se mantiene solo por compatibilidad con el cron
    y la pantalla de admin). on_progress(mensaje: str) se llama en cada
    paso; si cancel_check() devuelve True antes de grabar, no se toca ningún
    archivo. Si falla, tampoco (los ETL de Alumnos/Asistencias/Encuestas
    siguen usando el último resultado válido).

    Retorna {"status": "OK"|"ERROR"|"CANCELADO", "cantidad_ids": int|None,
    "diagnostico_referencia": [], "faltantes_forzados": [],
    "mensaje_error": str|None} -- con status OK, mensaje_error es un aviso
    (periodos ignorados / sin alumnos) o None. Nunca lanza.
    """
    def progreso(mensaje):
        if on_progress:
            on_progress(mensaje)

    try:
        progreso("Leyendo la población de alumnos activos...")
        poblacion = cargar_poblacion()
        if poblacion is None or poblacion.empty:
            return _resultado(
                "ERROR",
                mensaje_error=(
                    "No se subió la población de alumnos activos (CSV). Súbala en la pantalla "
                    "'Alumnos Activos' antes de ejecutar el ETL. No se modificó ningún archivo."
                ),
            )

        periodos = [str(p).strip() for p in periodos]
        periodos_poblacion = list(totales_por_periodo(poblacion).index)
        filtrada = poblacion[poblacion["periodo"].isin(periodos)]
        if filtrada.empty:
            return _resultado(
                "ERROR",
                mensaje_error=(
                    f"La población no tiene alumnos en los periodos configurados ({', '.join(periodos)}). "
                    f"Periodos presentes en el CSV: {', '.join(periodos_poblacion)}. "
                    "No se modificó ningún archivo."
                ),
            )

        if cancel_check and cancel_check():
            return _resultado(
                "CANCELADO",
                mensaje_error="Ejecución cancelada por el usuario. No se modificó ningún archivo.",
            )

        progreso(f"Grabando {filtrada['usuarios_id'].nunique()} ids activos...")
        ids = sorted(filtrada["usuarios_id"].unique())
        cantidad = guardar_ids_activos("\n".join(str(i) for i in ids))
        pares = {
            (int(uid), periodo): int(sem)
            for uid, periodo, sem in zip(filtrada["usuarios_id"], filtrada["periodo"], filtrada["semestre"])
        }
        guardar_pares_activos(pares)
        progreso(f"Listo: {cantidad} ids, {len(pares)} pares alumno-periodo.")

        partes_aviso = []
        ignorados = [p for p in periodos_poblacion if p not in periodos]
        if ignorados:
            partes_aviso.append(
                f"Periodos del CSV fuera de la configuración (ignorados): {', '.join(ignorados)}."
            )
        sin_alumnos = [p for p in periodos if p not in periodos_poblacion]
        if sin_alumnos:
            partes_aviso.append(f"Periodos configurados sin alumnos en el CSV: {', '.join(sin_alumnos)}.")

        return _resultado("OK", cantidad_ids=cantidad, mensaje_error=" ".join(partes_aviso) or None)
    except Exception as exc:
        log.exception("Fallo el ETL de activos (periodos=%s)", periodos)
        return _resultado("ERROR", mensaje_error=str(exc))
