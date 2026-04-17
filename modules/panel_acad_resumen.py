import streamlit as st
import pandas as pd
import plotly.express as px
import io
from utils import db_pia


def render():
    # Increase st.dataframe styler limit
    pd.set_option("styler.render.max_elements", 2000000) 

    st.subheader("Panel de Desempeño Académico")
    
    @st.cache_data
    def load_data():
        try:
            df = pd.read_csv("assets/data/alumnos.csv", sep=",", low_memory=False)
            df.columns = df.columns.str.strip()
            df = df[df["filial_periodo_letivo"].isin(["CDE", "CDE III"])]
            return df
        except FileNotFoundError:
            st.error("Archivo de datos no encontrado.")
            return pd.DataFrame()

    df = load_data()
    if df.empty:
        return

    # Columns
    COL_PERIODO = "ano_periodo_letivo"
    COL_SUBPERIODO = "periodo_anual_periodo_letivo"
    COL_SEMESTRE_ALUMNO = "semestre_alumno"
    COL_SEMESTRE_DISCIPLINA = "semestre_disciplina"
    COL_DISCIPLINA = "disciplina"
    COL_SECCION = "turma"
    COL_DOCENTE = "docente"
    COL_CALIFICACION = "calificacion_final_1a5"
    COL_ID_ALUMNO = "usuarios_id"
    COL_NOMBRE = "nome_sobrenome"

    # ---------------------------------------------------------------------
    # Filtros Globales (Top)
    # ---------------------------------------------------------------------
    
    # 1. Mandatory Filters: Periodo & Subperiodo
    c1, c2 = st.columns(2)
    
    periodos = sorted(df[COL_PERIODO].dropna().unique().astype(str).tolist())
    periodo_sel = c1.multiselect("Periodo (Año) *", periodos) 
    
    subperiodos = sorted(df[COL_SUBPERIODO].dropna().unique().astype(str).tolist())
    subperiodo_sel = c2.multiselect("Subperiodo (Semestre) *", subperiodos)
    
    # Validation
    if not periodo_sel or not subperiodo_sel:
        st.info("Seleccione **Periodo (Año)** y **Subperiodo (Semestre)** para continuar.")
        return

    # Apply Filters 1 (Mandatory)
    df_filtered = df.copy()
    df_filtered = df_filtered[df_filtered[COL_PERIODO].astype(str).isin(periodo_sel)]
    df_filtered = df_filtered[df_filtered[COL_SUBPERIODO].astype(str).isin(subperiodo_sel)]
    
    if df_filtered.empty:
        st.warning("No hay datos para el Periodo/Subperiodo seleccionados.")
        return

    # 2. Structural Filters (Global)
    # Order: Semestre Asignatura, Asignatura, Docente, Sección
    
    # Ensure numeric for sorting
    df_filtered[COL_SEMESTRE_DISCIPLINA] = pd.to_numeric(df_filtered[COL_SEMESTRE_DISCIPLINA], errors='coerce')
    df_filtered[COL_CALIFICACION] = pd.to_numeric(df_filtered[COL_CALIFICACION], errors='coerce')

    c3, c4, c5, c6 = st.columns(4)

    # 1. Semestre Asignatura
    semestres_disc = sorted(df_filtered[COL_SEMESTRE_DISCIPLINA].dropna().unique().astype(int).tolist())
    semestre_disc_sel = c3.multiselect("Semestre de la Asignatura", semestres_disc, format_func=lambda x: f"{x}º")
    if semestre_disc_sel:
        df_filtered = df_filtered[df_filtered[COL_SEMESTRE_DISCIPLINA].isin(semestre_disc_sel)]
        
    # 2. Asignatura
    disciplinas = sorted(df_filtered[COL_DISCIPLINA].dropna().unique().tolist())
    disciplina_sel = c4.multiselect("Asignatura", disciplinas)
    if disciplina_sel:
        df_filtered = df_filtered[df_filtered[COL_DISCIPLINA].isin(disciplina_sel)]

    # 3. Docente
    docentes = sorted(df_filtered[COL_DOCENTE].dropna().unique().tolist())
    docente_sel = c5.multiselect("Docente", docentes)
    if docente_sel:
        df_filtered = df_filtered[df_filtered[COL_DOCENTE].isin(docente_sel)]

    # 4. Sección
    secciones = sorted(df_filtered[COL_SECCION].dropna().unique().tolist())
    seccion_sel = c6.multiselect("Sección", secciones)
    if seccion_sel:
        df_filtered = df_filtered[df_filtered[COL_SECCION].isin(seccion_sel)]

    if df_filtered.empty:
        st.warning("No hay datos para los filtros seleccionados.")
        return

    st.divider()

    # ---------------------------------------------------------------------
    # TABS
    # ---------------------------------------------------------------------
    tab1, tab2 = st.tabs(["Resumen Académico", "Listado de Alumnos"])

    # ---------------------------------------------------------------------
    # TAB 1: Resumen por Materia e Sección (Renamed Columns)
    # ---------------------------------------------------------------------
    with tab1:
        st.markdown("### Resumen por Materia e Sección")
        
        GROUP_COLS = [COL_DISCIPLINA, COL_SEMESTRE_DISCIPLINA, COL_SECCION, COL_DOCENTE]
        
        # Grouping (using df_filtered which has global filters but NO Grade filter)
        group_base = df_filtered.groupby(GROUP_COLS)
        df_res = group_base.agg(
            Total_Matriculados=(COL_ID_ALUMNO, "count"),
            Promedio=(COL_CALIFICACION, "mean")
        ).reset_index()

        # Count Grades
        df_grades = df_filtered.pivot_table(
            index=GROUP_COLS,
            columns=COL_CALIFICACION,
            values=COL_ID_ALUMNO,
            aggfunc='count',
            fill_value=0
        ).reset_index()
        
        for i in range(1, 6):
            if i not in df_grades.columns:
                df_grades[i] = 0
                
        # Rename Grade Columns to "Calificación X"
        grade_cols = {i: f"Calificación {i}" for i in range(1, 6)}
        df_grades = df_grades.rename(columns=grade_cols)
        
        # Merge
        df_final = pd.merge(df_res, df_grades, on=GROUP_COLS, how="left")

        # Metrics
        df_final["Aprobados"] = df_final["Calificación 2"] + df_final["Calificación 3"] + df_final["Calificación 4"] + df_final["Calificación 5"]
        df_final["Reprobados"] = df_final["Calificación 1"]
        
        # Metrics Calculation
        df_final["% de Aprobácion"] = df_final.apply(lambda x: (x["Aprobados"]/x["Total_Matriculados"])*100 if x["Total_Matriculados"]>0 else 0, axis=1)
        df_final["% de Reprobación"] = df_final.apply(lambda x: (x["Reprobados"]/x["Total_Matriculados"])*100 if x["Total_Matriculados"]>0 else 0, axis=1)
        
        # Rename Columns for Display
        rename_map = {
            COL_DISCIPLINA: "Asignatura",
            COL_SEMESTRE_DISCIPLINA: "Semestre de la Asignatura",
            COL_SECCION: "Sección",
            COL_DOCENTE: "Docente",
            "Total_Matriculados": "Cantidad de Matriculados",
            "Promedio": "Promédio"
        }
        df_view = df_final.rename(columns=rename_map)

        # Display Order
        cols_order = [
            "Asignatura", "Semestre de la Asignatura", "Sección", "Docente",
            "Cantidad de Matriculados",
            "Calificación 1", "Calificación 2", "Calificación 3", "Calificación 4", "Calificación 5",
            "Promédio", "% de Aprobácion", "% de Reprobación"
        ]
        
        final_cols = [c for c in cols_order if c in df_view.columns]
        df_view = df_view[final_cols].sort_values(["Asignatura", "Sección"])
        
        # Formatting
        format_dict = {
            "Promédio": "{:.2f}",
            "% de Aprobácion": "{:.2f}%",
            "% de Reprobación": "{:.2f}%",
            "Semestre de la Asignatura": "{:.0f}"
        }

        st.dataframe(
            df_view.style.format(format_dict),
            width="stretch",
            hide_index=True
        )

        # Excel Export
        st.divider()
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df_view.to_excel(writer, index=False, sheet_name='Resumen')
        excel_bytes = excel_buffer.getvalue()
        
        st.download_button("Descargar Datos (Excel)", data=excel_bytes, file_name=f"Resumen_Academico.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Resumen Académico", "Excel"))


    # ---------------------------------------------------------------------
    # TAB 2: Listado de Alumnos (With Grade Filter)
    # ---------------------------------------------------------------------
    with tab2:
        st.markdown("### Listado de Alumnos")
        
        # 5. Calificación Filter (Local to this tab)
        calificaciones = sorted(df_filtered[COL_CALIFICACION].dropna().unique().astype(int).tolist())
        calificacion_sel = st.multiselect("Filtrar por Calificación", calificaciones)
        
        # Apply Calificación filter
        df_detail_view = df_filtered.copy()
        if calificacion_sel:
            df_detail_view = df_detail_view[df_detail_view[COL_CALIFICACION].isin(calificacion_sel)]
        
        if df_detail_view.empty:
             st.warning("No hay alumnos con la calificación seleccionada.")
        else:
            # Columns to show
            cols_detalle = [
                COL_ID_ALUMNO, COL_NOMBRE, COL_SEMESTRE_ALUMNO, 
                COL_DISCIPLINA, COL_SECCION, COL_CALIFICACION, 
                COL_SEMESTRE_DISCIPLINA
            ]
            
            # Map friendly names
            cols_map = {
                COL_ID_ALUMNO: "ID Alumno",
                COL_NOMBRE: "Nombre y Apellido",
                COL_SEMESTRE_ALUMNO: "Semestre del Alumno",
                COL_DISCIPLINA: "Asignatura",
                COL_SECCION: "Sección",
                COL_CALIFICACION: "Calificación",
                COL_SEMESTRE_DISCIPLINA: "Semestre de la Asignatura"
            }
            
            df_detalle = df_detail_view[cols_detalle].rename(columns=cols_map).sort_values(["Asignatura", "Sección", "Nombre y Apellido"])
            
            st.dataframe(
                df_view.style.format(format_dict),
                width="stretch",
                hide_index=True
            )

            # Excel Export
            st.divider()
            excel_buffer_2 = io.BytesIO()
            with pd.ExcelWriter(excel_buffer_2, engine='xlsxwriter') as writer:
                df_detalle.to_excel(writer, index=False, sheet_name='Listado')
            excel_bytes_2 = excel_buffer_2.getvalue()

            st.download_button("Descargar Datos (Excel)", data=excel_bytes_2, file_name=f"Listado_Alumnos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", key="btn_xls_tab2", on_click=db_pia.log_export_callback, args=("Resumen Académico - Listado de Alumnos", "Excel"))

