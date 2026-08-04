"""
services/etl/permanencia_runner.py

Orquesta la ejecución del ETL de Índice de Permanencia para un periodo dado
(pia_permanencia_etl_config: fecha_corte + corte_generado + activo por
periodo). Dos archivos por periodo, ambos en assets/data/global/:

  - permanencia_{label}.csv/parquet        -- "visión general", se
    sobrescribe en CADA ejecución (foto del día).
  - permanencia_{label}_corte.csv/parquet  -- snapshot CONGELADO: se escribe
    una única vez, la primera vez que se ejecuta el ETL en una fecha >= a la
    fecha_corte configurada para ese periodo. Una vez escrito, nunca se
    vuelve a sobrescribir (corte_generado pasa a True) -- así el indicador
    "Fecha de Corte" del dashboard siempre lee la misma foto congelada.

No usa fecha en el nombre de archivo (a diferencia del script original) para
no acoplar utils/data_config.py a la fecha de corte configurada -- ver
services/data/permanencia.py, que ya registra estos dos nombres fijos por
periodo.

No toca la base de datos "pia": quien llama (modules/permanencia_config_etl.py
o scripts/run_permanencia_etl_cron.py) es responsable de registrar el
resultado vía utils/db_pia.registrar_permanencia_etl_run y de marcar
corte_generado vía utils/db_pia.marcar_permanencia_corte_generado.
"""

import os
from datetime import date

from services.etl import permanencia_etl as etl
from scripts.csv_to_parquet import BASE_DIR, convert as convertir_a_parquet
from utils.system_logging import get_logger

log = get_logger()

TOTAL_PASOS = 6


def _rutas(label):
    return (
        os.path.join("assets", "data", "global", f"permanencia_{label}.csv"),
        os.path.join("assets", "data", "global", f"permanencia_{label}_corte.csv"),
    )


def _escribir_dataset(csv_path_rel, df):
    csv_path_abs = os.path.join(BASE_DIR, csv_path_rel)
    os.makedirs(os.path.dirname(csv_path_abs), exist_ok=True)
    df.to_csv(csv_path_abs, index=False, sep=";", encoding="utf-8-sig")
    convertir_a_parquet(csv_path_rel, ";", False, force=True)
    return csv_path_abs


def ejecutar_permanencia_etl(periodo: str, fecha_corte, corte_generado: bool,
                              on_progress=None, cancel_check=None) -> dict:
    """Ejecuta el pipeline completo para `periodo` (ej. '2026.1').

    fecha_corte: date|None -- fecha configurada para congelar el snapshot de
    este periodo (ver pia_permanencia_etl_config). corte_generado: bool --
    si ya se congeló antes (no se vuelve a hacer).

    on_progress(indice, total, etiqueta): 6 pasos fijos (extracción
    financiera, auditoría, notas, unificación, guardado de visión general,
    chequeo/guardado de fecha de corte).
    cancel_check(): se consulta ANTES de cada paso -- si se cancela, no se
    escribe ningún archivo (la escritura ocurre recién en los pasos 5/6,
    después de tener todo el DataFrame final armado).

    Retorna {"status": "OK"|"ERROR"|"CANCELADO", "filas": int|None,
    "corte_generado_ahora": bool, "mensaje_error": str|None}. Nunca lanza.
    """
    def _cancelado_check():
        return cancel_check is not None and cancel_check()

    def _paso(i, etiqueta):
        if on_progress is not None:
            on_progress(i, TOTAL_PASOS, etiqueta)

    def _resultado_cancelado():
        return {
            "status": "CANCELADO", "filas": None, "corte_generado_ahora": False,
            "mensaje_error": "Ejecución cancelada por el usuario. No se modificó ningún archivo.",
        }

    try:
        ids = etl.derivar_ids_periodo(periodo)
        engine = etl.obtener_engine()

        if _cancelado_check():
            return _resultado_cancelado()
        _paso(1, "Extrayendo matrículas/facturas (actual + próximo)")
        df_atual, df_proximo = etl.extraer_matriculas_financiero(engine, ids)

        if _cancelado_check():
            return _resultado_cancelado()
        _paso(2, "Extrayendo auditoría de cambios de matrícula")
        df_log = etl.extraer_auditoria(engine, df_atual)

        if _cancelado_check():
            return _resultado_cancelado()
        _paso(3, "Calculando notas (aprobado/reprobado)")
        ids_alumnos = df_atual["id_alumno"].dropna().astype(int).unique().tolist()
        ids_periodos = df_atual["periodo_lectivo_id"].dropna().astype(int).unique().tolist()
        df_notas = etl.calcular_notas(engine, ids_alumnos, ids_periodos)

        if _cancelado_check():
            return _resultado_cancelado()
        _paso(4, "Unificando resultado final")
        df_final = etl.unificar(df_atual, df_proximo, df_log, df_notas)

        if _cancelado_check():
            return _resultado_cancelado()
        _paso(5, "Guardando visión general")
        vg_csv_rel, corte_csv_rel = _rutas(ids["label_actual"])
        _escribir_dataset(vg_csv_rel, df_final)

        corte_generado_ahora = False
        if not corte_generado and fecha_corte is not None and date.today() >= fecha_corte:
            _paso(6, "Congelando snapshot de fecha de corte")
            _escribir_dataset(corte_csv_rel, df_final)
            corte_generado_ahora = True
        else:
            _paso(6, "Fecha de corte no alcanzada (o ya congelada) -- sin cambios en el snapshot")

        return {
            "status": "OK",
            "filas": len(df_final),
            "corte_generado_ahora": corte_generado_ahora,
            "mensaje_error": None,
        }
    except Exception as exc:
        log.exception("Fallo el ETL de permanencia (periodo=%s)", periodo)
        return {
            "status": "ERROR",
            "filas": None,
            "corte_generado_ahora": False,
            "mensaje_error": str(exc),
        }
