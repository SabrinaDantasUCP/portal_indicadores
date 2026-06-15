import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime
from utils import db_pia
from utils.system_logging import log_exception
from services.data.alumnos import load_current_alumnos
from services.calculations.eficiencia_academica import (
    COL_CATRACA,
    COL_COHORTE,
    COL_DETALLE,
    COL_FECHA_TITULADO,
    COL_ID_ALUMNO,
    COL_NOMBRE,
    COL_PERIODO_EGRESSO,
    COL_TITULADO,
    build_efficiency_context,
    calculate_titulation_efficiency,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import modules.rend_acad_alumno as raa

def render():
    st.subheader("Eficiencia de Titulación (ETE)")

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
    
    df_full = load_current_alumnos(only_cde=False)
    df = load_current_alumnos()
    if df.empty:
        st.error("Archivo de datos no encontrado.")
        return

    efficiency_context, missing_cols = build_efficiency_context(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return
    eiic_df = efficiency_context["eiic_df"]
    egresados_full = efficiency_context["egresados_full"]
    df_ete = calculate_titulation_efficiency(efficiency_context)
    if df_ete.empty:
        st.warning("No hay datos suficientes para calcular la eficiencia de titulación.")
        return

    # 📄 PDF FUNCTIONS
    def agregar_encabezado_y_pie(canvas, doc):
        canvas.saveState()
        width, height = landscape(A4)
        logo_path = None
        for p in ["assets/logo-ucp-icon.png", "assets/logo-ucp.png", "logo-ucp-icon.png"]:
            if os.path.exists(p): logo_path = p; break
        if logo_path:
            try: canvas.drawImage(logo_path, x=2*cm, y=height-2.5*cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
            except Exception as exc:
                log_exception("Error silencioso tratado en eficiencia_titulacion.py", exc)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#004080"))
        canvas.drawString(5*cm, height-1.5*cm, "Universidad Central del Paraguay")
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.black)
        canvas.drawString(5*cm, height-2.1*cm, "Facultad de Ciencias de la Salud — Carrera de Medicina")
        canvas.setStrokeColor(colors.HexColor("#004080"))
        canvas.setLineWidth(1)
        canvas.line(2*cm, height-3.0*cm, width-2*cm, height-3.0*cm)
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(width-2*cm, 1.2*cm, f"Página {doc.page}")
        canvas.restoreState()

    def gerar_pdf_ete(df_resumen, cohorte_sel=None):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=2*cm, rightMargin=2*cm, topMargin=4*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()
        
        titulo = "Reporte de Eficiencia de Titulación (ETE)" if not cohorte_sel else f"Detalle Eficiencia de Titulación - Cohorte {cohorte_sel}"
        story.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
        story.append(Spacer(1, 15))
        
        if cohorte_sel:
            row = df_resumen[df_resumen["cohorte"] == cohorte_sel].iloc[0]
            data_kpi = [[f"ETE: {row['ETE (%)']:.2f}%"]]
            t_kpi = Table(data_kpi, colWidths=[20*cm])
            t_kpi.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1565C0')),
                ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 24),
                ('TOPPADDING', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 10)
            ]))
            story.append(t_kpi)
            story.append(Spacer(1, 15))
            story.append(Paragraph(f"<b>Egresados Totales (EE):</b> {int(row['EE (Egresados)'])}", styles["Normal"]))
            story.append(Paragraph(f"<b>Estudiantes Titulados (ET):</b> {int(row['ET (Titulados)'])}", styles["Normal"]))
        else:
            data_rows = [["COHORTE", "Egresados", "Titulados", "ETE (%)"]]
            for _, r in df_resumen.iterrows():
                data_rows.append([str(r['cohorte']), str(int(r['EE (Egresados)'])), str(int(r['ET (Titulados)'])), f"{r['ETE (%)']:.2f}%"])
            t = Table(data_rows, repeatRows=1, colWidths=[5*cm]*4)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#004080')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            story.append(t)
            
        story.append(Spacer(1, 15))
        story.append(Spacer(1, 25))

        # --- Metodología ---
        small_style = styles["Normal"].clone('small')
        small_style.fontSize = 9
        small_style.leading = 12
        small_style.textColor = colors.grey

        story.append(Paragraph("<b>Metodología de Eficiencia de Titulación (ETE)</b>", small_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "El índice de titulación se determina por la proporción de titulados de una cohorte determinada y el número de egresados de la misma ventana temporal.",
            small_style
        ))
        story.append(Spacer(1, 6))
        
        formula = Paragraph(
            "<para align='center'>ETE = [ ET / EE ] x 100</para>",
            small_style
        )
        story.append(formula)
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Donde:</b>", small_style))
        story.append(Paragraph("• <b>ET (Estudiantes Titulados):</b> Estudiantes que ya recibieron sus títulos profesionales.", small_style))
        story.append(Paragraph("• <b>EE (Eficiencia de Egreso):</b> Número total de estudiantes que han egresado, incluyendo los regulares y los reincorporados de periodos anteriores.", small_style))

        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    # TABS
    tab1, tab2 = st.tabs(["Comparativo Global", "Detalle por Cohorte"])

    with tab1:
        st.markdown("### Eficiencia de Titulación (ETE) por Cohorte")
        st.info("Representa la proporción de egresados que han completado el trámite de titulación profesional.")
        
        fig = px.bar(df_ete, x="cohorte", y="ETE (%)", text_auto='.2f', color="ETE (%)", color_continuous_scale="Blues")
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(df_ete.rename(columns={"cohorte": "COHORTE"})[["COHORTE", "EE (Egresados)", "ET (Titulados)", "ETE (%)"]].style.format({
            "ETE (%)": "{:.2f}%"
        }), width="stretch", hide_index=True)
        
        pdf_all = gerar_pdf_ete(df_ete)
        buf_ex = io.BytesIO()
        with pd.ExcelWriter(buf_ex, engine='xlsxwriter') as wr:
            df_ete.to_excel(wr, index=False, sheet_name='ET Global')
        st.divider()
        c1, c2 = st.columns(2)
        c1.download_button("Descargar Reporte (PDF)", data=pdf_all, file_name="Reporte_ETE_Global.pdf", mime="application/pdf", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia de Titulación - Global", "PDF"))
        c2.download_button("Descargar Datos (Excel)", data=buf_ex.getvalue(), file_name="Datos_ETE_Global.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia de Titulación - Global", "Excel"))

    with tab2:
        cohorte_sel = st.selectbox("Seleccione una Cohorte", sorted(df_ete["cohorte"].tolist()), index=None)
        if cohorte_sel:
            row = df_ete[df_ete["cohorte"] == cohorte_sel].iloc[0]
            t_final = row['periodo_final']
            
            c_a, c_b, c_c = st.columns(3)
            c_a.metric("Eficiencia de Titulación", f"{row['ETE (%)']:.2f}%")
            c_b.metric("Egresados Totales", int(row['EE (Egresados)']))
            c_c.metric("Estudiantes Titulados", int(row['ET (Titulados)']))
            
            st.divider()
            
            # --- Universo de Egresados ---
            ece_reg_df = pd.merge(eiic_df[eiic_df[COL_COHORTE] == cohorte_sel], 
                                 egresados_full, on=COL_ID_ALUMNO, suffixes=('_orig', ''))
            ece_reg_df = ece_reg_df[ece_reg_df[COL_PERIODO_EGRESSO] <= t_final]
            ece_reg_df["Tipo Egreso"] = "Regular"
            
            ece_nreg_df = pd.merge(eiic_df[eiic_df[COL_COHORTE] != cohorte_sel], 
                                  egresados_full, on=COL_ID_ALUMNO, suffixes=('_orig', ''))
            ece_nreg_df = ece_nreg_df[ece_nreg_df[COL_PERIODO_EGRESSO] == t_final]
            ece_nreg_df["Tipo Egreso"] = "No Regular"
            
            lista_full = pd.concat([ece_reg_df, ece_nreg_df])[[COL_NOMBRE, COL_CATRACA, "Tipo Egreso", COL_TITULADO, COL_FECHA_TITULADO, COL_DETALLE, COL_ID_ALUMNO]]
            
            # Formatear fecha de titulación (YYYY-MM-DD -> DD/MM/YYYY)
            lista_full[COL_FECHA_TITULADO] = pd.to_datetime(lista_full[COL_FECHA_TITULADO], errors='coerce').dt.strftime('%d/%m/%Y')
            
            # Lógica de fallback: si no hay fecha, usar detalle
            lista_full["Información"] = lista_full[COL_FECHA_TITULADO].fillna(lista_full[COL_DETALLE])
            
            lista_full = lista_full.rename(columns={
                COL_NOMBRE: "Nombre", COL_CATRACA: "Catraca",
                COL_TITULADO: "¿Titulado?"
            })
            
            # Filtro opcional por Status
            st.markdown("#### Filtros de Listado")
            f_col1, f_col2 = st.columns(2)
            options_tit = sorted(lista_full["¿Titulado?"].dropna().unique().tolist())
            sel_tit = f_col1.multiselect("Filtrar por Status de Titulación", options_tit)
            
            options_tipo = sorted(lista_full["Tipo Egreso"].unique().tolist())
            sel_tipo = f_col2.multiselect("Filtrar por Tipo de Egreso", options_tipo)
            
            mask = pd.Series(True, index=lista_full.index)
            if sel_tit: mask &= lista_full["¿Titulado?"].isin(sel_tit)
            if sel_tipo: mask &= lista_full["Tipo Egreso"].isin(sel_tipo)
            
            lista_view = lista_full[mask].sort_values("Nombre")
            
            st.divider()
            st.markdown(f"### Listado de Egresados de la Ventana ({t_final})")
            # Mostrar Información invece di Fecha Titulación
            cols_to_show = ["Nombre", "Catraca", "Tipo Egreso", "¿Titulado?", "Información"]
            st.dataframe(lista_view[cols_to_show], width="stretch", hide_index=True)
            
            # Modal Perfil
            @st.dialog("Perfil Académico do Aluno", width="large")
            def modal_perfil(uid, dff):
                ds = dff[dff[raa.COL_ID_ALUMNO] == uid].copy()
                if not ds.empty: raa.render_alumno_details(ds, dff)
            
            if not lista_view.empty:
                st.divider()
                st.write("#### Consultar Historial Detallado")
                col_sel, col_btn = st.columns([2, 1])
                # Lista de opciones basada solo en los alumnos filtrados
                with col_sel:
                    dic_al = {f"{r['Nombre']} ({r['Catraca']})": r[COL_ID_ALUMNO] for _, r in lista_view.iterrows()}
                    sel_al = st.selectbox("Busque un alumno para ver su historial", options=list(dic_al.keys()), index=None, placeholder="Escriba el nombre del alumno...")
                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Ver Perfil Académico", icon=":material/person_search:", width="stretch", disabled=not sel_al):
                        modal_perfil(dic_al[sel_al], df_full)
            else:
                st.warning("No se encontraron alumnos con los filtros seleccionados.")
            
            st.divider()
            pdf_sel = gerar_pdf_ete(df_ete, cohorte_sel)
            buf_ex_sel = io.BytesIO()
            with pd.ExcelWriter(buf_ex_sel, engine='xlsxwriter') as wr:
                pd.DataFrame([row]).to_excel(wr, index=False, sheet_name='Resumen ETE')
                lista_view.to_excel(wr, index=False, sheet_name='Listado Alumnos')
            
            c3, c4 = st.columns(2)
            c3.download_button("Descargar Reporte (PDF)", data=pdf_sel, file_name=f"Reporte_ETE_{cohorte_sel}.pdf", mime="application/pdf", key="pdf_ete_sel", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia de Titulación", "PDF"))
            c4.download_button("Descargar Datos (Excel)", data=buf_ex_sel.getvalue(), file_name=f"Datos_ETE_{cohorte_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="excel_ete_sel", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia de Titulación", "Excel"))

    st.divider()
    st.markdown("""
    ### Metodología de Eficiencia de Titulación (ETE)
    El índice de titulación se determina por la proporción de titulados de una cohorte determinada y el número de egresados de la misma ventana temporal.
    """)
    st.latex(r"ETE = \frac{ET}{EE} \times 100")
    st.markdown("""
    **Donde:**
    - **ET (Estudiantes Titulados):** Estudiantes que ya recibieron sus títulos profesionales.
    - **EE (Eficiencia de Egreso):** Número total de estudiantes que han egresado, incluyendo los regulares y los reincorporados de periodos anteriores.
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
