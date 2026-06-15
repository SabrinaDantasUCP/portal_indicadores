import streamlit as st
import plotly.express as px
import io
import os
from datetime import datetime
from utils import db_pia
from utils.system_logging import log_exception
from services.data.alumnos import load_current_alumnos
from services.calculations.tasa_desercion import (
    COL_COHORTE,
    calculate_generational_dropout,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

def render():
    st.subheader("Tasa de Deserción Generacional (TDG)")

    # CSS para ocultar toolbar e estilizar botões
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
    
    df = load_current_alumnos()
    if df.empty:
        st.error("Archivo de datos no encontrado.")
        return

    resumen_tdg_full, resumen_tdg, missing_cols = calculate_generational_dropout(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return
    if resumen_tdg_full.empty:
        st.warning("No hay datos suficientes para calcular la deserción generacional.")
        return

    # -------------------------------------------------------------------------
    # PDF FUNCTIONS
    # -------------------------------------------------------------------------
    def agregar_encabezado_y_pie(canvas, doc):
        canvas.saveState()
        width, height = landscape(A4)
        logo_path = "assets/logo-ucp-icon.png" if os.path.exists("assets/logo-ucp-icon.png") else None
        if logo_path:
            try: canvas.drawImage(logo_path, x=2*cm, y=height-2.5*cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
            except Exception as exc:
                log_exception("Error silencioso tratado en tasa_desercion_generacional.py", exc)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#004080"))
        canvas.drawString(5*cm, height-1.5*cm, "Universidad Central del Paraguay")
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.black)
        canvas.drawString(5*cm, height-2.1*cm, "Facultad de Ciencias de la Salud - Carrera de Medicina")
        canvas.setStrokeColor(colors.HexColor("#004080"))
        canvas.setLineWidth(1)
        canvas.line(2*cm, height-3.0*cm, width-2*cm, height-3.0*cm)
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(width-2*cm, 1.2*cm, f"Página {doc.page}")
        canvas.restoreState()

    def gerar_pdf_tdg(df_dados, titulo):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=2*cm, rightMargin=2*cm, topMargin=4*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()
        story.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
        story.append(Spacer(1, 15))

        data_rows = [["Cohorte", "Inscritos (EIIC)", "Egresados (ECE)", "Desertores (ECA)", "TDG (%)"]]
        for _, row in df_dados.iterrows():
            data_rows.append([str(row[COL_COHORTE]), str(int(row['EIIC'])), str(int(row['ECE'])), str(int(row['ECA'])), f"{row['TDG (%)']:.2f}%"])

        tabla = Table(data_rows, repeatRows=1, colWidths=[4*cm, 4*cm, 4*cm, 4*cm, 4*cm])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#004080')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.4, colors.grey),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f2f2f2')])
        ]))
        story.append(tabla)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("<b>Metodología</b>", styles["Heading3"]))
        story.append(Paragraph("La <b>Deserción</b> se define como el abandono que hace el alumno de los cursos o carreras a las que se ha inscripto.", styles["Normal"]))
        story.append(Paragraph("La <b>Tasa de Deserción Generacional (TDG)</b> aprecia el comportamiento del flujo escolar de una cohorte durante el tiempo estipulado (12 semestres).", styles["Normal"]))
        story.append(Spacer(1, 5))
        story.append(Paragraph("<b>Fórmula:</b>", styles["Normal"]))
        story.append(Paragraph("<para align='center'>TDG = (ECA / EIIC) x 100</para>", styles["Normal"]))
        story.append(Spacer(1, 5))
        story.append(Paragraph("<b>Donde:</b>", styles["Normal"]))
        story.append(Paragraph("• <b>ECA</b> = EIIC - ECE (Estudiantes que abandonan la Carrera).", styles["Normal"]))
        story.append(Paragraph("• <b>EIIC</b> = Estudiantes Inscriptos al Inicio de la Carrera (1º semestre).", styles["Normal"]))
        story.append(Paragraph("• <b>ECE</b> = Estudiantes de la Cohorte que Egresan en el tiempo estipulado.", styles["Normal"]))
        
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------
    tab1, tab2 = st.tabs(["Comparativo", "Detalle por Cohorte"])

    with tab1:
        st.markdown("### Comparativo de Deserción Generacional")
        fig = px.bar(resumen_tdg, x=COL_COHORTE, y="TDG (%)", text_auto='.2f', labels={"TDG (%)": "TDG (%)", COL_COHORTE: "Cohorte"}, color="TDG (%)", color_continuous_scale="Reds")
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            resumen_tdg.style.format({
                "EIIC": "{:d}",
                "ECE": "{:d}",
                "ECA": "{:d}",
                "TDG (%)": "{:.2f}%"
            }), 
            width="stretch", 
            hide_index=True
        )

        st.divider()

    with tab2:
        cohorte_sel = st.selectbox("Seleccione una Cohorte", sorted(resumen_tdg_full[COL_COHORTE].unique()), index=None)
        if cohorte_sel:
            row = resumen_tdg_full[resumen_tdg_full[COL_COHORTE] == cohorte_sel].iloc[0]
            st.markdown(f"""
            <div style="text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px;">
                <h3 style="margin: 0; color: #555;">Tasa de Deserción Generacional</h3>
                <h1 style="margin: 10px 0 0 0; font-size: 48px; color: #b02a37;">{row['TDG (%)']:.2f}%</h1>
                <p style="margin-top: 5px; color: #666;">Cohorte: {cohorte_sel}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.write(f"**EIIC (Inscritos):** {int(row['EIIC'])}")
            st.write(f"**ECE (Egresados):** {int(row['ECE'])}")
            st.write(f"**ECA (Desertores):** {int(row['ECA'])}")

    st.divider()
    c_pdf, c_xls = st.columns(2)
    with c_pdf:
        # Usamos o resumen_tdg (que contém todas as coortes completas) ou o resumen_tdg_full? 
        # Geralmente o comparativo é o que se quer baixar.
        pdf_data = gerar_pdf_tdg(resumen_tdg, "Reporte de Deserción Generacional")
        st.download_button("Descargar Reporte (PDF)", pdf_data, f"TDG_Comparativo_{datetime.now().strftime('%Y%m%d')}.pdf", "application/pdf", icon=":material/download:", width="stretch", key="pdf_tdg", on_click=db_pia.log_export_callback, args=("Tasa de Deserción Generacional", "PDF"))
    with c_xls:
        buffer_xls = io.BytesIO()
        resumen_tdg.to_excel(buffer_xls, index=False)
        st.download_button("Descargar Datos (Excel)", buffer_xls.getvalue(), f"TDG_Datos_{datetime.now().strftime('%Y%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", key="xlsx_tdg", on_click=db_pia.log_export_callback, args=("Tasa de Deserción Generacional", "Excel"))

    # -------------------------------------------------------------------------
    # METODOLOGÍA (FINAL)
    # -------------------------------------------------------------------------
    st.divider()
    st.markdown("""
    La **Deserción** se define como el abandono que hace el alumno de los cursos o carreras a las que se ha inscripto.
    La **Tasa de Deserción Generacional (TDG)** aprecia el comportamiento del flujo escolar de una cohorte durante el tiempo estipulado (12 semestres).
    \n**Fórmula:**
    """)
    st.latex(r"TDG = \frac{ECA}{EIIC} \times 100")
    st.markdown("""
    **Donde:**
    * **ECA** = EIIC - ECE (Estudiantes que abandonan la Carrera).
    * **EIIC** = Estudiantes Inscriptos al Inicio de la Carrera (1º semestre).
    * **ECE** = Estudiantes de la Cohorte que Egresan en el tiempo estipulado.
    """)

