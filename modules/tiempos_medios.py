import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime
from utils import db_pia
from utils.system_logging import log_exception
from utils.ui import (
    COLOR_ATENCION,
    COLOR_BUENO,
    COLOR_MALO,
    COLOR_PRIMARIO,
    PALETA_CATEGORICA,
    estilizar_figura,
    formatear_entero,
    formatear_porcentaje,
    opciones_cohorte,
    render_cabecera_indicador,
    render_tarjetas_kpi,
    render_titulo_seccion,
    render_egresados_fuente_caption,
)
from services.data.alumnos import load_current_alumnos
from services.calculations.eficiencia_academica import (
    COL_CATRACA,
    COL_COHORTE,
    COL_ID_ALUMNO,
    COL_NOMBRE,
    calculate_average_egress_time,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import modules.rend_acad_alumno as raa

def render():
    render_cabecera_indicador(
        "Tiempos Medios de Egreso (TME)",
        "Cantidad promedio de semestres que tardan en egresar los alumnos de cada cohorte. El plan de estudios prevé 12 semestres.",
    )


    df_full = load_current_alumnos(only_cde=False)
    df = load_current_alumnos()

    if df.empty:
        st.error("Archivo de datos no encontrado.")
        return

    egresados_df, tme_resumen, missing_cols = calculate_average_egress_time(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return
    if egresados_df.empty or tme_resumen.empty:
        st.warning("No hay datos suficientes para calcular los tiempos medios de egreso.")
        return

    # --- Funciones PDF ---
    def agregar_encabezado_y_pie(canvas, doc):
        canvas.saveState()
        width, height = landscape(A4)
        logo_path = None
        for p in ["assets/logo-ucp-icon.png", "assets/logo-ucp.png", "logo-ucp-icon.png"]:
            if os.path.exists(p): logo_path = p; break
        if logo_path:
            try: canvas.drawImage(logo_path, x=2*cm, y=height-2.5*cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
            except Exception as exc:
                log_exception("Error silencioso tratado en tiempos_medios.py", exc)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#004080"))
        canvas.drawString(5*cm, height-1.5*cm, "Universidad Central del Paraguay")
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.black)
        canvas.drawString(5*cm, height-2.1*cm, "Facultad de Ciencias de la Salud - Carrera de Medicina")
        canvas.setStrokeColor(colors.HexColor("#004080"))
        canvas.setLineWidth(1)
        canvas.line(2*cm, height-3.0*cm, width-2*cm, height-3.0*cm)
        canvas.restoreState()

    def gerar_pdf_tme(res_df):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=2*cm, rightMargin=2*cm, topMargin=4*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()
        story.append(Paragraph("<b>Reporte de Tiempos Medios de Egreso (TME)</b>", styles["Title"]))
        story.append(Spacer(1, 15))
        
        data = [["COHORTE", "Total Egresados", "TME (Semestres)", "TME (Años)", "Rango Semestres"]]
        for _, r in res_df.iterrows():
            data.append([
                str(r[COL_COHORTE]), 
                str(int(r['N_Egresados'])), 
                f"{r['TME_Semestres']:.2f}",
                f"{r['TME_Anos']:.2f}",
                f"{int(r['Min_Sem'])} - {int(r['Max_Sem'])}"
            ])
        
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#004080')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
        ]))
        story.append(t)
        story.append(Spacer(1, 25))

        # --- Metodología ---
        small_style = styles["Normal"].clone('small')
        small_style.fontSize = 9
        small_style.leading = 12
        small_style.textColor = colors.grey

        story.append(Paragraph("<b>Metodología de Tiempos Medios de Egreso (TME)</b>", small_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Calcula el promedio de semestres empleados por los graduados de una cohorte para completar su carrera.",
            small_style
        ))
        story.append(Spacer(1, 6))
        
        formula = Paragraph(
            "<para align='center'>TME = [ Σ Semestres_i ] / N</para>",
            small_style
        )
        story.append(formula)
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Donde:</b>", small_style))
        story.append(Paragraph("• <b>Semestres_i:</b> Tiempo transcurrido entre el ingreso y el egreso del alumno i.", small_style))
        story.append(Paragraph("• <b>N:</b> Cantidad total de egresados de la cohorte analizada.", small_style))

        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)

        return buffer.getvalue()

    # --- Interfaz Principal ---
    tab1, tab2 = st.tabs(["Comparativo Global", "Detalle por Cohorte"])

    with tab1:
        tme_general = egresados_df["Semestres"].mean()
        en_tiempo = (egresados_df["Semestres"] <= 12).mean() * 100
        render_tarjetas_kpi([
            {"etiqueta": "TME promedio", "valor": f"{tme_general:.1f} sem".replace(".", ","),
             "detalle": f"≈ {tme_general / 2:.1f} años".replace(".", ","),
             "color": COLOR_BUENO if tme_general <= 12 else COLOR_ATENCION},
            {"etiqueta": "Egresados analizados", "valor": formatear_entero(len(egresados_df))},
            {"etiqueta": "Egresan en 12 sem. o menos", "valor": formatear_porcentaje(en_tiempo),
             "detalle": "Dentro del tiempo del plan", "color": COLOR_BUENO},
            {"etiqueta": "Cohortes", "valor": len(tme_resumen)},
        ])
        render_titulo_seccion(
            "Tiempo medio de egreso por cohorte",
            "La línea punteada marca los 12 semestres del plan: los puntos por encima indican cohortes que, "
            "en promedio, tardaron más de lo previsto.",
        )

        # Gráfico de Tendencia
        fig_trend = px.line(tme_resumen, x=COL_COHORTE, y="TME_Semestres", markers=True,
                           text=tme_resumen["TME_Semestres"].map(lambda v: f"{v:.1f}".replace(".", ",")),
                           custom_data=["N_Egresados"],
                           labels={"TME_Semestres": "Promedio Semestres", COL_COHORTE: "Cohorte"})
        fig_trend.update_traces(line_color=COLOR_PRIMARIO, textposition="top center",
                                hovertemplate="<b>%{x}</b><br>TME: %{y:.1f} semestres<br>Egresados: %{customdata[0]}<extra></extra>")
        fig_trend.add_hline(y=12, line_dash="dot", line_color=COLOR_BUENO, annotation_text="Plan de estudios: 12 semestres",
                            annotation_position="bottom right")
        estilizar_figura(fig_trend, titulo_y="Semestres hasta egresar", altura=380, leyenda=False)
        st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})

        render_titulo_seccion("Detalle por cohorte")
        st.dataframe(tme_resumen[[COL_COHORTE, "N_Egresados", "TME_Semestres", "TME_Anos", "Min_Sem", "Max_Sem"]].rename(columns={
            COL_COHORTE: "COHORTE", 
            "N_Egresados": "Total Egresados",
            "TME_Semestres": "TME (Semestres)", 
            "TME_Anos": "TME (Años)", 
            "Min_Sem": "Mínimo Sem.", 
            "Max_Sem": "Máximo Sem."
        }), width="stretch", hide_index=True)

        st.divider()
        c1, c2 = st.columns(2)
        pdf_data = gerar_pdf_tme(tme_resumen)
        c1.download_button("Descargar Reporte (PDF)", data=pdf_data, file_name="Reporte_TME_Global.pdf", mime="application/pdf", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tiempos Medios de Egreso", "PDF"))
        
        buf_ex = io.BytesIO()
        with pd.ExcelWriter(buf_ex, engine='xlsxwriter') as wr:
            tme_resumen.to_excel(wr, index=False, sheet_name='TME Global')
            egresados_df[[COL_COHORTE, COL_NOMBRE, COL_CATRACA, "Semestres"]].to_excel(wr, index=False, sheet_name='Detalle Egresados')
        c2.download_button("Descargar Datos (Excel)", data=buf_ex.getvalue(), file_name="Datos_TME_Global.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tiempos Medios de Egreso", "Excel"))

    with tab2:
        coh_list = opciones_cohorte(tme_resumen[COL_COHORTE].unique())
        sel_coh = st.selectbox("Seleccione una Cohorte", options=coh_list, index=None)
        
        if sel_coh:
            data_coh = egresados_df[egresados_df[COL_COHORTE] == sel_coh]
            
            # --- Layout Premium: Métricas de Cohorte ---
            tme_coh = data_coh["Semestres"].mean()
            min_s = int(data_coh["Semestres"].min())
            max_s = int(data_coh["Semestres"].max())
            render_tarjetas_kpi([
                {"etiqueta": "Egresados", "valor": formatear_entero(len(data_coh))},
                {"etiqueta": "TME de la cohorte", "valor": f"{tme_coh:.1f} sem".replace(".", ","),
                 "color": COLOR_BUENO if tme_coh <= 12 else COLOR_ATENCION},
                {"etiqueta": "Más rápido / más lento", "valor": f"{min_s} – {max_s} sem"},
                {"etiqueta": "En 12 sem. o menos", "valor": formatear_porcentaje((data_coh["Semestres"] <= 12).mean() * 100),
                 "color": COLOR_BUENO},
            ])
            
            st.divider()

            # --- Distribución Visual ---
            render_titulo_seccion("¿Cuántos semestres tardaron?", "Cantidad de egresados según los semestres que les llevó egresar.")
            fig_hist = px.histogram(data_coh, x="Semestres", nbins=max(5, max_s - min_s + 1), text_auto=True,
                                   labels={"Semestres": "Número de Semestres", "count": "Alumnos"})
            fig_hist.update_traces(marker_color=COLOR_PRIMARIO, hovertemplate="%{x} semestres: %{y} egresados<extra></extra>")
            estilizar_figura(fig_hist, titulo_x="Semestres hasta egresar", titulo_y="Egresados", altura=340, leyenda=False)
            fig_hist.update_layout(bargap=0.1)
            st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})

            st.divider()

            # --- Listado de Egresados ---
            render_titulo_seccion("Egresados de la cohorte")
            lista_view = data_coh[[COL_NOMBRE, COL_CATRACA, "Semestres", COL_ID_ALUMNO]].rename(columns={
                COL_NOMBRE: "Nombre", COL_CATRACA: "Número de Matrícula", "Semestres": "Duración (Sem.)"
            }).sort_values("Duración (Sem.)")
            st.dataframe(lista_view.drop(columns=[COL_ID_ALUMNO]), width="stretch", hide_index=True)

            @st.dialog("Perfil Académico del Estudiante", width="large")
            def modal_perfil(uid, dff):
                ds = dff[dff[raa.COL_ID_ALUMNO] == uid].copy()
                if not ds.empty: raa.render_alumno_details(ds, dff)
            
            st.divider()
            render_titulo_seccion("Consultar historial de un alumno")
            col_sel, col_btn = st.columns([2, 1])
            with col_sel:
                dic_al = {f"{r[COL_NOMBRE]} ({r[COL_CATRACA]})": r[COL_ID_ALUMNO] for _, r in data_coh.sort_values(COL_NOMBRE).iterrows()}
                sel_al = st.selectbox("Busque un egresado para ver su historial", options=list(dic_al.keys()), index=None, placeholder="Escriba el nombre del alumno...", key="sel_tme")
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Ver Perfil Académico", icon=":material/person_search:", width="stretch", disabled=not sel_al, key="btn_tme"):
                    modal_perfil(dic_al[sel_al], df_full)

    st.divider()
    with st.expander("¿Cómo se calcula el Tiempo Medio de Egreso?", icon=":material/functions:"):
        st.markdown("""
        Calcula el promedio de semestres empleados por los graduados de una cohorte para completar su carrera.
        """)
        st.latex(r"TME = \frac{\sum_{i=1}^{N} Semestres_i}{N}")
        st.markdown("""
        **Donde:**
        - **Semestres_i:** Tiempo transcurrido entre el ingreso y el egreso del alumno *i*.
        - **N:** Cantidad total de egresados de la cohorte analizada.
        """)

    st.divider()
    
    col_inf, col_btn = st.columns([3, 1], vertical_alignment="center")
    
    with col_inf:
        render_egresados_fuente_caption()
    
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
