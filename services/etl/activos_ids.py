"""
services/etl/activos_ids.py

Fuente única de "alumnos activos" usada para generar la variante v2 de los
ETL de Alumnos, Asistencias y Encuestas (Alumno→Docente). Reemplaza el
antiguo assets/data/global/base_datos_activos.csv (que había que subir por
SCP): ahora se sube un .txt vía la pantalla de admin "Alumnos Activos"
(modules/activos_config_etl.py), que sobrescribe siempre el mismo archivo
en ACTIVOS_TXT_PATH — "el último subido" es siempre el único que existe.

Formato esperado: un id por línea. Si la línea tiene más de una columna
separada por espacio/tab (ej. archivos exportados con un índice de fila
adelante, como "1\tab3"), se usa la ÚLTIMA columna.
"""

import io
import os
import re
import unicodedata

import pandas as pd

from scripts.csv_to_parquet import BASE_DIR

ACTIVOS_TXT_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "usuarios_activos_ids.txt")

# Pares (usuarios_id, periodo) "activo" -- solo lo escribe
# services/etl/activos_criterios_runner.py a partir de la población oficial
# (POBLACION_CSV_PATH), que sabe en QUÉ periodo específico cada alumno es
# activo; el upload manual de ACTIVOS_TXT_PATH no tiene esa granularidad.
# Lo usa services/etl/alumnos_etl.generar_alumnos_v2 para filtrar
# alumnos_v2 por (alumno, periodo) en vez de solo por alumno -- así el
# periodo x semestre de alumnos_v2 refleja exactamente la población oficial,
# en vez de traer TODO el historial de cualquier alumno activo en algún
# periodo.
ACTIVOS_PERIODOS_CSV_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "usuarios_activos_periodos.csv")

# Población oficial de alumnos activos, cerrada FUERA del portal (ETL
# etl_unico_activos_2018_2_2026_1.py + consolidado "Alumnos Reales Max 2
# Recursantes") y subida vía la pantalla de admin "Alumnos Activos". El
# portal no recalcula criterios, notas, recortes ni cohortes: solo consume
# esta lista (ver leer_poblacion / services/etl/activos_criterios_runner.py).
POBLACION_CSV_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "alumnos_activos_poblacion.csv")


def parsear_ids_activos(texto: str) -> list:
    """Parsea el contenido crudo del .txt: 1 id por línea (o última columna
    de cada línea, si hay más de una separada por espacio/tab). Ignora
    líneas vacías o cuya última columna no sea un entero."""
    ids = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        ultimo = linea.split()[-1]
        try:
            ids.append(int(ultimo))
        except ValueError:
            continue
    return ids


def guardar_ids_activos(texto: str) -> int:
    """Valida y guarda el .txt en ACTIVOS_TXT_PATH (sobrescribe el
    anterior). Devuelve la cantidad de ids válidos encontrados. Lanza
    ValueError si no se encontró ningún id válido, para no dejar pisado el
    archivo anterior con uno vacío/mal formateado."""
    ids = parsear_ids_activos(texto)
    if not ids:
        raise ValueError("No se encontró ningún id válido en el archivo.")

    os.makedirs(os.path.dirname(ACTIVOS_TXT_PATH), exist_ok=True)
    with open(ACTIVOS_TXT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(str(i) for i in ids))
    return len(ids)


def cargar_ids_activos():
    """None si todavía no se subió ningún archivo -- los runners lo
    interpretan como "no generar v2 todavía" (mismo comportamiento que
    antes con os.path.exists(base_datos_activos.csv))."""
    if not os.path.exists(ACTIVOS_TXT_PATH):
        return None
    with open(ACTIVOS_TXT_PATH, "r", encoding="utf-8") as f:
        ids = parsear_ids_activos(f.read())
    return set(ids) if ids else None


def guardar_pares_activos(pares) -> int:
    """Escribe ACTIVOS_PERIODOS_CSV_PATH con columnas
    usuarios_id,periodo,semestre a partir de un dict {(usuarios_id, periodo):
    semestre} (ver services/etl/activos_criterios_etl.calcular_ids_activos).
    Sobrescribe el anterior. Devuelve la cantidad de pares escritos."""
    filas = sorted(
        (int(uid), str(periodo), int(sem)) for (uid, periodo), sem in pares.items()
    )
    os.makedirs(os.path.dirname(ACTIVOS_PERIODOS_CSV_PATH), exist_ok=True)
    with open(ACTIVOS_PERIODOS_CSV_PATH, "w", encoding="utf-8") as f:
        f.write("usuarios_id,periodo,semestre\n")
        for uid, periodo, sem in filas:
            f.write(f"{uid},{periodo},{sem}\n")
    return len(filas)


def borrar_pares_activos():
    """Elimina ACTIVOS_PERIODOS_CSV_PATH si existe -- se llama cuando se
    sube una lista manual de ids (ver modules/activos_config_etl.py), ya
    que esa lista no tiene información de periodo y los pares viejos
    quedarían inconsistentes con los ids nuevos. Sin este archivo,
    generar_alumnos_v2 vuelve a filtrar solo por usuarios_id (todo el
    historial del alumno), que es el comportamiento seguro por defecto."""
    if os.path.exists(ACTIVOS_PERIODOS_CSV_PATH):
        os.remove(ACTIVOS_PERIODOS_CSV_PATH)


def cargar_pares_activos():
    """None si no existe el archivo (cálculo automático nunca corrió, o se
    invalidó por un upload manual de ids) -- en ese caso
    generar_alumnos_v2 debe filtrar solo por usuarios_id, sin exigir
    periodo. Si existe, devuelve {(usuarios_id, periodo): semestre}."""
    if not os.path.exists(ACTIVOS_PERIODOS_CSV_PATH):
        return None
    pares = {}
    with open(ACTIVOS_PERIODOS_CSV_PATH, "r", encoding="utf-8") as f:
        next(f, None)  # header
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                uid_str, periodo, sem_str = linea.split(",", 2)
                pares[(int(uid_str), periodo)] = int(sem_str)
            except ValueError:
                continue
    return pares if pares else None


# ─────────────────────────────────────────────
# POBLACIÓN OFICIAL DE ALUMNOS ACTIVOS (CSV/XLSX)
# ─────────────────────────────────────────────

# Cabecera normalizada (sin acentos, minúsculas, solo letras/dígitos) ->
# nombre interno. Tolera "Año"/"Ano", "Sección"/"seccion", "ID Usuario"/
# "id_usuario", "Doc. Oficial"/"doc oficial", etc.
_POBLACION_COLUMNAS = {
    "ano": "ano",
    "periodo": "periodo_anual",
    "catraca": "catraca",
    "idusuario": "usuarios_id",
    "nombre": "nome",
    "docoficial": "doc_oficial",
    "semestre": "semestre",
    "seccion": "seccion",
    "motivo": "motivo",
}
_POBLACION_OBLIGATORIAS = {
    "ano": "Año",
    "periodo_anual": "Periodo",
    "usuarios_id": "ID Usuario",
    "semestre": "Semestre",
}
POBLACION_COLUMNAS_SALIDA = [
    "usuarios_id", "periodo", "semestre", "seccion", "motivo", "catraca", "nome", "doc_oficial",
]
_ENTERO_RE = r"^\d+(?:\.0+)?$"  # "2018" o "2018.0" (celdas numéricas de Excel)


def _normalizar_cabecera(nombre) -> str:
    texto = unicodedata.normalize("NFKD", str(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def _decodificar(contenido: bytes) -> str:
    try:
        return contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenido.decode("latin-1")


def _detectar_separador(texto: str) -> str:
    primera = texto.splitlines()[0] if texto.strip() else ""
    conteos = {sep: primera.count(sep) for sep in ("\t", ";", ",")}
    sep = max(conteos, key=conteos.get)
    return sep if conteos[sep] > 0 else ";"


def _ejemplos(valores, n=5) -> str:
    valores = list(valores)
    texto = ", ".join(str(v) for v in valores[:n])
    return texto + (", ..." if len(valores) > n else "")


def leer_poblacion(contenido: bytes, nombre_archivo: str) -> pd.DataFrame:
    """Lee y valida el archivo de población oficial (.csv/.txt con separador
    ";", "," o tab -- detectado por la primera línea -- o .xlsx, usando la
    hoja "Alumnos" si existe). Todo se lee como texto para no perder ceros a
    la izquierda (ej. "Doc. Oficial" = "001675761").

    Columnas del archivo: Año, Periodo, Catraca, ID Usuario, Nombre,
    Doc. Oficial, Semestre, Sección, Motivo (obligatorias: Año, Periodo,
    ID Usuario, Semestre). Sección vacía es válida (alumno solo con materias
    recursadas) y la fila se conserva. No modifica semestre ni sección.

    Devuelve un DataFrame con POBLACION_COLUMNAS_SALIDA (usuarios_id y
    semestre int, periodo "AAAA.S", el resto texto). Lanza ValueError con
    un mensaje legible si el archivo no es válido."""
    extension = os.path.splitext(nombre_archivo or "")[1].lower()
    try:
        if extension in (".xlsx", ".xlsm"):
            hojas = pd.ExcelFile(io.BytesIO(contenido)).sheet_names
            hoja = next((h for h in hojas if _normalizar_cabecera(h) == "alumnos"), hojas[0])
            df = pd.read_excel(io.BytesIO(contenido), sheet_name=hoja, dtype=str)
        elif extension in (".csv", ".txt", ""):
            texto = _decodificar(contenido)
            if not texto.strip():
                raise ValueError("El archivo está vacío.")
            df = pd.read_csv(
                io.StringIO(texto), sep=_detectar_separador(texto), dtype=str,
                keep_default_na=False, engine="python",
            )
        else:
            raise ValueError(f"Formato no soportado ({extension}). Use .csv, .txt o .xlsx.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"No se pudo leer el archivo '{nombre_archivo}': {exc}") from exc

    renombrar = {}
    for col in df.columns:
        interno = _POBLACION_COLUMNAS.get(_normalizar_cabecera(col))
        if interno and interno not in renombrar.values():
            renombrar[col] = interno
    df = df[list(renombrar)].rename(columns=renombrar)

    faltantes = [visible for interno, visible in _POBLACION_OBLIGATORIAS.items() if interno not in df.columns]
    if faltantes:
        raise ValueError(
            f"Faltan columnas obligatorias: {', '.join(faltantes)}. Se esperan: Año, Periodo, "
            "Catraca, ID Usuario, Nombre, Doc. Oficial, Semestre, Sección, Motivo."
        )
    for interno in _POBLACION_COLUMNAS.values():
        if interno not in df.columns:
            df[interno] = ""

    df = df.fillna("").astype(str)
    for col in df.columns:
        df[col] = df[col].str.strip()
    # Filas totalmente vacías (ej. líneas en blanco al final del Excel/CSV).
    df = df[(df != "").any(axis=1)].reset_index(drop=True)
    if df.empty:
        raise ValueError("El archivo no tiene filas de datos.")

    fila_archivo = df.index + 2  # +1 cabecera, +1 base 1

    def _filas_con_error(mascara, columna, descripcion):
        ejemplos = [f"fila {f}: '{v}'" for f, v in zip(fila_archivo[mascara], df.loc[mascara, columna])]
        return f"{int(mascara.sum())} fila(s) con {descripcion} ({_ejemplos(ejemplos)})."

    errores = []
    for interno, visible in _POBLACION_OBLIGATORIAS.items():
        invalidas = ~df[interno].str.match(_ENTERO_RE)
        if invalidas.any():
            errores.append(_filas_con_error(invalidas, interno, f"'{visible}' vacío o no entero"))
    if errores:
        raise ValueError("Población inválida:\n- " + "\n- ".join(errores))

    for interno in _POBLACION_OBLIGATORIAS:
        df[interno] = df[interno].astype(float).astype(int)

    invalidas = ~df["periodo_anual"].isin([1, 2])
    if invalidas.any():
        errores.append(_filas_con_error(invalidas, "periodo_anual", "'Periodo' distinto de 1 o 2"))
    invalidas = ~df["semestre"].between(1, 12)
    if invalidas.any():
        errores.append(_filas_con_error(invalidas, "semestre", "'Semestre' fuera de 1-12"))

    df["periodo"] = df["ano"].astype(str) + "." + df["periodo_anual"].astype(str)

    duplicadas = df.duplicated(["usuarios_id", "periodo"], keep=False)
    if duplicadas.any():
        pares = df.loc[duplicadas, ["usuarios_id", "periodo"]].drop_duplicates()
        descripcion = [f"{uid} en {per}" for uid, per in zip(pares["usuarios_id"], pares["periodo"])]
        errores.append(
            f"{len(pares)} 'ID Usuario' repetido(s) en el mismo periodo "
            f"({int(duplicadas.sum())} filas; {_ejemplos(descripcion)})."
        )

    if errores:
        raise ValueError("Población inválida:\n- " + "\n- ".join(errores))

    return df[POBLACION_COLUMNAS_SALIDA].reset_index(drop=True)


def guardar_poblacion(df: pd.DataFrame) -> int:
    """Escribe la población (salida de leer_poblacion) en POBLACION_CSV_PATH
    de forma atómica (.tmp + os.replace): si algo falla a mitad de camino,
    el archivo anterior queda intacto. Devuelve la cantidad de filas."""
    os.makedirs(os.path.dirname(POBLACION_CSV_PATH), exist_ok=True)
    tmp_path = POBLACION_CSV_PATH + ".tmp"
    try:
        df[POBLACION_COLUMNAS_SALIDA].to_csv(tmp_path, index=False, encoding="utf-8")
        os.replace(tmp_path, POBLACION_CSV_PATH)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return len(df)


def cargar_poblacion():
    """None si todavía no se subió ninguna población. Si existe, devuelve
    el DataFrame con POBLACION_COLUMNAS_SALIDA (usuarios_id y semestre int,
    el resto texto -- se conservan ceros a la izquierda)."""
    if not os.path.exists(POBLACION_CSV_PATH):
        return None
    df = pd.read_csv(POBLACION_CSV_PATH, dtype=str, keep_default_na=False, encoding="utf-8")
    df["usuarios_id"] = df["usuarios_id"].astype(int)
    df["semestre"] = df["semestre"].astype(int)
    return df


def _clave_periodo(periodo: str):
    ano, _, sem = str(periodo).partition(".")
    return (int(ano), int(sem or 0))


def totales_por_periodo(df: pd.DataFrame) -> pd.Series:
    """Cantidad de usuarios_id únicos por periodo, en orden cronológico."""
    totales = df.groupby("periodo")["usuarios_id"].nunique()
    orden = sorted(totales.index, key=_clave_periodo)
    return totales.reindex(orden).rename("alumnos")
