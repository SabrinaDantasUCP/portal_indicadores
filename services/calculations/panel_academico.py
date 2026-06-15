import pandas as pd


COL_RES_PERIODO = "ano_periodo_letivo"
COL_RES_SUBPERIODO = "periodo_anual_periodo_letivo"
COL_RES_SEMESTRE_ALUMNO = "semestre_alumno"
COL_RES_SEMESTRE_DISCIPLINA = "semestre_disciplina"
COL_RES_DISCIPLINA = "disciplina"
COL_RES_SECCION = "turma"
COL_RES_DOCENTE = "docente"
COL_RES_CALIFICACION = "calificacion_final_1a5"
COL_RES_ID_ALUMNO = "usuarios_id"
COL_RES_NOMBRE = "nome_sobrenome"

COL_ASIS_PERIODO = "anho"
COL_ASIS_SUBPERIODO = "periodo_anual"
COL_ASIS_SEMESTRE_DISCIPLINA = "semestre_asignatura"
COL_ASIS_DISCIPLINA = "asignatura"
COL_ASIS_SECCION = "seccion"
COL_ASIS_DOCENTE = "docente"
COL_ASIS_MATRICULADOS = "matriculados"
COL_ASIS_PRESENTES = "presentes"
COL_ASIS_AUSENTES = "ausentes"
COL_ASIS_PORC_PRESENCIA = "porc_presencia"
COL_ASIS_TIPO_CLASE = "tipo_clase"
COL_ASIS_FECHA = "fecha"
COL_ASIS_MES = "mes_nombre"
COL_ASIS_MES_NUM = "mes_num"

MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def prepare_panel_resumen_source(df):
    required_cols = [
        COL_RES_PERIODO,
        COL_RES_SUBPERIODO,
        COL_RES_SEMESTRE_ALUMNO,
        COL_RES_SEMESTRE_DISCIPLINA,
        COL_RES_DISCIPLINA,
        COL_RES_SECCION,
        COL_RES_DOCENTE,
        COL_RES_CALIFICACION,
        COL_RES_ID_ALUMNO,
        COL_RES_NOMBRE,
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared = df.copy()
    prepared[COL_RES_SEMESTRE_DISCIPLINA] = pd.to_numeric(
        prepared[COL_RES_SEMESTRE_DISCIPLINA], errors="coerce"
    )
    prepared[COL_RES_CALIFICACION] = pd.to_numeric(prepared[COL_RES_CALIFICACION], errors="coerce")
    return prepared, []


def calculate_panel_resumen(df):
    group_cols = [COL_RES_DISCIPLINA, COL_RES_SEMESTRE_DISCIPLINA, COL_RES_SECCION, COL_RES_DOCENTE]
    missing_cols = [col for col in group_cols + [COL_RES_ID_ALUMNO, COL_RES_CALIFICACION] if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    df_res = (
        df.groupby(group_cols)
        .agg(
            Total_Matriculados=(COL_RES_ID_ALUMNO, "count"),
            Promedio=(COL_RES_CALIFICACION, "mean"),
        )
        .reset_index()
    )

    df_grades = (
        df.pivot_table(
            index=group_cols,
            columns=COL_RES_CALIFICACION,
            values=COL_RES_ID_ALUMNO,
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
    )

    for grade in range(1, 6):
        if grade not in df_grades.columns:
            df_grades[grade] = 0

    df_grades = df_grades.rename(columns={grade: f"Calificación {grade}" for grade in range(1, 6)})
    df_final = pd.merge(df_res, df_grades, on=group_cols, how="left")

    df_final["Aprobados"] = (
        df_final["Calificación 2"]
        + df_final["Calificación 3"]
        + df_final["Calificación 4"]
        + df_final["Calificación 5"]
    )
    df_final["Reprobados"] = df_final["Calificación 1"]
    df_final["% de Aprobácion"] = df_final.apply(
        lambda row: (row["Aprobados"] / row["Total_Matriculados"]) * 100
        if row["Total_Matriculados"] > 0
        else 0,
        axis=1,
    )
    df_final["% de Reprobación"] = df_final.apply(
        lambda row: (row["Reprobados"] / row["Total_Matriculados"]) * 100
        if row["Total_Matriculados"] > 0
        else 0,
        axis=1,
    )
    return df_final, []


def build_panel_resumen_view(df):
    rename_map = {
        COL_RES_DISCIPLINA: "Asignatura",
        COL_RES_SEMESTRE_DISCIPLINA: "Semestre de la Asignatura",
        COL_RES_SECCION: "Sección",
        COL_RES_DOCENTE: "Docente",
        "Total_Matriculados": "Cantidad de Matriculados",
        "Promedio": "Promédio",
    }
    cols_order = [
        "Asignatura",
        "Semestre de la Asignatura",
        "Sección",
        "Docente",
        "Cantidad de Matriculados",
        "Calificación 1",
        "Calificación 2",
        "Calificación 3",
        "Calificación 4",
        "Calificación 5",
        "Promédio",
        "% de Aprobácion",
        "% de Reprobación",
    ]
    df_view = df.rename(columns=rename_map)
    final_cols = [col for col in cols_order if col in df_view.columns]
    return df_view[final_cols].sort_values(["Asignatura", "Sección"])


def build_panel_alumnos_detail(df):
    cols_detail = [
        COL_RES_ID_ALUMNO,
        COL_RES_NOMBRE,
        COL_RES_SEMESTRE_ALUMNO,
        COL_RES_DISCIPLINA,
        COL_RES_SECCION,
        COL_RES_CALIFICACION,
        COL_RES_SEMESTRE_DISCIPLINA,
    ]
    missing_cols = [col for col in cols_detail if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    cols_map = {
        COL_RES_ID_ALUMNO: "ID Alumno",
        COL_RES_NOMBRE: "Nombre y Apellido",
        COL_RES_SEMESTRE_ALUMNO: "Semestre del Alumno",
        COL_RES_DISCIPLINA: "Asignatura",
        COL_RES_SECCION: "Sección",
        COL_RES_CALIFICACION: "Calificación",
        COL_RES_SEMESTRE_DISCIPLINA: "Semestre de la Asignatura",
    }
    detail = df[cols_detail].rename(columns=cols_map)
    return detail.sort_values(["Asignatura", "Sección", "Nombre y Apellido"]), []


def prepare_asistencia_source(df):
    required_cols = [
        COL_ASIS_PERIODO,
        COL_ASIS_SUBPERIODO,
        COL_ASIS_SEMESTRE_DISCIPLINA,
        COL_ASIS_DISCIPLINA,
        COL_ASIS_SECCION,
        COL_ASIS_DOCENTE,
        COL_ASIS_MATRICULADOS,
        COL_ASIS_PRESENTES,
        COL_ASIS_AUSENTES,
        COL_ASIS_PORC_PRESENCIA,
        COL_ASIS_TIPO_CLASE,
        COL_ASIS_FECHA,
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared = df.copy()
    prepared[COL_ASIS_PERIODO] = pd.to_numeric(prepared[COL_ASIS_PERIODO], errors="coerce").fillna(0).astype(int)
    prepared[COL_ASIS_SUBPERIODO] = (
        pd.to_numeric(prepared[COL_ASIS_SUBPERIODO], errors="coerce").fillna(0).astype(int)
    )
    prepared[COL_ASIS_SEMESTRE_DISCIPLINA] = (
        pd.to_numeric(prepared[COL_ASIS_SEMESTRE_DISCIPLINA], errors="coerce").fillna(0).astype(int)
    )
    tipo_clase_norm = (
        prepared[COL_ASIS_TIPO_CLASE]
        .astype(str)
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
    )
    before_practica_period = (prepared[COL_ASIS_PERIODO] < 2025) | (
        (prepared[COL_ASIS_PERIODO] == 2025) & (prepared[COL_ASIS_SUBPERIODO] < 2)
    )
    prepared = prepared[~(before_practica_period & tipo_clase_norm.eq("practica"))].copy()
    prepared[COL_ASIS_FECHA] = pd.to_datetime(prepared[COL_ASIS_FECHA], dayfirst=True, errors="coerce")
    for col in [COL_ASIS_MATRICULADOS, COL_ASIS_PRESENTES, COL_ASIS_AUSENTES]:
        prepared[col] = pd.to_numeric(prepared[col], errors="coerce").fillna(0)
    prepared[COL_ASIS_MES] = prepared[COL_ASIS_FECHA].dt.month.map(MESES_ES)
    prepared[COL_ASIS_MES_NUM] = prepared[COL_ASIS_FECHA].dt.month
    valid_subperiod_month = (
        ((prepared[COL_ASIS_SUBPERIODO] == 1) & prepared[COL_ASIS_MES_NUM].between(1, 6))
        | ((prepared[COL_ASIS_SUBPERIODO] == 2) & prepared[COL_ASIS_MES_NUM].between(7, 12))
    )
    prepared = prepared[valid_subperiod_month].copy()
    return prepared, []


def calculate_asistencia_metrics(df):
    return len(df), df[COL_ASIS_PORC_PRESENCIA].mean()


def calculate_asistencia_monthly_summary(df):
    group_cols = [
        COL_ASIS_MES,
        COL_ASIS_MES_NUM,
        COL_ASIS_DISCIPLINA,
        COL_ASIS_SECCION,
        COL_ASIS_DOCENTE,
        COL_ASIS_TIPO_CLASE,
    ]
    class_summary = (
        df.groupby(group_cols, dropna=False)
        .agg(
            Aulas=(COL_ASIS_FECHA, "nunique"),
            Matriculados=(COL_ASIS_MATRICULADOS, "max"),
            Presentes=(COL_ASIS_PRESENTES, "sum"),
        )
        .reset_index()
    )
    class_summary["Capacidad"] = class_summary["Aulas"] * class_summary["Matriculados"]

    summary = class_summary.groupby([COL_ASIS_MES, COL_ASIS_MES_NUM], dropna=False).agg(
        Presentes=("Presentes", "sum"),
        Capacidad=("Capacidad", "sum"),
    ).reset_index()
    summary["% Presentes"] = (summary["Presentes"] / summary["Capacidad"] * 100).where(
        summary["Capacidad"] > 0, 0
    ).clip(0, 100)
    summary["% Ausentes"] = 100 - summary["% Presentes"]
    summary = summary.sort_values(COL_ASIS_MES_NUM)
    chart_df = summary.melt(
        id_vars=[COL_ASIS_MES, COL_ASIS_MES_NUM],
        value_vars=["% Presentes", "% Ausentes"],
        var_name="Tipo",
        value_name="Porcentaje",
    )
    return summary, chart_df


def build_asistencia_detail(df):
    group_cols = [COL_ASIS_DISCIPLINA, COL_ASIS_SECCION, COL_ASIS_DOCENTE, COL_ASIS_TIPO_CLASE]
    summary = (
        df.groupby(group_cols, dropna=False)
        .agg(
            Aulas=(COL_ASIS_FECHA, "nunique"),
            Matriculados=(COL_ASIS_MATRICULADOS, "max"),
            Presentes=(COL_ASIS_PRESENTES, "sum"),
            Ausentes=(COL_ASIS_AUSENTES, "sum"),
        )
        .reset_index()
    )

    denominator = summary["Aulas"] * summary["Matriculados"]
    summary["% Presentes"] = (summary["Presentes"] / denominator * 100).where(denominator > 0, 0).clip(0, 100)
    summary["% Ausentes"] = 100 - summary["% Presentes"]

    summary = summary.rename(
        columns={
            COL_ASIS_DISCIPLINA: "Asignatura",
            COL_ASIS_SECCION: "Sección",
            COL_ASIS_DOCENTE: "Docente",
            COL_ASIS_TIPO_CLASE: "Tipo de Clase",
        }
    )
    cols_order = [
        "Asignatura",
        "Sección",
        "Docente",
        "Aulas",
        "Matriculados",
        "% Presentes",
        "% Ausentes",
        "Tipo de Clase",
    ]
    return summary[cols_order].fillna(0).sort_values(["Asignatura", "Sección", "Docente", "Tipo de Clase"])


def build_asistencia_by_date(df):
    detail = df[
        [
        COL_ASIS_FECHA,
        COL_ASIS_DISCIPLINA,
        COL_ASIS_SECCION,
        COL_ASIS_DOCENTE,
        COL_ASIS_TIPO_CLASE,
        COL_ASIS_MATRICULADOS,
        COL_ASIS_PRESENTES,
        COL_ASIS_AUSENTES,
        ]
    ].copy()
    detail["% Presentes"] = (
        detail[COL_ASIS_PRESENTES] / detail[COL_ASIS_MATRICULADOS] * 100
    ).where(detail[COL_ASIS_MATRICULADOS] > 0, 0)
    detail["% Ausentes"] = (
        detail[COL_ASIS_AUSENTES] / detail[COL_ASIS_MATRICULADOS] * 100
    ).where(detail[COL_ASIS_MATRICULADOS] > 0, 0)
    detail = detail.sort_values(by=[COL_ASIS_FECHA, COL_ASIS_DISCIPLINA, COL_ASIS_SECCION])
    rename_map = {
        COL_ASIS_FECHA: "Fecha",
        COL_ASIS_DISCIPLINA: "Asignatura",
        COL_ASIS_SECCION: "Sección",
        COL_ASIS_DOCENTE: "Docente",
        COL_ASIS_TIPO_CLASE: "Tipo de Clase",
        COL_ASIS_MATRICULADOS: "Matriculados",
    }
    detail = detail.rename(columns=rename_map)
    cols_order = [
        "Fecha",
        "Asignatura",
        "Sección",
        "Docente",
        "Tipo de Clase",
        "Matriculados",
        "% Presentes",
        "% Ausentes",
    ]
    return detail[cols_order].fillna(0)
