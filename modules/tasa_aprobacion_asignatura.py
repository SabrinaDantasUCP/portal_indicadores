import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime
from utils import db_pia
from utils.system_logging import log_exception
from services.data.alumnos import load_current_alumnos
from services.calculations.tasa_aprobacion import (
    COL_COHORTE,
    COL_DISCIPLINA,
    COL_SECCION,
    calculate_section_approval,
    calculate_subject_approval,
    prepare_approval_source,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

def render():
    st.subheader("Tasa de Aprobación por Asignatura")
    
    df = load_current_alumnos(only_regular=True)
    if df.empty:
        st.error("Archivo de datos no encontrado para la versión seleccionada.")
        return

    df, missing_cols = prepare_approval_source(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return

    # Filters
    col1, col2, col3 = st.columns(3)
    
    # 1. Cohorte
    cohortes = sorted(df[COL_COHORTE].dropna().unique().tolist())
    cohorte_sel = col1.selectbox("Cohorte", cohortes, index=None, placeholder="Seleccione Cohorte")
    
    if not cohorte_sel:
        st.info("Seleccione una Cohorte para continuar.")
        return

    # Filter by Cohorte
    df_filtered = df[df[COL_COHORTE] == cohorte_sel]
    
    # 2. Asignatura
    asignaturas = sorted(df_filtered[COL_DISCIPLINA].dropna().unique().tolist())
    asignatura_sel = col2.selectbox("Asignatura", asignaturas, index=None, placeholder="Todas")
    
    if asignatura_sel:
        # Filter by selected subject
        df_filtered = df_filtered[df_filtered[COL_DISCIPLINA] == asignatura_sel]

    # 3. Sección (Turma) - Only available if Asignatura is selected, as per request
    if asignatura_sel:
        secciones = sorted(df_filtered[COL_SECCION].dropna().unique().tolist())
        seccion_sel = col3.multiselect("Sección", secciones, placeholder="Todas")
        
        if seccion_sel:
            df_filtered = df_filtered[df_filtered[COL_SECCION].isin(seccion_sel)]
    else:
        seccion_sel = []
        col3.selectbox("Sección", [], index=None, placeholder="Seleccione una Asignatura", disabled=True)

    if df_filtered.empty:
        st.warning("No hay datos para la selección.")
        st.stop()

    resumen, missing_cols = calculate_subject_approval(df_filtered)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return
    
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
                log_exception("Error silencioso tratado en tasa_aprobacion_asignatura.py", exc)
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

    def gerar_pdf_taa(df_dados, cohorte_atual, titulo_tabela, col_principal_nome):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=4 * cm, bottomMargin=2 * cm
        )

        story = []
        styles = getSampleStyleSheet()

        story.append(Paragraph("<b>Reporte de Tasa de Aprobación por Asignatura</b>", styles["Title"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>Cohorte:</b> {cohorte_atual}", styles["Normal"]))
        story.append(Spacer(1, 15))

        story.append(Paragraph(f"<b>{titulo_tabela}</b>", styles["Heading3"]))
        story.append(Spacer(1, 10))

        # Tabela de Detalhes
        # Colunas esperadas no DF: [ColPrincipal, Inscritos, Aprobados, % Aprobación]
        # ColPrincipal varia (Asignatura ou Sección)
        
        data_rows = [[col_principal_nome, "Inscritos", "Aprobados", "% Aprobación"]]
        
        # Iterar sobre as linhas
        # O DF de entrada já deve estar com as colunas renomeadas corretamente para facilitar
        for _, row in df_dados.iterrows():
            data_rows.append([
                str(row[col_principal_nome]),
                str(int(row['Inscritos'])),
                str(int(row['Aprobados'])),
                f"{row['% Aprobación']:.2f}%"
            ])

        col_widths = [10 * cm, 4 * cm, 4 * cm, 4 * cm]
        
        tabla = Table(data_rows, repeatRows=1, colWidths=col_widths)
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004080')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')])
        ]))
        
        story.append(tabla)
        story.append(Spacer(1, 14))
        
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    st.divider()
    
    # ------------------------------------------------------------
    # 🧠 LÓGICA DE VISUALIZAÇÃO (View Switching)
    # ------------------------------------------------------------
    # Modo Detalhe se: Seção selecionada OU Asignatura selecionada (já que é single select agora)
    # Se asignatura_sel for None, é Overview Mode (Todas as Disciplinas)
    is_detail_mode = (asignatura_sel is not None)

    if is_detail_mode:
        # ------------------------------------------------------------
        # 🔍 MODO DETALHE (Por Seção)
        # ------------------------------------------------------------
        
        resumen_seccion, missing_cols = calculate_section_approval(df_filtered)
        if missing_cols:
            st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
            return
        
        # KPI KPI (Specific to selection)
        avg_approval_detail = resumen_seccion["% Aprobación"].mean()
        
        st.markdown(f"""
        <div style="text-align: center; padding: 10px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 10px;">
            <h4 style="margin: 0; color: #555; font-size: 16px;">Promedio de Aprobación</h4>
            <h2 style="margin: 5px 0 0 0; font-size: 32px; color: #004080;">{avg_approval_detail:.2f}%</h2>
        </div>
        """, unsafe_allow_html=True)

        st.divider()
        st.markdown("### Aprobación por Sección")

        # Gráfico de Seções (Em cima)
        fig_sec = px.bar(
            resumen_seccion,
            x=COL_SECCION,
            y="% Aprobación",
            text_auto='.1f',
            color="% Aprobación",
            color_continuous_scale="Greens"
        )
        st.plotly_chart(fig_sec, use_container_width=True)
            
        # Prepare Data for Display and Export
        df_export_detail = resumen_seccion.rename(columns={COL_SECCION: "Sección"})
        col_order_detail = ["Sección", "Inscritos", "Aprobados", "% Aprobación"]
        # Ensure columns exist (Inscritos and Aprobados are already there, % Aprobación too)
        df_export_detail = df_export_detail[col_order_detail]

        st.dataframe(
            df_export_detail.style.format({"% Aprobación": "{:.2f}%"}),
            width="stretch",
            hide_index=True
        )

        # ------------------------------------------------------------
        # 📥 DOWNLOADS (Detail Mode)
        # ------------------------------------------------------------
        # 1. PDF
        pdf_bytes = gerar_pdf_taa(df_export_detail, cohorte_sel, f"Detalle por Sección: {subject if 'subject' in locals() else 'Filtro'}", "Sección")
        
        # 2. Excel
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df_export_detail.to_excel(writer, index=False, sheet_name='Detalle Sección')
            workbook = writer.book
            num_fmt = workbook.add_format({'num_format': '0.00'})
            ws = writer.sheets['Detalle Sección']
            ws.set_column(0, 0, 20) # Sección
            ws.set_column(3, 3, 15, num_fmt) # %

        excel_bytes = excel_buffer.getvalue()

        st.divider()
        c_pdf, c_xls = st.columns(2, gap="medium")
        with c_pdf:
            st.download_button("Descargar Reporte (PDF)", data=pdf_bytes, file_name=f"Reporte_Seccion_{cohorte_sel}.pdf", mime="application/pdf", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa Aprobación Asignatura - Sección", "PDF"))
        with c_xls:
            st.download_button("Descargar Datos (Excel)", data=excel_bytes, file_name=f"Datos_Seccion_{cohorte_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa Aprobación Asignatura - Sección", "Excel"))


    else:
        # ------------------------------------------------------------
        # sMODO GERAL (Por Asignatura)
        # ------------------------------------------------------------
        
        # KPI Geral
        avg_approval = resumen["Tasa Aprobación (%)"].mean()
    
        st.markdown(f"""
        <div style="text-align: center; padding: 10px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 10px;">
            <h4 style="margin: 0; color: #555; font-size: 16px;">Promedio de la Tasa de Aprobación por Asignatura</h4>
            <h2 style="margin: 5px 0 0 0; font-size: 32px; color: #004080;">{avg_approval:.2f}%</h2>
            <p style="margin-top: 5px; font-size: 12px; color: #666;">Cohorte: {cohorte_sel}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()

        # Ordenar para o gráfico
        resumen_sorted = resumen.sort_values("Tasa Aprobación (%)", ascending=True)
        height_dynamic = max(400, len(resumen_sorted) * 25)

        fig = px.bar(
            resumen_sorted, 
            y=COL_DISCIPLINA, 
            x="Tasa Aprobación (%)", 
            orientation='h',
            text_auto='.1f',
            title=f"Tasa de Aprobación por Asignatura",
            color="Tasa Aprobación (%)",
            color_continuous_scale="Blues",
            height=height_dynamic
        )
        
        fig.update_layout(
            clickmode='event+select',
            yaxis_title=None,
            xaxis_title="Tasa de Aprobación (%)",
            margin=dict(l=0, r=0, t=40, b=0)
        )
        
        # Capture selection
        selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points")
        
        # Filter table based on chart selection
        st.divider()
        
        if selection and selection["selection"]["points"]:
            selected_items = [point["y"] for point in selection["selection"]["points"]]
            st.info(f"Mostrando {len(selected_items)} asignaturas seleccionadas.")
            resumen_table = resumen[resumen[COL_DISCIPLINA].isin(selected_items)].copy()
        else:
            resumen_table = resumen.copy()
        
        # Renomear e Ordenar
        resumen_table = resumen_table.rename(columns={
            COL_DISCIPLINA: "Asignatura",
            "Total": "Inscritos",
            "Tasa Aprobación (%)": "% Aprobación"
        })
        
        cols_order = ["Asignatura", "Inscritos", "Aprobados", "% Aprobación"]
        resumen_table = resumen_table[cols_order]

        st.dataframe(
            resumen_table.style.format({"% Aprobación": "{:.2f}%"}),
            width="stretch",
            hide_index=True
        )

        # ------------------------------------------------------------
        # 📥 DOWNLOADS (Overview Mode)
        # ------------------------------------------------------------
        # 1. PDF
        pdf_bytes = gerar_pdf_taa(resumen_table, cohorte_sel, "Detalle por Asignatura", "Asignatura")
        
        # 2. Excel
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            resumen_table.to_excel(writer, index=False, sheet_name='Detalle Asignatura')
            workbook = writer.book
            num_fmt = workbook.add_format({'num_format': '0.00'})
            ws = writer.sheets['Detalle Asignatura']
            ws.set_column(0, 0, 40) # Asignatura
            ws.set_column(3, 3, 15, num_fmt) # %

        excel_bytes = excel_buffer.getvalue()

        st.divider()
        c_pdf, c_xls = st.columns(2, gap="medium")
        with c_pdf:
            st.download_button("Descargar Reporte (PDF)", data=pdf_bytes, file_name=f"Reporte_Asignatura_{cohorte_sel}.pdf", mime="application/pdf", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa Aprobación Asignatura", "PDF"))
        with c_xls:
            st.download_button("Descargar Datos (Excel)", data=excel_bytes, file_name=f"Datos_Asignatura_{cohorte_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa Aprobación Asignatura", "Excel"))

    # ------------------------------------------------------------
    # 🔹 EXPLANATION
    # ------------------------------------------------------------
    st.divider()
    st.markdown("""        
        La **Tasa de Aprobación** se define como la relación entre el número de aprobados o promovidos y los alumnos inscritos en el periodo. \n
        La **Tasa de Aprobación por Asignatura (TAA)** muestra la aprobación o promoción de los estudiantes en las asignaturas
        correspondientes a cierto semestre con relación a los estudiantes inscriptos a esas asignaturas.
        """)    

    st.markdown("""
    ### Tasa de Aprobación por Asignatura (TAA)
    """)    
        
    st.latex(r"""
    TAA = \left( \frac{EPAS}{EIS} \right) \times 100
    """)

    st.markdown("""
    **Donde:**
        
    * **TAA:** Tasa de Aprobación por Asignatura.
    * **EPA:** número de Estudiantes Promovidos por Asignaturas (debe ser
        calculado por cada asignatura)
    * **EIS:** Número de Estudiantes Inscriptos en la Asignatura
    """)
