#!/usr/bin/env python
"""
scripts/etl_asistencias.py

Wrapper fino para uso MANUAL (terminal) del ETL de asistencias (SysEduca +
Biometría -> asistencia_unificada_v1/v2). Toda la lógica real vive en
services/etl/asistencias_etl.py (funciones puras) y
services/etl/asistencias_runner.py (orquestador) -- ese módulo no ejecuta
nada a nivel de código al importarlo, así que también es usado por el admin
module (modules/asistencias_config_etl.py) y por el cron
(scripts/run_asistencias_etl_cron.py) sin disparar consultas indeseadas.

Reemplaza al script "notebook" que estaba en services/etl/etl_asistencias.py
(ejecutaba las 3 fases -- SysEduca, Biometría, Junción -- a nivel de módulo).

Uso manual:

    python scripts/etl_asistencias.py --anos-syseduca 2021-2025 --periodos-biometria 2025.2,2026.1

O directamente desde un notebook:

    from services.etl.asistencias_runner import ejecutar_asistencias_etl
    resultado = ejecutar_asistencias_etl([2021, 2022, 2023, 2024, 2025], ["2025.2"])
"""

import argparse
import sys

from services.etl.asistencias_runner import ejecutar_asistencias_etl


def _parse_anos(valor: str):
    valor = valor.strip()
    if "-" in valor and "," not in valor:
        inicio, fin = valor.split("-", 1)
        return list(range(int(inicio), int(fin) + 1))
    return [int(a) for a in valor.split(",") if a.strip()]


def _parse_periodos(valor: str):
    return [p.strip() for p in valor.split(",") if p.strip()]


def main():
    parser = argparse.ArgumentParser(description="Genera asistencia_unificada_v1/v2 (SysEduca + Biometría)")
    parser.add_argument(
        "--anos-syseduca", type=str, required=True,
        help="Años SysEduca (antes de 2025.2): rango ('2021-2025') o lista ('2021,2023')",
    )
    parser.add_argument(
        "--periodos-biometria", type=str, required=True,
        help="Periodos Biometría (desde 2025.2): lista separada por coma, ej. '2025.2,2026.1'",
    )
    args = parser.parse_args()

    anos_syseduca = _parse_anos(args.anos_syseduca)
    periodos_biometria = _parse_periodos(args.periodos_biometria)
    resultado = ejecutar_asistencias_etl(anos_syseduca, periodos_biometria)

    if resultado["status"] == "OK":
        print(
            f"OK: asistencia_unificada_v1={resultado['filas_v1']} filas, "
            f"asistencia_unificada_v2={resultado['filas_v2']} filas."
        )
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
            "Não use %run — em vez disso, chame a função diretamente, por exemplo:\n\n"
            "    from services.etl.asistencias_runner import ejecutar_asistencias_etl\n"
            "    resultado = ejecutar_asistencias_etl([2024, 2025], ['2025.2'])\n"
        )
    else:
        main()
