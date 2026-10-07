#!/usr/bin/env python
"""
scripts/test_poblacion_activos.py

Prueba rápida (sin pytest) de la población oficial de alumnos activos:
services/etl/activos_ids.leer_poblacion/guardar_poblacion/cargar_poblacion y
services/etl/activos_criterios_runner.ejecutar_activos_criterios_etl.

Redirige POBLACION_CSV_PATH, ACTIVOS_TXT_PATH y ACTIVOS_PERIODOS_CSV_PATH a
una carpeta temporal: NO toca nada en assets/data/global (y lo verifica).

Uso:
    python scripts/test_poblacion_activos.py
"""

import hashlib
import io
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.etl import activos_ids  # noqa: E402
from services.etl.activos_criterios_runner import ejecutar_activos_criterios_etl  # noqa: E402

CABECERA = ["Año", "Periodo", "Catraca", "ID Usuario", "Nombre", "Doc. Oficial", "Semestre", "Sección", "Motivo"]
FILAS = [
    ["2018", "2", "C1", "101", "Ana Peña", "001675761", "1", "A", ""],
    ["2018", "2", "C2", "102", "José Núñez", " 955946 ", "3", "", "Recursante"],
    ["2018", "2", "C3", "103", "Lía", "123", "5", "b", ""],
    ["2026", "1", "C1", "101", "Ana Peña", "001675761", "10", "A", ""],
    ["2026", "1", "C4", "104", "Iñaki", "777", "2", "C", ""],
]

resultados = []


def check(nombre, condicion, detalle=""):
    resultados.append(bool(condicion))
    print(f"[{'OK' if condicion else 'FALLA'}] {nombre}" + (f" -- {detalle}" if detalle and not condicion else ""))


def texto_csv(sep, filas=FILAS):
    return "\n".join(sep.join(f) for f in [CABECERA] + filas) + "\n"


def bytes_xlsx(filas=FILAS):
    df = pd.DataFrame(filas, columns=CABECERA)
    for col in ("Año", "Periodo", "ID Usuario", "Semestre"):
        df[col] = df[col].astype(int)  # como vendrían de Excel (celdas numéricas)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame({"x": [1]}).to_excel(w, sheet_name="Resumen", index=False)
        df.to_excel(w, sheet_name="Alumnos", index=False)
    return buf.getvalue()


def espera_error(nombre, contenido, archivo, fragmento):
    try:
        activos_ids.leer_poblacion(contenido, archivo)
        check(nombre, False, "no lanzó ValueError")
    except ValueError as e:
        check(nombre, fragmento in str(e), f"mensaje: {e}")


def hash_carpeta(carpeta):
    h = {}
    if os.path.isdir(carpeta):
        for nombre in sorted(os.listdir(carpeta)):
            ruta = os.path.join(carpeta, nombre)
            if os.path.isfile(ruta):
                with open(ruta, "rb") as f:
                    h[nombre] = hashlib.md5(f.read()).hexdigest()
    return h


def main():
    carpeta_real = os.path.dirname(activos_ids.POBLACION_CSV_PATH)
    antes = hash_carpeta(carpeta_real)

    with tempfile.TemporaryDirectory() as tmp:
        activos_ids.POBLACION_CSV_PATH = os.path.join(tmp, "alumnos_activos_poblacion.csv")
        activos_ids.ACTIVOS_TXT_PATH = os.path.join(tmp, "usuarios_activos_ids.txt")
        activos_ids.ACTIVOS_PERIODOS_CSV_PATH = os.path.join(tmp, "usuarios_activos_periodos.csv")

        # 1. Mismo contenido en 3 formatos -> DataFrames iguales
        df_tab = activos_ids.leer_poblacion(texto_csv("\t").encode("utf-8"), "pob.txt")
        df_pc = activos_ids.leer_poblacion(texto_csv(";").encode("latin-1"), "pob.csv")
        df_xlsx = activos_ids.leer_poblacion(bytes_xlsx(), "pob.xlsx")
        for nombre, df in (("';' latin-1", df_pc), (".xlsx hoja Alumnos", df_xlsx)):
            try:
                pd.testing.assert_frame_equal(df_tab, df)
                check(f"tab utf-8 == {nombre}", True)
            except AssertionError as e:
                check(f"tab utf-8 == {nombre}", False, str(e))
        check("columnas de salida", list(df_tab.columns) == activos_ids.POBLACION_COLUMNAS_SALIDA, list(df_tab.columns))
        check("periodo AAAA.S", sorted(df_tab["periodo"].unique()) == ["2018.2", "2026.1"])
        check("nombre con acento (latin-1)", "José Núñez" in set(df_pc["nome"]))

        # 2. Ceros a la izquierda y strip
        docs = dict(zip(df_tab["usuarios_id"], df_tab["doc_oficial"]))
        check("Doc. Oficial conserva cero a la izquierda", docs[101] == "001675761", docs[101])
        check("' 955946 ' -> '955946'", docs[102] == "955946", repr(docs[102]))

        # 3. Sección vacía se conserva
        fila_102 = df_tab[(df_tab["usuarios_id"] == 102)]
        check("fila con Sección vacía se mantiene", len(fila_102) == 1 and fila_102["seccion"].iloc[0] == "")
        check("total de filas", len(df_tab) == len(FILAS), len(df_tab))

        # 4. Errores de validación
        dup = FILAS + [["2018", "2", "C9", "101", "Ana", "1", "2", "A", ""]]
        espera_error("ID repetido en el mismo periodo -> ValueError", texto_csv(";", dup).encode(), "x.csv", "repetido")
        sem13 = FILAS + [["2018", "2", "C9", "999", "X", "1", "13", "A", ""]]
        espera_error("semestre 13 -> ValueError", texto_csv(";", sem13).encode(), "x.csv", "Semestre")
        espera_error("falta columna obligatoria -> ValueError", b"Ano;Periodo;ID Usuario\n2018;2;1\n", "x.csv", "Semestre")
        cab_tolerante = "ano,PERIODO,id usuario,semestre,seccion\n2018,2,5,1,\n".encode()
        check("cabeceras tolerantes (ano/seccion/minúsculas)", len(activos_ids.leer_poblacion(cab_tolerante, "x.csv")) == 1)

        # 5. Guardar / cargar
        activos_ids.guardar_poblacion(df_tab)
        df_cargado = activos_ids.cargar_poblacion()
        try:
            pd.testing.assert_frame_equal(df_tab, df_cargado, check_dtype=False)
            check("guardar_poblacion + cargar_poblacion ida y vuelta", True)
        except AssertionError as e:
            check("guardar_poblacion + cargar_poblacion ida y vuelta", False, str(e))
        check("sin .tmp residual", not os.path.exists(activos_ids.POBLACION_CSV_PATH + ".tmp"))
        totales = activos_ids.totales_por_periodo(df_cargado)
        check("totales_por_periodo", totales.to_dict() == {"2018.2": 3, "2026.1": 2}, totales.to_dict())

        # 6. ETL: periodos configurados 2018.2 y 2019.1; CSV con 2018.2 y 2026.1
        resultado = ejecutar_activos_criterios_etl(["2018.2", "2019.1"])
        check("ETL status OK", resultado["status"] == "OK", resultado)
        check("ETL cantidad_ids = 3", resultado["cantidad_ids"] == 3, resultado["cantidad_ids"])
        aviso = resultado["mensaje_error"] or ""
        check("aviso menciona 2026.1 ignorado", "2026.1" in aviso and "ignorados" in aviso, aviso)
        check("aviso menciona 2019.1 sin alumnos", "2019.1" in aviso and "sin alumnos" in aviso, aviso)
        check("formato de retorno", set(resultado) == {
            "status", "cantidad_ids", "diagnostico_referencia", "faltantes_forzados", "mensaje_error",
        })
        check("ids grabados = solo 2018.2", activos_ids.cargar_ids_activos() == {101, 102, 103},
              activos_ids.cargar_ids_activos())
        pares = activos_ids.cargar_pares_activos()
        esperado = {(101, "2018.2"): 1, (102, "2018.2"): 3, (103, "2018.2"): 5}
        check("cargar_pares_activos con el semestre del archivo", pares == esperado, pares)

        # 7. ETL sin alumnos en los periodos -> ERROR sin tocar archivos
        mtime = os.path.getmtime(activos_ids.ACTIVOS_TXT_PATH)
        resultado = ejecutar_activos_criterios_etl(["2020.1"])
        check("ETL sin periodos en el CSV -> ERROR", resultado["status"] == "ERROR", resultado)
        check("ERROR no toca el .txt", os.path.getmtime(activos_ids.ACTIVOS_TXT_PATH) == mtime)

        # 8. Cancelado y población inexistente
        resultado = ejecutar_activos_criterios_etl(["2018.2"], cancel_check=lambda: True)
        check("cancel_check -> CANCELADO", resultado["status"] == "CANCELADO", resultado)
        os.remove(activos_ids.POBLACION_CSV_PATH)
        resultado = ejecutar_activos_criterios_etl(["2018.2"])
        check("sin población -> ERROR", resultado["status"] == "ERROR"
              and "No se subió la población" in (resultado["mensaje_error"] or ""), resultado)

    check("assets/data/global sin cambios", hash_carpeta(carpeta_real) == antes)

    print(f"\n{sum(resultados)}/{len(resultados)} verificaciones OK")
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()
