#!/usr/bin/env python
"""
scripts/etl_indice_permanencia.py

Wrapper fino para uso MANUAL (terminal) del ETL de Índice de Permanencia.
Toda la lógica real vive en services/etl/permanencia_etl.py (funciones
puras) y services/etl/permanencia_runner.py (orquestador) -- no ejecuta nada
a nivel de código al importarlos, así que también son usados por el admin
module (modules/permanencia_config_etl.py) y por el cron
(scripts/run_permanencia_etl_cron.py) sin disparar consultas indeseadas.

Reemplaza al script "notebook" que estaba en
services/etl/etl_indice_permanencia.py (ejecutaba todo a nivel de módulo,
con las constantes de periodo hardcodeadas al tope).

Uso manual:

    python scripts/etl_indice_permanencia.py --periodo 2026.1 --fecha-corte 2026-09-15

Sin --fecha-corte, usa la configurada en pia_permanencia_etl_config (o hoy +
lejos si el periodo todavía no está configurado -- no genera snapshot).
"""

import argparse
import sys
from datetime import date, datetime

from utils import db_pia
from services.etl.permanencia_runner import ejecutar_permanencia_etl


def main():
    parser = argparse.ArgumentParser(description="Genera permanencia_{label}.csv/parquet (visión general + corte)")
    parser.add_argument("--periodo", type=str, required=True, help="Periodo a procesar, ej. '2026.1'")
    parser.add_argument(
        "--fecha-corte", type=str, default=None,
        help="Fecha de corte (YYYY-MM-DD). Si no se pasa, usa la de pia_permanencia_etl_config.",
    )
    args = parser.parse_args()

    config = db_pia.get_permanencia_etl_config(args.periodo)
    if args.fecha_corte:
        fecha_corte = date.fromisoformat(args.fecha_corte)
        corte_generado = bool(config["corte_generado"]) if config else False
    elif config:
        fecha_corte = config["fecha_corte"]
        corte_generado = bool(config["corte_generado"])
    else:
        fecha_corte, corte_generado = None, False

    resultado = ejecutar_permanencia_etl(args.periodo, fecha_corte, corte_generado)

    if resultado["status"] == "OK":
        print(f"OK: {resultado['filas']} filas.")
        if resultado["corte_generado_ahora"]:
            print("Snapshot de fecha de corte CONGELADO en este run.")
            if config:
                db_pia.marcar_permanencia_corte_generado(args.periodo)
    else:
        print(f"{resultado['status']}: {resultado['mensaje_error']}")
        sys.exit(1)


def _running_in_jupyter() -> bool:
    return "ipykernel_launcher" in sys.argv[0] or "ipykernel" in sys.modules


if __name__ == "__main__":
    if _running_in_jupyter():
        print(
            "Este script foi carregado dentro do Jupyter/IPython.\n"
            "Não use %run — em vez disso, chame a função diretamente, por exemplo:\n\n"
            "    from services.etl.permanencia_runner import ejecutar_permanencia_etl\n"
            "    resultado = ejecutar_permanencia_etl('2026.1', None, False)\n"
        )
    else:
        main()
