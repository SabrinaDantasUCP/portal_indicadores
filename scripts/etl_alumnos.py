#!/usr/bin/env python
# coding: utf-8

"""
scripts/etl_alumnos.py

Wrapper fino para uso MANUAL (terminal ou notebook/Jupyter) del ETL de
alumnos (matrículas + notas -> alumnos_v1/alumnos_v2). Toda la lógica real
(queries, procesar_ano, generar_alumnos_v1/v2) vive ahora en
services/etl/alumnos_etl.py — ese módulo no ejecuta nada a nivel de código al
importarlo, así que también es usado por el admin module
(modules/alumnos_config_etl.py) y por el cron (services/etl/alumnos_runner.py,
scripts/run_alumnos_etl_cron.py) sin disparar consultas indeseadas.

A diferencia del ETL de encuestas, este NO necesita ninguna VPN: se conecta
directo a MYSQL_HOST_SYS (host externo).

Uso manual:

    from services.etl.alumnos_etl import procesar_anos, generar_alumnos_v1, generar_alumnos_v2
    from services.etl.activos_ids import cargar_ids_activos
    df_consolidado, errores = procesar_anos([2025, 2026], pasta_temp="assets/data/temp_years")
    df_v1 = generar_alumnos_v1(df_consolidado, egresados_xlsx_path="assets/data/global/egressados.xlsx")
    df_v2 = generar_alumnos_v2(df_v1, cargar_ids_activos())

O, para correr el pipeline completo (incluyendo escritura de CSV+parquet en
las rutas que usa el dashboard, assets/data/v1 y assets/data/v2):

    python scripts/etl_alumnos.py --anos 2017-2027
    python scripts/etl_alumnos.py --anos 2025,2026
"""

import argparse
import sys

from services.etl.alumnos_runner import ejecutar_alumnos_etl


def _parse_anos(valor: str):
    """Acepta tanto rangos ("2017-2027") como listas separadas por coma
    ("2025,2026")."""
    valor = valor.strip()
    if "-" in valor and "," not in valor:
        inicio, fin = valor.split("-", 1)
        return list(range(int(inicio), int(fin) + 1))
    return [int(a) for a in valor.split(",") if a.strip()]


def main():
    parser = argparse.ArgumentParser(description="Genera alumnos_v1/alumnos_v2 a partir de matrículas + notas")
    parser.add_argument(
        "--anos", type=str, required=True,
        help="Años a procesar: rango ('2017-2027') o lista separada por coma ('2025,2026')",
    )
    args = parser.parse_args()

    anos = _parse_anos(args.anos)
    resultado = ejecutar_alumnos_etl(anos)

    if resultado["status"] == "OK":
        print(
            f"OK: alumnos_v1={resultado['filas_v1']} filas, "
            f"alumnos_v2={resultado['filas_v2']} filas."
        )
        if resultado["mensaje_error"]:
            print(f"Aviso: {resultado['mensaje_error']}")
    else:
        print(f"ERROR: {resultado['mensaje_error']}")
        sys.exit(1)


def _running_in_jupyter() -> bool:
    """Detecta se o código está rodando dentro de um kernel Jupyter/IPython
    (ex: notebook, JupyterLab, %run), em vez de um script chamado direto pelo
    terminal (python arquivo.py ...)."""
    return "ipykernel_launcher" in sys.argv[0] or "ipykernel" in sys.modules


if __name__ == "__main__":
    if _running_in_jupyter():
        print(
            "Este script foi carregado dentro do Jupyter/IPython.\n"
            "Não use %run — em vez disso, chame as funções diretamente, por exemplo:\n\n"
            "    from services.etl.alumnos_etl import procesar_anos, generar_alumnos_v1, generar_alumnos_v2\n"
            "    df_consolidado, errores = procesar_anos([2025, 2026])\n"
        )
    else:
        main()
