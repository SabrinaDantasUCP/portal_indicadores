import pandas as pd


COL_ANO = "ano_periodo_letivo"
COL_PERIODO_SEM = "periodo_anual_periodo_letivo"
COL_ID_ALUMNO = "usuarios_id"
COL_NOMBRE = "nome_sobrenome"
COL_CATRACA = "numero_catraca"
COL_SEMESTRE = "semestre_alumno"
COL_COHORTE = "cohorte"


def prepare_promotion_source(df):
    required_cols = [COL_ANO, COL_PERIODO_SEM, COL_ID_ALUMNO, COL_SEMESTRE, COL_COHORTE]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared = df.copy()
    prepared[COL_SEMESTRE] = pd.to_numeric(prepared[COL_SEMESTRE], errors="coerce")
    prepared[COL_ANO] = pd.to_numeric(prepared[COL_ANO], errors="coerce")
    prepared[COL_PERIODO_SEM] = pd.to_numeric(prepared[COL_PERIODO_SEM], errors="coerce")

    prepared = prepared.dropna(
        subset=[COL_SEMESTRE, COL_ID_ALUMNO, COL_ANO, COL_PERIODO_SEM, COL_COHORTE]
    )
    prepared["periodo_sort"] = prepared[COL_ANO] * 10 + prepared[COL_PERIODO_SEM]
    return prepared, []


def calculate_all_promotions(df):
    periodos_unicos = sorted(df["periodo_sort"].unique())
    periodo_to_idx = {periodo: idx for idx, periodo in enumerate(periodos_unicos)}
    records = []
    details = {}

    for cohorte in sorted(df[COL_COHORTE].unique()):
        df_cohorte = df[df[COL_COHORTE] == cohorte]
        for semestre in range(1, 12):
            inscritos = df_cohorte[df_cohorte[COL_SEMESTRE] == semestre]
            if inscritos.empty:
                continue

            enrolled_ids = inscritos[COL_ID_ALUMNO].unique()
            promoted_ids = []

            for student_id in enrolled_ids:
                current_period = inscritos[
                    inscritos[COL_ID_ALUMNO] == student_id
                ]["periodo_sort"].max()
                current_idx = periodo_to_idx.get(current_period)

                if current_idx is None or current_idx + 1 >= len(periodos_unicos):
                    continue

                next_period = periodos_unicos[current_idx + 1]
                promoted = df_cohorte[
                    (df_cohorte[COL_ID_ALUMNO] == student_id)
                    & (df_cohorte[COL_SEMESTRE] == semestre + 1)
                    & (df_cohorte["periodo_sort"] == next_period)
                ]
                if not promoted.empty:
                    promoted_ids.append(student_id)

            transition = f"Semestre {semestre} al {semestre + 1}"
            enrolled_count = len(enrolled_ids)
            promoted_count = len(promoted_ids)

            records.append({
                "Cohorte": cohorte,
                "Transición": transition,
                "EIns": enrolled_count,
                "EPr": promoted_count,
                "TPr (%)": (promoted_count / enrolled_count) * 100 if enrolled_count else 0,
                "Año": int(inscritos[COL_ANO].max()),
            })
            details[(cohorte, transition)] = promoted_ids

    return pd.DataFrame(records), details
