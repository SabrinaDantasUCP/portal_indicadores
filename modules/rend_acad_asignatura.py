import streamlit as st
import pandas as pd
import io
import os
import re
from datetime import datetime
from utils import db_pia
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# ------------------------------------------------------------
# 📘 Página: Tasa de Rendimiento Académico Semestral por Asignatura
# ------------------------------------------------------------
def render():
    st.subheader("Rendimiento Académico por Asignatura")

    # CSS para esconder toolbar e ajustar botões
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
        df = pd.read_csv("assets/data/alumnos.csv", sep=",", low_memory=False)
        df.columns = df.columns.str.strip()
        
        # Filtro obrigatório: Regular e CDE
        df = df[(df["tipo_disciplina"] == "Regular") & (df["filial_periodo_letivo"].isin(["CDE", "CDE III"]))]
        
        # Converter semestre para número para ordenação correta (1 a 12)
        df["semestre_disciplina"] = pd.to_numeric(df["semestre_disciplina"], errors='coerce')
        return df

    df = load_data()

    # 🧩 Colunas
    COL_COHORTE = "cohorte"
    COL_SEMESTRE_DISCIPLINA = "semestre_disciplina"
    COL_DISCIPLINA = "disciplina"
    COL_CALIFICACION = "calificacion_final_1a5"
    COL_ID_ALUMNO = "usuarios_id"

    df[COL_COHORTE] = df[COL_COHORTE].astype(str).str.strip()

    # ------------------------------------------------------------
    # 🎚️ Filtros em Cascata
    # ------------------------------------------------------------
    def limpar_filtros():
        st.session_state["cohorte_sel"] = None
        st.session_state["semestre_sel"] = []
        st.session_state["asignatura_sel"] = []
        st.rerun()

    col1, col2, col3 = st.columns(3)

    # 1️⃣ COHORTE
    cohorte_vals = sorted(df[COL_COHORTE].dropna().unique().tolist())
    cohorte_sel = col1.selectbox("Cohorte", cohorte_vals, index=None, placeholder="Seleccione una Cohorte", key="cohorte_sel")

    if not cohorte_sel:
        col2.multiselect("Semestre", [], disabled=True)
        col3.multiselect("Asignatura", [], disabled=True)
        st.info("Seleccione una **Cohorte** para visualizar los datos")
        return

    df_filtrado = df[df[COL_COHORTE] == cohorte_sel]

    # 2️⃣ SEMESTRE (Ordenação 1-12)
    semestre_opts = sorted(df_filtrado[COL_SEMESTRE_DISCIPLINA].dropna().unique().astype(int).tolist())
    semestre_sel = col2.multiselect(
        "Semestre", 
        semestre_opts,
        format_func=lambda x: f"{x}º Semestre"
    )
    
    if semestre_sel:
        df_filtrado = df_filtrado[df_filtrado[COL_SEMESTRE_DISCIPLINA].isin(semestre_sel)]

    # 3️⃣ ASIGNATURA
    asignatura_vals = sorted(df_filtrado[COL_DISCIPLINA].dropna().unique().tolist())
    asignatura_sel = col3.multiselect("Asignatura", asignatura_vals)
    
    if asignatura_sel:
        df_filtrado = df_filtrado[df_filtrado[COL_DISCIPLINA].isin(asignatura_sel)]

    if df_filtrado.empty:
        st.warning("⚠️ No se encontraron datos para los filtros seleccionados.")
        return

    # ------------------------------------------------------------
    # 📊 Cálculo
    # ------------------------------------------------------------
    df_unicos = df_filtrado.drop_duplicates(subset=[COL_COHORTE, COL_SEMESTRE_DISCIPLINA, COL_DISCIPLINA, COL_ID_ALUMNO])

    resumen = (
        df_unicos
        .groupby([COL_COHORTE, COL_SEMESTRE_DISCIPLINA, COL_DISCIPLINA])
        .agg(TRASA=(COL_CALIFICACION, "mean"), N=(COL_ID_ALUMNO, "count"))
        .reset_index()
    )

    # DataFrame para exibição (com "º Semestre")
    df_display = resumen.copy()
    df_display[COL_SEMESTRE_DISCIPLINA] = df_display[COL_SEMESTRE_DISCIPLINA].apply(lambda x: f"{int(x)}º Semestre")
    
    mapa_colunas = {
        COL_COHORTE: "Cohorte",
        COL_SEMESTRE_DISCIPLINA: "Semestre",
        COL_DISCIPLINA: "Asignatura",
        "N": "Estudiantes (N)",
        "TRASA": "Promedio (TRASA)"
    }
    df_display = df_display.rename(columns=mapa_colunas)

    # ------------------------------------------------------------
    # 📊 KPIs Gerais
    # ------------------------------------------------------------
    st.divider()
    total_asignaturas = len(df_display)
    total_alumnos = df_filtrado[COL_ID_ALUMNO].nunique()
    
    kpi1, kpi2, kpi3 = st.columns(3)
    def kpi_box(label, value):
        return f"""<div style="background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 10px; padding: 20px; text-align: center;">
        <span style="font-size: 14px; color: #666; font-weight: 600; text-transform: uppercase;">{label}</span><br>
        <span style="font-size: 28px; color: #333; font-weight: 700;">{value}</span></div>"""

    kpi1.markdown(kpi_box("Cohorte", cohorte_sel), unsafe_allow_html=True)
    kpi2.markdown(kpi_box("Estudiantes (N)", total_alumnos), unsafe_allow_html=True)
    kpi3.markdown(kpi_box("Asignaturas", total_asignaturas), unsafe_allow_html=True)
    
    st.divider()

    # ------------------------------------------------------------
    # 🔄 EXIBIÇÃO POR SEMESTRE (CAIXAS)
    # ------------------------------------------------------------
    semestres_presentes = sorted(df_display["Semestre"].unique(), key=lambda x: int(x.split('º')[0]))

    for semestre in semestres_presentes:
        st.markdown(f"""<div style="border: 1px solid #ddd; border-radius: 10px; background-color: #f9f9f9; padding: 14px 20px; margin-top: 25px; margin-bottom: 15px; font-size: 18px; font-weight: 600; color: #444;">{semestre}</div>""", unsafe_allow_html=True)
        
        df_sem = df_display[df_display["Semestre"] == semestre]
        st.dataframe(
            df_sem[["Asignatura", "Estudiantes (N)", "Promedio (TRASA)"]].style.format({"Promedio (TRASA)": "{:.2f}"}),
            width="stretch", hide_index=True
        )

    # ------------------------------------------------------------
    # 📄 CONFIGURAÇÃO DO PDF (ReportLab - Lógica Completa)
    # ------------------------------------------------------------
    
    def agregar_encabezado_y_pie(canvas, doc):
        canvas.saveState()
        width, height = landscape(A4)
        # Logo
        logo_path = "assets/logo-ucp-icon.png"
        if os.path.exists(logo_path):
            canvas.drawImage(logo_path, 2*cm, height-2.5*cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
        
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#004080"))
        canvas.drawString(5*cm, height-1.5*cm, "Universidad Central del Paraguay")
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.black)
        canvas.drawString(5*cm, height-2.1*cm, "Facultad de Ciencias de la Salud — Carrera de Medicina")
        canvas.setStrokeColor(colors.HexColor("#004080"))
        canvas.line(2*cm, height-3.0*cm, width-2*cm, height-3.0*cm)
        # Rodapé
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(width-2*cm, 1.2*cm, f"Página {doc.page}")
        canvas.restoreState()

    def gerar_pdf_completo(df_pdf_dados, cohorte_atual):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=2*cm, rightMargin=2*cm, topMargin=4*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()

        story.append(Paragraph("<b>Reporte de Rendimiento Académico por Asignatura</b>", styles["Title"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<b>Cohorte:</b> {cohorte_atual}", styles["Normal"]))
        story.append(Spacer(1, 12))

        # Tabela
        # Ordenar pelo número do semestre para o PDF
        df_pdf_dados['n_sem'] = df_pdf_dados['Semestre'].apply(lambda x: int(x.split('º')[0]))
        df_pdf_dados = df_pdf_dados.sort_values(['n_sem', 'Asignatura'])

        data_rows = [["Semestre", "Asignatura", "Estudiantes (N)", "Promedio (TRASA)"]]
        for _, row in df_pdf_dados.iterrows():
            data_rows.append([row['Semestre'], row['Asignatura'], str(row['Estudiantes (N)']), f"{row['Promedio (TRASA)']:.2f}"])

        tabla = Table(data_rows, repeatRows=1, colWidths=[3*cm, 13*cm, 3.5*cm, 3.5*cm])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#004080')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.4, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f2f2f2')])
        ]))
        story.append(tabla)
        
        # --- Seção Teórica no PDF ---
        story.append(Spacer(1, 20))
        small_style = styles["Normal"].clone('small')
        small_style.fontSize = 9
        small_style.textColor = colors.grey
        
        story.append(Paragraph("<b>Tasa de Rendimiento Académico (TRA)</b>", small_style))
        story.append(Paragraph("Está definido por el promedio de la calificación obtenido por el estudiante...", small_style))
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>TRASA<sub>(1)</sub> = [CE<sub>(1)</sub>A<sub>(1)</sub> + ... + CE<sub>(n)</sub>A<sub>(1)</sub>] / N</b>", small_style))
        
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    # ------------------------------------------------------------
    # 📥 BOTÕES DE DOWNLOAD
    # ------------------------------------------------------------
    pdf_final = gerar_pdf_completo(df_display, cohorte_sel)
    
    st.divider()
    c_pdf, c_xls = st.columns(2)
    with c_pdf:
        st.download_button("Descargar Reporte (PDF)", data=pdf_final, file_name=f"Reporte_{cohorte_sel}.pdf", width="stretch", icon=":material/download:", on_click=db_pia.log_export_callback, args=("Rendimiento Asignatura", "PDF"))
    with c_xls:
        buffer_ex = io.BytesIO()
        df_display.to_excel(buffer_ex, index=False)
        st.download_button("Descargar Datos (Excel)", data=buffer_ex.getvalue(), file_name=f"Datos_{cohorte_sel}.xlsx", width="stretch", icon=":material/download:", on_click=db_pia.log_export_callback, args=("Rendimiento Asignatura", "Excel"))

    # ------------------------------------------------------------
    # 🔹 Explicação Final na Tela
    # ------------------------------------------------------------
    st.divider()
    
    st.markdown("""        
    La Tasa de Rendimiento Académico (TRA) está definida por el promedio de la calificación obtenido por el estudiante en las materias en las cuales ha presentado exámenes, independientemente del tipo de examen (Chaín, 1995).
    En este caso **se calcula el rendimiento académico por estudiantes en forma individual, por asignatura, por semestre y general, por generación o cohorte.** 
    De acuerdo con el razonamiento anterior, los cálculos quedan como sigue:     
    """)
    st.markdown("""          
    #### Tasa de Rendimiento Académico Semestral de la Asignatura, promedio (TRASA)               
    """)

    st.latex(r"""
    \text{TRASA(1)} = \frac{\text{CE}_{(1)}A_{(1)} + \text{CE}_{(2)}A_{(1)} + \text{CE}_{(3)}A_{(1)} + \dots + \text{CE}_{(n)}A_{(1)}}{N}
    """)

    st.markdown("""
    **Donde:**

    - **TRASA(1):** Tasa de Rendimiento Académico Semestral de la Asignatura (debe ser calculada para cada asignatura).  
    - **CE(1)A(1):** Calificación del Estudiante 1 en la Asignatura 1 al final del semestre.
    - **CE(2)A(1):** Calificación del Estudiante 2 en la Asignatura 1 al final del semestre.  
    - **CE(3)A(1):** Calificación del Estudiante 3 en la Asignatura 1 al final del semestre.  
    - **CE(n)A(1):** Calificación del Estudiante "n" en la Asignatura "n" al final del semestre.  
    - **N:** Número de datos (cantidad de asignaturas examinadas).  
    """)
    
if __name__ == "__main__":
    render()