import pandas as pd


COL_ANO = "ano"
COL_PERIODO = "periodo_anual_nome"
COL_SEMESTRE = "semestre_nome"
COL_DISCIPLINA = "disciplina_nome"
COL_TURMA = "turma_nome"
COL_QUANTIDADE = "quantidade_alunos"

REQUIRED_COLUMNS = [
    COL_ANO,
    COL_PERIODO,
    COL_SEMESTRE,
    COL_DISCIPLINA,
    COL_TURMA,
    COL_QUANTIDADE,
]


def validate_matriculas_source(df):
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def calculate_matriculas_summary(df):
    missing_cols = validate_matriculas_source(df)
    if missing_cols:
        return pd.DataFrame(), missing_cols

    group_cols = [COL_ANO, COL_PERIODO, COL_SEMESTRE, COL_DISCIPLINA, COL_TURMA]
    summary = (
        df.groupby(group_cols, dropna=False)[COL_QUANTIDADE]
        .sum()
        .reset_index(name="Cantidad de Alumnos")
    )
    return summary, []


def build_matriculas_view(df):
    view = df.copy()
    view["Cantidad de Alumnos"] = view["Cantidad de Alumnos"].apply(
        lambda value: f"{int(value):,}".replace(",", ".")
    )
    return view.rename(
        columns={
            COL_ANO: "Año",
            COL_PERIODO: "Período Anual",
            COL_SEMESTRE: "Semestre",
            COL_DISCIPLINA: "Disciplina",
            COL_TURMA: "Turma",
            "Cantidad de Alumnos": "Cantidad de Alumnos",
        }
    )
