import streamlit as st
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import landscape
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import io
import os

def render():
    st.subheader("Notas")

    import plotly.express as px

    # --- Cargar datos ---
    @st.cache_data
    def cargar_notas():
        df = pd.read_excel("assets/data/notas.xlsx")
        df.columns = [c.strip().lower() for c in df.columns]
        return df

    df_notas = cargar_notas()

    # --- Verificar columnas necesarias ---
    columnas_necesarias = [
        "periodo", "sub_periodo", "asignatura",
        "profesor", "seccion", "aprobado_reprobado"
    ]
    faltantes = [c for c in columnas_necesarias if c not in df_notas.columns]
    if faltantes:
        st.error(f"⚠️ Faltan columnas en el archivo: {', '.join(faltantes)}")
        st.stop()

    # Detectar columna de alumno
    col_alumno = None
    for posible in ["alumno", "estudiante", "nombre", "nombre_alumno"]:
        if posible in df_notas.columns:
            col_alumno = posible
            break

    if not col_alumno:
        st.warning("⚠️ No se detectó la columna de alumnos. Solo se mostrará la estructura.")

    # --- Filtros en cascada ---
    st.markdown("### Filtros")

    col1, col2, col3 = st.columns(3)
    col4, col5 = st.columns(2)

    periodo_vals = sorted(df_notas["periodo"].dropna().unique().tolist())
    subperiodo_vals = sorted(df_notas["sub_periodo"].dropna().unique().tolist())

    periodo_sel = col1.multiselect("Período", periodo_vals)
    subperiodo_sel = col2.multiselect("Sub-Período", subperiodo_vals)

    df_temp = df_notas.copy()
    if periodo_sel:
        df_temp = df_temp[df_temp["periodo"].isin(periodo_sel)]
    if subperiodo_sel:
        df_temp = df_temp[df_temp["sub_periodo"].isin(subperiodo_sel)]

    asignaturas = sorted(df_temp["asignatura"].dropna().unique().tolist())
    asignatura_sel = col3.multiselect("Asignatura", asignaturas)
    if asignatura_sel:
        df_temp = df_temp[df_temp["asignatura"].isin(asignatura_sel)]

    profesores = sorted(df_temp["profesor"].dropna().unique().tolist())
    profesor_sel = col4.multiselect("Profesor", profesores)
    if profesor_sel:
        df_temp = df_temp[df_temp["profesor"].isin(profesor_sel)]

    secciones = sorted(df_temp["seccion"].dropna().unique().tolist())
    seccion_sel = col5.multiselect("Sección", secciones)
    if seccion_sel:
        df_temp = df_temp[df_temp["seccion"].isin(seccion_sel)]


    # --- Resultados ---
    if df_temp.empty:
        st.warning("No se encontraron registros con los filtros seleccionados.")
    else:
        if col_alumno:
            # 🔹 Eliminar duplicados: cada alumno cuenta solo una vez por asignatura
            df_unico = df_temp.drop_duplicates(subset=[col_alumno, "asignatura"])

            # Agrupar por asignatura
            resumen = (
                df_unico.groupby(["asignatura"])
                .agg(
                    total_alumnos=(col_alumno, "nunique"),
                    aprobados=("aprobado_reprobado", lambda x: (x == "Aprobado").sum()),
                    reprobados=("aprobado_reprobado", lambda x: (x == "Reprobado").sum())
                )
                .reset_index()
            )

            resumen["% Aprobados"] = (
                resumen["aprobados"] / resumen["total_alumnos"] * 100
            ).round(1)

            # Mostrar tabela formatada
            resumen_vista = resumen.copy()
            for c in ["total_alumnos", "aprobados", "reprobados"]:
                resumen_vista[c] = resumen_vista[c].apply(lambda x: f"{int(x):,}".replace(",", "."))
            st.dataframe(resumen_vista, width="stretch", hide_index=True)

            # Totales gerais (considerando aluno único)
            total_alumnos = int(df_unico[col_alumno].nunique())
            total_aprobados = (df_unico["aprobado_reprobado"] == "Aprobado").sum()
            total_reprobados = (df_unico["aprobado_reprobado"] == "Reprobado").sum()
            pct_aprobados = round(total_aprobados / total_alumnos * 100, 1) if total_alumnos else 0

           # colA, colB = st.columns(2)
           # colA.metric("Total de alumnos considerados", f"{total_alumnos:,}".replace(",", "."))
           # colB.metric("% de Aprobación General", f"{pct_aprobados}%")

            # --- Gráficos ---
            st.markdown("### Visualización de Aprobaciones")

            if asignatura_sel:
                # Gráfico de barras: % aprobados por asignatura
                fig = px.bar(
                    resumen,
                    x="asignatura",
                    y="% Aprobados",
                    color="% Aprobados",
                    text="% Aprobados",
                    color_continuous_scale="Blues",
                    title="% de Aprobados por Asignatura",
                )
                fig.update_traces(texttemplate="%{text}%", textposition="outside")
                fig.update_layout(yaxis_title="Porcentaje de Aprobados", xaxis_title="Asignatura")
                st.plotly_chart(fig, use_container_width=True)

            else:
                # Gráfico geral (pizza consolidada)
                fig = px.pie(
                    names=["Aprobados", "Reprobados"],
                    values=[total_aprobados, total_reprobados],
                    color=["Aprobados", "Reprobados"],
                    color_discrete_map={"Aprobados": "#0070C0", "Reprobados": "#FF6666"},
                    # title=f"Distribución General de Resultados ({pct_aprobados}% Aprobados)"
                    title=f"Distribución General de Resultados"
                )
                fig.update_traces(textinfo="label+percent", textfont_size=14)
                st.plotly_chart(fig, use_container_width=True)
