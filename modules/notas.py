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
from services.data.notas import load_current_notas
from services.calculations.notas import (
    COL_ASIGNATURA,
    COL_PERIODO,
    COL_PROFESOR,
    COL_SECCION,
    COL_SUBPERIODO,
    build_notas_summary_view,
    calculate_notas_summary,
    detect_student_column,
    validate_notas_source,
)

def render():
    st.subheader("Notas")

    import plotly.express as px

    df_notas = load_current_notas()
    if df_notas.empty:
        st.error("Archivo de datos no encontrado.")
        return

    # --- Verificar columnas necesarias ---
    faltantes = validate_notas_source(df_notas)
    if faltantes:
        st.error(f"⚠️ Faltan columnas en el archivo: {', '.join(faltantes)}")
        st.stop()

    # Detectar columna de alumno
    col_alumno = detect_student_column(df_notas)

    if not col_alumno:
        st.warning("⚠️ No se detectó la columna de alumnos. Solo se mostrará la estructura.")

    # --- Filtros en cascada ---
    st.markdown("### Filtros")

    col1, col2, col3 = st.columns(3)
    col4, col5 = st.columns(2)

    periodo_vals = sorted(df_notas[COL_PERIODO].dropna().unique().tolist())
    subperiodo_vals = sorted(df_notas[COL_SUBPERIODO].dropna().unique().tolist())

    periodo_sel = col1.multiselect("Período", periodo_vals)
    subperiodo_sel = col2.multiselect("Sub-Período", subperiodo_vals)

    df_temp = df_notas.copy()
    if periodo_sel:
        df_temp = df_temp[df_temp[COL_PERIODO].isin(periodo_sel)]
    if subperiodo_sel:
        df_temp = df_temp[df_temp[COL_SUBPERIODO].isin(subperiodo_sel)]

    asignaturas = sorted(df_temp[COL_ASIGNATURA].dropna().unique().tolist())
    asignatura_sel = col3.multiselect("Asignatura", asignaturas)
    if asignatura_sel:
        df_temp = df_temp[df_temp[COL_ASIGNATURA].isin(asignatura_sel)]

    profesores = sorted(df_temp[COL_PROFESOR].dropna().unique().tolist())
    profesor_sel = col4.multiselect("Profesor", profesores)
    if profesor_sel:
        df_temp = df_temp[df_temp[COL_PROFESOR].isin(profesor_sel)]

    secciones = sorted(df_temp[COL_SECCION].dropna().unique().tolist())
    seccion_sel = col5.multiselect("Sección", secciones)
    if seccion_sel:
        df_temp = df_temp[df_temp[COL_SECCION].isin(seccion_sel)]


    # --- Resultados ---
    if df_temp.empty:
        st.warning("No se encontraron registros con los filtros seleccionados.")
    else:
        if col_alumno:
            resumen, totals = calculate_notas_summary(df_temp, col_alumno)

            # Mostrar tabela formatada
            resumen_vista = build_notas_summary_view(resumen)
            st.dataframe(resumen_vista, width="stretch", hide_index=True)

            # Totales gerais (considerando aluno único)
            total_aprobados = totals["total_aprobados"]
            total_reprobados = totals["total_reprobados"]

           # colA, colB = st.columns(2)
           # colA.metric("Total de alumnos considerados", f"{total_alumnos:,}".replace(",", "."))
           # colB.metric("% de Aprobación General", f"{pct_aprobados}%")

            # --- Gráficos ---
            st.markdown("### Visualización de Aprobaciones")

            if asignatura_sel:
                # Gráfico de barras: % aprobados por asignatura
                fig = px.bar(
                    resumen,
                    x=COL_ASIGNATURA,
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
