#!/usr/bin/env python
"""
scripts/run_permanencia_etl_cron.py

Punto de entrada del cron nocturno (03:30, ver scripts/run_permanencia_etl_cron.sh).
Recorre todos los periodos con activo=True en pia_permanencia_etl_config
(normalmente solo el periodo vigente) y ejecuta el ETL de cada uno vía
services/etl/permanencia_runner.ejecutar_permanencia_etl, registrando el
resultado en pia_permanencia_etl_run. Si el snapshot de "fecha de corte" se
congela en este run, marca corte_generado=TRUE para que no se vuelva a
congelar.

No necesita VPN (mismo MYSQL_HOST_SYS que alumnos/asistencias). Usa el mismo
lock global (una ejecución de permanencia a la vez, sin importar el periodo)
que el botón "Ejecutar ahora" del admin.
"""

import sys
from datetime import datetime

from utils import db_pia
from services.etl.permanencia_runner import ejecutar_permanencia_etl


def _procesar_periodo(periodo, fecha_corte, corte_generado):
    if not db_pia.try_acquire_permanencia_etl_lock("CRON", periodo):
        estado = db_pia.get_permanencia_etl_lock_status()
        print(
            f"[{datetime.now()}] Ya hay una ejecución de permanencia en curso "
            f"(periodo={estado['periodo']}, disparado_por={estado['disparado_por']}). "
            f"Se omite {periodo} en este disparo del cron."
        )
        return False

    print(f"[{datetime.now()}] Ejecutando ETL de permanencia para periodo={periodo}")
    iniciado_en = datetime.now()
    try:
        resultado = ejecutar_permanencia_etl(periodo, fecha_corte, corte_generado)
    except Exception as exc:
        resultado = {"status": "ERROR", "filas": None, "corte_generado_ahora": False, "mensaje_error": str(exc)}
    finally:
        db_pia.release_permanencia_etl_lock()
    finalizado_en = datetime.now()

    db_pia.registrar_permanencia_etl_run(
        periodo=periodo,
        disparado_por="CRON",
        status=resultado["status"],
        iniciado_en=iniciado_en,
        finalizado_en=finalizado_en,
        filas=resultado["filas"],
        corte_generado_en_este_run=resultado["corte_generado_ahora"],
        mensaje_error=resultado["mensaje_error"],
    )

    if resultado["corte_generado_ahora"]:
        db_pia.marcar_permanencia_corte_generado(periodo)
        print(f"[{datetime.now()}] Snapshot de fecha de corte CONGELADO para {periodo}.")

    if resultado["status"] == "OK":
        print(f"[{datetime.now()}] OK: {periodo} -> {resultado['filas']} filas.")
        return True
    else:
        print(f"[{datetime.now()}] {resultado['status']}: {periodo} -> {resultado['mensaje_error']}")
        return False


def main():
    configs = db_pia.get_permanencia_etl_configs()
    activos = [c for c in configs if c["activo"]]
    print(f"[{datetime.now()}] {len(activos)} periodo(s) activo(s) de permanencia encontrado(s).")

    hubo_error = False
    for cfg in activos:
        ok = _procesar_periodo(cfg["periodo"], cfg["fecha_corte"], bool(cfg["corte_generado"]))
        if not ok:
            hubo_error = True

    if hubo_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
