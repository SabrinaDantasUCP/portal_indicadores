#!/usr/bin/env python
"""
scripts/run_asistencias_etl_cron.py

Punto de entrada del cron nocturno (03:00, ver scripts/run_asistencias_etl_cron.sh).
Lee la configuración activa en pia_asistencias_etl_config (años SysEduca +
periodos Biometría + toggle activo) y ejecuta el ETL vía
services/etl/asistencias_runner.ejecutar_asistencias_etl, registrando el
resultado en pia_asistencias_etl_run.

No necesita VPN: SysEduca (MYSQL_HOST_SYS) y Biometría (PG_HOST) son
alcanzables directo, igual que el ETL de alumnos.
"""

import sys
from datetime import datetime

from utils import db_pia
from services.etl.asistencias_runner import ejecutar_asistencias_etl


def main():
    config = db_pia.get_asistencias_etl_config()
    if not config:
        print(f"[{datetime.now()}] No hay configuración de ETL de asistencias (pia_asistencias_etl_config vacía).")
        sys.exit(1)

    if not config["activo"]:
        print(f"[{datetime.now()}] ETL de asistencias pausado (activo=False). No se ejecuta.")
        return

    anos_syseduca = config["anos_syseduca"]
    periodos_biometria = config["periodos_biometria"]

    if not db_pia.try_acquire_asistencias_etl_lock("CRON"):
        estado = db_pia.get_asistencias_etl_lock_status()
        print(
            f"[{datetime.now()}] Ya hay una ejecución en curso "
            f"(disparado_por={estado['disparado_por']}, iniciado_en={estado['iniciado_en']}). "
            "Se omite este disparo del cron para no pisarla."
        )
        return

    print(
        f"[{datetime.now()}] Ejecutando ETL de asistencias para "
        f"años SysEduca={anos_syseduca}, periodos Biometría={periodos_biometria}"
    )

    iniciado_en = datetime.now()
    try:
        resultado = ejecutar_asistencias_etl(anos_syseduca, periodos_biometria)
    except Exception as exc:
        resultado = {
            "status": "ERROR", "filas_v1": None, "filas_v2": None,
            "anos_con_error": anos_syseduca, "periodos_con_error": periodos_biometria,
            "mensaje_error": str(exc),
        }
    finally:
        db_pia.release_asistencias_etl_lock()
    finalizado_en = datetime.now()

    db_pia.registrar_asistencias_etl_run(
        disparado_por="CRON",
        status=resultado["status"],
        iniciado_en=iniciado_en,
        finalizado_en=finalizado_en,
        anos_syseduca_procesados=anos_syseduca,
        periodos_biometria_procesados=periodos_biometria,
        filas_v1=resultado["filas_v1"],
        filas_v2=resultado["filas_v2"],
        mensaje_error=resultado["mensaje_error"],
    )

    if resultado["status"] == "OK":
        print(
            f"[{datetime.now()}] OK: asistencia_unificada_v1={resultado['filas_v1']} filas, "
            f"asistencia_unificada_v2={resultado['filas_v2']} filas."
        )
        if resultado["mensaje_error"]:
            print(f"[{datetime.now()}] Aviso: {resultado['mensaje_error']}")
    else:
        print(f"[{datetime.now()}] ERROR: {resultado['mensaje_error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
