"""Convierte los CSV de datos a Parquet.

Uso:
    python scripts/csv_to_parquet.py            # convierte solo los CSV mas nuevos que su parquet
    python scripts/csv_to_parquet.py --force    # reconvierte todo

Ejecutar despues de cada regeneracion de los CSV (o desde el cron semanal
del servidor, hasta que el ETL escriba Parquet directamente).
"""

import argparse
import os
import sys
import time

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (ruta csv relativa al proyecto, separador, normalizar nombres de columnas)
SOURCES = [
    ("assets/data/v1/alumnos_v1.csv", ",", True),
    ("assets/data/v1/asistencia_unificada_v1.csv", ",", True),
    ("assets/data/v2/alumnos_v2.csv", ",", True),
    ("assets/data/v2/asistencia_unificada_v2.csv", ",", True),
    ("assets/data/global/permanencia_20252.csv", ";", False),
    ("assets/data/global/permanencia_20252_05-04-2026.csv", ";", False),
    ("assets/data/global/permanencia_20261.csv", ";", False),
    ("assets/data/global/permanencia_20261_16-07-2026.csv", ";", False),
    ("assets/data/v1/indicadores_encuestas_alumnos_al_docente_20261_v1.csv", ",", False),
    ("assets/data/v2/indicadores_encuestas_alumnos_al_docente_20261_v2.csv", ",", False),
    ("assets/data/global/avance_encuestas_docente_autoeval_20261.csv", ",", False),
]


def convert(csv_rel_path, sep, strip_columns, force=False):
    csv_path = os.path.join(BASE_DIR, csv_rel_path)
    parquet_path = os.path.splitext(csv_path)[0] + ".parquet"

    if not os.path.exists(csv_path):
        print(f"  OMITIDO (no existe): {csv_rel_path}")
        return

    if (
        not force
        and os.path.exists(parquet_path)
        and os.path.getmtime(parquet_path) >= os.path.getmtime(csv_path)
    ):
        print(f"  al dia: {csv_rel_path}")
        return

    start = time.time()
    df = pd.read_csv(csv_path, sep=sep, low_memory=False)
    if strip_columns:
        df.columns = df.columns.str.strip()

    if len(df.columns) == 1:
        print(f"  ADVERTENCIA: {csv_rel_path} tiene 1 sola columna; revisar separador '{sep}'")

    df.to_parquet(parquet_path, index=False)

    csv_mb = os.path.getsize(csv_path) / 1e6
    pq_mb = os.path.getsize(parquet_path) / 1e6
    print(
        f"  OK: {csv_rel_path} -> {os.path.basename(parquet_path)} | "
        f"{len(df):,} filas x {len(df.columns)} cols | "
        f"{csv_mb:.1f} MB -> {pq_mb:.1f} MB | {time.time() - start:.1f}s"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="reconvertir aunque el parquet este al dia")
    args = parser.parse_args()

    print("Convirtiendo CSV -> Parquet...")
    errors = 0
    for csv_rel_path, sep, strip_columns in SOURCES:
        try:
            convert(csv_rel_path, sep, strip_columns, force=args.force)
        except Exception as exc:
            errors += 1
            print(f"  ERROR en {csv_rel_path}: {exc}")

    if errors:
        sys.exit(1)
    print("Listo.")


if __name__ == "__main__":
    main()
