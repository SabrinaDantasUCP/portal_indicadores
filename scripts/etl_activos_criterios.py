#!/usr/bin/env python
# coding: utf-8

"""
scripts/etl_activos_criterios.py

Wrapper fino para uso MANUAL (terminal o notebook/Jupyter) del ETL de
"Alumnos Activos por Criterios". Toda la lógica real vive en
services/etl/activos_criterios_etl.py -- ese módulo no ejecuta nada a nivel
de código al importarlo, así que también es usado por el admin module
(modules/activos_config_etl.py) y por el cron
(services/etl/activos_criterios_runner.py,
scripts/run_activos_criterios_etl_cron.py) sin disparar consultas
indeseadas.

No necesita VPN: se conecta directo a MYSQL_HOST_SYS (host externo) y a
Postgres (Biometría).

Uso manual:

    from services.etl.activos_criterios_etl import calcular_ids_activos
    resultado = calcular_ids_activos(
        ["2025.1", "2025.2", "2026.1"],
        egresados_path="assets/data/global/egressados.xlsx",
        tfg_path="assets/data/global/tfg.xlsx",
        rues_path="assets/data/global/rues.xlsx",
    )
    print(len(resultado["ids_activos"]))

O, para correr el pipeline completo (incluyendo la escritura de
usuarios_activos_ids.txt, que es lo que leen los ETL de Alumnos,
Asistencias y Encuestas):

    python scripts/etl_activos_criterios.py --periodos 2018.2-2026.1
    python scripts/etl_activos_criterios.py --periodos 2025.1,2025.2,2026.1
"""

import argparse
import sys

from services.etl.activos_criterios_runner import ejecutar_activos_criterios_etl
from utils import db_pia


def _parse_periodos(valor: str):
    """Acepta tanto rangos ("2018.2-2026.1") como listas separadas por coma
    ("2025.1,2025.2,2026.1"). Un rango expande año.semestre en pasos de
    medio año."""
    valor = valor.strip()
    if "-" in valor and "," not in valor:
        inicio, fin = valor.split("-", 1)
        ano_i, sem_i = (int(x) for x in inicio.split("."))
        ano_f, sem_f = (int(x) for x in fin.split("."))
        rank_i = ano_i * 2 + (sem_i - 1)
        rank_f = ano_f * 2 + (sem_f - 1)
        periodos = []
        for rank in range(rank_i, rank_f + 1):
            ano, sem = divmod(rank, 2)
            periodos.append(f"{ano}.{sem + 1}")
        return periodos
    return [p.strip() for p in valor.split(",") if p.strip()]


def main():
    parser = argparse.ArgumentParser(description="Calcula usuarios_id activos por criterios de negocio")
    parser.add_argument(
        "--periodos", type=str, required=True,
        help="Periodos a procesar: rango ('2018.2-2026.1') o lista separada por coma ('2025.1,2025.2')",
    )
    args = parser.parse_args()

    periodos = _parse_periodos(args.periodos)
    referencia = db_pia.get_activos_criterios_referencia()
    resultado = ejecutar_activos_criterios_etl(periodos, referencia=referencia)

    if resultado["status"] == "OK":
        print(f"OK: {resultado['cantidad_ids']} ids activos calculados.")
        if resultado["mensaje_error"]:
            print(f"Aviso: {resultado['mensaje_error']}")
    else:
        print(f"ERROR: {resultado['mensaje_error']}")
        sys.exit(1)


def _running_in_jupyter() -> bool:
    return "ipykernel_launcher" in sys.argv[0] or "ipykernel" in sys.modules


if __name__ == "__main__":
    if _running_in_jupyter():
        print(
            "Este script foi carregado dentro do Jupyter/IPython.\n"
            "Não use %run — em vez disso, chame as funções diretamente, por exemplo:\n\n"
            "    from services.etl.activos_criterios_etl import calcular_ids_activos\n"
            "    resultado = calcular_ids_activos(['2025.1', '2025.2', '2026.1'])\n"
        )
    else:
        main()
