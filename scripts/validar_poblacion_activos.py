#!/usr/bin/env python
"""
scripts/validar_poblacion_activos.py

Compara lo que el portal tiene cargado como "alumnos activos" contra el
consolidado oficial ("Alumnos Reales Max 2 Recursantes", .xlsx con las hojas
Alumnos/Matriz/Excluidos, o solo el CSV de la hoja Alumnos). SOLO LECTURA:
no escribe ni modifica ningún archivo.

Verificaciones (cada una imprime OK / FALLA / N/A):
  0. La población cargada en el portal es igual a la hoja Alumnos del
     consolidado (pares usuarios_id/periodo/semestre).
  1. Alumnos (ID únicos) por periodo = valores esperados, y total de filas.
  2. Ningún ID Usuario repetido en el mismo periodo.
  3. Semestres 1-10, de 2021.1 en adelante: ninguna sección con más de 95
     alumnos (sección agrupada sin distinguir mayúsculas/espacios).
  4. Matriz semestre x periodo idéntica a la hoja "Matriz" del consolidado.
  5. Hoja "Excluidos": 1.475 filas (700 / 283 / 492 por tipo).
  6. usuarios_activos_periodos.csv == población en los periodos configurados.
  7. alumnos_v2 (después del ETL de Alumnos) vs. población: conteo por
     periodo/semestre y (usuarios_id, periodo) del CSV que no están en v2.

Uso (desde la raíz del proyecto, con el venv activo):

    python scripts/validar_poblacion_activos.py "ruta/al/consolidado.xlsx"
    python scripts/validar_poblacion_activos.py alumnos.csv --periodos 2018.2-2026.1
    # Antes de subir al portal (valida el archivo en vez de la población guardada):
    python scripts/validar_poblacion_activos.py consolidado.xlsx --poblacion-archivo consolidado.xlsx

Sin --periodos, los periodos configurados se leen de
pia_activos_criterios_config (requiere acceso a la base "pia"); si no hay
acceso, se usan todos los periodos de la población.
Código de salida: 0 si todo OK/N/A, 1 si hubo alguna FALLA.
"""

import argparse
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.csv_to_parquet import BASE_DIR  # noqa: E402
from services.etl.activos_ids import (  # noqa: E402
    POBLACION_CSV_PATH,
    cargar_pares_activos,
    cargar_poblacion,
    leer_poblacion,
    totales_por_periodo,
)

TOTALES_ESPERADOS = {
    "2018.2": 492, "2019.1": 888, "2019.2": 1144, "2020.1": 1525, "2020.2": 1615,
    "2021.1": 2298, "2021.2": 2604, "2022.1": 3152, "2022.2": 3440, "2023.1": 4012,
    "2023.2": 4353, "2024.1": 4981, "2024.2": 5445, "2025.1": 6557, "2025.2": 6844,
    "2026.1": 6909,
}
FILAS_ESPERADAS = 56259
CUPO_MAX_SECCION = 95
PERIODO_CUPO_DESDE = (2021, 1)
EXCLUIDOS_ESPERADOS = {
    "Menor promedio": 700,
    "Recursante sin motivo explícito": 283,
    "Aumento de coorte": 492,
}
ALUMNOS_V2_PATH = os.path.join(BASE_DIR, "assets", "data", "v2", "alumnos_v2.csv")

estados = []


def reportar(numero, titulo, estado, detalles=()):
    estados.append(estado)
    print(f"\n[{estado}] {numero}. {titulo}")
    for linea in detalles:
        print(f"      {linea}")


def clave_periodo(periodo):
    ano, _, sem = str(periodo).partition(".")
    return (int(ano), int(sem or 0))


def parsear_periodos(valor):
    valor = valor.strip()
    if "-" in valor and "," not in valor:
        inicio, fin = (clave_periodo(p) for p in valor.split("-", 1))
        rank_i, rank_f = inicio[0] * 2 + inicio[1] - 1, fin[0] * 2 + fin[1] - 1
        return [f"{r // 2}.{r % 2 + 1}" for r in range(rank_i, rank_f + 1)]
    return [p.strip() for p in valor.split(",") if p.strip()]


def matriz(df):
    """semestre x periodo con usuarios_id únicos (int)."""
    m = df.groupby(["semestre", "periodo"])["usuarios_id"].nunique().unstack(fill_value=0)
    return m.reindex(columns=sorted(m.columns, key=clave_periodo)).sort_index()


def es_xlsx(ruta):
    return os.path.splitext(ruta)[1].lower() in (".xlsx", ".xlsm")


def leer_hoja(ruta, hoja, **kwargs):
    if not es_xlsx(ruta):
        return None
    hojas = pd.ExcelFile(ruta).sheet_names
    nombre = next((h for h in hojas if h.strip().lower() == hoja.lower()), None)
    return pd.read_excel(ruta, sheet_name=nombre, **kwargs) if nombre else None


def leer_matriz_consolidado(ruta):
    """Hoja "Matriz": una fila de cabecera con "semestre" + periodos, luego
    una fila por semestre y una fila TOTAL (ignorada)."""
    crudo = leer_hoja(ruta, "Matriz", header=None, dtype=str)
    if crudo is None:
        return None
    crudo = crudo.fillna("")
    fila_cab = next(
        i for i, fila in crudo.iterrows()
        if sum(bool(re.fullmatch(r"\d{4}\.[12]", str(v).strip())) for v in fila) >= 2
    )
    cabecera = [str(v).strip() for v in crudo.iloc[fila_cab]]
    columnas = {i: p for i, p in enumerate(cabecera) if re.fullmatch(r"\d{4}\.[12]", p)}
    filas = {}
    for _, fila in crudo.iloc[fila_cab + 1:].iterrows():
        sem = str(fila.iloc[0]).strip()
        if not re.fullmatch(r"\d+(\.0+)?", sem):
            continue  # TOTAL / filas vacías
        filas[int(float(sem))] = {p: int(float(fila.iloc[i] or 0)) for i, p in columnas.items()}
    m = pd.DataFrame.from_dict(filas, orient="index").fillna(0).astype(int)
    return m.reindex(columns=sorted(m.columns, key=clave_periodo)).sort_index()


def periodos_configurados(arg, poblacion):
    if arg:
        return parsear_periodos(arg), "--periodos"
    try:
        from utils import db_pia
        config = db_pia.get_activos_criterios_config()
        if config and config["periodos"]:
            return list(config["periodos"]), "pia_activos_criterios_config"
    except Exception as exc:  # sin acceso a la base "pia"
        print(f"(Aviso: no se pudo leer pia_activos_criterios_config: {exc})")
    return list(totales_por_periodo(poblacion).index), "todos los periodos de la población"


def main():
    parser = argparse.ArgumentParser(description="Valida la población de alumnos activos contra el consolidado.")
    parser.add_argument("consolidado", help="Consolidado .xlsx (hojas Alumnos/Matriz/Excluidos) o CSV de la hoja Alumnos")
    parser.add_argument("--periodos", help="Periodos configurados: rango '2018.2-2026.1' o lista '2025.1,2025.2'")
    parser.add_argument("--poblacion-archivo", help="Validar este archivo en lugar de la población guardada en el portal")
    parser.add_argument("--max-listar", type=int, default=50, help="Máximo de faltantes a listar en el ítem 7")
    args = parser.parse_args()

    if args.poblacion_archivo:
        with open(args.poblacion_archivo, "rb") as f:
            poblacion = leer_poblacion(f.read(), args.poblacion_archivo)
        print(f"Población: archivo {args.poblacion_archivo}")
    else:
        poblacion = cargar_poblacion()
        print(f"Población: {POBLACION_CSV_PATH}")
    if poblacion is None or poblacion.empty:
        print("FALLA: no hay población cargada en el portal (suba el CSV en la pantalla 'Alumnos Activos').")
        sys.exit(1)
    print(f"Consolidado: {args.consolidado}")

    # 0. Población del portal == hoja Alumnos del consolidado
    with open(args.consolidado, "rb") as f:
        try:
            consolidado = leer_poblacion(f.read(), args.consolidado)
        except ValueError as e:
            consolidado = None
            reportar(0, "Población del portal == hoja Alumnos del consolidado", "FALLA",
                     [f"El consolidado no es válido: {e}"])
    if consolidado is not None:
        a = set(zip(poblacion["usuarios_id"], poblacion["periodo"], poblacion["semestre"]))
        b = set(zip(consolidado["usuarios_id"], consolidado["periodo"], consolidado["semestre"]))
        reportar(0, "Población del portal == hoja Alumnos del consolidado", "OK" if a == b else "FALLA", [
            f"Solo en el portal: {len(a - b)} · solo en el consolidado: {len(b - a)}",
            *[f"ej. portal: {x}" for x in sorted(a - b)[:5]],
            *[f"ej. consolidado: {x}" for x in sorted(b - a)[:5]],
        ] if a != b else [f"{len(a)} pares iguales"])

    # 1. Totales por periodo
    totales = totales_por_periodo(poblacion)
    detalles, ok = [], True
    for periodo in sorted(set(TOTALES_ESPERADOS) | set(totales.index), key=clave_periodo):
        esperado, real = TOTALES_ESPERADOS.get(periodo), int(totales.get(periodo, 0))
        marca = "ok" if esperado == real else "DIFERENTE"
        ok &= esperado == real
        detalles.append(f"{periodo}: esperado={esperado if esperado is not None else '-'} real={real} {marca}")
    ok &= len(poblacion) == FILAS_ESPERADAS
    detalles.append(f"Total de filas: esperado={FILAS_ESPERADAS} real={len(poblacion)}")
    reportar(1, "Alumnos únicos por periodo y total de filas", "OK" if ok else "FALLA", detalles)

    # 2. Sin ID repetido por periodo
    dup = poblacion[poblacion.duplicated(["usuarios_id", "periodo"], keep=False)]
    reportar(2, "Ningún ID Usuario repetido en el mismo periodo", "OK" if dup.empty else "FALLA",
             [f"{len(dup)} filas repetidas, ej.: {list(zip(dup['usuarios_id'], dup['periodo']))[:5]}"] if len(dup) else [])

    # 3. Cupo por sección
    df = poblacion[
        poblacion["semestre"].between(1, 10)
        & poblacion["periodo"].map(lambda p: clave_periodo(p) >= PERIODO_CUPO_DESDE)
        & (poblacion["seccion"].str.strip() != "")
    ].copy()
    df["seccion_norm"] = df["seccion"].str.lower().str.replace(r"\s+", "", regex=True)
    por_seccion = df.groupby(["periodo", "semestre", "seccion_norm"])["usuarios_id"].nunique()
    excedidas = por_seccion[por_seccion > CUPO_MAX_SECCION]
    reportar(3, f"Semestres 1-10 desde 2021.1: ninguna sección con más de {CUPO_MAX_SECCION} alumnos",
             "OK" if excedidas.empty else "FALLA",
             [f"{p} sem {s} sección '{sec}': {n}" for (p, s, sec), n in excedidas.items()]
             or [f"{len(por_seccion)} secciones revisadas, máximo {int(por_seccion.max()) if len(por_seccion) else 0}"])

    # 4. Matriz
    m_cons = leer_matriz_consolidado(args.consolidado)
    if m_cons is None:
        reportar(4, "Matriz semestre x periodo == hoja Matriz", "N/A", ["El consolidado no tiene hoja 'Matriz'."])
    else:
        m_pob = matriz(poblacion)
        filas = sorted(set(m_pob.index) | set(m_cons.index))
        cols = sorted(set(m_pob.columns) | set(m_cons.columns), key=clave_periodo)
        a = m_pob.reindex(index=filas, columns=cols, fill_value=0)
        b = m_cons.reindex(index=filas, columns=cols, fill_value=0)
        difs = [(s, p, int(a.at[s, p]), int(b.at[s, p])) for s in filas for p in cols if a.at[s, p] != b.at[s, p]]
        reportar(4, "Matriz semestre x periodo == hoja Matriz", "OK" if not difs else "FALLA",
                 [f"sem {s} {p}: portal={x} consolidado={y}" for s, p, x, y in difs[:30]]
                 or [f"{len(filas)} semestres x {len(cols)} periodos idénticos"])

    # 5. Excluidos
    excl = leer_hoja(args.consolidado, "Excluidos", dtype=str)
    if excl is None:
        reportar(5, "Hoja Excluidos", "N/A", ["El consolidado no tiene hoja 'Excluidos'."])
    else:
        col_tipo = next((c for c in excl.columns if "tipo" in str(c).lower()), None)
        conteo = excl[col_tipo].fillna("").str.strip().value_counts().to_dict() if col_tipo else {}
        ok = len(excl) == sum(EXCLUIDOS_ESPERADOS.values()) and all(
            conteo.get(k, 0) == v for k, v in EXCLUIDOS_ESPERADOS.items()
        )
        reportar(5, "Hoja Excluidos: 1.475 filas (700 / 283 / 492)", "OK" if ok else "FALLA", [
            f"Filas: {len(excl)} (esperado {sum(EXCLUIDOS_ESPERADOS.values())})",
            *[f"{k}: {conteo.get(k, 0)} (esperado {v})" for k, v in EXCLUIDOS_ESPERADOS.items()],
            *[f"Otro tipo '{k}': {v}" for k, v in conteo.items() if k not in EXCLUIDOS_ESPERADOS],
        ])

    # 6. Pares alumno-periodo
    periodos, origen = periodos_configurados(args.periodos, poblacion)
    filtrada = poblacion[poblacion["periodo"].isin(periodos)]
    esperado = {(int(u), p): int(s) for u, p, s in zip(filtrada["usuarios_id"], filtrada["periodo"], filtrada["semestre"])}
    pares = cargar_pares_activos() or {}
    faltan = set(esperado) - set(pares)
    sobran = set(pares) - set(esperado)
    sem_dif = [k for k in set(esperado) & set(pares) if esperado[k] != pares[k]]
    reportar(6, f"usuarios_activos_periodos.csv == población en los periodos configurados ({origen})",
             "OK" if not (faltan or sobran or sem_dif) else "FALLA", [
                 f"Periodos: {', '.join(periodos)}",
                 f"Pares esperados={len(esperado)} en archivo={len(pares)} · faltan={len(faltan)} "
                 f"sobran={len(sobran)} semestre distinto={len(sem_dif)}",
                 *[f"ej. falta: {k}" for k in sorted(faltan)[:5]],
                 *[f"ej. sobra: {k}" for k in sorted(sobran)[:5]],
                 *[f"ej. semestre: {k} población={esperado[k]} archivo={pares[k]}" for k in sorted(sem_dif)[:5]],
             ])

    # 7. alumnos_v2 vs población
    if not os.path.exists(ALUMNOS_V2_PATH):
        reportar(7, "alumnos_v2 vs. población", "N/A", [f"No existe {ALUMNOS_V2_PATH} (corra el ETL de Alumnos)."])
    else:
        v2 = pd.read_csv(
            ALUMNOS_V2_PATH, encoding="utf-8-sig", low_memory=False,
            usecols=["usuarios_id", "ano_periodo_letivo", "periodo_anual_periodo_letivo", "semestre_alumno"],
        )
        v2 = v2.dropna(subset=["usuarios_id", "ano_periodo_letivo", "periodo_anual_periodo_letivo"])
        v2["usuarios_id"] = v2["usuarios_id"].astype(int)
        v2["periodo"] = (v2["ano_periodo_letivo"].astype(int).astype(str) + "."
                         + v2["periodo_anual_periodo_letivo"].astype(int).astype(str))
        v2 = v2.drop_duplicates(["usuarios_id", "periodo"])
        v2["semestre"] = pd.to_numeric(v2["semestre_alumno"], errors="coerce").fillna(0).astype(int)

        pob_claves = set(esperado)
        v2_claves = set(zip(v2["usuarios_id"], v2["periodo"]))
        no_en_v2 = sorted(pob_claves - v2_claves, key=lambda k: (clave_periodo(k[1]), k[0]))
        no_en_pob = v2_claves - pob_claves

        m_pob = matriz(filtrada)
        m_v2 = matriz(v2[v2["periodo"].isin(periodos)])
        filas = sorted(set(m_pob.index) | set(m_v2.index))
        cols = sorted(set(m_pob.columns) | set(m_v2.columns), key=clave_periodo)
        a = m_pob.reindex(index=filas, columns=cols, fill_value=0)
        b = m_v2.reindex(index=filas, columns=cols, fill_value=0)
        difs = [(s, p, int(a.at[s, p]), int(b.at[s, p])) for s in filas for p in cols if a.at[s, p] != b.at[s, p]]

        por_periodo = pd.Series([p for _, p in no_en_v2]).value_counts() if no_en_v2 else pd.Series(dtype=int)
        reportar(7, "alumnos_v2 vs. población (periodos configurados)",
                 "OK" if not (no_en_v2 or no_en_pob or difs) else "FALLA", [
                     f"(usuarios_id, periodo) de la población que NO están en alumnos_v2: {len(no_en_v2)}"
                     " (alumnos sin periodo_letivo en la base del portal)",
                     *[f"  {p}: {int(n)}" for p, n in sorted(por_periodo.items(), key=lambda x: clave_periodo(x[0]))],
                     *[f"  - usuarios_id={u} periodo={p}" for u, p in no_en_v2[:args.max_listar]],
                     *([f"  ... y {len(no_en_v2) - args.max_listar} más (use --max-listar)"]
                       if len(no_en_v2) > args.max_listar else []),
                     f"(usuarios_id, periodo) en alumnos_v2 que NO están en la población: {len(no_en_pob)}",
                     f"Celdas periodo/semestre distintas: {len(difs)}",
                     *[f"  sem {s} {p}: población={x} alumnos_v2={y}" for s, p, x, y in difs[:30]],
                 ])

    fallas = estados.count("FALLA")
    print(f"\nResumen: {estados.count('OK')} OK · {fallas} FALLA · {estados.count('N/A')} N/A")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
