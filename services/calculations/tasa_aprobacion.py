import pandas as pd

from services.data.duckdb_engine import aggregate


COL_COHORTE = "cohorte"
COL_DISCIPLINA = "disciplina"
COL_SECCION = "turma"
COL_CALIFICACION = "calificacion_final_1a5"
COL_ID_ALUMNO = "usuarios_id"
COL_SEMESTRE = "semestre_alumno"


def prepare_approval_source(df):
    required_cols = [COL_COHORTE, COL_CALIFICACION, COL_ID_ALUMNO]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared = df.copy()
    prepared[COL_CALIFICACION] = pd.to_numeric(
        prepared[COL_CALIFICACION],
        errors="coerce",
    )
    prepared["aprobado"] = prepared[COL_CALIFICACION] >= 2
    return prepared, []


def calculate_subject_approval(df):
    required_cols = [COL_DISCIPLINA, COL_ID_ALUMNO, "aprobado"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    resumen = aggregate(
        df,
        f'''
        SELECT "{COL_DISCIPLINA}" AS "{COL_DISCIPLINA}",
               COUNT("{COL_ID_ALUMNO}") AS "Total",
               SUM(CASE WHEN "aprobado" THEN 1 ELSE 0 END) AS "Aprobados"
        FROM src
        WHERE "{COL_DISCIPLINA}" IS NOT NULL
        GROUP BY "{COL_DISCIPLINA}"
        ''',
    )
    resumen = resumen.sort_values(COL_DISCIPLINA).reset_index(drop=True)
    resumen["Tasa Aprobación (%)"] = (resumen["Aprobados"] / resumen["Total"]) * 100
    return resumen, []


def calculate_section_approval(df):
    required_cols = [COL_SECCION, COL_ID_ALUMNO, "aprobado"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    resumen = aggregate(
        df,
        f'''
        SELECT "{COL_SECCION}" AS "{COL_SECCION}",
               COUNT("{COL_ID_ALUMNO}") AS "Inscritos",
               SUM(CASE WHEN "aprobado" THEN 1 ELSE 0 END) AS "Aprobados"
        FROM src
        WHERE "{COL_SECCION}" IS NOT NULL
        GROUP BY "{COL_SECCION}"
        ''',
    )
    resumen = resumen.sort_values(COL_SECCION).reset_index(drop=True)
    resumen["% Aprobación"] = (resumen["Aprobados"] / resumen["Inscritos"]) * 100
    return resumen, []


def calculate_career_approval(df):
    required_cols = [COL_COHORTE, COL_SEMESTRE, COL_ID_ALUMNO, COL_CALIFICACION]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared, missing_cols = prepare_approval_source(df)
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared[COL_SEMESTRE] = pd.to_numeric(prepared[COL_SEMESTRE], errors="coerce")
    prepared = prepared.dropna(subset=[COL_SEMESTRE])

    # Agregacion en dos niveles empujada a DuckDB:
    #  - nivel alumno/semestre: asignaturas cursadas vs. aprobadas
    #  - nivel cohorte/semestre: inscriptos (EIS) y aprobaron todas (EPAS)
    resumen = aggregate(
        prepared,
        f'''
        WITH alumno_semestre AS (
            SELECT "{COL_COHORTE}" AS cohorte,
                   "{COL_SEMESTRE}" AS sem,
                   "{COL_ID_ALUMNO}" AS uid,
                   COUNT("{COL_CALIFICACION}") AS total_asignaturas,
                   SUM(CASE WHEN "aprobado" THEN 1 ELSE 0 END) AS total_aprobadas
            FROM src
            WHERE "{COL_COHORTE}" IS NOT NULL AND "{COL_ID_ALUMNO}" IS NOT NULL
            GROUP BY 1, 2, 3
        )
        SELECT cohorte AS "{COL_COHORTE}",
               sem AS "{COL_SEMESTRE}",
               COUNT(uid) AS "EIS",
               SUM(CASE WHEN total_asignaturas = total_aprobadas THEN 1 ELSE 0 END) AS "EPAS"
        FROM alumno_semestre
        GROUP BY cohorte, sem
        ''',
    )
    resumen = resumen.sort_values([COL_COHORTE, COL_SEMESTRE]).reset_index(drop=True)
    resumen["TAC (%)"] = (resumen["EPAS"] / resumen["EIS"]) * 100
    resumen["Semestre"] = resumen[COL_SEMESTRE].apply(lambda value: f"{int(value)}º Semestre")
    return resumen, []
