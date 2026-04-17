import streamlit as st
import pandas as pd
import io
import os
import re 
import unicodedata 
from datetime import datetime, timedelta
from utils import db_pia
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# ------------------------------------------------------------
# Pagina: Tasa de Rendimiento Academico de los Semestres (TRAS)
# ------------------------------------------------------------
def render():
    st.subheader("Rendimiento Académico por Semestre")

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
        """Carrega e cacheia o dataset"""
        df = pd.read_csv("assets/data/alumnos.csv", sep=",", low_memory=False)
        df.columns = df.columns.str.strip()
        return df

    df = load_data()

    # ------------------------------------------------------------
    # Columnas
    # ------------------------------------------------------------
    COL_COHORTE = "cohorte"
    COL_SEMESTRE = "semestre_alumno"
    COL_CALIFICACION = "calificacion_final_1a5"
    COL_ID_ALUMNO = "usuarios_id"
    COL_TIPO_DISCIPLINA = "tipo_disciplina"
    COL_FILIAL = "filial_periodo_letivo"

    # Tratamento de strings
    df[COL_COHORTE] = df[COL_COHORTE].astype(str).str.strip()
    
    # Converter semestre para número para ordenação correta (1 a 12)
    df[COL_SEMESTRE] = pd.to_numeric(df[COL_SEMESTRE], errors='coerce')

    # ------------------------------------------------------------
    # Filtros (COHORTE + SEMESTRE)
    # ------------------------------------------------------------
    col1, col2 = st.columns(2)

    # 1. COHORTE
    cohorte_vals = sorted(df[COL_COHORTE].dropna().unique().tolist())
    cohorte_sel = col1.selectbox(
        "Cohorte", 
        cohorte_vals, 
        index=None, 
        placeholder="Seleccione una Cohorte"
    )

    # Lógica de Bloqueio
    if not cohorte_sel:
        st.info("Seleccione una **Cohorte** para visualizar los datos.")
        col2.multiselect("Semestre", [], disabled=True)
        return

    # Filtra o DF pela Cohorte selecionada, Tipo Regular e Filial CDE
    df_filtrado = df[
        (df[COL_COHORTE] == cohorte_sel) & 
        (df[COL_TIPO_DISCIPLINA] == "Regular") &
        (df[COL_FILIAL].isin(["CDE", "CDE III"]))
    ]

    # 2. SEMESTRE
    semestre_opts = sorted(df_filtrado[COL_SEMESTRE].dropna().unique().astype(int).tolist())
    semestre_sel = col2.multiselect(
        "Semestre", 
        semestre_opts,
        format_func=lambda x: f"{x}º Semestre"
    )
    
    if semestre_sel:
        df_filtrado = df_filtrado[df_filtrado[COL_SEMESTRE].isin(semestre_sel)]

    if df_filtrado.empty:
        st.warning("No se encontraron datos para los filtros seleccionados (Regular + CDE).")
        return

    # ------------------------------------------------------------
    # Calculo do TRAS
    # ------------------------------------------------------------
    
    # PASSO 1: Calcular o TRASE (Rendimento de CADA aluno no semestre)
    df_trase = (
        df_filtrado
        .groupby([COL_COHORTE, COL_SEMESTRE, COL_ID_ALUMNO])
        .agg(TRASE=(COL_CALIFICACION, "mean"))
        .reset_index()
    )

    # PASSO 2: Calcular o TRAS (Média dos TRASEs para o semestre)
    df_tras = (
        df_trase
        .groupby([COL_COHORTE, COL_SEMESTRE])
        .agg(
            TRAS=("TRASE", "mean"),
            N=(COL_ID_ALUMNO, "count")
        )
        .reset_index()
    )

    df_tras["TRAS"] = df_tras["TRAS"].fillna(0)

    # Renomeação para exibição
    mapa_colunas = {
        COL_COHORTE: "Cohorte",
        COL_SEMESTRE: "Semestre",
        "N": "Estudiantes (N)",
        "TRAS": "Promedio (TRAS)"
    }
    df_display = df_tras.rename(columns=mapa_colunas)

    st.divider()

    # ------------------------------------------------------------
    # KPIs Gerais
    # ------------------------------------------------------------
    total_semestres = len(df_display)
    total_alunos_unicos = df_filtrado[COL_ID_ALUMNO].nunique()
    
    kpi1, kpi2 = st.columns(2)

    def kpi_box(label, value):
        return f"""
        <div style="
            background-color: #f9f9f9;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        ">
            <span style="font-size: 14px; color: #666; text-transform: uppercase; font-weight: 600; margin-bottom: 5px;">
                {label}
            </span>
            <span style="font-size: 28px; color: #333; font-weight: 700;">
                {value}
            </span>
        </div>
        """

    kpi1.markdown(kpi_box("Cohorte", cohorte_sel), unsafe_allow_html=True)
    kpi2.markdown(kpi_box("Total Estudiantes", total_alunos_unicos), unsafe_allow_html=True)
    
    st.divider()

    # ------------------------------------------------------------
    # EXIBICAO SEPARADA POR SEMESTRE
    # ------------------------------------------------------------
    if "Semestre" in df_display.columns:
        # Formata para string "Xº Semestre" para exibição, mas ordena primeiro
        df_display_sorted = df_display.sort_values("Semestre")
        
        # Converte para lista de strings formatadas para o loop
        semestres_presentes = [f"{int(s)}º Semestre" for s in df_display_sorted["Semestre"].unique()]
        
        # Adiciona coluna formatada ao DF para filtro interno
        df_display["Semestre_Fmt"] = df_display["Semestre"].apply(lambda x: f"{int(x)}º Semestre")

        for semestre in semestres_presentes:
            
            # Filtra apenas o semestre atual
            df_semestre = df_display[df_display["Semestre_Fmt"] == semestre]
            
            # Extrai os valores únicos para este semestre (assumindo 1 linha por semestre/cohorte)
            if not df_semestre.empty:
                val_n = df_semestre["Estudiantes (N)"].iloc[0]
                val_tras = df_semestre["Promedio (TRAS)"].iloc[0]
            else:
                val_n = 0
                val_tras = 0.0
            
            # 1. Caixa Cinza com o Nome do Semestre (Cabeçalho)
            st.markdown(
            f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 10px;
                background-color: #f9f9f9;
                padding: 14px 20px;
                margin-top: 25px;
                margin-bottom: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                font-size: 20px;
                font-weight: 600;
                color: #444;
                display: flex;
                align-items: center;
                gap: 15px;
            ">  
                <span>{semestre}</span>
            </div>
            """,
            unsafe_allow_html=True
            )
            
            # 2. Duas caixas lado a lado (Estudiantes e Promedio)
            c1, c2 = st.columns(2)
            
            # Estilo CSS reutilizável para as caixas internas
            box_style = """
                background-color: #ffffff;
                border: 1px solid #eee;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
            """
            
            # Coluna 1: Estudiantes
            c1.markdown(f"""
            <div style="{box_style}">
                <span style="font-size: 14px; color: #666; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">
                    Estudiantes (N)
                </span>
                <span style="font-size: 26px; color: #333; font-weight: 700;">
                    {val_n}
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            # Coluna 2: Promedio (TRAS)
            c2.markdown(f"""
            <div style="{box_style}">
                <span style="font-size: 14px; color: #666; font-weight: 600; text-transform: uppercase; margin-bottom: 8px;">
                    Promedio (TRAS)
                </span>
                <span style="font-size: 26px; color: #004080; font-weight: 700;">
                    {val_tras:.2f}
                </span>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
    else:
        st.error("Error: no se encontró la columna 'Semestre'.")

    
    # ============================================================
    # CONFIGURACAO DO PDF (ReportLab - TRAS)
    # ============================================================
    
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
        canvas.drawString(5 * cm, height - 2.1 * cm, "Facultad de Ciencias de la Salud — Carrera de Medicina")
        
        canvas.setStrokeColor(colors.HexColor("#004080"))
        canvas.setLineWidth(1)
        canvas.line(2 * cm, height - 3.0 * cm, width - 2 * cm, height - 3.0 * cm)

        # --- Rodapé ---
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(width - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    def gerar_pdf_tras(df_dados, cohorte_atual):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=4 * cm, bottomMargin=2 * cm
        )

        story = []
        styles = getSampleStyleSheet()

        story.append(Paragraph("<b>Reporte de Rendimiento Académico por Semestre(TRAS)</b>", styles["Title"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>Cohorte:</b> {cohorte_atual}", styles["Normal"]))
        story.append(Spacer(1, 12))

        # Tabela (Usando o DF completo para o relatório)
        # Ordenação para o PDF
        df_pdf = df_dados.copy()
        df_pdf = df_pdf.sort_values('Semestre')
        
        # Formata semestre para string
        df_pdf['Semestre'] = df_pdf['Semestre'].apply(lambda x: f"{int(x)}º Semestre")

        data_rows = [["Semestre", "Estudiantes (N)", "Promedio (TRAS)"]]
        
        for _, row in df_pdf.iterrows():
            data_rows.append([
                str(row['Semestre']),
                str(row['Estudiantes (N)']),
                f"{row['Promedio (TRAS)']:.2f}"
            ])

        col_widths = [6 * cm, 5 * cm, 5 * cm]
        
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

               # --- Rodapé e Explicações ---
        story.append(Spacer(1, 20))
        small_style = styles["Normal"].clone('small')
        small_style.fontSize = 9
        small_style.leading = 12 
        small_style.textColor = colors.grey

        story.append(Paragraph("<b>Tasa de Rendimiento Académico (TRA)</b>", small_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Está definido por el promedio de la calificación obtenido por el estudiante "
            "en las materias en las cuales ha presentado exámenes, independientemente del tipo de examen "
            "(<i>Chaín, 1995</i>).", small_style))

        story.append(Paragraph(
            "Se calcula por estudiante, por asignatura, por semestre y general, por generación o cohorte.",
            small_style))
        story.append(Spacer(1, 8))

        # Subtítulo
        story.append(Paragraph("<b>Rendimiento Académico por Semestre(TRAS)</b>", small_style))
        story.append(Spacer(1, 8))

        # Fórmula estilizada no PDF
        formula = Paragraph(
            "<para align='center'>"
            "<b>TRAS<sub>(1)</sub> = "
            "<font face='Courier-Bold'>[TRASE<sub>(1)</sub> + TRASE<sub>(2)</sub> + TRASE<sub>(3)</sub> +... + TRASE<sub>(n)</sub>/ N</font></b>"
            "</para>",
            small_style
        )

        story.append(formula)
        story.append(Spacer(1, 6))


        story.append(Paragraph("<b>Donde:</b>", small_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph("<b>TRAS(1):</b> Tasa de Rendimiento Académico del Semestre (TRAS) (debe ser calculada en cada semestre).", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>TRASE(1):</b> Tasa de Rendimiento Académico del Semestre del Estudiante 1.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>TRASE(2):</b> Tasa de Rendimiento Académico del Semestre del Estudiante 2.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>TRASE(3):</b> Tasa de Rendimiento Académico del Semestre del Estudiante 3.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>TRASE(n):</b> Tasa de Rendimiento Académico del Semestre del Estudiante 'n'.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>N:</b> Número de datos (cantidad de estudiantes con rendimiento académico en el semestre).", small_style))


        # --- Construir ---
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    # ============================================================
    # GERACAO E DOWNLOADS
    # ============================================================

    # 1. Gerar PDF
    dados_pdf = gerar_pdf_tras(df_display, cohorte_sel)

    # 2. Gerar Excel (Formatado)
    buffer_excel = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer_excel, engine='xlsxwriter') as writer:
            
            # Formata Semestre antes de exportar
            df_export = df_display.copy()
            if "Semestre_Fmt" in df_export.columns:
                 df_export["Semestre"] = df_export["Semestre_Fmt"]
                 df_export = df_export.drop(columns=["Semestre_Fmt"])
            else:
                 df_export["Semestre"] = df_export["Semestre"].apply(lambda x: f"{int(x)}º Semestre")
            
            df_export.to_excel(writer, index=False, sheet_name='TRAS')
            workbook = writer.book
            worksheet = writer.sheets['TRAS']
            
            num_fmt = workbook.add_format({'num_format': '0.00'})
            
            for i, col in enumerate(df_export.columns):
                max_len = max(df_export[col].astype(str).map(len).max(), len(col)) + 2
                if col == "Promedio (TRAS)":
                    worksheet.set_column(i, i, max_len, num_fmt)
                else:
                    worksheet.set_column(i, i, max_len)
    except:
        with pd.ExcelWriter(buffer_excel) as writer:
             df_export = df_display.copy()
             df_export["Semestre"] = df_export["Semestre"].apply(lambda x: f"{int(x)}º Semestre")
             df_export.to_excel(writer, index=False, sheet_name='TRAS')

    dados_excel = buffer_excel.getvalue()

    # 3. Botões
    st.divider()
    col_pdf, col_excel = st.columns(2, gap="medium")

    with col_pdf:
        st.download_button(
            label="Descargar Reporte (PDF)",
            data=dados_pdf,
            file_name=f"Reporte_TRAS_{cohorte_sel}.pdf",
            mime="application/pdf",
            icon=":material/download:",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Rendimiento Semestre", "PDF")
        )

    with col_excel:
        st.download_button(
            label="Descargar Datos (Excel)",
            data=dados_excel,
            file_name=f"Datos_TRAS_{cohorte_sel}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Rendimiento Semestre", "Excel")  
        )

    # ------------------------------------------------------------
    # 🔹 Explicação e Geração de Documentos
    # ------------------------------------------------------------
    st.divider()
    
    st.markdown("""        
    La *Tasa de Rendimiento Académico (TRA)* está definida por el promedio de la calificación obtenido por el estudiante en las materias en las cuales ha presentado exámenes, independientemente del tipo de examen (*Chaín, 1995*).
    En este caso **se calcula el rendimiento académico por estudiantes en forma individual, por asignatura, por semestre y general, por generación o cohorte.**
    De acuerdo con el razonamiento anterior, los cálculos quedan como sigue:
                
    """)

    st.markdown("""
    ### Tasa de Rendimiento Académico por Semestre (TRAS)
    """)

    st.latex(r"""
    \text{TRAS(1)} = \frac{\text{TRASE}_{(1)} + \text{TRASE}_{(2)} + \text{TRASE}_{(3)} + \dots + \text{TRASE}_{(n)}}{N}
    """)

    st.markdown("""
    **Donde:**

    - **TRAS(1):** Tasa de Rendimiento Académico del Semestre (TRAS) (debe ser calculada en cada semestre).  
    - **TRASE(1):** Tasa de Rendimiento Académico del Semestre del Estudiante 1.
    - **TRASE(2):** Tasa de Rendimiento Académico del Semestre del Estudiante 2.
    - **TRASE(3):** Tasa de Rendimiento Académico del Semestre del Estudiante 3.
    - **TRASE(n):** Tasa de Rendimiento Académico del Semestre del Estudiante "n".
    - **N:** Número de datos (cantidad de estudiantes con rendimiento académico en el semestre).  
    """)