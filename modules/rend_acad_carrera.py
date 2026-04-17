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
# Pagina: Tasa de Rendimiento Academico de la Carrera (TRC)
# ------------------------------------------------------------
def render():
    st.subheader("Rendimiento Académico de la Carrera")

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
    # 🧩 Colunas
    # ------------------------------------------------------------
    # ------------------------------------------------------------
    # 🧩 Colunas
    # ------------------------------------------------------------
    COL_COHORTE = "cohorte"
    COL_SEMESTRE = "semestre_alumno"
    COL_CALIFICACION = "calificacion_final_1a5"
    COL_ID_ALUMNO = "usuarios_id"
    COL_TIPO_DISCIPLINA = "tipo_disciplina"
    COL_FILIAL = "filial_periodo_letivo"

    # Tratamento de strings
    COL_TIPO_DISCIPLINA = "tipo_disciplina"
    COL_FILIAL = "filial_periodo_letivo"

    # Tratamento de strings
    df[COL_COHORTE] = df[COL_COHORTE].astype(str).str.strip()
    
    # Converter semestre para número para ordenação correta (1 a 12)
    # Garante que seja numérico, forçando erros a NaN e depois dropando ou preenchendo se necessário
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
    
    # 2. SEMESTRE (Ordenacion 1-12)
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
    # Calculo do TRC (Carrera)
    # ------------------------------------------------------------
    
    # PASSO 1: TRASE (Média Aluno/Semestre)
    df_trase = (
        df_filtrado
        .groupby([COL_COHORTE, COL_SEMESTRE, COL_ID_ALUMNO])
        .agg(TRASE=(COL_CALIFICACION, "mean"))
        .reset_index()
    )

    # PASSO 2: TRAS (Média do Semestre baseada nos alunos)
    df_tras = (
        df_trase
        .groupby([COL_COHORTE, COL_SEMESTRE])
        .agg(
            TRAS=("TRASE", "mean"),
            N_ALUNOS=(COL_ID_ALUMNO, "count")
        )
        .reset_index()
    )

    # PASSO 3: TRC (Média da Carreira baseada nos Semestres)
    trc_valor = df_tras["TRAS"].mean() # Média simples dos TRAS conforme fórmula
    
    # Preparando DF para exibição (Detalhamento por semestre)
    df_display = df_tras.copy()
    
    # Ordenação dos semestres
    df_display = df_display.sort_values(COL_SEMESTRE)
    
    # Formatação da coluna semestre para exibição (Ex: 1 -> "1º Semestre")
    df_display[COL_SEMESTRE] = df_display[COL_SEMESTRE].apply(lambda x: f"{int(x)}º Semestre")
    
    # Renomeação
    mapa_colunas = {
        COL_COHORTE: "Cohorte",
        COL_SEMESTRE: "Semestre",
        "N_ALUNOS": "Estudiantes(N)",
        "TRAS": "Rendimiento Semestral (TRAS)"
    }
    df_display = df_display.rename(columns=mapa_colunas)

    st.divider()

    # ------------------------------------------------------------
    # KPI PRINCIPAL (TRC)
    # ------------------------------------------------------------
    
    # Layout centralizado para o número principal
    st.markdown(f"""
    <div style="
        display: flex; 
        justify-content: center; 
        align-items: center; 
        margin-bottom: 30px;
    ">
        <div style="
            background-color: #004080;
            color: white;
            padding: 30px 50px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            max-width: 600px;
            width: 100%;
        ">
            <h2 style="margin: 0; font-size: 20px; font-weight: 400; opacity: 0.9;">Tasa de Rendimiento de la Carrera (TRC)</h2>
            <h1 style="margin: 10px 0 0 0; font-size: 56px; font-weight: 700;">{trc_valor:.2f}</h1>
            <p style="margin-top: 10px; font-size: 25px; opacity: 0.8;">Cohorte: {cohorte_sel}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ------------------------------------------------------------
    # Detalhamento (Breakdown por Semestre)
    # ------------------------------------------------------------
    st.subheader("Desglose por Semestre")
    
    # 1. Ordenação correta dos semestres (Já ordenado antes de formatar, mas garantindo pela string formatada se necessário ou uso do índice original se preservado. 
    # Como já está ordenado no df_display, seguimos a ordem do DF.)
    
    # 2. Loop para criar o grid de 2 colunas
    semestres_list = df_display["Semestre"].tolist()
    
    for i in range(0, len(semestres_list), 2):
        cols = st.columns(2)
        batch = semestres_list[i:i+2] # Pega pares de semestres
        
        for idx, semestre in enumerate(batch):
            # Filtra dados do semestre específico
            row_data = df_display[df_display["Semestre"] == semestre].iloc[0]
            val_tras = row_data["Rendimiento Semestral (TRAS)"]
            val_n = row_data["Estudiantes(N)"]
            
            with cols[idx]:
                # HTML do Card (Estilo Limpo e Profissional)
                card_html = f"""
                <div style="
                border: 1px solid #e0e0e0;
                border-radius: 12px;
                background-color: #ffffff;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                overflow: hidden;
                font-family: sans-serif;
                ">
                <div style="
                background-color: #f8f9fa;
                padding: 12px 20px;
                border-bottom: 1px solid #e0e0e0;
                display: flex;
                justify-content: space-between;
                align-items: center;
                ">
                <span style="font-weight: 700; color: #333; font-size: 16px;">
                {semestre}

                </div>
                    
                <div style="padding: 20px; display: flex; justify-content: space-around; align-items: center;">                
                <div style="text-align: center; flex: 1;">
                <div style="font-size: 11px; text-transform: uppercase; color: #888; font-weight: 600; margin-bottom: 4px;">                            Promedio
                </div>
                <div style="font-size: 28px; font-weight: 800; color: #004080;">
                {val_tras:.2f}
                </div>
                </div>
                        
                <div style="width: 1px; height: 35px; background-color: #eee;"></div>
                
                <div style="text-align: center; flex: 1;">
                <div style="font-size: 11px; text-transform: uppercase; color: #888; font-weight: 600; margin-bottom: 4px;">
                Estudiantes
                </div>
                 <div style="font-size: 28px; font-weight: 800; color: #444;">
                {val_n}
                </div>
                </div>
                
                </div>
                </div>
                """
                
                # Renderiza o HTML (unsafe_allow_html=True é essencial)
                st.markdown(card_html, unsafe_allow_html=True)

    # ------------------------------------------------------------
    # 🔹 Explicação e Geração de Documentos
    # ------------------------------------------------------------


    # ============================================================
    # CONFIGURACAO DO PDF (ReportLab - TRC)
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

    def gerar_pdf_trc(df_dados, cohorte_atual, trc_valor):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=4 * cm, bottomMargin=2 * cm
        )

        story = []
        styles = getSampleStyleSheet()


        story.append(Paragraph("<b>Reporte de Rendimiento Académico de la Carrera (TRC)</b>", styles["Title"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>Cohorte:</b> {cohorte_atual}", styles["Normal"]))
        story.append(Spacer(1, 15))

        # --- GRANDE NÚMERO NO PDF ---
        # Tabela simples para destacar o TRC
    # --- KPI TRC ---

        data_kpi = [[f"TRC: {trc_valor:.2f}"]]
        t_kpi = Table(data_kpi, colWidths=[20*cm])
        t_kpi.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#004080')),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # Centraliza verticalmente
            
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 24),
            ('LEADING', (0,0), (-1,-1), 28), # <--- IMPORTANTE: Ajusta a altura da linha para o texto não "cair"
            
            # Reduzi o padding para a caixa ficar menos alta
            ('BOTTOMPADDING', (0,0), (-1,-1), 8), 
            ('TOPPADDING', (0,0), (-1,-1), 8),
            
            ('ROUNDEDCORNERS', [10, 10, 10, 10]), 
        ]))
        story.append(t_kpi)

        story.append(Spacer(1, 15))

        story.append(Paragraph("<b>Detalle por Semestre (TRAS)</b>", styles["Heading3"]))
        story.append(Spacer(1, 10))

        # Tabela de Detalhes
        data_rows = [["Semestre", "Estudiantes(N)", "Promedio (TRAS)"]]
        
        for _, row in df_dados.iterrows():
            data_rows.append([
                str(row['Semestre']),
                str(row['Estudiantes(N)']),
                f"{row['Rendimiento Semestral (TRAS)']:.2f}"
            ])

        col_widths = [8 * cm, 6 * cm, 6 * cm]
        
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

        # Explicação
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
        story.append(Paragraph("<b>Tasa de Rendimiento Académico de la Carrera, promedio (TRC)</b>", small_style))
        story.append(Spacer(1, 8))

        # Fórmula estilizada no PDF
        formula = Paragraph(
            "<para align='center'>"
            "<b>TRC = "
            "<font face='Courier-Bold'>[TRAS<sub>(1)</sub> + TRAS<sub>(2)</sub> + TRAS<sub>(3)</sub> +... + TRAS<sub>(n)</sub>/ N</font></b>"
            "</para>",
            small_style
        )

        story.append(formula)
        story.append(Spacer(1, 6))


        story.append(Paragraph("<b>Donde:</b>", small_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph("<b>TRC:</b> Tasa de Rendimiento Académico de la Carrera (calculada para la generación o cohorte).", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>TRAS(1):</b> Tasa de Rendimiento Académico del Primer Semestre.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>TRAS(2):</b> Tasa de Rendimiento Académico del Segundo Semestre.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>TRAS(3):</b> Tasa de Rendimiento Académico del Tercero Semestre.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>TRAS(n):</b> Tasa de Rendimiento Académico del Último Semestre", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>N:</b> Número de datos (cantidad de estudiantes con rendimiento académico en el semestre).", small_style))

        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    # ============================================================
    # 📥 GERAÇÃO E DOWNLOADS
    # ============================================================

    # 1. Gerar PDF
    dados_pdf = gerar_pdf_trc(df_display, cohorte_sel, trc_valor)

    # 2. Gerar Excel (Formatado)
    buffer_excel = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer_excel, engine='xlsxwriter') as writer:
            # Aba Detalhada
            df_display.to_excel(writer, index=False, sheet_name='Detalle Semestres')
            
            # Aba Resumo
            df_resumo = pd.DataFrame([{"Cohorte": cohorte_sel, "TRC": trc_valor}])
            df_resumo.to_excel(writer, index=False, sheet_name='Resumen TRC')
            
            workbook = writer.book
            
            # Formatação
            num_fmt = workbook.add_format({'num_format': '0.00'})
            
            # Formata Aba Detalhe
            ws_det = writer.sheets['Detalle Semestres']
            for i, col in enumerate(df_display.columns):
                max_len = max(df_display[col].astype(str).map(len).max(), len(col)) + 2
                if "TRAS" in col:
                    ws_det.set_column(i, i, max_len, num_fmt)
                else:
                    ws_det.set_column(i, i, max_len)
                    
            # Formata Aba Resumo
            ws_res = writer.sheets['Resumen TRC']
            ws_res.set_column(1, 1, 15, num_fmt)

    except:
        with pd.ExcelWriter(buffer_excel) as writer:
             df_display.to_excel(writer, index=False, sheet_name='Datos TRC')

    dados_excel = buffer_excel.getvalue()

    # 3. Botões
    st.divider()
    col_pdf, col_excel = st.columns(2, gap="medium")

    with col_pdf:
        st.download_button(
            label="Descargar Reporte (PDF)",
            data=dados_pdf,
            file_name=f"Reporte_TRC_{cohorte_sel}.pdf",
            mime="application/pdf",
            icon=":material/download:",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Rendimiento Carrera", "PDF")
        )

    with col_excel:
        st.download_button(
            label="Descargar Datos (Excel)",
            data=dados_excel,
            file_name=f"Datos_TRC_{cohorte_sel}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Rendimiento Carrera", "Excel")  
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
    ### Tasa de Rendimiento Académico de la Carrera, promedio (TRC)
    """)
    
    st.latex(r"""
    \text{TRC} = \frac{\text{TRAS}_{(1)} + \text{TRAS}_{(2)} + \text{TRAS}_{(3)} + \dots + \text{TRAS}_{(n)}}{N}
    """)

    st.markdown("""
    **Donde:**
    
    * **TRC:** Tasa de Rendimiento Académico de la Carrera (calculada para la generación o **cohorte**).
    * **TRAS(1):** Tasa de Rendimiento Académico del Primer Semestre.
    * **TRAS(2):** Tasa de Rendimiento Académico del Segundo Semestre.
    * **TRAS(3):** Tasa de Rendimiento Académico del Tercero Semestre.            
    * **TRAS(n):** Tasa de Rendimiento Académico del Último Semestre.
    * **N:** Número de datos (cantidad de semestres establecidos en el plan de estudios o analizados).
    """)