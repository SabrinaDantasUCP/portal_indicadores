import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from utils import db_pia
from utils.system_logging import log_exception
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from services.data.asistencia import load_current_asistencia
from services.calculations.panel_academico import (
    COL_ASIS_DISCIPLINA,
    COL_ASIS_DOCENTE,
    COL_ASIS_MES,
    COL_ASIS_MES_NUM,
    COL_ASIS_PERIODO,
    COL_ASIS_SECCION,
    COL_ASIS_SEMESTRE_DISCIPLINA,
    COL_ASIS_SUBPERIODO,
    COL_ASIS_TIPO_CLASE,
    build_asistencia_by_date,
    build_asistencia_detail,
    calculate_asistencia_metrics,
    calculate_asistencia_monthly_summary,
    prepare_asistencia_source,
)

# -------------------------------------------------------------------------
# 📄 PDF FUNCTIONS
# -------------------------------------------------------------------------
def agregar_encabezado_y_pie(canvas, doc):
    canvas.saveState()
    width, height = landscape(A4)

    # --- Logo ---
    logo_path = None
    possible_paths = ["assets/logo-ucp-icon.png", "assets/logo-ucp.png", "logo-ucp-icon.png"]
    for candidate in possible_paths:
        if os.path.exists(candidate):
            logo_path = candidate
            break
    
    if logo_path:
        try:
            canvas.drawImage(logo_path, x=2 * cm, y=height - 2.5 * cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
        except Exception as exc:
            log_exception("Error silencioso tratado en panel_acad_asistencias.py", exc)
    # --- Cabeçalho ---
    canvas.setFont("Helvetica-Bold", 14)
    canvas.setFillColor(colors.HexColor("#004080"))
    canvas.drawString(5 * cm, height - 1.5 * cm, "Universidad Central del Paraguay")
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.black)
    canvas.drawString(5 * cm, height - 2.1 * cm, "Facultad de Ciencias de la Salud — Carrera de Medicina")
    
    canvas.setStrokeColor(colors.HexColor("#004080"))
    canvas.setLineWidth(1)
    canvas.line(2 * cm, height - 3.0 * cm, width - 2 * cm, height - 3.0 * cm)

    # --- Rodapé ---
    canvas.setFont("Helvetica-Oblique", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(width - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()

@st.cache_data(show_spinner="Cargando datos para exportación...")
def gerar_pdf_asistencia(df_dados, titulo, col_widths=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1 * cm, rightMargin=1 * cm, topMargin=4 * cm, bottomMargin=2 * cm
    )

    story = []
    styles = getSampleStyleSheet()
    
    # Create center style
    style_center = ParagraphStyle(
        name='NormalCenter',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=8,
        leading=9
    )

    story.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
    story.append(Spacer(1, 10))

    # Convert headers and data to list of lists
    headers = df_dados.columns.tolist()
    
    # Prepare data with Paragraph for text wrapping
    data = [headers]
    for _, row in df_dados.iterrows():
        row_list = []
        for item in row:
            if isinstance(item, str) and len(item) > 15: # Arbitrary threshold for wrapping
                    row_list.append(Paragraph(item, style_center))
            else:
                    # For non-wrapped text, the TableStyle aligns it, but if it is short text we can still use Paragraph or str()
                    # Using str() is fine as TableStyle ALIGN=CENTER handles it strings, 
                    # BUT consistency is better if we use Paragraph for all? No, str is faster.
                    # TableStyle ALIGN works for str.
                    row_list.append(str(item))
        data.append(row_list)
    
    # Determine column widths
    final_col_widths = None
    if col_widths:
        # Check if length matches
            if len(col_widths) == len(headers):
                final_col_widths = col_widths
    
    if not final_col_widths:
        width, height = landscape(A4)
        avail_width = width - 2*cm
        col_width = avail_width / len(headers)
        final_col_widths = [col_width] * len(headers)

    tabla = Table(data, repeatRows=1, colWidths=final_col_widths)
    
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004080')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')]),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    story.append(tabla)
    story.append(Spacer(1, 14))
    
    try:
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
    except Exception as e:
        return None 

    return buffer.getvalue()

@st.cache_data(show_spinner="Generando Excel...")
def generate_excel_bytes(df, sheet_name='Sheet1'):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()




def render():
    # Increase st.dataframe styler limit
    pd.set_option("styler.render.max_elements", 2000000) 

    st.subheader("Panel de Asistencia")


    df = load_current_asistencia()
    if df.empty:
        st.warning("El archivo de datos está vacío.")
        return

    df, missing_cols = prepare_asistencia_source(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return

    # ---------------------------------------------------------------------
    # Filtros
    # ---------------------------------------------------------------------    
    # Contenedor para filtros
    with st.container():
        c1, c2 = st.columns(2)
        c3, c4, c5 = st.columns(3)
        c6, c7 = st.columns(2)

        # 1. Filtro: Año (Obligatorio)
        anhos_disponibles = sorted(df[COL_ASIS_PERIODO].unique(), reverse=True)
        anho_sel = c1.multiselect("Periodo (Año) *", anhos_disponibles)

        # Filtrado progresivo para Periodo
        df_temp = df.copy()
        if anho_sel:
            df_temp = df_temp[df_temp[COL_ASIS_PERIODO].isin(anho_sel)]

        # 2. Filtro: Periodo (Obligatorio)
        periodos_disponibles = sorted(df_temp[COL_ASIS_SUBPERIODO].unique())
        periodo_sel = c2.multiselect("Subperiodo (Semestre) *", periodos_disponibles)

        # CHECK DE OBLIGATORIEDAD
        if not anho_sel or not periodo_sel:
            st.info("Seleccione **Periodo (Año)** y **Subperiodo (Semestre)** para continuar.")
            return

        # Filtrado progresivo para Semestre
        if periodo_sel:
            df_temp = df_temp[df_temp[COL_ASIS_SUBPERIODO].isin(periodo_sel)]

        # 3. Filtro: Semestre de la Asignatura
        semestres_disponibles = sorted(df_temp[COL_ASIS_SEMESTRE_DISCIPLINA].unique())
        semestre_sel = c3.multiselect("Semestre de la Asignatura", semestres_disponibles, format_func=lambda x: f"{x}º Semestre")

        # Filtrado progresivo para Asignatura
        if semestre_sel:
            df_temp = df_temp[df_temp[COL_ASIS_SEMESTRE_DISCIPLINA].isin(semestre_sel)]

        # 4. Filtro: Asignatura
        asignaturas_disponibles = sorted(df_temp[COL_ASIS_DISCIPLINA].astype(str).unique())
        asignatura_sel = c4.multiselect("Asignatura", asignaturas_disponibles)

        # Filtrado progresivo para Docente
        if asignatura_sel:
            df_temp = df_temp[df_temp[COL_ASIS_DISCIPLINA].isin(asignatura_sel)]

        # 5. Filtro: Docente
        docentes_disponibles = sorted(df_temp[COL_ASIS_DOCENTE].astype(str).unique())
        docente_sel = c5.multiselect("Docente", docentes_disponibles)

        # Filtrado progresivo para Sección
        if docente_sel:
            df_temp = df_temp[df_temp[COL_ASIS_DOCENTE].isin(docente_sel)]

        # 6. Filtro: Sección
        secciones_disponibles = sorted(df_temp[COL_ASIS_SECCION].astype(str).unique())
        seccion_sel = c6.multiselect("Sección", secciones_disponibles)

        # Filtrado progresivo para Tipo de Clase
        if seccion_sel:
            df_temp = df_temp[df_temp[COL_ASIS_SECCION].isin(seccion_sel)]

        # 7. Filtro: Tipo de Clase
        tipos_clase_disponibles = sorted(df_temp[COL_ASIS_TIPO_CLASE].astype(str).unique())
        tipo_clase_sel = c7.multiselect("Tipo de Clase", tipos_clase_disponibles)

    # ---------------------------------------------------------------------
    # Aplicar Filtros al Dataframe Principal
    # ---------------------------------------------------------------------
    df_filtered = df.copy()

    # Filtros Obligatorios ya chequeados arriba en la UI, pero aplicamos aqui
    df_filtered = df_filtered[df_filtered[COL_ASIS_PERIODO].isin(anho_sel)]
    df_filtered = df_filtered[df_filtered[COL_ASIS_SUBPERIODO].isin(periodo_sel)]

    if semestre_sel:
        df_filtered = df_filtered[df_filtered[COL_ASIS_SEMESTRE_DISCIPLINA].isin(semestre_sel)]

    if asignatura_sel:
        df_filtered = df_filtered[df_filtered[COL_ASIS_DISCIPLINA].isin(asignatura_sel)]

    if docente_sel:
        df_filtered = df_filtered[df_filtered[COL_ASIS_DOCENTE].isin(docente_sel)]

    if seccion_sel:
        df_filtered = df_filtered[df_filtered[COL_ASIS_SECCION].isin(seccion_sel)]

    if tipo_clase_sel:
        df_filtered = df_filtered[df_filtered[COL_ASIS_TIPO_CLASE].isin(tipo_clase_sel)]

    # ---------------------------------------------------------------------
    # Exualización de Resultados
    # ---------------------------------------------------------------------
    if df_filtered.empty:
        st.info("No se encontraron registros con los filtros seleccionados.")
        return

    st.divider()

    # Métricas Resumen Globales (Siempre visibles o dentro de Tabs?) 
    # Generalmente metricas globales quedan bien fuera
    total_registros, promedio_presencia = calculate_asistencia_metrics(df_filtered)

    m1, m2 = st.columns(2)
    m1.metric("Total de Registros de Clase", total_registros)
    m2.metric("Promedio General de Presencia", f"{promedio_presencia:.2f}%")

    # ---------------------------------------------------------------------
    # TABS
    # ---------------------------------------------------------------------
    tab1, tab2, tab3 = st.tabs(["Resumen", "Detalle", "Por Fecha"])

    # --- TAB 1: RESUMEN ---
    with tab1:
        st.markdown("#### Evolución de Asistencia")
        
        # Agrupar por Mes (y mes_num para ordenar)
        df_agrupado, df_melt = calculate_asistencia_monthly_summary(df_filtered)
        
        # Mapeo de colores amigable
        color_map = {
            "% Presentes": '#2ca02c',
            "% Ausentes": '#d62728',
        }

        fig = px.bar(
            df_melt,
            x=COL_ASIS_MES,
            y='Porcentaje',
            color='Tipo',
            barmode='group',
            text_auto=True,
            color_discrete_map=color_map,
            labels={COL_ASIS_MES: "Mes", "Porcentaje": "%", "Tipo": "Indicador"}
        )
        
        fig.update_layout(
            xaxis_title="Mes",
            yaxis_title="Porcentaje",
            legend_title="Indicador",
            uniformtext_minsize=8, 
            uniformtext_mode='hide',
            separators=",." # Decimal=, Miles=. (Estilo Latam/Euro)
        )
        
        fig.update_yaxes(ticksuffix="%", range=[0, 100])
        fig.update_traces(
            texttemplate='%{y:.2f}%',
            textposition='auto'
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # Download Buttons Tab 1 (Resumen)
        st.divider()
        c_pdf, c_xls = st.columns(2, gap="medium")
        
        # Prepare Table for PDF (Resumen)
        df_export_resumen = df_agrupado.copy()
        df_export_resumen = df_export_resumen.drop(columns=[COL_ASIS_MES_NUM], errors='ignore')
        for col in ["% Presentes", "% Ausentes"]:
            if col in df_export_resumen.columns:
                df_export_resumen[col] = df_export_resumen[col].round(2)
        
        # PDF - No Chart
        pdf_bytes = gerar_pdf_asistencia(df_export_resumen, "Evolución de Asistencia", col_widths=None)
        if pdf_bytes:
             with c_pdf:
                 st.download_button("Descargar Reporte (PDF)", data=pdf_bytes, file_name=f"Resumen_Asistencia.pdf", mime="application/pdf", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Asistencia - Resumen", "PDF"))
        else:
             with c_pdf:
                st.warning("No se pudo generar el PDF.")

        # Excel - Cached
        excel_bytes = generate_excel_bytes(df_export_resumen, sheet_name='Resumen')
        
        with c_xls:
            st.download_button("Descargar Datos (Excel)", data=excel_bytes, file_name=f"Resumen_Asistencia.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Asistencia - Resumen", "Excel"))


    # --- TAB 2: DETALLE ---
    with tab2:
        st.markdown("#### Resumen por Asignatura, Sección y Docente")
        
        # Seleccionar columnas relevantes para mostrar
        df_display = build_asistencia_detail(df_filtered)
        
        # Formateo para visualización
        st.dataframe(
            df_display.style.format({
                "Aulas": "{:.0f}",
                "Matriculados": "{:.0f}",
                "% Presentes": "{:.2f}%",
                "% Ausentes": "{:.2f}%",
            }, na_rep="0"),
            width="stretch",
            hide_index=True

        )

        # Download Buttons Tab 2 (Detalle)
        st.divider()
        c_pdf2, c_xls2 = st.columns(2, gap="medium")

        # PDF Definition for Detalle
        cols_pdf_detalle = [
            "Asignatura",
            "Sección",
            "Docente",
            "Aulas",
            "Matriculados",
            "% Presentes",
            "% Ausentes",
            "Tipo de Clase",
        ]
        df_pdf_detalle = df_display[cols_pdf_detalle].copy()
        
        df_pdf_detalle["% Presentes"] = df_pdf_detalle["% Presentes"].apply(lambda x: f"{x:.2f}%")
        df_pdf_detalle["% Ausentes"] = df_pdf_detalle["% Ausentes"].apply(lambda x: f"{x:.2f}%")

        # Custom widths
        # A4 Landscape width ~27.7cm
        col_widths_detalle = [
            4.0 * cm, # Asignatura
            3.0 * cm, # Sección
            4.5 * cm, # Docente
            1.6 * cm, # Aulas
            2.0 * cm, # Matriculados
            2.0 * cm, # % Presentes
            2.0 * cm, # % Ausentes
            2.5 * cm, # Tipo de Clase
        ]

        pdf_bytes_2 = gerar_pdf_asistencia(df_pdf_detalle, "Detalle de Asistencia", col_widths=col_widths_detalle)
        
        if pdf_bytes_2:
            with c_pdf2:
                st.download_button("Descargar Reporte (PDF)", data=pdf_bytes_2, file_name=f"Detalle_Asistencia.pdf", mime="application/pdf", icon=":material/download:", width="stretch", key="btn_pdf_asist_2", on_click=db_pia.log_export_callback, args=("Asistencia - Detalle", "PDF"))
        else:
            with c_pdf2:
                st.warning("No se pudo generar el PDF.")

        # Excel - Cached
        excel_bytes_2 = generate_excel_bytes(df_display, sheet_name='Detalle')

        with c_xls2:
            st.download_button("Descargar Datos (Excel)", data=excel_bytes_2, file_name=f"Detalle_Asistencia.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", key="btn_xls_asist_2", on_click=db_pia.log_export_callback, args=("Asistencia - Detalle", "Excel"))

    # --- TAB 3: POR FECHA ---
    with tab3:
        st.markdown("#### Asistencia por Fecha")

        df_by_date = build_asistencia_by_date(df_filtered)

        st.dataframe(
            df_by_date.style.format({
                "Fecha": lambda t: t.strftime("%d/%m/%Y") if pd.notnull(t) and t != 0 else "",
                "Matriculados": "{:.0f}",
                "% Presentes": "{:.2f}%",
                "% Ausentes": "{:.2f}%",
            }, na_rep="0"),
            width="stretch",
            hide_index=True,
        )

        st.divider()
        c_pdf3, c_xls3 = st.columns(2, gap="medium")

        cols_pdf_fecha = ["Fecha", "Asignatura", "Sección", "Docente", "Tipo de Clase", "Matriculados", "% Presentes", "% Ausentes"]
        df_pdf_fecha = df_by_date[cols_pdf_fecha].copy()
        df_pdf_fecha["Fecha"] = df_pdf_fecha["Fecha"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else "")
        df_pdf_fecha["% Presentes"] = df_pdf_fecha["% Presentes"].apply(lambda x: f"{x:.2f}%")
        df_pdf_fecha["% Ausentes"] = df_pdf_fecha["% Ausentes"].apply(lambda x: f"{x:.2f}%")

        col_widths_fecha = [
            2.0 * cm,
            3.5 * cm,
            2.6 * cm,
            4.0 * cm,
            2.4 * cm,
            2.0 * cm,
            2.0 * cm,
            2.0 * cm,
        ]

        pdf_bytes_3 = gerar_pdf_asistencia(df_pdf_fecha, "Asistencia por Fecha", col_widths=col_widths_fecha)
        if pdf_bytes_3:
            with c_pdf3:
                st.download_button("Descargar Reporte (PDF)", data=pdf_bytes_3, file_name=f"Asistencia_Por_Fecha.pdf", mime="application/pdf", icon=":material/download:", width="stretch", key="btn_pdf_asist_3", on_click=db_pia.log_export_callback, args=("Asistencia - Por Fecha", "PDF"))
        else:
            with c_pdf3:
                st.warning("No se pudo generar el PDF.")

        excel_bytes_3 = generate_excel_bytes(df_by_date, sheet_name='Por Fecha')
        with c_xls3:
            st.download_button("Descargar Datos (Excel)", data=excel_bytes_3, file_name=f"Asistencia_Por_Fecha.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", key="btn_xls_asist_3", on_click=db_pia.log_export_callback, args=("Asistencia - Por Fecha", "Excel"))

