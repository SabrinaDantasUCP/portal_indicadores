"""Capa de acceso analitico con DuckDB.

Motor columnar embebido (sin servidor) usado para las agregaciones pesadas.
Dos formas de uso:

- aggregate(df, sql): ejecuta SQL sobre un DataFrame de pandas ya cargado,
  referenciado como `src` en el SQL. Empuja el GROUP BY al motor vectorizado
  de DuckDB. La entrada y la salida siguen siendo DataFrames de pandas, por lo
  que las funciones de calculo mantienen la misma firma.

- query_parquet(path, sql): consulta un archivo parquet directamente (lectura
  columnar con pushdown de columnas/filtros), sin materializar todo en pandas.
  Pensado para futuras agregaciones que lean directo del parquet.
"""

import duckdb


def aggregate(df, sql):
    """Ejecuta `sql` sobre `df` (referenciado como `src`) y devuelve un DataFrame.

    Usa una conexion en memoria efimera por llamada: sin estado compartido,
    seguro entre hilos/sesiones. El registro del DataFrame es zero-copy (Arrow).
    """
    con = duckdb.connect()
    try:
        con.register("src", df)
        return con.execute(sql).df()
    finally:
        con.close()


def query_parquet(path, sql, params=None):
    """Ejecuta `sql` leyendo un parquet referenciado como `src` mediante read_parquet.

    Ejemplo:
        query_parquet(ruta, "SELECT cohorte, COUNT(*) FROM src GROUP BY cohorte")
    """
    con = duckdb.connect()
    try:
        con.execute("CREATE VIEW src AS SELECT * FROM read_parquet(?)", [path])
        return con.execute(sql, params or []).df()
    finally:
        con.close()
