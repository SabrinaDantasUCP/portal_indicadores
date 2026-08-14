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
