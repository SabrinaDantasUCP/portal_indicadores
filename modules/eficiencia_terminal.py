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
import modules.rend_acad_alumno as raa

def render():
    st.subheader("Eficiencia Terminal (ET)")

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
            df = pd.read_csv(
                "assets/data/alumnos.csv", 
                sep=",", 
                dtype={
                    'periodo_egresso_format': str, 
                    'estado_titulacion': str
                },
                parse_dates=['fecha_titulacion'], # O Pandas já tenta converter para data aqui
                low_memory=False
            )
            df.columns = df.columns.str.strip()
            # Filtrar por CDE conforme padrão de outros módulos
            df = df[df["filial_periodo_letivo"].isin(["CDE", "CDE III"])].copy()
            return df
        except FileNotFoundError:
            st.error("Archivo de datos no encontrado.")
            return pd.DataFrame()

    df = load_data()
    if df.empty:
        return

    # Colunas necessárias
    COL_COHORTE = "cohorte"
    COL_ID_ALUMNO = "usuarios_id"
    COL_NOMBRE = "nome_sobrenome"
    COL_CATRACA = "numero_catraca"
    COL_SEMESTRE_ALUMNO = "semestre_alumno"
    COL_PERIODO_EGRESSO = "periodo_egresso_format"
    COL_ANO_FINAL_COHORTE = "ano_final_coorte"

    # --- Lógica de Cálculo da Eficiência Terminal ---
    
    # 1. Identificar EIIC (Ingressantes da coorte no 1º semestre)
    # Incluimos Nombre y Catraca para el listado detallado
    eiic_df = df[df[COL_SEMESTRE_ALUMNO].astype(float) == 1].groupby([COL_COHORTE, COL_ID_ALUMNO]).first().reset_index()
    
    # 2. Identificar ECE (Egressos em tempo regular daquela coorte)
    # Primero buscamos los egresados usando periodo_egresso_format
    # Si periodo_egresso_format está vacío, el alumno aún no finalizó
    egressos_df = df.dropna(subset=[COL_PERIODO_EGRESSO]).groupby([COL_COHORTE, COL_ID_ALUMNO]).first().reset_index()
    
    # Cruzamos con los ingressantes (EIIC) para garantizar que son de la misma coorte
    # Y verificamos si el periodo_egresso_format <= ano_final_coorte
    ece_df = pd.merge(eiic_df[[COL_COHORTE, COL_ID_ALUMNO, COL_ANO_FINAL_COHORTE]], 
                      egressos_df[[COL_ID_ALUMNO, COL_PERIODO_EGRESSO]], 
                      on=COL_ID_ALUMNO, how="inner")
    
    # Converter para numérico para comparación cronológica (Ej: 2023.1 <= 2024.1)
    ece_df[COL_PERIODO_EGRESSO] = pd.to_numeric(ece_df[COL_PERIODO_EGRESSO], errors='coerce')
    ece_df[COL_ANO_FINAL_COHORTE] = pd.to_numeric(ece_df[COL_ANO_FINAL_COHORTE], errors='coerce')
    
    ece_df = ece_df[ece_df[COL_PERIODO_EGRESSO] <= ece_df[COL_ANO_FINAL_COHORTE]]

    # --- Identificar Cohortes que completaron 12 semestres ---
    cohortes_completas = df.groupby(COL_COHORTE)[COL_SEMESTRE_ALUMNO].max()
    cohortes_completas = cohortes_completas[cohortes_completas >= 12].index.tolist()

    # 3. Agrupar Resultados por Cohorte
    resumen_eiic = eiic_df.groupby(COL_COHORTE)[COL_ID_ALUMNO].count().reset_index(name="EIIC")
    resumen_ece = ece_df.groupby(COL_COHORTE)[COL_ID_ALUMNO].count().reset_index(name="ECE")
    
    resumen_et = pd.merge(resumen_eiic, resumen_ece, on=COL_COHORTE, how="left").fillna(0)
    resumen_et["ECE"] = resumen_et["ECE"].astype(int)
    resumen_et["EIIC"] = resumen_et["EIIC"].astype(int)
    
    # --- Aplicar Filtro de 12 Semestres (Requisito: ciclo completo) ---
    resumen_et = resumen_et[resumen_et[COL_COHORTE].isin(cohortes_completas)]
    
    resumen_et["ET (%)"] = (resumen_et["ECE"] / resumen_et["EIIC"]) * 100
    resumen_et = resumen_et.sort_values(COL_COHORTE)

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

    def gerar_pdf_et(df_dados, cohorte_atual, et_valor, eiic_valor, ece_valor):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=4 * cm, bottomMargin=2 * cm
        )

        story = []
        styles = getSampleStyleSheet()

        story.append(Paragraph("<b>Reporte de Eficiencia Terminal (ET)</b>", styles["Title"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>Cohorte:</b> {cohorte_atual}", styles["Normal"]))
        story.append(Spacer(1, 15))

        # --- KPI ET ---
        data_kpi = [[f"ET: {et_valor:.2f}%"]]
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

        # Detalhes complementares
        story.append(Paragraph(f"<b>Inicíantes (EIIC):</b> {int(eiic_valor)}", styles["Normal"]))
        story.append(Paragraph(f"<b>Egresados Regulares (ECE):</b> {int(ece_valor)}", styles["Normal"]))
        story.append(Spacer(1, 15))

        story.append(Spacer(1, 20))

        # --- Metodología ---
        small_style = styles["Normal"].clone('small')
        small_style.fontSize = 9
        small_style.leading = 12
        small_style.textColor = colors.grey

        story.append(Paragraph("<b>Metodología de Eficiencia Terminal (ET)</b>", small_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "La Eficiencia Terminal es la relación porcentual entre los egresados de un nivel educativo dado y el número de estudiantes que ingresaron al primer curso de este nivel educativo “n” años antes (Camarena et al., 1985).",
            small_style
        ))
        story.append(Spacer(1, 6))
        
        formula = Paragraph(
            "<para align='center'>ET = [ ECE / EIIC ] x 100</para>",
            small_style
        )
        story.append(formula)
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Donde:</b>", small_style))
        story.append(Paragraph("<b>ET:</b> Eficiencia Terminal.", small_style))
        story.append(Paragraph("<b>ECE:</b> Número de Estudiantes de la Cohorte que Egresan en el tiempo estipulado por el plan de estudios (egresados regulares).", small_style))
        story.append(Paragraph("<b>EIIC:</b> Número de Estudiantes que se Inscriben al Inicio de la Carrera (matriculados en el primer semestre).", small_style))

        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    def gerar_pdf_et_comparativo(df_dados):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=4 * cm, bottomMargin=2 * cm
        )

        story = []
        styles = getSampleStyleSheet()

        story.append(Paragraph("<b>Comparativo de Eficiencia Terminal (ET)</b>", styles["Title"]))
        story.append(Spacer(1, 15))

        # Tabela
        data_rows = [["COHORTE", "EIIC", "ECE", "ET (%)"]]
        
        for _, row in df_dados.iterrows():
            data_rows.append([
                str(row['cohorte']),
                str(int(row['EIIC'])),
                str(int(row['ECE'])),
                f"{row['ET (%)']:.2f}%"
            ])

        col_widths = [8 * cm, 4 * cm, 4 * cm, 4 * cm]
        
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
        story.append(Spacer(1, 25))

        # --- Metodología ---
        small_style = styles["Normal"].clone('small')
        small_style.fontSize = 9
        small_style.leading = 12
        small_style.textColor = colors.grey

        story.append(Paragraph("<b>Metodología de Eficiencia Terminal (ET)</b>", small_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "La Eficiencia Terminal es la relación porcentual entre los egresados de un nivel educativo dado y el número de estudiantes que ingresaron al primer curso de este nivel educativo “n” años antes (Camarena et al., 1985).",
            small_style
        ))
        story.append(Spacer(1, 6))
        
        formula = Paragraph(
            "<para align='center'>ET = [ ECE / EIIC ] x 100</para>",
            small_style
        )
        story.append(formula)
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Donde:</b>", small_style))
        story.append(Paragraph("<b>ET:</b> Eficiencia Terminal.", small_style))
        story.append(Paragraph("<b>ECE:</b> Número de Estudiantes de la Cohorte que Egresan en el tiempo estipulado por el plan de estudios (egresados regulares).", small_style))
        story.append(Paragraph("<b>EIIC:</b> Número de Estudiantes que se Inscriben al Inicio de la Carrera (matriculados en el primer semestre).", small_style))

        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    # -------------------------------------------------------------------------
    # TABS
    # -------------------------------------------------------------------------
    tab1, tab2 = st.tabs(["Comparativo Global", "Detalle por Cohorte"])

    with tab1:
        st.markdown("### Eficiencia Terminal entre Cohortes")
        st.info("Este indicador se calcula únicamente para las **cohortes que ya han completado los 12 semestres** del plan de estudios.")
        
        fig_global = px.bar(
            resumen_et, 
            x=COL_COHORTE, 
            y="ET (%)", 
            text_auto='.2f',
            labels={"ET (%)": "Eficiencia Terminal (%)", COL_COHORTE: "Cohorte"},
            color="ET (%)",
            color_continuous_scale="Viridis"
        )
        fig_global.update_traces(textposition='outside')
        st.plotly_chart(fig_global, use_container_width=True)
        
        st.dataframe(
            resumen_et.rename(columns={COL_COHORTE: "COHORTE"}).style.format({"ET (%)": "{:.2f}%"}),
            width="stretch",
            hide_index=True
        )

        # Download Buttons tab 1
        st.divider()
        c1, c2 = st.columns(2)
        pdf_bytes_all = gerar_pdf_et_comparativo(resumen_et)
        
        # Excel
        buffer_excel_all = io.BytesIO()
        with pd.ExcelWriter(buffer_excel_all, engine='xlsxwriter') as writer:
            resumen_et.to_excel(writer, index=False, sheet_name='ET Global')
        excel_bytes_all = buffer_excel_all.getvalue()

        with c1:
            st.download_button("Descargar Reporte (PDF)", data=pdf_bytes_all, file_name="Reporte_ET_Comparativo.pdf", mime="application/pdf", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia Terminal - Comparativo", "PDF"))
        with c2:
            st.download_button("Descargar Datos (Excel)", data=excel_bytes_all, file_name="Dados_ET_Comparativo.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia Terminal - Comparativo", "Excel"))

    with tab2:
        cohortes_list = sorted(resumen_et[COL_COHORTE].unique().tolist())
        cohorte_sel = st.selectbox("Seleccione una Cohorte (Ciclo Completo)", cohortes_list, index=None)

        if cohorte_sel:
            # Filtrar dados para a coorte selecionada
            dados_sel = resumen_et[resumen_et[COL_COHORTE] == cohorte_sel].iloc[0]
            
            # Cards KPI
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Eficiencia Terminal", f"{dados_sel['ET (%)']:.2f}%")
            with col_b:
                st.metric("Ingresantes (EIIC)", int(dados_sel['EIIC']))
            with col_c:
                st.metric("Egresados Regulares (ECE)", int(dados_sel['ECE']))

            st.divider()
            
            # --- Listado de Alumnos (Solicitado por el usuario) ---
            st.markdown("### Listado de Alumnos de la Cohorte")
            
            # Preparar dataframe de la lista
            # Marcamos quién es egresado regular cruzando con ece_df
            lista_alumnos = eiic_df[eiic_df[COL_COHORTE] == cohorte_sel][[COL_NOMBRE, COL_CATRACA, COL_ID_ALUMNO]].copy()
            ids_ece = ece_df[ece_df[COL_COHORTE] == cohorte_sel][COL_ID_ALUMNO].unique()
            
            lista_alumnos["¿Egresado Regular?"] = lista_alumnos[COL_ID_ALUMNO].apply(lambda x: "Sí" if x in ids_ece else "No")
            
            # Renombrar para visualización
            lista_view = lista_alumnos.rename(columns={
                COL_NOMBRE: "Nombre y Apellido",
                COL_CATRACA: "Catraca"
            })[[ "Nombre y Apellido", "Catraca", "¿Egresado Regular?"]].sort_values("Nombre y Apellido")
            
            st.dataframe(
                lista_view,
                width="stretch",
                hide_index=True
            )

            # --- Ventana Modal para Perfil del Aluno ---
            @st.dialog("Perfil Académico del Estudiante", width="large")
            def mostrar_perfil_detalhado(id_alumno, df_local):
                # Filtrar os dados do aluno específico
                # Usamos a lógica do raa (Rendimento Acadêmico Aluno)
                df_student = df_local[df_local[raa.COL_ID_ALUMNO] == id_alumno].copy()
                if not df_student.empty:
                    raa.render_alumno_details(df_student, df_local)
                else:
                    st.error("No se encontraron datos para este estudiante.")

            st.divider()
            
            st.write("#### Consultar Histórico Detallado")
            col_sel, col_btn = st.columns([2, 1])
            
            with col_sel:
                # Criar lista de opções ordenada alfabeticamente (Nome - ID)
                opciones_alumnos = {f"{row[COL_NOMBRE]} ({row[COL_CATRACA]})": row[COL_ID_ALUMNO] for _, row in lista_alumnos.sort_values(COL_NOMBRE).iterrows()}
                alumno_a_consultar = st.selectbox("Busque un alumno para ver su historial", options=list(opciones_alumnos.keys()), index=None, placeholder="Escriba el nombre del alumno...")
            
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Ver Perfil Académico", icon=":material/person_search:", width="stretch", disabled=not alumno_a_consultar):
                    id_sel = opciones_alumnos[alumno_a_consultar]
                    mostrar_perfil_detalhado(id_sel, df)

            st.divider()
            
            # Downloads tab 2
            pdf_bytes_sel = gerar_pdf_et(resumen_et, cohorte_sel, dados_sel['ET (%)'], dados_sel['EIIC'], dados_sel['ECE'])
            
            buffer_excel_sel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel_sel, engine='xlsxwriter') as writer:
                # Hoja de Resumen
                pd.DataFrame([dados_sel]).to_excel(writer, index=False, sheet_name='Resumen ET')
                # Hoja de Listado Detallado (Nueva)
                lista_view.to_excel(writer, index=False, sheet_name='Listado Alumnos')
                
                # Formato básico
                workbook = writer.book
                ws_list = writer.sheets['Listado Alumnos']
                ws_list.set_column(0, 0, 40) # Nombre
                ws_list.set_column(1, 1, 15) # Catraca
                ws_list.set_column(2, 2, 20) # Status
                
            excel_bytes_sel = buffer_excel_sel.getvalue()

            c3, c4 = st.columns(2)
            with c3:
                st.download_button("Descargar Reporte (PDF)", data=pdf_bytes_sel, file_name=f"Reporte_ET_{cohorte_sel}.pdf", mime="application/pdf", icon=":material/download:", width="stretch", key="pdf_sel", on_click=db_pia.log_export_callback, args=("Eficiencia Terminal", "PDF"))
            with c4:
                st.download_button("Descargar Datos (Excel)", data=excel_bytes_sel, file_name=f"Dados_ET_{cohorte_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", key="excel_sel", on_click=db_pia.log_export_callback, args=("Eficiencia Terminal", "Excel"))

    # Explicação Final
    st.divider()
    st.markdown("""
    ### Metodología de Eficiencia Terminal (ET)
    
    La **Eficiencia Terminal** es la relación porcentual entre los egresados de un nivel educativo dado y el número de estudiantes que ingresaron al primer curso de este nivel educativo “n” años antes (Camarena et al., 1985).
    """)
    
    st.latex(r"ET = \frac{ECE}{EIIC} \times 100")
    
    st.markdown("""
    **Donde:**
    - **ET:** Eficiencia Terminal.
    - **ECE:** Número de Estudiantes de la Cohorte que Egresan en el tiempo estipulado por el plan de estudios (egresados regulares).
    - **EIIC:** Número de Estudiantes que se Inscriben al Inicio de la Carrera (matriculados en el primer semestre).
    """)

    st.divider()
    
    col_inf, col_btn = st.columns([3, 1], vertical_alignment="center")
    
    with col_inf:
        st.markdown('<p style="color: #4f4f4f; font-size: 0.85rem; margin-bottom: 0;">Los datos de titulados y egresados están basados en los datos enviados por la Secretaria General Académica el día 09/01/2026.</p>', unsafe_allow_html=True)
    
    with col_btn:
        from utils.excel_export import get_egresados_excel_bytes
        egresados_data = get_egresados_excel_bytes()
        if egresados_data:
            st.download_button(
                label="Planilla de Egresados",
                data=egresados_data,
                file_name="egresados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                icon=":material/download:",
                on_click=db_pia.log_export_callback, args=("Planilla de Egresados", "Excel")
            )
