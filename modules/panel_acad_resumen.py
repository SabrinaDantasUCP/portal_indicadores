import streamlit as st
import pandas as pd
import io
from utils import db_pia
from services.data.alumnos import load_current_alumnos
from services.calculations.panel_academico import (
    COL_RES_CALIFICACION,
    COL_RES_DISCIPLINA,
    COL_RES_DOCENTE,
    COL_RES_PERIODO,
    COL_RES_SECCION,
    COL_RES_SEMESTRE_DISCIPLINA,
    COL_RES_SUBPERIODO,
    build_panel_alumnos_detail,
    build_panel_resumen_view,
    calculate_panel_resumen,
    prepare_panel_resumen_source,
)


def render():
    # Increase st.dataframe styler limit
    pd.set_option("styler.render.max_elements", 2000000) 

    st.subheader("Panel de Desempeño Académico")
    
    df = load_current_alumnos()
    if df.empty:
        st.error("Archivo de datos no encontrado.")
        return

    df, missing_cols = prepare_panel_resumen_source(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return

    # ---------------------------------------------------------------------
    # Filtros Globales (Top)
    # ---------------------------------------------------------------------
    
    # 1. Mandatory Filters: Periodo & Subperiodo
    c1, c2 = st.columns(2)
    
    periodos = sorted(df[COL_RES_PERIODO].dropna().unique().astype(str).tolist())
    periodo_sel = c1.multiselect("Periodo (Año) *", periodos) 
    
    subperiodos = sorted(df[COL_RES_SUBPERIODO].dropna().unique().astype(str).tolist())
    subperiodo_sel = c2.multiselect("Subperiodo (Semestre) *", subperiodos)
    
    # Validation
    if not periodo_sel or not subperiodo_sel:
        st.info("Seleccione **Periodo (Año)** y **Subperiodo (Semestre)** para continuar.")
        return

    # Apply Filters 1 (Mandatory)
    df_filtered = df.copy()
    df_filtered = df_filtered[df_filtered[COL_RES_PERIODO].astype(str).isin(periodo_sel)]
    df_filtered = df_filtered[df_filtered[COL_RES_SUBPERIODO].astype(str).isin(subperiodo_sel)]
    
    if df_filtered.empty:
        st.warning("No hay datos para el Periodo/Subperiodo seleccionados.")
        return

    # 2. Structural Filters (Global)
    # Order: Semestre Asignatura, Asignatura, Docente, Sección
    
    c3, c4, c5, c6 = st.columns(4)

    # 1. Semestre Asignatura
    semestres_disc = sorted(df_filtered[COL_RES_SEMESTRE_DISCIPLINA].dropna().unique().astype(int).tolist())
    semestre_disc_sel = c3.multiselect("Semestre de la Asignatura", semestres_disc, format_func=lambda x: f"{x}º")
    if semestre_disc_sel:
        df_filtered = df_filtered[df_filtered[COL_RES_SEMESTRE_DISCIPLINA].isin(semestre_disc_sel)]
        
    # 2. Asignatura
    disciplinas = sorted(df_filtered[COL_RES_DISCIPLINA].dropna().unique().tolist())
    disciplina_sel = c4.multiselect("Asignatura", disciplinas)
    if disciplina_sel:
        df_filtered = df_filtered[df_filtered[COL_RES_DISCIPLINA].isin(disciplina_sel)]

    # 3. Docente
    docentes = sorted(df_filtered[COL_RES_DOCENTE].dropna().unique().tolist())
    docente_sel = c5.multiselect("Docente", docentes)
    if docente_sel:
        df_filtered = df_filtered[df_filtered[COL_RES_DOCENTE].isin(docente_sel)]

    # 4. Sección
    secciones = sorted(df_filtered[COL_RES_SECCION].dropna().unique().tolist())
    seccion_sel = c6.multiselect("Sección", secciones)
    if seccion_sel:
        df_filtered = df_filtered[df_filtered[COL_RES_SECCION].isin(seccion_sel)]

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
        
        df_final, missing_cols = calculate_panel_resumen(df_filtered)
        if missing_cols:
            st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
            return

        df_view = build_panel_resumen_view(df_final)
        
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
        calificaciones = sorted(df_filtered[COL_RES_CALIFICACION].dropna().unique().astype(int).tolist())
        calificacion_sel = st.multiselect("Filtrar por Calificación", calificaciones)
        
        # Apply Calificación filter
        df_detail_view = df_filtered.copy()
        if calificacion_sel:
            df_detail_view = df_detail_view[df_detail_view[COL_RES_CALIFICACION].isin(calificacion_sel)]
        
        if df_detail_view.empty:
             st.warning("No hay alumnos con la calificación seleccionada.")
        else:
            df_detalle, missing_cols = build_panel_alumnos_detail(df_detail_view)
            if missing_cols:
                st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
                return
            
            st.dataframe(
                df_detalle,
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

