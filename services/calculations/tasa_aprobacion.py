import pandas as pd


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

    resumen = (
        df.groupby(COL_DISCIPLINA)
        .agg(
            Total=(COL_ID_ALUMNO, "count"),
            Aprobados=("aprobado", "sum"),
        )
        .reset_index()
    )
    resumen["Tasa Aprobación (%)"] = (resumen["Aprobados"] / resumen["Total"]) * 100
    return resumen, []


def calculate_section_approval(df):
    required_cols = [COL_SECCION, COL_ID_ALUMNO, "aprobado"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    resumen = (
        df.groupby(COL_SECCION)
        .agg(
            Inscritos=(COL_ID_ALUMNO, "count"),
            Aprobados=("aprobado", "sum"),
        )
        .reset_index()
    )
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

    alumno_semestre = (
        prepared.groupby([COL_COHORTE, COL_SEMESTRE, COL_ID_ALUMNO])
        .agg(
            Total_Asignaturas=(COL_CALIFICACION, "count"),
            Total_Aprobadas=("aprobado", "sum"),
        )
        .reset_index()
    )
    alumno_semestre["aprobo_todas"] = (
        alumno_semestre["Total_Asignaturas"] == alumno_semestre["Total_Aprobadas"]
    )

    resumen = (
        alumno_semestre.groupby([COL_COHORTE, COL_SEMESTRE])
        .agg(
            EIS=(COL_ID_ALUMNO, "count"),
            EPAS=("aprobo_todas", "sum"),
        )
        .reset_index()
    )
    resumen["TAC (%)"] = (resumen["EPAS"] / resumen["EIS"]) * 100
    resumen["Semestre"] = resumen[COL_SEMESTRE].apply(lambda value: f"{int(value)}º Semestre")
    return resumen, []
