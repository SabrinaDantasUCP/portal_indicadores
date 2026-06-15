import pandas as pd


COL_PERIODO = "periodo"
COL_SUBPERIODO = "sub_periodo"
COL_ASIGNATURA = "asignatura"
COL_PROFESOR = "profesor"
COL_SECCION = "seccion"
COL_RESULTADO = "aprobado_reprobado"

REQUIRED_COLUMNS = [
    COL_PERIODO,
    COL_SUBPERIODO,
    COL_ASIGNATURA,
    COL_PROFESOR,
    COL_SECCION,
    COL_RESULTADO,
]

STUDENT_COLUMN_CANDIDATES = ["alumno", "estudiante", "nombre", "nombre_alumno"]


def validate_notas_source(df):
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def detect_student_column(df):
    for col in STUDENT_COLUMN_CANDIDATES:
        if col in df.columns:
            return col
    return None


def calculate_notas_summary(df, student_col):
    if not student_col:
        return pd.DataFrame(), {}

    df_unico = df.drop_duplicates(subset=[student_col, COL_ASIGNATURA])
    summary = (
        df_unico.groupby([COL_ASIGNATURA])
        .agg(
            total_alumnos=(student_col, "nunique"),
            aprobados=(COL_RESULTADO, lambda values: (values == "Aprobado").sum()),
            reprobados=(COL_RESULTADO, lambda values: (values == "Reprobado").sum()),
        )
        .reset_index()
    )
    summary["% Aprobados"] = (summary["aprobados"] / summary["total_alumnos"] * 100).round(1)

    total_alumnos = int(df_unico[student_col].nunique())
    total_aprobados = int((df_unico[COL_RESULTADO] == "Aprobado").sum())
    total_reprobados = int((df_unico[COL_RESULTADO] == "Reprobado").sum())
    pct_aprobados = round(total_aprobados / total_alumnos * 100, 1) if total_alumnos else 0

    totals = {
        "total_alumnos": total_alumnos,
        "total_aprobados": total_aprobados,
        "total_reprobados": total_reprobados,
        "pct_aprobados": pct_aprobados,
    }
    return summary, totals


def build_notas_summary_view(df):
    view = df.copy()
    for col in ["total_alumnos", "aprobados", "reprobados"]:
        view[col] = view[col].apply(lambda value: f"{int(value):,}".replace(",", "."))
    return view
