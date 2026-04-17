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
    st.subheader("Tasa de Deserción Semestral de la Cohorte (TDSC)")

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
    
    @st.cache_data
    def load_data():
        try:
            df = pd.read_csv("assets/data/alumnos.csv", low_memory=False)
            df.columns = df.columns.str.strip()
            df = df[df["filial_periodo_letivo"].isin(["CDE", "CDE III"])].copy()
            return df
        except Exception:
            return pd.DataFrame()

    df = load_data()
    if df.empty:
        st.error("Archivo de datos no encontrado.")
        return

    COL_COHORTE = "cohorte"
    COL_ID_ALUMNO = "usuarios_id"
    COL_SEMESTRE_ALUMNO = "semestre_alumno"

    # --- Lógica de Cálculo TDSC ---
    df[COL_SEMESTRE_ALUMNO] = pd.to_numeric(df[COL_SEMESTRE_ALUMNO], errors='coerce')
    df_clean = df.dropna(subset=[COL_SEMESTRE_ALUMNO, COL_ID_ALUMNO, COL_COHORTE])
    inscritos = df_clean.groupby([COL_COHORTE, COL_SEMESTRE_ALUMNO, COL_ID_ALUMNO]).first().reset_index()

    cohortes_list = sorted(inscritos[COL_COHORTE].unique().tolist())
    cohorte_sel = st.selectbox("Seleccione una Cohorte para ver la evolución semestral", cohortes_list, index=None)

    # -------------------------------------------------------------------------
    # PDF FUNCTIONS
    # -------------------------------------------------------------------------
    def agregar_encabezado_y_pie(canvas, doc):
        canvas.saveState()
        width, height = landscape(A4)
        logo_path = "assets/logo-ucp-icon.png" if os.path.exists("assets/logo-ucp-icon.png") else None
        if logo_path:
            try: canvas.drawImage(logo_path, x=2*cm, y=height-2.5*cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
            except: pass
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#004080"))
        canvas.drawString(5*cm, height-1.5*cm, "Universidad Central del Paraguay")
        canvas.setFont("Helvetica", 10)
        canvas.drawString(5*cm, height-2.1*cm, "Facultad de Ciencias de la Salud - Carrera de Medicina")
        canvas.setStrokeColor(colors.HexColor("#004080"))
        canvas.setLineWidth(1)
        canvas.line(2*cm, height-3.0*cm, width-2*cm, height-3.0*cm)
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(width-2*cm, 1.2*cm, f"Página {doc.page}")
        canvas.restoreState()

    def gerar_pdf_tdsc(df_dados, cohorte_atual):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=2*cm, rightMargin=2*cm, topMargin=4*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()
        story.append(Paragraph(f"<b>Reporte de Deserción Semestral - Cohorte {cohorte_atual}</b>", styles["Title"]))
        story.append(Spacer(1, 15))

        data_rows = [["Semestre", "Inscritos (EIS)", "Abandono (EACS)", "TDSC (%)"]]
        for _, row in df_dados.iterrows():
            data_rows.append([row['Semestre'], str(int(row['EIS'])), str(int(row['EACS'])), f"{row['TDSC (%)']:.2f}%"])

        tabla = Table(data_rows, repeatRows=1, colWidths=[6*cm, 5*cm, 5*cm, 5*cm])
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
        story.append(Paragraph("La <b>Tasa de Deserción Semestral de la Cohorte (TDSC)</b> caracteriza el comportamiento por semestre para tomar decisiones oportunas.", styles["Normal"]))
        story.append(Spacer(1, 5))
        story.append(Paragraph("<b>Fórmula:</b>", styles["Normal"]))
        story.append(Paragraph("<para align='center'>TDSC = (EACS / EIS) x 100</para>", styles["Normal"]))
        story.append(Spacer(1, 5))
        story.append(Paragraph("<b>Donde:</b>", styles["Normal"]))
        story.append(Paragraph("• <b>EACS</b> = Estudiantes que abandonan la Carrera (presentes en semestre S pero ausentes en S+1).", styles["Normal"]))
        story.append(Paragraph("• <b>EIS</b> = Estudiantes Inscriptos al inicio del Semestre.", styles["Normal"]))
        
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    if cohorte_sel:
        ins_coh = inscritos[inscritos[COL_COHORTE] == cohorte_sel]
        max_sem = int(ins_coh[COL_SEMESTRE_ALUMNO].max())
        limite_sem = min(max_sem, 12)
        datos_tdsc = []
        for s in range(1, limite_sem):
            eis_ids = set(ins_coh[ins_coh[COL_SEMESTRE_ALUMNO] == s][COL_ID_ALUMNO])
            s_plus_1_ids = set(ins_coh[ins_coh[COL_SEMESTRE_ALUMNO] == s + 1][COL_ID_ALUMNO])
            eis_count = len(eis_ids)
            if eis_count == 0: continue
            eacs_ids = eis_ids - s_plus_1_ids
            eacs_count = len(eacs_ids)
            datos_tdsc.append({"Semestre": f"{s}º -> {s+1}º", "EIS": eis_count, "EACS": eacs_count, "TDSC (%)": (eacs_count / eis_count) * 100})
            
        if not datos_tdsc:
            st.warning("No hay datos suficientes para calcular la deserción semestral.")
        else:
            df_tdsc = pd.DataFrame(datos_tdsc)
            st.markdown(f"### Evolución de Deserción Semestral - Cohorte {cohorte_sel}")
            fig = px.line(df_tdsc, x="Semestre", y="TDSC (%)", text=[f"{v:.2f}%" for v in df_tdsc["TDSC (%)"]], markers=True)
            fig.update_traces(textposition="top center", line_color="#b02a37")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_tdsc.style.format({"TDSC (%)": "{:.2f}%"}), width="stretch", hide_index=True)

            st.divider()
            c_pdf, c_xls = st.columns(2)
            with c_pdf:
                pdf_data = gerar_pdf_tdsc(df_tdsc, cohorte_sel)
                st.download_button("Descargar Reporte (PDF)", pdf_data, f"TDSC_{cohorte_sel}.pdf", "application/pdf", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa de Deserción Semestral", "PDF"))
            with c_xls:
                buffer_xls = io.BytesIO()
                df_tdsc.to_excel(buffer_xls, index=False)
                st.download_button("Descargar Datos (Excel)", buffer_xls.getvalue(), f"TDSC_Datos_{cohorte_sel}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa de Deserción Semestral", "Excel"))

    # -------------------------------------------------------------------------
    # METODOLOGÍA (FINAL)
    # -------------------------------------------------------------------------
    st.divider()
    st.markdown("""
    La **Tasa de Deserción Semestral de la Cohorte (TDSC)** caracteriza el comportamiento por semestre para tomar decisiones oportunas.
    \n**Fórmula:**
    """)
    st.latex(r"TDSC = \frac{EACS}{EIS} \times 100")
    st.markdown("""
    **Donde:**
    * **EACS** = Estudiantes que abandonan la Carrera (presentes en semestre S pero ausentes en S+1).
    * **EIS** = Estudiantes Inscriptos al inicio del Semestre.
    """)

