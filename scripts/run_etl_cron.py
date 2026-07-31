#!/usr/bin/env python
"""
scripts/run_etl_cron.py

Punto de entrada del cron 3x al día (ver scripts/run_etl_cron.sh). Busca
todas las configuraciones activas en pia_encuesta_etl_config y ejecuta el
ETL de cada una vía services/etl/encuesta_runner.ejecutar_config, registrando
el resultado en pia_encuesta_etl_run. Una falla en una configuración (p. ej.
VPN del ERP caída) no interrumpe la ejecución de las demás.
"""

import sys
from datetime import datetime

from utils import db_pia
from services.etl.encuesta_runner import ejecutar_config


def main():
    configs = db_pia.get_encuesta_etl_configs_activos()
    print(f"[{datetime.now()}] {len(configs)} configuración(es) activa(s) encontrada(s).")

    hubo_error = False
    for cfg in configs:
        nombre = f"{cfg['tipo_encuesta']} / {cfg['sede']} / {cfg['periodo']} / {cfg['carrera']}"
        print(f"[{datetime.now()}] Ejecutando: {nombre} (dataset={cfg['dataset_name']})")

        iniciado_en = datetime.now()
        try:
            resultado = ejecutar_config(cfg)
        except Exception as exc:
            resultado = {"status": "ERROR", "filas": None, "mensaje_error": str(exc)}
        finalizado_en = datetime.now()

        db_pia.registrar_encuesta_etl_run(
            config_id=cfg["id"],
            disparado_por="CRON",
            status=resultado["status"],
            iniciado_en=iniciado_en,
            finalizado_en=finalizado_en,
            filas_generadas=resultado["filas"],
            mensaje_error=resultado["mensaje_error"],
        )

        if resultado["status"] == "OK":
            print(f"[{datetime.now()}] OK: {nombre} -> {resultado['filas']} filas.")
        else:
            hubo_error = True
            print(f"[{datetime.now()}] ERROR: {nombre} -> {resultado['mensaje_error']}")

    if hubo_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
