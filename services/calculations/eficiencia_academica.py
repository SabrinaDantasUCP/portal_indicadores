import pandas as pd


COL_COHORTE = "cohorte"
COL_ID_ALUMNO = "usuarios_id"
COL_NOMBRE = "nome_sobrenome"
COL_CATRACA = "numero_catraca"
COL_SEMESTRE_ALUMNO = "semestre_alumno"
COL_PERIODO_EGRESSO = "periodo_egresso_format"
COL_ANO_FINAL_COHORTE = "ano_final_coorte"
COL_TITULADO = "estado_titulacion"
COL_FECHA_TITULADO = "fecha_titulacion"
COL_DETALLE = "detalle"
COL_TIPO_INGRESO = "tipo_ingresso"
COL_PERIODO_INGRESO = "ano_inicial_coorte"


def prepare_efficiency_source(df):
    required_cols = [
        COL_COHORTE,
        COL_ID_ALUMNO,
        COL_SEMESTRE_ALUMNO,
        COL_PERIODO_EGRESSO,
        COL_ANO_FINAL_COHORTE,
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared = df.copy()
    prepared[COL_SEMESTRE_ALUMNO] = pd.to_numeric(
        prepared[COL_SEMESTRE_ALUMNO],
        errors="coerce",
    )
    prepared[COL_PERIODO_EGRESSO] = pd.to_numeric(
        prepared[COL_PERIODO_EGRESSO],
        errors="coerce",
    )
    prepared[COL_ANO_FINAL_COHORTE] = pd.to_numeric(
        prepared[COL_ANO_FINAL_COHORTE],
        errors="coerce",
    )
    return prepared, []


def get_initial_students(df):
    return (
        df[df[COL_SEMESTRE_ALUMNO] == 1]
        .groupby([COL_COHORTE, COL_ID_ALUMNO])
        .first()
        .reset_index()
    )


def get_graduates(df):
    return (
        df.dropna(subset=[COL_PERIODO_EGRESSO])
        .groupby([COL_ID_ALUMNO])
        .first()
        .reset_index()
    )


def get_complete_cohortes(df):
    max_semestre = df.groupby(COL_COHORTE)[COL_SEMESTRE_ALUMNO].max()
    return max_semestre[max_semestre >= 12].index.tolist()


def build_efficiency_context(df):
    prepared, missing_cols = prepare_efficiency_source(df)
    if missing_cols:
        return {}, missing_cols

    context = {
        "df": prepared,
        "eiic_df": get_initial_students(prepared),
        "egresados_full": get_graduates(prepared),
        "cohortes_completas": get_complete_cohortes(prepared),
    }
    return context, []


def get_regular_graduates(eiic_df, egresados_full, cohorte, periodo_final):
    regular = pd.merge(
        eiic_df[eiic_df[COL_COHORTE] == cohorte][[COL_ID_ALUMNO]],
        egresados_full,
        on=COL_ID_ALUMNO,
        how="inner",
    )
    return regular[regular[COL_PERIODO_EGRESSO] <= periodo_final]


def get_non_regular_graduates(eiic_df, egresados_full, cohorte, periodo_final):
    non_regular = pd.merge(
        eiic_df[eiic_df[COL_COHORTE] != cohorte][[COL_ID_ALUMNO]],
        egresados_full,
        on=COL_ID_ALUMNO,
        how="inner",
    )
    return non_regular[non_regular[COL_PERIODO_EGRESSO] == periodo_final]


def calculate_terminal_efficiency(context):
    eiic_df = context["eiic_df"]
    egresados_full = context["egresados_full"]
    complete_cohortes = context["cohortes_completas"]

    ece_rows = []
    summary_rows = []

    for cohorte, group in eiic_df.groupby(COL_COHORTE):
        periodo_final = group[COL_ANO_FINAL_COHORTE].iloc[0]
        if pd.isna(periodo_final):
            continue

        eiic_count = len(group)
        if eiic_count == 0:
            continue

        regular = get_regular_graduates(eiic_df, egresados_full, cohorte, periodo_final)
        regular = regular.copy()
        regular[COL_COHORTE] = cohorte
        ece_rows.append(regular)

        summary_rows.append({
            COL_COHORTE: cohorte,
            "EIIC": eiic_count,
            "ECE": len(regular),
            "ET (%)": (len(regular) / eiic_count) * 100,
        })

    resumen = pd.DataFrame(summary_rows)
    if not resumen.empty:
        resumen = resumen[resumen[COL_COHORTE].isin(complete_cohortes)].sort_values(COL_COHORTE)

    ece_df = pd.concat(ece_rows, ignore_index=True) if ece_rows else pd.DataFrame()
    return resumen, ece_df


def calculate_egress_efficiency(context):
    eiic_df = context["eiic_df"]
    egresados_full = context["egresados_full"]
    complete_cohortes = context["cohortes_completas"]
    ventanas = (
        eiic_df.groupby(COL_COHORTE)[COL_ANO_FINAL_COHORTE]
        .first()
        .reset_index()
    )

    rows = []
    for _, window in ventanas.iterrows():
        cohorte = window[COL_COHORTE]
        periodo_final = window[COL_ANO_FINAL_COHORTE]
        if pd.isna(periodo_final):
            continue

        eiic_count = len(eiic_df[eiic_df[COL_COHORTE] == cohorte])
        if eiic_count == 0:
            continue

        regular = get_regular_graduates(eiic_df, egresados_full, cohorte, periodo_final)
        non_regular = get_non_regular_graduates(eiic_df, egresados_full, cohorte, periodo_final)
        total = len(regular) + len(non_regular)

        rows.append({
            COL_COHORTE: cohorte,
            "periodo_final": periodo_final,
            "EIIC": eiic_count,
            "ECE_reg": len(regular),
            "ECE_nreg": len(non_regular),
            "Total_Egresados": total,
            "EE (%)": (total / eiic_count) * 100,
        })

    resumen = pd.DataFrame(rows)
    if not resumen.empty:
        resumen = resumen[resumen[COL_COHORTE].isin(complete_cohortes)].sort_values(COL_COHORTE)
    return resumen


def calculate_rezago(context):
    df_ee = calculate_egress_efficiency(context)
    if df_ee.empty:
        return pd.DataFrame()

    resumen = df_ee.copy()
    resumen["ET (%)"] = (resumen["ECE_reg"] / resumen["EIIC"]) * 100
    resumen["RE (%)"] = resumen["EE (%)"] - resumen["ET (%)"]
    return resumen[[COL_COHORTE, "periodo_final", "EIIC", "ET (%)", "RE (%)", "EE (%)", "ECE_nreg"]]


def calculate_titulation_efficiency(context):
    eiic_df = context["eiic_df"]
    egresados_full = context["egresados_full"]
    complete_cohortes = context["cohortes_completas"]
    ventanas = (
        eiic_df.groupby(COL_COHORTE)[COL_ANO_FINAL_COHORTE]
        .first()
        .reset_index()
    )

    rows = []
    for _, window in ventanas.iterrows():
        cohorte = window[COL_COHORTE]
        periodo_final = window[COL_ANO_FINAL_COHORTE]
        if pd.isna(periodo_final):
            continue

        regular = get_regular_graduates(eiic_df, egresados_full, cohorte, periodo_final)
        non_regular = get_non_regular_graduates(eiic_df, egresados_full, cohorte, periodo_final)
        graduates_window = pd.concat([regular, non_regular])
        total_graduates = len(graduates_window)
        if total_graduates == 0 or COL_TITULADO not in graduates_window.columns:
            continue

        titulados = graduates_window[
            graduates_window[COL_TITULADO].astype(str).str.strip().str.upper() == "SI"
        ]
        rows.append({
            COL_COHORTE: cohorte,
            "periodo_final": periodo_final,
            "EE (Egresados)": total_graduates,
            "ET (Titulados)": len(titulados),
            "ETE (%)": (len(titulados) / total_graduates) * 100,
        })

    resumen = pd.DataFrame(rows)
    if not resumen.empty:
        resumen = resumen[resumen[COL_COHORTE].isin(complete_cohortes)].sort_values(COL_COHORTE)
    return resumen


def calculate_max_valid_semester(cohorte_str, year_now=2026, period_now=1):
    try:
        inicio = str(cohorte_str).split(" - ")[0]
        year_in = int(inicio.split(".")[0])
        period_in = int(inicio.split(".")[1])
        diff = (year_now - year_in) * 2 + (period_now - period_in)
        return diff + 1
    except Exception:
        return 12


def calculate_retention(df):
    required_cols = [COL_COHORTE, COL_ID_ALUMNO, COL_SEMESTRE_ALUMNO]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared = df.copy()
    prepared[COL_SEMESTRE_ALUMNO] = pd.to_numeric(
        prepared[COL_SEMESTRE_ALUMNO],
        errors="coerce",
    )

    eiic_df = (
        prepared[prepared[COL_SEMESTRE_ALUMNO] == 1]
        .groupby([COL_COHORTE, COL_ID_ALUMNO])
        .first()
        .reset_index()
    )
    total_por_cohorte = eiic_df.groupby(COL_COHORTE)[COL_ID_ALUMNO].count().rename("EIIC")

    ids_eiic = eiic_df[COL_ID_ALUMNO].unique()
    df_cohort = prepared[prepared[COL_ID_ALUMNO].isin(ids_eiic)].copy()
    max_sem_per_student = (
        df_cohort.groupby([COL_COHORTE, COL_ID_ALUMNO])[COL_SEMESTRE_ALUMNO]
        .max()
        .reset_index()
    )
    max_sem_per_student.columns = [COL_COHORTE, COL_ID_ALUMNO, "max_sem_alcanzado"]

    sems_range = pd.DataFrame({COL_SEMESTRE_ALUMNO: range(1, 13)})
    dense_df = (
        max_sem_per_student.assign(key=1)
        .merge(sems_range.assign(key=1), on="key")
        .drop("key", axis=1)
    )
    dense_df = dense_df[dense_df[COL_SEMESTRE_ALUMNO] <= dense_df["max_sem_alcanzado"]]

    retencion_df = (
        dense_df.groupby([COL_COHORTE, COL_SEMESTRE_ALUMNO])[COL_ID_ALUMNO]
        .nunique()
        .reset_index()
        .rename(columns={COL_ID_ALUMNO: "EIS"})
    )
    retencion_df = pd.merge(retencion_df, total_por_cohorte, on=COL_COHORTE)
    retencion_df["max_sem_teorico"] = retencion_df[COL_COHORTE].apply(calculate_max_valid_semester)
    retencion_df = retencion_df[
        retencion_df[COL_SEMESTRE_ALUMNO] <= retencion_df["max_sem_teorico"]
    ]
    retencion_df["TR (%)"] = (retencion_df["EIS"] / retencion_df["EIIC"]) * 100
    return retencion_df, []


def calculate_semesters_between(inicio, fin):
    try:
        y_in, p_in = map(float, str(inicio).split("."))
        y_out, p_out = map(float, str(fin).split("."))
        return int((y_out - y_in) * 2 + (p_out - p_in) + 1)
    except Exception:
        return None


def calculate_average_egress_time(df):
    required_cols = [COL_COHORTE, COL_ID_ALUMNO, COL_PERIODO_INGRESO, COL_PERIODO_EGRESSO]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), pd.DataFrame(), missing_cols

    egresados_df = df.dropna(subset=[COL_PERIODO_EGRESSO, COL_PERIODO_INGRESO]).copy()
    egresados_df = egresados_df.groupby(COL_ID_ALUMNO).first().reset_index()
    egresados_df["Semestres"] = egresados_df.apply(
        lambda row: calculate_semesters_between(
            row[COL_PERIODO_INGRESO],
            row[COL_PERIODO_EGRESSO],
        ),
        axis=1,
    )
    egresados_df = egresados_df.dropna(subset=["Semestres"])

    resumen = (
        egresados_df.groupby(COL_COHORTE)
        .agg({
            "Semestres": ["mean", "count", "min", "max"],
            COL_ID_ALUMNO: "count",
        })
        .reset_index()
    )
    resumen.columns = [
        COL_COHORTE,
        "TME_Semestres",
        "N_Egresados",
        "Min_Sem",
        "Max_Sem",
        "Total_Count",
    ]
    resumen["TME_Anos"] = resumen["TME_Semestres"] / 2
    return egresados_df, resumen, []
