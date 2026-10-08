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
    """Para cada cohorte y semestre S (1..11): EIns = alumnos inscriptos en S;
    EPr = los que, en el periodo inmediatamente siguiente a su último periodo
    en S, aparecen inscriptos en S+1 dentro de la misma cohorte.

    Versión vectorizada (mismo resultado que el bucle alumno por alumno
    anterior, que tardaba minutos con la base completa)."""
    periodos_unicos = sorted(df["periodo_sort"].unique())
    siguiente_periodo = dict(zip(periodos_unicos[:-1], periodos_unicos[1:]))

    pares = df[[COL_COHORTE, COL_ID_ALUMNO, COL_SEMESTRE, "periodo_sort"]].drop_duplicates()
    inscritos = pares[pares[COL_SEMESTRE].between(1, 11)]

    # Último periodo de cada alumno en el semestre S y el periodo que le sigue.
    actual = (
        inscritos.groupby([COL_COHORTE, COL_SEMESTRE, COL_ID_ALUMNO], sort=False)["periodo_sort"]
        .max()
        .reset_index()
    )
    actual["periodo_siguiente"] = actual["periodo_sort"].map(siguiente_periodo)
    actual["semestre_siguiente"] = actual[COL_SEMESTRE] + 1

    destino = pares.rename(columns={COL_SEMESTRE: "semestre_siguiente", "periodo_sort": "periodo_siguiente"})
    destino = destino.assign(promovido=True)
    actual = actual.merge(
        destino, on=[COL_COHORTE, COL_ID_ALUMNO, "semestre_siguiente", "periodo_siguiente"], how="left"
    )
    actual["promovido"] = actual["promovido"].eq(True)

    ano_max = df[df[COL_SEMESTRE].between(1, 11)].groupby([COL_COHORTE, COL_SEMESTRE])[COL_ANO].max()

    records = []
    details = {}
    for (cohorte, semestre), grupo in actual.groupby([COL_COHORTE, COL_SEMESTRE], sort=True):
        semestre = int(semestre)
        transition = f"Semestre {semestre} al {semestre + 1}"
        enrolled_count = grupo[COL_ID_ALUMNO].nunique()
        promoted_ids = grupo.loc[grupo["promovido"], COL_ID_ALUMNO].unique().tolist()
        promoted_count = len(promoted_ids)
        records.append({
            "Cohorte": cohorte,
            "Transición": transition,
            "EIns": enrolled_count,
            "EPr": promoted_count,
            "TPr (%)": (promoted_count / enrolled_count) * 100 if enrolled_count else 0,
            "Año": int(ano_max.loc[(cohorte, semestre)]),
        })
        details[(cohorte, transition)] = promoted_ids

    return pd.DataFrame(records), details
