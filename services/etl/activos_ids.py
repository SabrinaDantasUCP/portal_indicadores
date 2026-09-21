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

import os

from scripts.csv_to_parquet import BASE_DIR

ACTIVOS_TXT_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "usuarios_activos_ids.txt")

# Pares (usuarios_id, periodo) "activo" -- solo lo escribe
# services/etl/activos_criterios_runner.py (el cálculo automático por
# criterios sabe en QUÉ periodo específico cada alumno califica; el upload
# manual de ACTIVOS_TXT_PATH no tiene esa granularidad). Lo usa
# services/etl/alumnos_etl.generar_alumnos_v2 para filtrar alumnos_v2 por
# (alumno, periodo) en vez de solo por alumno -- así el periodo x semestre
# de alumnos_v2 refleja exactamente los periodos en que cada alumno calificó
# (incluido el ajuste por muestreo de 2018.2-2020.2), en vez de traer TODO
# el historial de cualquier alumno que califique en algún periodo.
ACTIVOS_PERIODOS_CSV_PATH = os.path.join(BASE_DIR, "assets", "data", "global", "usuarios_activos_periodos.csv")


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
