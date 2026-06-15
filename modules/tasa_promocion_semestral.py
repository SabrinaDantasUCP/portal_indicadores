import streamlit as st
import plotly.express as px
import io
import os
from datetime import datetime
from utils import db_pia
from utils.system_logging import log_exception
from services.data.alumnos import load_current_alumnos
from services.calculations.tasa_promocion import (
    COL_ANO,
    COL_CATRACA,
    COL_COHORTE,
    COL_ID_ALUMNO,
    COL_NOMBRE,
    calculate_all_promotions,
    prepare_promotion_source,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import modules.rend_acad_alumno as raa

def render():
    st.subheader("Tasa de Promoción")

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
    
    df_full = load_current_alumnos(only_regular=True)
    if df_full.empty:
        st.error("Archivo de datos no encontrado.")
        return

    df, missing_cols = prepare_promotion_source(df_full)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return
    if df.empty:
        st.warning("No hay datos suficientes para calcular la tasa de promoción.")
        return

    df_master, df_detalles_master = calculate_all_promotions(df)
    if df_master.empty:
        st.warning("No hay datos suficientes para calcular la tasa de promoción.")
        return

    # 📄 PDF FUNCTIONS
    def agregar_encabezado_y_pie(canvas, doc):
        canvas.saveState()
        width, height = landscape(A4)
        logo_path = "assets/logo-ucp-icon.png" if os.path.exists("assets/logo-ucp-icon.png") else None
        if logo_path:
            try: canvas.drawImage(logo_path, x=2*cm, y=height-2.5*cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
            except Exception as exc:
                log_exception("Error silencioso tratado en tasa_promocion_semestral.py", exc)
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

    def gerar_pdf_tpr(df_dados, titulo, extra_text=""):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=2*cm, rightMargin=2*cm, topMargin=4*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()
        story.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
        story.append(Spacer(1, 15))

        cols = df_dados.columns.tolist()
        data_rows = [cols]
        for _, row in df_dados.iterrows():
            formatted_row = []
            for col in cols:
                val = row[col]
                if isinstance(val, float): formatted_row.append(f"{val:.2f}%")
                else: formatted_row.append(str(val))
            data_rows.append(formatted_row)

        tabla = Table(data_rows, repeatRows=1)
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
        story.append(Paragraph("La <b>Tasa de Promoción (TPr)</b> mide la proporción de estudiantes que avanzan de un semestre al siguiente en periodos consecutivos.", styles["Normal"]))
        story.append(Spacer(1, 5))
        story.append(Paragraph("<para align='center'>TPr = [ Σ EPr / Σ EIns ] x 100</para>", styles["Normal"]))
        story.append(Spacer(1, 10))
        if extra_text: story.append(Paragraph(extra_text, styles["Normal"]))
        
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    # --- UI ---
    tab_cohorte, tab_detalle = st.tabs(["Análisis por Cohorte", "Detalle de Alumnos"])

    with tab_cohorte:
        cohortes_disponibles = sorted(df_master["Cohorte"].unique(), reverse=True)
        cohorte_sel = st.selectbox("Seleccione una Cohorte", cohortes_disponibles, index=0)
        
        if cohorte_sel:
            df_c = df_master[df_master["Cohorte"] == cohorte_sel]
            
            # Ordenar transições numericamente para o gráfico e tabela
            df_c = df_c.sort_values("Transición", key=lambda x: x.str.extract(r'(\d+)')[0].astype(int))
            
            avg_semestral = df_c["TPr (%)"].mean()
            total_eins = df_c["EIns"].sum()
            total_epr = df_c["EPr"].sum()
            tpr_total = (total_epr / total_eins) * 100 if total_eins > 0 else 0

            c1, c2, c3 = st.columns(3)
            c1.metric("Promoción Total (Cohorte)", f"{tpr_total:.2f}%")
            c2.metric("Promedio Semestral", f"{avg_semestral:.2f}%")
            c3.metric("Evaluaciones (Semestres)", len(df_c))

            st.markdown("#### Evolución Semestral")
            fig_sem = px.bar(df_c, x="Transición", y="TPr (%)", text_auto='.2f', color="TPr (%)", color_continuous_scale="GnBu")
            st.plotly_chart(fig_sem, use_container_width=True)

            # Resumo Anual removido conforme solicitação do usuário
            
            st.markdown("#### Detalle por Transición")
            st.dataframe(df_c[["Transición", "EIns", "EPr", "TPr (%)"]].style.format({"TPr (%)": "{:.2f}%"}), hide_index=True, width="stretch")

            st.divider()
            cx1, cx2 = st.columns(2)
            with cx1:
                pdf_data = gerar_pdf_tpr(df_c[["Transición", "EIns", "EPr", "TPr (%)"]], f"Reporte de Promoción - Cohorte {cohorte_sel}")
                st.download_button("Descargar Reporte (PDF)", pdf_data, f"TPr_{cohorte_sel}.pdf", key="pdf_coh", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa de Promoción Semestral", "PDF"))
            with cx2:
                buffer_xls = io.BytesIO()
                df_c.to_excel(buffer_xls, index=False)
                st.download_button("Descargar Datos (Excel)", buffer_xls.getvalue(), f"TPr_{cohorte_sel}.xlsx", key="xls_coh", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa de Promoción Semestral", "Excel"))

    with tab_detalle:
        coh_det = st.selectbox("Cohorte", df_master["Cohorte"].unique(), index=len(df_master["Cohorte"].unique())-1, key="det_coh")
        
        # Obter e ordenar transições numericamente (S1, S2, ..., S10)
        trans_opts = sorted(df_master[df_master["Cohorte"] == coh_det]["Transición"].unique(), 
                            key=lambda x: int(x.split(" ")[1]) if " " in x else 0)
        
        if not trans_opts:
            st.warning("No hay transiciones registradas para esta cohorte.")
        else:
            if "tp_trans_sel" not in st.session_state or st.session_state.tp_trans_sel not in trans_opts:
                st.session_state.tp_trans_sel = trans_opts[0]

            # Grid de botões 6x2
            with st.container(border=True):
                st.caption("Seleccione una transición para ver el listado:")
                cols_grid = [st.columns(6), st.columns(6)]
                for i, trans in enumerate(trans_opts):
                    row_idx = i // 6
                    col_idx = i % 6
                    if row_idx < 2:
                        label_btn = trans.replace("Semestre ", "S").replace(" al ", "->")
                        b_type = "primary" if st.session_state.tp_trans_sel == trans else "secondary"
                        if cols_grid[row_idx][col_idx].button(label_btn, key=f"btn_tp_{i}_{coh_det}", use_container_width=True, type=b_type):
                            st.session_state.tp_trans_sel = trans
                            st.rerun()

            trans_det = st.session_state.tp_trans_sel
                
            if trans_det and (coh_det, trans_det) in df_detalles_master:
                ids = df_detalles_master[(coh_det, trans_det)]
                df_list = df[df[COL_ID_ALUMNO].isin(ids)].groupby(COL_ID_ALUMNO).first().reset_index()
                lista_alumnos_trans = df_list[[COL_NOMBRE, COL_CATRACA, COL_ID_ALUMNO]].copy()
                
                df_list_view = df_list[[COL_NOMBRE]].rename(columns={COL_NOMBRE: "Estudiante"}).sort_values("Estudiante")
                
                st.markdown(f"""
                <div style="background-color: #e8f0fe; border-left: 5px solid #1a73e8; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                    <span style="color: #555; font-size: 14px; font-weight: bold; text-transform: uppercase;">Alumnos Promovidos en {trans_det}</span><br>
                    <span style="color: #1a73e8; font-size: 28px; font-weight: bold;">{len(df_list_view)}</span>
                </div>
                """, unsafe_allow_html=True)
                st.dataframe(df_list_view, width="stretch", hide_index=True)

                # --- Buscar Histórico Detalhado ---
                st.divider()
                st.write("#### Consultar Histórico Detallado")
                
                @st.dialog("Perfil Académico del Estudiante", width="large")
                def modal_perfil(uid, dff):
                    ds = dff[dff[COL_ID_ALUMNO] == uid].copy()
                    if not ds.empty:
                        raa.render_alumno_details(ds, dff)
                
                col_sel, col_btn = st.columns([2, 1])
                with col_sel:
                    opciones_alumnos = {f"{row[COL_NOMBRE]} ({row[COL_CATRACA]})": row[COL_ID_ALUMNO] for _, row in lista_alumnos_trans.sort_values(COL_NOMBRE).iterrows()}
                    alumno_a_consultar = st.selectbox("Busque un alumno para ver su historial", options=list(opciones_alumnos.keys()), index=None, placeholder="Escriba el nombre del alumno...", key="sel_tp_perfil")
                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Ver Perfil Académico", icon=":material/person_search:", width="stretch", disabled=not alumno_a_consultar, key="btn_tp_perfil"):
                        modal_perfil(opciones_alumnos[alumno_a_consultar], df_full)
            else:
                st.info("No hay datos detallados para esta selección.")

    st.divider()
    st.markdown("""
    ### Metodología de Tasa de Promoción
    Identifica la proporción de estudiantes que avanzan de un curso o semestre al siguiente en el periodo académico posterior.
    """)
    st.latex(r"TPr = \frac{\sum EPr}{\sum EIns} \times 100")
    
    st.divider()
