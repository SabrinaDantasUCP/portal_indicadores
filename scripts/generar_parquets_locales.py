"""
scripts/generar_parquets_locales.py

Script para generar datasets Parquet locales de desarrollo para el módulo de encuestas.
Construye los archivos necesarios en assets/data/encuestas/ respetando el esquema oficial
del ETL y del diseño HTML de JuanFer:
  - encuestas_alumnos_al_docente_20261_v1.parquet
  - encuestas_alumnos_al_docente_20261_v2.parquet
  - encuestas_docente_autoeval_20261.parquet

Permite el funcionamiento completo y visualización local del sistema sin depender
de la conectividad por VPN ni de las tareas cron del servidor.
"""

import os
import pandas as pd

from modules.encuestas_ev1 import (
    ASIGNACIONES_REFERENCIA,
    CATALOGO_PEDAGOGICO_EV1,
    PERFILES_DOCENTES_REFERENCIA,
)

CARPETA_SALIDA = os.path.join("assets", "data", "encuestas")
os.makedirs(CARPETA_SALIDA, exist_ok=True)


def construir_dataset_alumno_docente() -> pd.DataFrame:
    """Construye un DataFrame consolidado con todas las capas de indicadores de la EV1."""
    filas = []

    # 1. Indicador: avance_general
    filas.append({
        "indicador": "avance_general",
        "alumnos_unicos_esperados": 3,
        "alumnos_unicos_que_respondieron_al_menos_una": 2,
        "porcentaje_avance_alumnos": 66.67,
        "alumnos_unicos_que_respondieron_todas": 1,
        "porcentaje_avance_alumnos_todas": 33.33,
        "encuestas_esperadas": 13,
        "encuestas_respondidas": 9,
        "porcentaje_avance_encuestas": 69.23,
        "vigencia": "2026 - Subperiodo 1",
        "semestres_habilitados": "1, 2, 3, 4, 5, 6, 7, 8, 9, 10",
    })

    # 2. Indicador: avance_por_materia_seccion_grupo
    df_asig = pd.DataFrame(ASIGNACIONES_REFERENCIA)
    resumen_grupos = (
        df_asig.groupby(["materia", "seccion", "grupo", "docente"])
        .agg(
            alumnos_esperados=("alumno", "count"),
            alumnos_que_respondieron=("estado", lambda s: (s == "Completada").sum()),
        )
        .reset_index()
    )
    resumen_grupos["porcentaje_avance"] = (
        resumen_grupos["alumnos_que_respondieron"] / resumen_grupos["alumnos_esperados"] * 100.0
    ).round(2)

    for _, fila in resumen_grupos.iterrows():
        filas.append({
            "indicador": "avance_por_materia_seccion_grupo",
            "materia": fila["materia"],
            "seccion": fila["seccion"],
            "grupo": fila["grupo"],
            "docente": fila["docente"],
            "alumnos_esperados": int(fila["alumnos_esperados"]),
            "alumnos_que_respondieron": int(fila["alumnos_que_respondieron"]),
            "porcentaje_avance": float(fila["porcentaje_avance"]),
        })

    # 3. Indicador: avance_por_alumno
    for idx, asig in enumerate(ASIGNACIONES_REFERENCIA):
        filas.append({
            "indicador": "avance_por_alumno",
            "system_id": f"ALU{idx+1:04d}",
            "alumno": asig["alumno"],
            "materia": asig["materia"],
            "seccion": asig["seccion"],
            "grupo": asig["grupo"],
            "docente": asig["docente"],
            "docente_id": idx + 10,
            "planificacion_id": 100 + idx,
            "respondio": (asig["estado"] == "Completada"),
        })

    # 4. Indicador: resultado_general
    filas.append({
        "indicador": "resultado_general",
        "promedio_general": 4.31,
        "pct_favorable": 84.0,
        "pct_neutral": 10.0,
        "pct_desfavorable": 6.0,
        "dist_1": 15,
        "dist_2": 30,
        "dist_3": 75,
        "dist_4": 285,
        "dist_5": 345,
        "dimension_mejor": "Dominio y Planificación",
        "dimension_oportunidad": "Retroalimentación",
        "n_docentes_evaluados": 5,
        "n_respuestas_validas": 750,
        "n_criterios": 16,
    })

    # 5. Indicador: resultado_por_dimension
    for dim in CATALOGO_PEDAGOGICO_EV1:
        filas.append({
            "indicador": "resultado_por_dimension",
            "id_dimension": dim["id"],
            "dimension_nombre": dim["nombre"],
            "orden": dim["id"],
            "promedio": dim["puntaje_referencia"],
            "pct_favorable": 85.0,
            "pct_desfavorable": 5.0,
            "n_indicadores": len(dim["criterios"]),
            "n_respuestas": 150,
            "delta_vs_general": round(dim["puntaje_referencia"] - 4.31, 2),
        })

    # 6. Indicador: resultado_por_indicador
    for dim in CATALOGO_PEDAGOGICO_EV1:
        for idx_crit, cri in enumerate(dim["criterios"]):
            filas.append({
                "indicador": "resultado_por_indicador",
                "id_dimension": dim["id"],
                "dimension_nombre": dim["nombre"],
                "id_indicador": cri["indicador"].split(".")[0].strip(),
                "indicador_nombre": cri["indicador"],
                "orden": idx_crit + 1,
                "promedio": cri["puntaje"],
                "pct_favorable": 84.0,
                "pct_desfavorable": 6.0,
                "descriptor": cri["descriptor"],
                "n_criterios": 1,
                "n_respuestas": 150,
            })

    # 7. Indicador: resultado_por_criterio
    for dim in CATALOGO_PEDAGOGICO_EV1:
        for cri in dim["criterios"]:
            filas.append({
                "indicador": "resultado_por_criterio",
                "id_dimension": dim["id"],
                "dimension_nombre": dim["nombre"],
                "id_indicador": cri["indicador"].split(".")[0].strip(),
                "indicador_nombre": cri["indicador"],
                "id_criterio": cri["n"],
                "criterio_nombre": cri["texto"],
                "orden": cri["n"],
                "promedio": cri["puntaje"],
                "pct_favorable": 85.0,
                "pct_neutral": 10.0,
                "pct_desfavorable": 5.0,
                "dist_1": 2,
                "dist_2": 4,
                "dist_3": 10,
                "dist_4": 38,
                "dist_5": 46,
                "n_respuestas": 100,
            })

    # 8. Indicador: resultado_por_docente
    for doc_id, (nombre, p) in enumerate(PERFILES_DOCENTES_REFERENCIA.items(), start=1):
        filas.append({
            "indicador": "resultado_por_docente",
            "docente": nombre,
            "docente_id": doc_id,
            "promedio": p["score"],
            "descriptor": "Fortaleza" if p["score"] >= 4.4 else ("Adecuado" if p["score"] >= 4.1 else "Seguimiento"),
            "promedio_dim_1": p["dims"][0],
            "promedio_dim_2": p["dims"][1],
            "promedio_dim_3": p["dims"][2],
            "promedio_dim_4": p["dims"][3],
            "promedio_dim_5": p["dims"][4],
            "n_evaluaciones_recibidas": 15,
            "n_respuestas_validas": 75,
        })

    return pd.DataFrame(filas)


def construir_dataset_autoeval_docente() -> pd.DataFrame:
    """Construye un DataFrame para la autoevaluación docente."""
    filas = [
        {
            "indicador": "avance_general_docente",
            "docentes_unicos_esperados": 7,
            "docentes_unicos_que_respondieron_al_menos_una": 5,
            "porcentaje_avance_docentes": 71.43,
            "docentes_unicos_que_respondieron_todas": 4,
            "porcentaje_avance_docentes_todas": 57.14,
            "vigencia": "2026 - Subperiodo 1",
            "semestres_habilitados": "1..10",
        },
        {
            "indicador": "avance_por_docente",
            "materia": "ANATOMIA I",
            "seccion": "A",
            "grupo": "TEORIA",
            "docente": "LUIS SALINAS",
            "docente_id": 1,
            "planificacion_id": 101,
            "respondio": True,
        },
    ]
    return pd.DataFrame(filas)


def generar_archivos():
    """Genera y guarda los archivos parquet en assets/data/encuestas/."""
    df_alumno = construir_dataset_alumno_docente()
    ruta_v1 = os.path.join(CARPETA_SALIDA, "encuestas_alumnos_al_docente_20261_v1.parquet")
    ruta_v2 = os.path.join(CARPETA_SALIDA, "encuestas_alumnos_al_docente_20261_v2.parquet")
    df_alumno.to_parquet(ruta_v1, index=False)
    df_alumno.to_parquet(ruta_v2, index=False)
    print(f"Generado exitosamente: {ruta_v1} ({len(df_alumno)} filas)")
    print(f"Generado exitosamente: {ruta_v2} ({len(df_alumno)} filas)")

    df_doc = construir_dataset_autoeval_docente()
    ruta_autoeval = os.path.join(CARPETA_SALIDA, "encuestas_docente_autoeval_20261.parquet")
    df_doc.to_parquet(ruta_autoeval, index=False)
    print(f"Generado exitosamente: {ruta_autoeval} ({len(df_doc)} filas)")


if __name__ == "__main__":
    generar_archivos()
