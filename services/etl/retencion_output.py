# -*- coding: utf-8 -*-
"""
services/etl/retencion_output.py

Módulo de retención y purga segura de snapshots acumulativos en el directorio output/.
Garantiza que el espacio en disco no se sature por acumulaciones históricas periódicas,
cumpliendo una regla inquebrantable:
SI el sistema está congelado, pausado o sin nuevas generaciones, NO toca lo que tiene
(piso mínimo garantizado de versiones).
"""
import os
import re
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any

from scripts.csv_to_parquet import BASE_DIR
from utils.system_logging import get_logger

log = get_logger()

# Directorio por defecto de salida de snapshots
DIRECTORIO_OUTPUT_DEFECTO = os.path.join(BASE_DIR, "output")

# Definición de patrones de snapshots acumulativos con marca de tiempo (timestamp)
# Cada patrón define el nombre de la serie y la expresión regular estricta
PATRONES_SERIES_SNAPSHOTS = [
    {
        "nombre_serie": "indicadores_encuestas_v1",
        "regex": re.compile(r"^indicadores_encuestas_(\d{8}_\d{6})\.csv$", re.IGNORECASE),
    },
    {
        "nombre_serie": "indicadores_encuestas_v2",
        "regex": re.compile(r"^indicadores_encuestas_v2_(\d{8}_\d{6})\.csv$", re.IGNORECASE),
    },
    {
        "nombre_serie": "indicadores_encuestas_autoeval_docente",
        "regex": re.compile(r"^indicadores_encuestas_docente_autoeval_(\d{8}_\d{6})\.csv$", re.IGNORECASE),
    },
    {
        "nombre_serie": "avance_por_alumno_activos",
        "regex": re.compile(r"^avance_por_alumno_activos_(\d{8}_\d{6})\.csv$", re.IGNORECASE),
    },
]


def clasificar_archivo_snapshot(nombre_archivo: str) -> str:
    """
    Determina a qué serie de snapshots pertenece un archivo.
    Retorna el identificador de la serie o None si no es un snapshot purgable.
    """
    # Salvaguarda estricta: si contiene '_raw' o no es .csv, nunca se clasifica como snapshot
    if "_raw" in nombre_archivo.lower() or not nombre_archivo.lower().endswith(".csv"):
        return None

    for item in PATRONES_SERIES_SNAPSHOTS:
        if item["regex"].match(nombre_archivo):
            return item["nombre_serie"]

    return None


def aplicar_retencion_output(
    directorio_output: str = None,
    dias_retencion: int = 7,
    min_versiones: int = 2,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Aplica la política de retención de 7 días sobre los snapshots de output/.

    Reglas de protección:
    1. Piso mínimo inquebrantable (min_versiones): para cada serie se conservan
       SIEMPRE al menos `min_versiones` más recientes (por defecto 2), sin importar
       su antigüedad. Si un proceso está congelado o pausado, NUNCA se borran.
    2. Ventana de antigüedad (dias_retencion): únicamente los archivos que excedan
       el piso mínimo Y cuya antigüedad sea superior a `dias_retencion` son eliminados.
    3. Whitelist estricta: los archivos de insumo crudo (*_raw.csv) o cualquier otro
       archivo fuera de los patrones de snapshot quedan totalmente intocados.

    Retorna un diccionario con las métricas del proceso.
    """
    ruta_dir = directorio_output or DIRECTORIO_OUTPUT_DEFECTO

    resultado = {
        "directorio": ruta_dir,
        "dias_retencion": dias_retencion,
        "min_versiones": min_versiones,
        "dry_run": dry_run,
        "total_archivos_evaluados": 0,
        "archivos_conservados": [],
        "archivos_eliminados": [],
        "bytes_liberados": 0,
        "mb_liberados": 0.0,
    }

    if not os.path.exists(ruta_dir):
        log.warning("El directorio de salida no existe: %s", ruta_dir)
        return resultado

    archivos_presentes = os.listdir(ruta_dir)
    agrupacion_por_serie: Dict[str, List[Dict[str, Any]]] = {}

    for nombre in archivos_presentes:
        serie = clasificar_archivo_snapshot(nombre)
        if not serie:
            continue

        ruta_completa = os.path.join(ruta_dir, nombre)
        if not os.path.isfile(ruta_completa):
            continue

        try:
            mtime = os.path.getmtime(ruta_completa)
            tamano = os.path.getsize(ruta_completa)
            fecha_modificacion = datetime.fromtimestamp(mtime)
        except OSError as error_lectura:
            log.warning("No se pudo obtener información de %s: %s", nombre, error_lectura)
            continue

        agrupacion_por_serie.setdefault(serie, []).append({
            "nombre": nombre,
            "ruta": ruta_completa,
            "mtime": mtime,
            "fecha": fecha_modificacion,
            "tamano_bytes": tamano,
            "serie": serie,
        })

    ahora = datetime.now()
    fecha_limite = ahora - timedelta(days=dias_retencion)

    # Procesar cada serie de snapshots de forma independiente
    for serie, lista_archivos in agrupacion_por_serie.items():
        # Ordenar de más reciente a más antiguo
        lista_ordenada = sorted(lista_archivos, key=lambda x: x["mtime"], reverse=True)
        resultado["total_archivos_evaluados"] += len(lista_ordenada)

        # 1. Asegurar el piso mínimo garantizado (las primeras min_versiones quedan protegidas)
        versiones_protegidas = lista_ordenada[:min_versiones]
        versiones_candidatas = lista_ordenada[min_versiones:]

        for arch in versiones_protegidas:
            resultado["archivos_conservados"].append({
                "nombre": arch["nombre"],
                "serie": serie,
                "motivo": f"Piso mínimo de seguridad (últimas {min_versiones} versiones)",
                "tamano_mb": round(arch["tamano_bytes"] / (1024 * 1024), 2),
            })

        # 2. Evaluar candidatos restantes por fecha de corte
        for arch in versiones_candidatas:
            if arch["fecha"] < fecha_limite:
                # Supera los días de retención y excede el piso mínimo: califica para purga
                tamano_archivo = arch["tamano_bytes"]
                tamano_mb = round(tamano_archivo / (1024 * 1024), 2)

                if not dry_run:
                    try:
                        os.remove(arch["ruta"])
                        log.info(
                            "Snapshot eliminado por retención de %s días: %s (%s MB)",
                            dias_retencion, arch["nombre"], tamano_mb,
                        )
                        resultado["archivos_eliminados"].append({
                            "nombre": arch["nombre"],
                            "serie": serie,
                            "tamano_mb": tamano_mb,
                        })
                        resultado["bytes_liberados"] += tamano_archivo
                    except OSError as error_eliminar:
                        log.error("Error al eliminar snapshot %s: %s", arch["ruta"], error_eliminar)
                        resultado["archivos_conservados"].append({
                            "nombre": arch["nombre"],
                            "serie": serie,
                            "motivo": f"Error al intentar eliminar: {error_eliminar}",
                            "tamano_mb": tamano_mb,
                        })
                else:
                    # Modo simulación (dry-run)
                    log.info(
                        "[DRY-RUN] Snapshot calificado para eliminación: %s (%s MB, fecha=%s)",
                        arch["nombre"], tamano_mb, arch["fecha"],
                    )
                    resultado["archivos_eliminados"].append({
                        "nombre": arch["nombre"],
                        "serie": serie,
                        "tamano_mb": tamano_mb,
                    })
                    resultado["bytes_liberados"] += tamano_archivo
            else:
                # Dentro de la ventana de 7 días: se conserva
                resultado["archivos_conservados"].append({
                    "nombre": arch["nombre"],
                    "serie": serie,
                    "motivo": f"Dentro del periodo de retención de {dias_retencion} días",
                    "tamano_mb": round(arch["tamano_bytes"] / (1024 * 1024), 2),
                })

    resultado["mb_liberados"] = round(resultado["bytes_liberados"] / (1024 * 1024), 2)

    if resultado["archivos_eliminados"]:
        log.info(
            "Retención completada en %s: %s archivos eliminados, %s MB liberados (Modo dry_run=%s).",
            ruta_dir, len(resultado["archivos_eliminados"]), resultado["mb_liberados"], dry_run,
        )
    else:
        log.info(
            "Retención completada en %s: no hubo archivos obsoletos para eliminar. Todos protegidos o vigentes.",
            ruta_dir,
        )

    return resultado


def main():
    """Punto de entrada de línea de comandos para auditoría o ejecución manual."""
    parser = argparse.ArgumentParser(
        description="Aplica la política de retención segura de snapshots en output/ (defecto: 7 días y min 2 versiones)."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DIRECTORIO_OUTPUT_DEFECTO,
        help="Ruta al directorio output/ (por defecto ./output)",
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=7,
        help="Días máximos de antigüedad para conservar snapshots (por defecto 7)",
    )
    parser.add_argument(
        "--min-versiones",
        type=int,
        default=2,
        help="Piso mínimo de versiones a conservar por serie sin importar su fecha (por defecto 2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo simulación: solo muestra qué archivos se eliminarían sin borrar ninguno",
    )

    args = parser.parse_args()

    print("==========================================================")
    print(" Auditoría y Purga Segura de Snapshots de ETL")
    print(f" Directorio:    {args.output_dir}")
    print(f" Retención:     {args.dias} días")
    print(f" Piso mínimo:   {args.min_versiones} versiones por serie")
    print(f" Modo Dry-Run:  {args.dry_run}")
    print("==========================================================")

    res = aplicar_retencion_output(
        directorio_output=args.output_dir,
        dias_retencion=args.dias,
        min_versiones=args.min_versiones,
        dry_run=args.dry_run,
    )

    print("\n--- RESUMEN ---")
    print(f"Archivos evaluados:  {res['total_archivos_evaluados']}")
    print(f"Archivos conservados: {len(res['archivos_conservados'])}")
    print(f"Archivos eliminados:  {len(res['archivos_eliminados'])}")
    print(f"Espacio liberado:     {res['mb_liberados']} MB ({res['bytes_liberados']} bytes)")

    if res["archivos_conservados"]:
        print("\nDetalle de conservados:")
        for c in res["archivos_conservados"]:
            print(f"  [CONSERVADO] {c['nombre']} ({c['tamano_mb']} MB) -> {c['motivo']}")

    if res["archivos_eliminados"]:
        accion = "[CALIFICADO PARA ELIMINAR]" if args.dry_run else "[ELIMINADO]"
        print(f"\nDetalle de eliminados {accion}:")
        for e in res["archivos_eliminados"]:
            print(f"  {accion} {e['nombre']} ({e['tamano_mb']} MB)")


if __name__ == "__main__":
    main()
