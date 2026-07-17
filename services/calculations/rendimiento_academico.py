import pandas as pd

from services.data.duckdb_engine import aggregate


COL_PERIODO = "ano_periodo_letivo"
COL_SUBPERIODO = "periodo_anual_periodo_letivo"
COL_SEMESTRE_ALUMNO = "semestre_alumno"
COL_SEMESTRE_DISCIPLINA = "semestre_disciplina"
COL_ALUMNO = "nome_sobrenome"
COL_CATRACA = "numero_catraca"
COL_ID_ALUMNO = "usuarios_id"
COL_COHORTE = "cohorte"
COL_TIPO_ALUMNO = "tipo_ingresso"
COL_STATUS_ALUMNO = "nombre_status_actual"
COL_CALIFICACION = "calificacion_final_1a5"
COL_DISCIPLINA = "disciplina"
COL_SECCION = "turma"
COL_FILIAL = "filial_periodo_letivo"
COL_TIPO_DISCIPLINA = "tipo_disciplina"
COL_RESULTADO = "resultado_final"
COL_EGRESO = "periodo_egresso_format"
COL_ESTADO_TITULO = "estado_titulacion"
COL_FECHA_TITULO = "fecha_titulacion"
COL_DETALLE_TITULO = "detalle"


def prepare_rendimiento_source(df):
    required_cols = [COL_COHORTE, COL_ID_ALUMNO, COL_CALIFICACION]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared = df.copy()
    prepared[COL_COHORTE] = prepared[COL_COHORTE].astype(str).str.strip()
    prepared[COL_CALIFICACION] = pd.to_numeric(
        prepared[COL_CALIFICACION],
        errors="coerce",
    )

    if COL_SEMESTRE_ALUMNO in prepared.columns:
        prepared[COL_SEMESTRE_ALUMNO] = pd.to_numeric(
            prepared[COL_SEMESTRE_ALUMNO],
            errors="coerce",
        )

    if COL_SEMESTRE_DISCIPLINA in prepared.columns:
        prepared[COL_SEMESTRE_DISCIPLINA] = pd.to_numeric(
            prepared[COL_SEMESTRE_DISCIPLINA],
            errors="coerce",
        )

    return prepared, []


def calculate_student_general_performance(df, alumno_nome):
    required_cols = [COL_ALUMNO, COL_TIPO_DISCIPLINA, COL_CALIFICACION]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return 0.0, missing_cols

    df_regulares = df[
        (df[COL_ALUMNO] == alumno_nome)
        & (df[COL_TIPO_DISCIPLINA].astype(str).str.strip().str.upper() == "REGULAR")
    ]
    return df_regulares[COL_CALIFICACION].mean(), []


def calculate_subject_performance(df):
    required_cols = [
        COL_COHORTE,
        COL_SEMESTRE_DISCIPLINA,
        COL_DISCIPLINA,
        COL_ID_ALUMNO,
        COL_CALIFICACION,
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    # drop_duplicates(keep="first") depende del orden de las filas -> se mantiene
    # en pandas para preservar la semantica exacta; solo el groupby va a DuckDB.
    df_unicos = df.drop_duplicates(
        subset=[COL_COHORTE, COL_SEMESTRE_DISCIPLINA, COL_DISCIPLINA, COL_ID_ALUMNO]
    )
    resumen = aggregate(
        df_unicos,
        f'''
        SELECT "{COL_COHORTE}" AS "{COL_COHORTE}",
               "{COL_SEMESTRE_DISCIPLINA}" AS "{COL_SEMESTRE_DISCIPLINA}",
               "{COL_DISCIPLINA}" AS "{COL_DISCIPLINA}",
               AVG("{COL_CALIFICACION}") AS "TRASA",
               COUNT("{COL_ID_ALUMNO}") AS "N"
        FROM src
        WHERE "{COL_COHORTE}" IS NOT NULL
          AND "{COL_SEMESTRE_DISCIPLINA}" IS NOT NULL
          AND "{COL_DISCIPLINA}" IS NOT NULL
        GROUP BY 1, 2, 3
        ''',
    )
    resumen = resumen.sort_values(
        [COL_COHORTE, COL_SEMESTRE_DISCIPLINA, COL_DISCIPLINA]
    ).reset_index(drop=True)
    return resumen, []


def calculate_semester_performance(df):
    required_cols = [COL_COHORTE, COL_SEMESTRE_ALUMNO, COL_ID_ALUMNO, COL_CALIFICACION]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    # Promedio de promedios en dos niveles, empujado a DuckDB:
    #  - TRASE: promedio del alumno en el semestre
    #  - TRAS: promedio de los TRASE de la cohorte/semestre; N: cantidad de alumnos
    df_tras = aggregate(
        df,
        f'''
        WITH trase AS (
            SELECT "{COL_COHORTE}" AS cohorte,
                   "{COL_SEMESTRE_ALUMNO}" AS sem,
                   "{COL_ID_ALUMNO}" AS uid,
                   AVG("{COL_CALIFICACION}") AS trase
            FROM src
            WHERE "{COL_COHORTE}" IS NOT NULL
              AND "{COL_SEMESTRE_ALUMNO}" IS NOT NULL
              AND "{COL_ID_ALUMNO}" IS NOT NULL
            GROUP BY 1, 2, 3
        )
        SELECT cohorte AS "{COL_COHORTE}",
               sem AS "{COL_SEMESTRE_ALUMNO}",
               AVG(trase) AS "TRAS",
               COUNT(uid) AS "N"
        FROM trase
        GROUP BY cohorte, sem
        ''',
    )
    df_tras = df_tras.sort_values([COL_COHORTE, COL_SEMESTRE_ALUMNO]).reset_index(drop=True)
    df_tras["TRAS"] = df_tras["TRAS"].fillna(0)
    return df_tras, []


def calculate_career_performance(df):
    df_tras, missing_cols = calculate_semester_performance(df)
    if missing_cols:
        return pd.DataFrame(), 0.0, missing_cols

    df_career = df_tras.rename(columns={"N": "N_ALUNOS"}).copy()
    trc_valor = df_career["TRAS"].mean() if not df_career.empty else 0.0
    return df_career, trc_valor, []
