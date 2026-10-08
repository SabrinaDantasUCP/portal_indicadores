#!/usr/bin/env python
"""
scripts/run_activos_criterios_etl_cron.py

Punto de entrada del cron de "Alumnos Activos por Criterios" (ver
scripts/run_activos_criterios_etl_cron.sh). Lee la configuración activa en
pia_activos_criterios_config (lista de periodos + toggle activo) y la tabla
de referencia (pia_activos_criterios_referencia), ejecuta el ETL vía
services/etl/activos_criterios_runner.ejecutar_activos_criterios_etl, y
registra el resultado en pia_activos_criterios_run.

IMPORTANTE: este cron debe programarse para correr ANTES que
run_alumnos_etl_cron.sh, run_asistencias_etl_cron.sh y run_etl_cron.sh
(encuestas) -- los tres leen el archivo que este script genera
(usuarios_activos_ids.txt) al armar su variante v2. Sugerido: 02:00 (los
demás corren a las 04:00).

No necesita VPN: se conecta directo a MYSQL_HOST_SYS (host externo) y a
Postgres (Biometría), igual que el ETL de asistencias.
"""

import sys
from datetime import datetime

from utils import db_pia
from services.etl.activos_criterios_runner import ejecutar_activos_criterios_etl


def main():
    config = db_pia.get_activos_criterios_config()
    if not config:
        print(f"[{datetime.now()}] No hay configuración de activos por criterios (pia_activos_criterios_config vacía).")
        sys.exit(1)

    if not config["activo"]:
        print(f"[{datetime.now()}] ETL de activos por criterios pausado (activo=False). No se ejecuta.")
        return

    periodos = config["periodos"]
    referencia = db_pia.get_activos_criterios_referencia()

    if not db_pia.try_acquire_activos_criterios_lock("CRON"):
        estado = db_pia.get_activos_criterios_lock_status()
        print(
            f"[{datetime.now()}] Ya hay una ejecución en curso "
            f"(disparado_por={estado['disparado_por']}, iniciado_en={estado['iniciado_en']}). "
            "Se omite este disparo del cron para no pisarla."
        )
        return

    print(f"[{datetime.now()}] Ejecutando ETL de activos por criterios para periodos: {periodos}")

    iniciado_en = datetime.now()
    try:
        resultado = ejecutar_activos_criterios_etl(periodos, referencia=referencia)
    except Exception as exc:
        resultado = {
            "status": "ERROR", "cantidad_ids": None,
            "diagnostico_referencia": [], "faltantes_forzados": [], "mensaje_error": str(exc),
        }
    finally:
        db_pia.release_activos_criterios_lock()
    finalizado_en = datetime.now()

    db_pia.registrar_activos_criterios_run(
        disparado_por="CRON",
        status=resultado["status"],
        iniciado_en=iniciado_en,
        finalizado_en=finalizado_en,
        periodos_procesados=periodos,
        cantidad_ids=resultado["cantidad_ids"],
        mensaje_error=resultado["mensaje_error"],
    )

    if resultado["status"] == "OK":
        print(f"[{datetime.now()}] OK: {resultado['cantidad_ids']} ids activos calculados.")
        if resultado["mensaje_error"]:
            print(f"[{datetime.now()}] Aviso: {resultado['mensaje_error']}")
    else:
        print(f"[{datetime.now()}] ERROR: {resultado['mensaje_error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
