import streamlit as st
import plotly.express as px
import io
import os
from datetime import datetime
from utils import db_pia
from utils.ui import (
    COLOR_ATENCION,
    COLOR_BUENO,
    COLOR_MALO,
    COLOR_PRIMARIO,
    PALETA_CATEGORICA,
    estilizar_figura,
    formatear_entero,
    formatear_porcentaje,
    render_cabecera_indicador,
    render_tarjetas_kpi,
    render_titulo_seccion,
)
from utils.system_logging import log_exception
from services.data.alumnos import load_current_alumnos
from services.calculations.tasa_desercion import (
    COL_COHORTE,
    calculate_semester_dropout,
    prepare_semester_enrollments,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

def render():
    render_cabecera_indicador(
        "Tasa de Deserción Semestral de la Cohorte (TDSC)",
        "Para una cohorte, qué porcentaje de los alumnos inscriptos en cada semestre ya no aparece en el semestre siguiente. Ayuda a detectar en qué momento de la carrera se pierden más alumnos.",
    )

    
    df = load_current_alumnos()
    if df.empty:
        st.error("Archivo de datos no encontrado.")
        return

    inscritos, missing_cols = prepare_semester_enrollments(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return
    if inscritos.empty:
        st.warning("No hay datos suficientes para calcular la deserción semestral.")
        return

    cohortes_list = sorted(inscritos[COL_COHORTE].unique().tolist())
    cohorte_sel = st.selectbox("Seleccione una Cohorte para ver la evolución semestral", cohortes_list, index=None,
                               placeholder="Elija una cohorte")
    if not cohorte_sel:
        st.info("Seleccione una **cohorte** para ver en qué semestres se produce la deserción.", icon=":material/touch_app:")

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
                log_exception("Error silencioso tratado en tasa_desercion_semestral.py", exc)
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
        df_tdsc = calculate_semester_dropout(inscritos, cohorte_sel)
        if df_tdsc.empty:
            st.warning("No hay datos suficientes para calcular la deserción semestral.")
        else:
            critico = df_tdsc.loc[df_tdsc["TDSC (%)"].idxmax()]
            render_tarjetas_kpi([
                {"etiqueta": "Inscriptos al inicio", "valor": formatear_entero(df_tdsc["EIS"].iloc[0]),
                 "detalle": f"Semestre {df_tdsc['Semestre'].iloc[0].split(' ')[0]}"},
                {"etiqueta": "Abandonos en total", "valor": formatear_entero(df_tdsc["EACS"].sum()), "color": COLOR_MALO},
                {"etiqueta": "Deserción promedio", "valor": formatear_porcentaje(df_tdsc["TDSC (%)"].mean(), 2),
                 "detalle": "Por cambio de semestre", "color": COLOR_ATENCION},
                {"etiqueta": "Paso más crítico", "valor": critico["Semestre"].replace("º -> ", "º → "),
                 "detalle": f"{formatear_porcentaje(critico['TDSC (%)'], 2)} de deserción", "color": COLOR_MALO},
            ])
            render_titulo_seccion(
                f"Deserción por cambio de semestre — cohorte {cohorte_sel}",
                "Cada barra muestra el porcentaje de alumnos de un semestre que no se inscribió en el siguiente.",
            )
            df_plot = df_tdsc.assign(
                Paso=df_tdsc["Semestre"].str.replace("º -> ", "º → ", regex=False),
                Etiqueta=df_tdsc["TDSC (%)"].map(lambda v: formatear_porcentaje(v, 2)),
            )
            fig = px.bar(df_plot, x="Paso", y="TDSC (%)", text="Etiqueta", custom_data=["EIS", "EACS"])
            fig.update_traces(marker_color=COLOR_MALO, textposition="outside", cliponaxis=False,
                              hovertemplate="<b>%{x}</b><br>Deserción: %{text}<br>Inscriptos: %{customdata[0]}"
                                            "<br>Abandonan: %{customdata[1]}<extra></extra>")
            estilizar_figura(fig, titulo_x="Cambio de semestre", titulo_y="Deserción", porcentaje=True, altura=380, leyenda=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
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
    with st.expander("¿Cómo se calcula la Deserción Semestral?", icon=":material/functions:"):
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

