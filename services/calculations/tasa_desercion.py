import pandas as pd


COL_COHORTE = "cohorte"
COL_ID_ALUMNO = "usuarios_id"
COL_SEMESTRE_ALUMNO = "semestre_alumno"
COL_PERIODO_EGRESSO = "periodo_egresso_format"
COL_ANO_FINAL_COHORTE = "ano_final_coorte"


def prepare_semester_enrollments(df):
    required_cols = [COL_COHORTE, COL_ID_ALUMNO, COL_SEMESTRE_ALUMNO]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    df_clean = df.copy()
    df_clean[COL_SEMESTRE_ALUMNO] = pd.to_numeric(
        df_clean[COL_SEMESTRE_ALUMNO],
        errors="coerce",
    )
    df_clean = df_clean.dropna(subset=required_cols)

    enrollments = (
        df_clean
        .groupby([COL_COHORTE, COL_SEMESTRE_ALUMNO, COL_ID_ALUMNO])
        .first()
        .reset_index()
    )
    return enrollments, []


def calculate_semester_dropout(enrollments, cohorte):
    ins_coh = enrollments[enrollments[COL_COHORTE] == cohorte]
    if ins_coh.empty:
        return pd.DataFrame()

    max_sem = int(ins_coh[COL_SEMESTRE_ALUMNO].max())
    limite_sem = min(max_sem, 12)
    rows = []

    for semestre in range(1, limite_sem):
        current_ids = set(
            ins_coh[ins_coh[COL_SEMESTRE_ALUMNO] == semestre][COL_ID_ALUMNO]
        )
        next_ids = set(
            ins_coh[ins_coh[COL_SEMESTRE_ALUMNO] == semestre + 1][COL_ID_ALUMNO]
        )
        current_count = len(current_ids)
        if current_count == 0:
            continue

        dropout_count = len(current_ids - next_ids)
        rows.append({
            "Semestre": f"{semestre}º -> {semestre + 1}º",
            "EIS": current_count,
            "EACS": dropout_count,
            "TDSC (%)": (dropout_count / current_count) * 100,
        })

    return pd.DataFrame(rows)


def calculate_generational_dropout(df):
    required_cols = [
        COL_COHORTE,
        COL_ID_ALUMNO,
        COL_SEMESTRE_ALUMNO,
        COL_PERIODO_EGRESSO,
        COL_ANO_FINAL_COHORTE,
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), pd.DataFrame(), missing_cols

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

    egressos_df = (
        prepared.dropna(subset=[COL_PERIODO_EGRESSO])
        .groupby([COL_COHORTE, COL_ID_ALUMNO])
        .first()
        .reset_index()
    )

    ece_df = pd.merge(
        eiic_df[[COL_COHORTE, COL_ID_ALUMNO, COL_ANO_FINAL_COHORTE]],
        egressos_df[[COL_ID_ALUMNO, COL_PERIODO_EGRESSO]],
        on=COL_ID_ALUMNO,
        how="inner",
    )
    ece_df[COL_PERIODO_EGRESSO] = pd.to_numeric(
        ece_df[COL_PERIODO_EGRESSO],
        errors="coerce",
    )
    ece_df[COL_ANO_FINAL_COHORTE] = pd.to_numeric(
        ece_df[COL_ANO_FINAL_COHORTE],
        errors="coerce",
    )
    ece_df = ece_df[ece_df[COL_PERIODO_EGRESSO] <= ece_df[COL_ANO_FINAL_COHORTE]]

    complete_cohortes = prepared.groupby(COL_COHORTE)[COL_SEMESTRE_ALUMNO].max()
    complete_cohortes = complete_cohortes[complete_cohortes >= 12].index.tolist()

    resumen_eiic = (
        eiic_df.groupby(COL_COHORTE)[COL_ID_ALUMNO]
        .count()
        .reset_index(name="EIIC")
    )
    resumen_ece = (
        ece_df.groupby(COL_COHORTE)[COL_ID_ALUMNO]
        .count()
        .reset_index(name="ECE")
    )

    resumen_full = pd.merge(resumen_eiic, resumen_ece, on=COL_COHORTE, how="left").fillna(0)
    resumen_full["EIIC"] = resumen_full["EIIC"].astype(int)
    resumen_full["ECE"] = resumen_full["ECE"].astype(int)
    resumen_full["ECA"] = (resumen_full["EIIC"] - resumen_full["ECE"]).astype(int)
    resumen_full["TDG (%)"] = (resumen_full["ECA"] / resumen_full["EIIC"]) * 100

    resumen_complete = (
        resumen_full[resumen_full[COL_COHORTE].isin(complete_cohortes)]
        .sort_values(COL_COHORTE)
    )
    return resumen_full, resumen_complete, []
