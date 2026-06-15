import pandas as pd


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

    df_unicos = df.drop_duplicates(
        subset=[COL_COHORTE, COL_SEMESTRE_DISCIPLINA, COL_DISCIPLINA, COL_ID_ALUMNO]
    )
    resumen = (
        df_unicos.groupby([COL_COHORTE, COL_SEMESTRE_DISCIPLINA, COL_DISCIPLINA])
        .agg(TRASA=(COL_CALIFICACION, "mean"), N=(COL_ID_ALUMNO, "count"))
        .reset_index()
    )
    return resumen, []


def calculate_semester_performance(df):
    required_cols = [COL_COHORTE, COL_SEMESTRE_ALUMNO, COL_ID_ALUMNO, COL_CALIFICACION]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    df_trase = (
        df.groupby([COL_COHORTE, COL_SEMESTRE_ALUMNO, COL_ID_ALUMNO])
        .agg(TRASE=(COL_CALIFICACION, "mean"))
        .reset_index()
    )
    df_tras = (
        df_trase.groupby([COL_COHORTE, COL_SEMESTRE_ALUMNO])
        .agg(TRAS=("TRASE", "mean"), N=(COL_ID_ALUMNO, "count"))
        .reset_index()
    )
    df_tras["TRAS"] = df_tras["TRAS"].fillna(0)
    return df_tras, []


def calculate_career_performance(df):
    df_tras, missing_cols = calculate_semester_performance(df)
    if missing_cols:
        return pd.DataFrame(), 0.0, missing_cols

    df_career = df_tras.rename(columns={"N": "N_ALUNOS"}).copy()
    trc_valor = df_career["TRAS"].mean() if not df_career.empty else 0.0
    return df_career, trc_valor, []
