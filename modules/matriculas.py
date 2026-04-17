import streamlit as st
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import landscape
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import io
import os
from utils import db_pia

def render():
    st.subheader("Matrículas")

    # --- Cargar datos ---
    @st.cache_data
    def cargar_datos():
        df = pd.read_excel("assets/data/matriculados-20251.xlsx")
        df.columns = [c.strip().lower() for c in df.columns]
        return df

    df = cargar_datos()

    # --- Verifica columna ---
    if "quantidade_alunos" not in df.columns:
        st.error("⚠️ No se encontró la columna 'quantidade_alunos' en el archivo Excel.")
        st.stop()

    # --- Definir nombres de columnas ---
    COL_ANO       = "ano"
    COL_PERIODO   = "periodo_anual_nome"
    COL_SEMESTRE  = "semestre_nome"
    COL_DISC      = "disciplina_nome"
    COL_TURMA     = "turma_nome"
    COL_QTD       = "quantidade_alunos"

    st.subheader("Filtros")

    # --- Filtros dinámicos en cascada ---
    ano_vals      = sorted(df[COL_ANO].dropna().unique().tolist()) if COL_ANO in df.columns else []
    periodo_vals  = sorted(df[COL_PERIODO].dropna().unique().tolist()) if COL_PERIODO in df.columns else []
    semestre_vals = sorted(df[COL_SEMESTRE].dropna().unique().tolist()) if COL_SEMESTRE in df.columns else []

    col1, col2, col3 = st.columns(3)
    col4, col5 = st.columns(2)

    ano_sel      = col1.multiselect("Año", ano_vals)
    periodo_sel  = col2.multiselect("Período Anual", periodo_vals)
    semestre_sel = col3.multiselect("Semestre", semestre_vals)

    # Filtros dependientes (en cascada)
    df_temp = df.copy()
    if ano_sel:
        df_temp = df_temp[df_temp[COL_ANO].isin(ano_sel)]
    if periodo_sel:
        df_temp = df_temp[df_temp[COL_PERIODO].isin(periodo_sel)]
    if semestre_sel:
        df_temp = df_temp[df_temp[COL_SEMESTRE].isin(semestre_sel)]

    # Disciplinas disponíveis conforme semestre
    if semestre_sel:
        disc_vals = sorted(df_temp[df_temp[COL_SEMESTRE].isin(semestre_sel)][COL_DISC].dropna().unique().tolist())
    else:
        disc_vals = sorted(df_temp[COL_DISC].dropna().unique().tolist())

    disc_sel = col4.multiselect("Disciplina", disc_vals)

    # Turmas disponíveis conforme disciplina
    if disc_sel:
        turma_vals = sorted(df_temp[df_temp[COL_DISC].isin(disc_sel)][COL_TURMA].dropna().unique().tolist())
    else:
        turma_vals = sorted(df_temp[COL_TURMA].dropna().unique().tolist())

    turma_sel = col5.multiselect("Turma", turma_vals)

    # --- Aplicar filtros ---
    df_filtrado = df.copy()
    if ano_sel:
        df_filtrado = df_filtrado[df_filtrado[COL_ANO].isin(ano_sel)]
    if periodo_sel:
        df_filtrado = df_filtrado[df_filtrado[COL_PERIODO].isin(periodo_sel)]
    if semestre_sel:
        df_filtrado = df_filtrado[df_filtrado[COL_SEMESTRE].isin(semestre_sel)]
    if disc_sel:
        df_filtrado = df_filtrado[df_filtrado[COL_DISC].isin(disc_sel)]
    if turma_sel:
        df_filtrado = df_filtrado[df_filtrado[COL_TURMA].isin(turma_sel)]

    # --- Tabla resumen ---

    if not df_filtrado.empty:
        # Agrupar y sumar
        agrup_cols = [COL_ANO, COL_PERIODO, COL_SEMESTRE, COL_DISC, COL_TURMA]
        resumen = (
            df_filtrado
            .groupby(agrup_cols, dropna=False)[COL_QTD]
            .sum()
            .reset_index(name="Cantidad de Alumnos")
        )

        # Formata números com separador de milhar
        resumen["Cantidad de Alumnos"] = resumen["Cantidad de Alumnos"].apply(lambda x: f"{int(x):,}".replace(",", "."))

        # Renomeia colunas para exibição
        resumen_vista = resumen.rename(columns={
            "ano": "Año",
            "periodo_anual_nome": "Período Anual",
            "semestre_nome": "Semestre",
            "disciplina_nome": "Disciplina",
            "turma_nome": "Turma",
            "Cantidad de Alumnos": "Cantidad de Alumnos"
        })


        st.dataframe(resumen_vista, width="stretch", hide_index=True)
        st.markdown(
            """
            <style>
                /* Oculta o menu de opções (⋮) da tabela Streamlit */
                [data-testid="stElementToolbar"] {
                    display: none !important;
                }
            </style>
            """,
            unsafe_allow_html=True
)

        # --- Generar PDF ---
        # --- Generar PDF institucional con logo y fecha en todas las páginas ---
        from datetime import datetime
        from reportlab.lib.pagesizes import landscape
        from reportlab.pdfgen import canvas

        fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Caminho da logo
        logo_path = None
        for candidate in ["assets/logo-ucp-icon.png", "assets/logo-ucp-icon.png"]:
            if os.path.exists(candidate):
                logo_path = candidate
                break

        # --- Cabeçalho e rodapé para todas as páginas ---
        def agregar_encabezado_y_pie(canvas, doc):
            canvas.saveState()
            width, height = landscape(A4)

            # Logo (mantém proporção e evita distorção)
            if logo_path:
                try:
                    logo_width = 2 * cm
                    logo_height = 2 * cm
                    canvas.drawImage(
                        logo_path,
                        x=2 * cm,
                        y=height - 3.5 * cm,
                        width=logo_width,
                        height=logo_height,
                        preserveAspectRatio=True,
                        mask='auto'
                    )
                except Exception:
                    pass

            # Texto institucional
            canvas.setFont("Helvetica-Bold", 12)
            canvas.drawString(8.5 * cm, height - 2.2 * cm, "Universidad Central del Paraguay")
            canvas.setFont("Helvetica", 10)
            canvas.drawString(8.5 * cm, height - 2.8 * cm, "Reporte de Matrículas")

            # Rodapé com data
            canvas.setFont("Helvetica-Oblique", 9)
            canvas.drawRightString(width - 2 * cm, 1.5 * cm, f"Generado el {fecha_actual}")

            canvas.restoreState()

        # --- Gerar o PDF ---
        from reportlab.platypus import PageTemplate, Frame

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=4 * cm,   # espaço para o cabeçalho
            bottomMargin=2 * cm
        )
        story = []
        styles = getSampleStyleSheet()

        # --- Filtros aplicados ---
        filtros_texto = f"""
        <b>Filtros aplicados:</b><br/>
        Año: {', '.join(map(str, ano_sel)) if ano_sel else 'Todos'}<br/>
        Período Anual: {', '.join(map(str, periodo_sel)) if periodo_sel else 'Todos'}<br/>
        Semestre: {', '.join(map(str, semestre_sel)) if semestre_sel else 'Todos'}<br/>
        Disciplina: {', '.join(map(str, disc_sel)) if disc_sel else 'Todas'}<br/>
        Turma: {', '.join(map(str, turma_sel)) if turma_sel else 'Todas'}
        """
        story.append(Paragraph(filtros_texto, styles["Normal"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph("<b>Detalle de alumnos matriculados</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        # --- Tabela principal ---
        data_pdf = [resumen_vista.columns.tolist()] + resumen_vista.values.tolist()
        tabla = Table(data_pdf, repeatRows=1)
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004080')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ]))
        story.append(tabla)
        story.append(Spacer(1, 12))

        # --- Pie institucional ---
        story.append(Paragraph(
            "Universidad Central del Paraguay — Sistema de Gestión Académica", styles["Italic"]
        ))

        # --- Adicionar cabeçalho e rodapé em todas as páginas ---
        doc.build(
            story,
            onFirstPage=agregar_encabezado_y_pie,
            onLaterPages=agregar_encabezado_y_pie
        )

        pdf = buffer.getvalue()

        st.download_button(
            label="📄 Descargar reporte en PDF",
            data=pdf,
            file_name=f"reporte_matriculas_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            on_click=db_pia.log_export_callback, args=("Matrículas", "PDF")
        )

    else:
        st.warning("No se encontraron datos con los filtros seleccionados.")