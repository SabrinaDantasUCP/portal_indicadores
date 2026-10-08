import streamlit as st
import pandas as pd
import plotly.express as px
import io
from utils import db_pia
from utils.ui import (
    COLOR_ATENCION,
    COLOR_BUENO,
    COLOR_MALO,
    estilizar_figura,
    formatear_entero,
    formatear_porcentaje,
    render_cabecera_indicador,
    render_tarjetas_kpi,
    render_titulo_seccion,
)
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

    render_cabecera_indicador(
        "Panel de Desempeño Académico",
        "Calificaciones finales por asignatura, sección y docente en el periodo elegido: cuántos alumnos "
        "aprobaron, cuántos reprobaron y el promedio (escala 1 a 5; se aprueba con 2 o más).",
    )
    
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
    
    # 1. Filtro obligatorio: periodo lectivo "AAAA.S". Antes eran dos filtros
    # separados (año y subperiodo) y se podían combinar periodos inexistentes.
    ano_num = pd.to_numeric(df[COL_RES_PERIODO], errors="coerce")
    sub_num = pd.to_numeric(df[COL_RES_SUBPERIODO], errors="coerce")
    validos = ano_num.notna() & sub_num.notna()
    df = df[validos].copy()
    df["_periodo_lectivo"] = ano_num[validos].astype(int).astype(str) + "." + sub_num[validos].astype(int).astype(str)
    # Del más reciente al más antiguo; por defecto, el más reciente.
    periodos = sorted(df["_periodo_lectivo"].unique(), key=lambda p: tuple(int(x) for x in p.split(".")), reverse=True)

    periodo_sel = st.multiselect(
        "Periodo lectivo *", periodos, default=periodos[:1], placeholder="Elija uno o más periodos",
        help="Formato AAAA.S (año y semestre lectivo). Solo se listan periodos con datos.",
    )
    if not periodo_sel:
        st.info("Seleccione al menos un **periodo lectivo** para continuar.", icon=":material/touch_app:")
        return

    df_filtered = df[df["_periodo_lectivo"].isin(periodo_sel)]
    if df_filtered.empty:
        st.warning("No hay datos para el periodo seleccionado.")
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

    calificaciones_validas = pd.to_numeric(df_filtered[COL_RES_CALIFICACION], errors="coerce").dropna()
    aprobacion = (calificaciones_validas >= 2).mean() * 100 if len(calificaciones_validas) else 0
    render_tarjetas_kpi([
        {"etiqueta": "Alumnos", "valor": formatear_entero(df_filtered["usuarios_id"].nunique()),
         "detalle": "Distintos, en los filtros elegidos"},
        {"etiqueta": "Asignaturas", "valor": formatear_entero(df_filtered[COL_RES_DISCIPLINA].nunique())},
        {"etiqueta": "Promedio", "valor": f"{calificaciones_validas.mean():.2f}".replace(".", ",") if len(calificaciones_validas) else "–",
         "detalle": "Calificación final (1 a 5)"},
        {"etiqueta": "Aprobación", "valor": formatear_porcentaje(aprobacion),
         "detalle": "Calificaciones de 2 a 5",
         "color": COLOR_BUENO if aprobacion >= 80 else (COLOR_ATENCION if aprobacion >= 60 else COLOR_MALO)},
    ])

    # ---------------------------------------------------------------------
    # TABS
    # ---------------------------------------------------------------------
    tab1, tab2 = st.tabs(["Resumen Académico", "Listado de Alumnos"])

    # ---------------------------------------------------------------------
    # TAB 1: Resumen por Materia e Sección (Renamed Columns)
    # ---------------------------------------------------------------------
    with tab1:
        render_titulo_seccion(
            "Distribución de calificaciones",
            "Cantidad de calificaciones finales de cada valor. El 1 es reprobado; de 2 a 5, aprobado.",
        )
        distribucion = (
            calificaciones_validas.astype(int).value_counts().reindex(range(1, 6), fill_value=0)
            .rename_axis("Calificación").reset_index(name="Cantidad")
        )
        distribucion["Etiqueta"] = distribucion["Cantidad"].map(formatear_entero)
        fig_dist = px.bar(distribucion, x="Calificación", y="Cantidad", text="Etiqueta")
        fig_dist.update_traces(
            marker_color=[COLOR_MALO] + [COLOR_BUENO] * 4, textposition="outside", cliponaxis=False,
            hovertemplate="Calificación %{x}: %{text}<extra></extra>",
        )
        estilizar_figura(fig_dist, titulo_x="Calificación final", titulo_y="Cantidad", altura=300, leyenda=False)
        fig_dist.update_xaxes(dtick=1)
        st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar": False})

        render_titulo_seccion("Resumen por asignatura y sección")
        
        df_final, missing_cols = calculate_panel_resumen(df_filtered)
        if missing_cols:
            st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
            return

        df_view = build_panel_resumen_view(df_final)
        
        # Formatting
        st.dataframe(
            df_view,
            width="stretch",
            hide_index=True,
            column_config={
                "Semestre de la Asignatura": st.column_config.NumberColumn("Semestre", format="%dº"),
                "Cantidad de Matriculados": st.column_config.NumberColumn("Matriculados"),
                "Promedio": st.column_config.NumberColumn("Promedio", format="%.2f"),
                "% de Aprobación": st.column_config.ProgressColumn(
                    "% de Aprobación", min_value=0, max_value=100, format="%.1f%%"),
                "% de Reprobación": st.column_config.NumberColumn("% de Reprobación", format="%.1f%%"),
            },
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
        render_titulo_seccion("Listado de alumnos", "Una fila por alumno y asignatura, con su calificación final.")
        
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

