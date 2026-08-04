#!/usr/bin/env python
"""
scripts/run_alumnos_etl_cron.py

Punto de entrada del cron nocturno (04:00, ver scripts/run_alumnos_etl_cron.sh).
Lee la configuración activa en pia_alumnos_etl_config (lista de años + toggle
activo) y ejecuta el ETL vía services/etl/alumnos_runner.ejecutar_alumnos_etl,
registrando el resultado en pia_alumnos_etl_run.

A diferencia del cron de encuestas (scripts/run_etl_cron.py), este NO
necesita VPN: se conecta directo a MYSQL_HOST_SYS (host externo), así que
puede ir en el crontab del usuario normal (no root).
"""

import sys
from datetime import datetime

from utils import db_pia
from services.etl.alumnos_runner import ejecutar_alumnos_etl


def main():
    config = db_pia.get_alumnos_etl_config()
    if not config:
        print(f"[{datetime.now()}] No hay configuración de ETL de alumnos (pia_alumnos_etl_config vacía).")
        sys.exit(1)

    if not config["activo"]:
        print(f"[{datetime.now()}] ETL de alumnos pausado (activo=False). No se ejecuta.")
        return

    anos = config["anos"]

    if not db_pia.try_acquire_alumnos_etl_lock("CRON"):
        estado = db_pia.get_alumnos_etl_lock_status()
        print(
            f"[{datetime.now()}] Ya hay una ejecución en curso "
            f"(disparado_por={estado['disparado_por']}, iniciado_en={estado['iniciado_en']}). "
            "Se omite este disparo del cron para no pisarla."
        )
        return

    print(f"[{datetime.now()}] Ejecutando ETL de alumnos para años: {anos}")

    iniciado_en = datetime.now()
    try:
        resultado = ejecutar_alumnos_etl(anos)
    except Exception as exc:
        resultado = {
            "status": "ERROR", "filas_v1": None, "filas_v2": None,
            "anos_con_error": anos, "mensaje_error": str(exc),
        }
    finally:
        db_pia.release_alumnos_etl_lock()
    finalizado_en = datetime.now()

    db_pia.registrar_alumnos_etl_run(
        disparado_por="CRON",
        status=resultado["status"],
        iniciado_en=iniciado_en,
        finalizado_en=finalizado_en,
        anos_procesados=anos,
        filas_v1=resultado["filas_v1"],
        filas_v2=resultado["filas_v2"],
        mensaje_error=resultado["mensaje_error"],
    )

    if resultado["status"] == "OK":
        print(
            f"[{datetime.now()}] OK: alumnos_v1={resultado['filas_v1']} filas, "
            f"alumnos_v2={resultado['filas_v2']} filas."
        )
        if resultado["mensaje_error"]:
            print(f"[{datetime.now()}] Aviso: {resultado['mensaje_error']}")
    else:
        print(f"[{datetime.now()}] ERROR: {resultado['mensaje_error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
