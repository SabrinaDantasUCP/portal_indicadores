import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime
from utils import db_pia
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

def render():
    st.subheader("Tasa de Aprobación por Carrera")

    # CSS to hide toolbar and style buttons (copied from other modules)
    st.markdown("""
        <style>
        [data-testid="stElementToolbar"] { display: none; }
        div[data-testid="stDownloadButton"] button {
            min-height: 50px !important;
            font-size: 16px !important;
            border-radius: 8px !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    @st.cache_data
    def load_data():
        try:
            df = pd.read_csv("assets/data/alumnos.csv", sep=",", low_memory=False)
            df.columns = df.columns.str.strip()
            # Filter for Regular subjects and CDE as per other modules pattern
            # Using copy() to avoid SettingWithCopyWarning
            df = df[(df["tipo_disciplina"] == "Regular") & (df["filial_periodo_letivo"].isin(["CDE", "CDE III"]))].copy()
            return df
        except FileNotFoundError:
            st.error("Archivo de datos no encontrado.")
            return pd.DataFrame()

    df = load_data()
    if df.empty:
        return

    COL_COHORTE = "cohorte"
    COL_CALIFICACION = "calificacion_final_1a5"
    COL_ID_ALUMNO = "usuarios_id"
    COL_SEMESTRE = "semestre_alumno"

    # Pre-process Data for TAC (All Cohorts)
    # 1. Validate numeric semester for sorting
    df[COL_SEMESTRE] = pd.to_numeric(df[COL_SEMESTRE], errors='coerce')
    df = df.dropna(subset=[COL_SEMESTRE])

    # 2. Determine pass/fail per subject
    df["aprobado"] = df[COL_CALIFICACION] >= 2

    # 3. Group by Cohorte + Semester + Student to find EPAS candidates
    # This prepares data for both views
    alumno_semestre_all = df.groupby([COL_COHORTE, COL_SEMESTRE, COL_ID_ALUMNO]).agg(
        Total_Asignaturas=(COL_CALIFICACION, "count"),
        Total_Aprobadas=("aprobado", "sum")
    ).reset_index()

    # Student is EPAS if Total_Asignaturas == Total_Aprobadas
    alumno_semestre_all["aprobo_todas"] = alumno_semestre_all["Total_Asignaturas"] == alumno_semestre_all["Total_Aprobadas"]

    # 4. Agregate per Cohorte + Semester to find TAC
    resumen_semestre_all = alumno_semestre_all.groupby([COL_COHORTE, COL_SEMESTRE]).agg(
        EIS=(COL_ID_ALUMNO, "count"),
        EPAS=("aprobo_todas", "sum")
    ).reset_index()

    # 5. Calculate TAC
    resumen_semestre_all["TAC (%)"] = (resumen_semestre_all["EPAS"] / resumen_semestre_all["EIS"]) * 100
    resumen_semestre_all["Semestre"] = resumen_semestre_all[COL_SEMESTRE].apply(lambda x: f"{int(x)}º Semestre")
    
    # -------------------------------------------------------------------------
    # PDF FUNCTIONS
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
            except: pass

        # --- Cabeçalho ---
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#004080"))
        canvas.drawString(5 * cm, height - 1.5 * cm, "Universidad Central del Paraguay")
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.black)
        canvas.drawString(5 * cm, height - 2.1 * cm, "Facultad de Ciencias de la Salud - Carrera de Medicina")
        
        canvas.setStrokeColor(colors.HexColor("#004080"))
        canvas.setLineWidth(1)
        canvas.line(2 * cm, height - 3.0 * cm, width - 2 * cm, height - 3.0 * cm)

        # --- Rodapé ---
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(width - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    def gerar_pdf_tac(df_dados, cohorte_atual, tac_valor):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=4 * cm, bottomMargin=2 * cm
        )

        story = []
        styles = getSampleStyleSheet()

        story.append(Paragraph("<b>Reporte de Tasa de Aprobación por Carrera (TAC)</b>", styles["Title"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>Cohorte:</b> {cohorte_atual}", styles["Normal"]))
        story.append(Spacer(1, 15))

        # --- KPI TAC ---
        data_kpi = [[f"TAC Promedio: {tac_valor:.2f}%"]]
        t_kpi = Table(data_kpi, colWidths=[20*cm])
        t_kpi.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#004080')),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 24),
            ('LEADING', (0,0), (-1,-1), 28),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8), 
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]), 
        ]))
        story.append(t_kpi)

        story.append(Spacer(1, 15))

        story.append(Paragraph("<b>Detalle por Semestre</b>", styles["Heading3"]))
        story.append(Spacer(1, 10))

        # Tabela de Detalhes
        data_rows = [["Semestre", "Inscritos (EIS)", "Aprobados (EPAS)", "TAC (%)"]]
        
        for _, row in df_dados.iterrows():
            data_rows.append([
                str(row['Semestre']),
                str(int(row['EIS'])),
                str(int(row['EPAS'])),
                f"{row['TAC (%)']:.2f}%"
            ])

        col_widths = [6 * cm, 5 * cm, 5 * cm, 5 * cm]
        
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

    def gerar_pdf_tac_comparativo(df_dados):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=4 * cm, bottomMargin=2 * cm
        )

        story = []
        styles = getSampleStyleSheet()

        story.append(Paragraph("<b>Comparativo de Tasa de Aprobación por Carrera (TAC)</b>", styles["Title"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Evaluación entre Cohortes", styles["Normal"]))
        story.append(Spacer(1, 15))

        # Tabela
        data_rows = [["Cohorte", "TAC Promedio (%)"]]
        
        for _, row in df_dados.iterrows():
            data_rows.append([
                str(row['cohorte']),
                f"{row['TAC (%)']:.2f}%"
            ])

        col_widths = [10 * cm, 8 * cm]
        
        tabla = Table(data_rows, repeatRows=1, colWidths=col_widths)
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004080')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')])
        ]))
        
        story.append(tabla)
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    # -------------------------------------------------------------------------
    # TABS
    # -------------------------------------------------------------------------
    tab1, tab2 = st.tabs(["Comparativo", "Detalle por Cohorte"])

    # -------------------------------------------------------------------------
    # TAB 1: Vista General
    # -------------------------------------------------------------------------
    with tab1:
        st.markdown("### Comparativo de Tasa de Aprobación entre Cohortes")
        
        # Chart: Average TAC per Cohorte (ignoring semesters)
        resumen_cohorte = resumen_semestre_all.groupby(COL_COHORTE)["TAC (%)"].mean().reset_index()
        resumen_cohorte = resumen_cohorte.sort_values(COL_COHORTE)
        
        fig_all = px.bar(
            resumen_cohorte, 
            x=COL_COHORTE, 
            y="TAC (%)", 
            text_auto='.2f',
            labels={"TAC (%)": "Tasa de Aprobación - Promedio (%)", COL_COHORTE: "Cohorte"}
        )
        fig_all.update_traces(textposition='outside')
        st.plotly_chart(fig_all, use_container_width=True)
        
        # ------------------------------------------------------------
        # GENERATION AND DOWNLOADS (Tab 1)
        # ------------------------------------------------------------
        
        # 1. Generate PDF
        dados_pdf_all = gerar_pdf_tac_comparativo(resumen_cohorte)

        # 2. Generate Excel
        buffer_excel_all = io.BytesIO()
        with pd.ExcelWriter(buffer_excel_all, engine='xlsxwriter') as writer:
            resumen_cohorte.to_excel(writer, index=False, sheet_name='Comparativo TAC')
            # Format
            workbook = writer.book
            num_fmt = workbook.add_format({'num_format': '0.00'})
            ws = writer.sheets['Comparativo TAC']
            ws.set_column(0, 0, 15) # Cohorte
            ws.set_column(1, 1, 15, num_fmt) # TAC
            
        dados_excel_all = buffer_excel_all.getvalue()

        # 3. Buttons
        st.divider()
        c_pdf, c_xls = st.columns(2, gap="medium")
        
        with c_pdf:
            st.download_button(
                label="Descargar Reporte (PDF)",
                data=dados_pdf_all,
                file_name=f"Reporte_TAC_Comparativo_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                icon=":material/download:",
                width="stretch",
                on_click=db_pia.log_export_callback, args=("Tasa Aprobación Carrera - Comparativo", "PDF")
            )
            
        with c_xls:
            st.download_button(
                label="Descargar Datos (Excel)",
                data=dados_excel_all,
                file_name=f"Datos_TAC_Comparativo_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                icon=":material/download:",
                width="stretch",
                on_click=db_pia.log_export_callback, args=("Tasa Aprobación Carrera - Comparativo", "Excel")
            )

    # -------------------------------------------------------------------------
    # TAB 2: Detalle por Cohorte (Existing Logic)
    # -------------------------------------------------------------------------
    with tab2:
        
        cohortes = sorted(df[COL_COHORTE].dropna().unique().tolist())
        cohorte_sel = st.selectbox("", cohortes, index=None, key="sel_cohorte_tab2")

        if not cohorte_sel:
            st.info("Seleccione una **Cohorte** para ver el detalle.")
        else:
            # Filter prepared data
            resumen_semestre = resumen_semestre_all[resumen_semestre_all[COL_COHORTE] == cohorte_sel].copy()
            
            # KPI
            tac_promedio = resumen_semestre["TAC (%)"].mean()
            st.markdown(f"""
            <div style="text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px;">
                <h3 style="margin: 0; color: #555;">Promedio de la Tasa de Aprobación</h3>
                <h1 style="margin: 10px 0 0 0; font-size: 48px; color: #004080;">{tac_promedio:.2f}%</h1>
                <p style="margin-top: 5px; color: #666;">Cohorte: {cohorte_sel}</p>
            </div>
            """, unsafe_allow_html=True)

            st.divider()
            st.markdown(f"### Evolución de la Tasa de Aprobación - Cohorte {cohorte_sel}")

            # Chart (Single Cohorte)
            resumen_semestre = resumen_semestre.sort_values(COL_SEMESTRE)

            fig = px.line(
                resumen_semestre, 
                x="Semestre", 
                y="TAC (%)", 
                markers=True,
                labels={"TAC (%)": "Tasa de Aprobación (%)"}
            )
            fig.update_traces(
                line_color='#004080', 
                line_width=3, 
                marker_size=10,
                selected_marker_size=15, 
                selected_marker_color='red'
            )
            
            fig.update_layout(clickmode='event+select', dragmode='select') 
            
            selection = st.plotly_chart(
                fig, 
                use_container_width=True, 
                on_select="rerun", 
                selection_mode="points",
                key="tac_chart_selection_single"
            )
            
            # Table
            st.dataframe(
                resumen_semestre[[COL_SEMESTRE, "EIS", "EPAS", "TAC (%)"]]
                .rename(columns={COL_SEMESTRE: "Semestre"})
                .style.format({"TAC (%)": "{:.2f}%", "Semestre": "{:.0f}º Semestre"}),
                width="stretch",
                hide_index=True
            )

            # ------------------------------------------------------------
            # GENERATION AND DOWNLOADS
            # ------------------------------------------------------------

            # 1. Generate PDF
            dados_pdf = gerar_pdf_tac(resumen_semestre, cohorte_sel, tac_promedio)

            # 2. Generate Excel (Formatted)
            buffer_excel = io.BytesIO()
            try:
                with pd.ExcelWriter(buffer_excel, engine='xlsxwriter') as writer:
                    # Detail Sheet
                    resumen_semestre.rename(columns={COL_SEMESTRE: "Semestre"}).to_excel(writer, index=False, sheet_name='Detalle Semestres')
                    
                    # Summary Sheet
                    df_resumo = pd.DataFrame([{"Cohorte": cohorte_sel, "TAC Promedio": tac_promedio}])
                    df_resumo.to_excel(writer, index=False, sheet_name='Resumen TAC')
                    
                    workbook = writer.book
                    num_fmt = workbook.add_format({'num_format': '0.00'})
                    
                    # Format Detail Sheet
                    ws_det = writer.sheets['Detalle Semestres']
                    for i, col in enumerate(resumen_semestre.columns):
                        max_len = 20 # Standard width
                        ws_det.set_column(i, i, max_len)
                            
                    # Format Summary Sheet
                    ws_res = writer.sheets['Resumen TAC']
                    ws_res.set_column(1, 1, 15, num_fmt)

            except:
                with pd.ExcelWriter(buffer_excel) as writer:
                     resumen_semestre.to_excel(writer, index=False, sheet_name='Datos TAC')

            dados_excel = buffer_excel.getvalue()

            # 3. Buttons
            st.divider()
            col_pdf, col_excel = st.columns(2, gap="medium")

            with col_pdf:
                st.download_button(
                    label="Descargar Reporte (PDF)",
                    data=dados_pdf,
                    file_name=f"Reporte_TAC_{cohorte_sel}.pdf",
                    mime="application/pdf",
                    icon=":material/download:",
                    width="stretch",
                    on_click=db_pia.log_export_callback, args=("Tasa Aprobación Carrera", "PDF")
                )

            with col_excel:
                st.download_button(
                    label="Descargar Datos (Excel)",
                    data=dados_excel,
                    file_name=f"Datos_TAC_{cohorte_sel}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    icon=":material/download:",
                    width="stretch",
                    on_click=db_pia.log_export_callback, args=("Tasa Aprobación Carrera", "Excel")  
                )

    # ------------------------------------------------------------
    # EXPLANATION (Shared)
    # ------------------------------------------------------------
    st.divider()

    st.markdown("""        
    La **Tasa de Aprobación** se define como la relación entre el número de aprobados o promovidos y los alumnos inscritos en el periodo. \n
    La **Tasa de Aprobación por Carrera (TAC)** permite identificar a los estudiantes regulares de la carrera, es decir, aquellos que son promovidos en forma íntegra.
    """)    

    st.markdown("""
    ### Tasa de Aprobación por Carrera (TAC)
    """)
    
    st.latex(r"""
    TAC = \left( \frac{EPAS}{EIS} \right) \times 100
    """)

    st.markdown("""
    **Donde:**
    
    * **TAC:** Tasa de Aprobación por Carrera.
    * **EPAS:** Número de Estudiantes Promovidos en todas las Asignaturas del
      Semestre de la Carrera (estudiantes que aprueban todas las asignaturas,
      es decir, estudiantes regulares)
    * **EIS:** Número de Estudiantes Inscriptos en el Semestre
    Fuente de consulta de la promoción del estudiante es el Acta de
    Calificación
    """)
