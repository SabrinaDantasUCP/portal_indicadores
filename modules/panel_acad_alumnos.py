import io

import pandas as pd
import streamlit as st

from services.data.alumnos import load_current_alumnos
from utils import db_pia


COL_ID_ALUMNO = "usuarios_id"
COL_NOMBRE = "nome_sobrenome"
COL_PERIODO = "ano_periodo_letivo"
COL_SUBPERIODO = "periodo_anual_periodo_letivo"
COL_SEMESTRE = "semestre_alumno"


def _format_int(value):
    return f"{int(value):,}".replace(",", ".")


def _prepare_alumnos(df):
    required_cols = [COL_ID_ALUMNO, COL_NOMBRE, COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared = df[required_cols].copy()
    prepared[COL_PERIODO] = pd.to_numeric(prepared[COL_PERIODO], errors="coerce")
    prepared[COL_SUBPERIODO] = pd.to_numeric(prepared[COL_SUBPERIODO], errors="coerce")
    prepared[COL_SEMESTRE] = pd.to_numeric(prepared[COL_SEMESTRE], errors="coerce")
    prepared = prepared.dropna(subset=[COL_ID_ALUMNO, COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE])
    prepared[COL_PERIODO] = prepared[COL_PERIODO].astype(int)
    prepared[COL_SUBPERIODO] = prepared[COL_SUBPERIODO].astype(int)
    prepared[COL_SEMESTRE] = prepared[COL_SEMESTRE].astype(int)
    prepared = prepared[prepared[COL_SEMESTRE].between(1, 12)].copy()
    prepared["Periodo"] = prepared[COL_PERIODO].astype(str) + "." + prepared[COL_SUBPERIODO].astype(str)
    return prepared, []


def _build_period_summary(df):
    unique_period = df[[COL_ID_ALUMNO, COL_PERIODO, COL_SUBPERIODO, "Periodo"]].drop_duplicates()
    summary = (
        unique_period.groupby([COL_PERIODO, COL_SUBPERIODO, "Periodo"], as_index=False)[COL_ID_ALUMNO]
        .nunique()
        .rename(columns={COL_ID_ALUMNO: "Alumnos"})
        .sort_values([COL_PERIODO, COL_SUBPERIODO])
    )
    return summary[["Periodo", "Alumnos"]]


def _build_semester_summary(df):
    unique_semester = df[
        [COL_ID_ALUMNO, COL_PERIODO, COL_SUBPERIODO, "Periodo", COL_SEMESTRE]
    ].drop_duplicates()
    summary = (
        unique_semester.pivot_table(
            index=[COL_PERIODO, COL_SUBPERIODO, "Periodo"],
            columns=COL_SEMESTRE,
            values=COL_ID_ALUMNO,
            aggfunc="nunique",
            fill_value=0,
        )
        .reset_index()
        .sort_values([COL_PERIODO, COL_SUBPERIODO])
    )
    for semester in range(1, 13):
        if semester not in summary.columns:
            summary[semester] = 0
    summary = summary.rename(columns={semester: f"{semester}º" for semester in range(1, 13)})
    semester_cols = [f"{semester}º" for semester in range(1, 13)]
    summary["Total"] = summary[semester_cols].sum(axis=1)
    return summary[["Periodo", *semester_cols, "Total"]]


def _build_alumnos_list(df):
    latest = (
        df.sort_values([COL_ID_ALUMNO, COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE])
        .drop_duplicates(subset=[COL_ID_ALUMNO], keep="last")
        .rename(
            columns={
                COL_ID_ALUMNO: "ID Alumno",
                COL_NOMBRE: "Nombre y Apellido",
                COL_SEMESTRE: "Semestre",
            }
        )
    )
    return latest[["ID Alumno", "Nombre y Apellido", "Periodo", "Semestre"]].sort_values(
        ["Nombre y Apellido", "ID Alumno"]
    )


@st.cache_data(show_spinner="Generando Excel...")
def _generate_excel_bytes(period_summary, semester_summary, alumnos_list):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        period_summary.to_excel(writer, index=False, sheet_name="Por Periodo")
        semester_summary.to_excel(writer, index=False, sheet_name="Por Semestre")
        alumnos_list.to_excel(writer, index=False, sheet_name="Listado")
    return buffer.getvalue()


def render():
    st.subheader("Alumnos")

    df = load_current_alumnos()
    if df.empty:
        st.error("Archivo de alumnos no encontrado o vacío.")
        return

    df, missing_cols = _prepare_alumnos(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return

    total_alumnos = df[COL_ID_ALUMNO].nunique()
    st.markdown(
        f"""
        <div style="font-size:34px; font-weight:700; color:#003366; margin: 6px 0 18px 0;">
            {_format_int(total_alumnos)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    period_summary = _build_period_summary(df)
    semester_summary = _build_semester_summary(df)
    alumnos_list = _build_alumnos_list(df)

    tab1, tab2, tab3 = st.tabs(["Por Periodo", "Por Semestre", "Listado"])

    with tab1:
        period_display = period_summary.copy()
        period_display["Alumnos"] = period_display["Alumnos"].apply(_format_int)
        left, _, _ = st.columns([1.2, 1, 1])
        with left:
            st.dataframe(
                period_display,
                width=360,
                height=min(420, 38 * (len(period_display) + 1)),
                hide_index=True,
            )

    with tab2:
        st.dataframe(
            semester_summary.style.format({col: "{:.0f}" for col in semester_summary.columns if col != "Periodo"}),
            width="stretch",
            hide_index=True,
        )

    with tab3:
        st.dataframe(
            alumnos_list.style.format({"Semestre": "{:.0f}"}),
            width="stretch",
            hide_index=True,
        )

    st.divider()
    excel_bytes = _generate_excel_bytes(period_summary, semester_summary, alumnos_list)
    st.download_button(
        "Descargar Datos (Excel)",
        data=excel_bytes,
        file_name="Alumnos_Analizados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
        width="stretch",
        on_click=db_pia.log_export_callback,
        args=("Alumnos", "Excel"),
    )
