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
    st.subheader("Eficiencia de Egreso (EE)")

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
            df = pd.read_csv("assets/data/alumnos.csv", sep=",", low_memory=False)
            df.columns = df.columns.str.strip()
            df = df[df["filial_periodo_letivo"].isin(["CDE", "CDE III"])].copy()
            return df
        except FileNotFoundError:
            st.error("Archivo de datos no encontrado.")
            return pd.DataFrame()

    df = load_data()
    if df.empty:
        return

    # --- Columnas ---
    COL_COHORTE = "cohorte"
    COL_ID_ALUMNO = "usuarios_id"
    COL_NOMBRE = "nome_sobrenome"
    COL_CATRACA = "numero_catraca"
    COL_SEMESTRE_ALUMNO = "semestre_alumno"
    COL_PERIODO_EGRESSO = "periodo_egresso_format"
    COL_ANO_FINAL_COHORTE = "ano_final_coorte"

    # --- Lógica de Cálculo de Eficiencia de Egreso (EE) ---
    
    # 1. EIIC: Ingresantes al 1º semestre de cada cohorte
    eiic_df = df[df[COL_SEMESTRE_ALUMNO].astype(float) == 1].groupby([COL_COHORTE, COL_ID_ALUMNO]).first().reset_index()
    
    # 2. Ventanas de Egreso por Cohorte
    # Mapeamos cada cohorte a su periodo final esperado
    ventanas_coorte = eiic_df.groupby(COL_COHORTE)[COL_ANO_FINAL_COHORTE].first().reset_index()
    ventanas_coorte[COL_ANO_FINAL_COHORTE] = pd.to_numeric(ventanas_coorte[COL_ANO_FINAL_COHORTE], errors='coerce')
    
    # 3. Egresados Totales
    egresados_full = df.dropna(subset=[COL_PERIODO_EGRESSO]).groupby([COL_ID_ALUMNO]).first().reset_index()
    egresados_full[COL_PERIODO_EGRESSO] = pd.to_numeric(egresados_full[COL_PERIODO_EGRESSO], errors='coerce')
    
    # 4. Cálculo por Cohorte Objetivo
    resumen_ee = []
    
    for _, vent in ventanas_coorte.iterrows():
        c_objetivo = vent[COL_COHORTE]
        t_objetivo = vent[COL_ANO_FINAL_COHORTE]
        
        if pd.isna(t_objetivo): continue
        
        # Ingressantes (EIIC)
        eiic_count = len(eiic_df[eiic_df[COL_COHORTE] == c_objetivo])
        if eiic_count == 0: continue
        
        # ECE(reg): Alumnos de la cohorte que egresan en tiempo regular (<= T_objetivo)
        # Seleccionamos solo ID para el merge y evitar conflictos de nombres
        ece_reg_df = pd.merge(eiic_df[eiic_df[COL_COHORTE] == c_objetivo][[COL_ID_ALUMNO]], 
                             egresados_full, on=COL_ID_ALUMNO, how="inner")
        ece_reg_df = ece_reg_df[ece_reg_df[COL_PERIODO_EGRESSO] <= t_objetivo]
        ece_reg_count = len(ece_reg_df)
        
        # ECE(n reg): Alumnos de OTRAS cohortes que egresan en el T_objetivo de la cohorte actual
        ece_nreg_df = pd.merge(eiic_df[eiic_df[COL_COHORTE] != c_objetivo][[COL_ID_ALUMNO]], 
                              egresados_full, on=COL_ID_ALUMNO, how="inner")
        
        # Deben egresar exactamente en el periodo final de la cohorte objetivo
        ece_nreg_df = ece_nreg_df[ece_nreg_df[COL_PERIODO_EGRESSO] == t_objetivo]
        ece_nreg_count = len(ece_nreg_df)
        
        ee_porc = ((ece_reg_count + ece_nreg_count) / eiic_count) * 100
        
        resumen_ee.append({
            "cohorte": c_objetivo,
            "periodo_final": t_objetivo,
            "EIIC": eiic_count,
            "ECE_reg": ece_reg_count,
            "ECE_nreg": ece_nreg_count,
            "Total_Egresados": ece_reg_count + ece_nreg_count,
            "EE (%)": ee_porc
        })
        
    df_ee = pd.DataFrame(resumen_ee).sort_values("cohorte")

    # --- Filtro de Cohortes Completas (12 semestres) ---
    max_semestre = df.groupby(COL_COHORTE)[COL_SEMESTRE_ALUMNO].max()
    cohortes_completas = max_semestre[max_semestre >= 12].index.tolist()
    df_ee = df_ee[df_ee["cohorte"].isin(cohortes_completas)]

    # 📄 PDF FUNCTIONS
    def agregar_encabezado_y_pie(canvas, doc):
        canvas.saveState()
        width, height = landscape(A4)
        logo_path = None
        for p in ["assets/logo-ucp-icon.png", "assets/logo-ucp.png", "logo-ucp-icon.png"]:
            if os.path.exists(p): logo_path = p; break
        if logo_path:
            try: canvas.drawImage(logo_path, x=2*cm, y=height-2.5*cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
            except: pass
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

    def gerar_pdf_ee(df_resumen, cohorte_sel=None):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=2*cm, rightMargin=2*cm, topMargin=4*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()
        
        titulo = "Reporte de Eficiencia de Egreso (EE)" if not cohorte_sel else f"Detalle Eficiencia de Egreso - Cohorte {cohorte_sel}"
        story.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
        story.append(Spacer(1, 15))
        
        if cohorte_sel:
            row = df_resumen[df_resumen["cohorte"] == cohorte_sel].iloc[0]
            data_kpi = [[f"EE: {row['EE (%)']:.2f}%"]]
            t_kpi = Table(data_kpi, colWidths=[20*cm])
            style = TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#2E7D32')),
                ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 24),
                ('TOPPADDING', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 10)
            ])
            t_kpi.setStyle(style)
            story.append(t_kpi)
            story.append(Spacer(1, 15))
            story.append(Paragraph(f"<b>Ingresantes (EIIC):</b> {int(row['EIIC'])}", styles["Normal"]))
            story.append(Paragraph(f"<b>Egresados Regulares (ECE reg):</b> {int(row['ECE_reg'])}", styles["Normal"]))
            story.append(Paragraph(f"<b>Egresados Otras Cohortes (ECE nreg):</b> {int(row['ECE_nreg'])}", styles["Normal"]))
        else:
            data_rows = [["Cohorte", "Periodo Final", "EIIC", "ECE Reg", "ECE nReg", "Total", "EE (%)"]]
            for _, r in df_resumen.iterrows():
                p_final = f"{r['periodo_final']:.1f}" if pd.notna(r['periodo_final']) else ""
                data_rows.append([
                    str(r['cohorte']), 
                    p_final,
                    str(int(r['EIIC'])), 
                    str(int(r['ECE_reg'])), 
                    str(int(r['ECE_nreg'])), 
                    str(int(r['Total_Egresados'])), 
                    f"{r['EE (%)']:.2f}%"
                ])
            t = Table(data_rows, repeatRows=1, colWidths=[3*cm, 3*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 3*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#004080')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            story.append(t)
            
        story.append(Spacer(1, 25))

        # --- Metodología ---
        small_style = styles["Normal"].clone('small')
        small_style.fontSize = 9
        small_style.leading = 12
        small_style.textColor = colors.grey

        story.append(Paragraph("<b>Metodología de Eficiencia de Egreso (EE)</b>", small_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Se define como la relación cuantitativa de los estudiantes que finalizan la enseñanza en el tiempo previsto en el plan de estudios o en periodos posteriores en relación a su cohorte de entrada.",
            small_style
        ))
        story.append(Spacer(1, 6))
        
        formula = Paragraph(
            "<para align='center'><b>EE = [ (ECE_reg + ECE_nreg) / EIIC ] x 100</b></para>",
            small_style
        )
        story.append(formula)
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Donde:</b>", small_style))
        story.append(Paragraph("• <b>ECE(reg):</b> Estudiantes de la cohorte que egresan en tiempo regular.", small_style))
        story.append(Paragraph("• <b>ECE(n reg):</b> Estudiantes de otras cohortes que egresan en el periodo final de la cohorte actual.", small_style))
        story.append(Paragraph("• <b>EIIC:</b> Estudiantes matriculados en el primer semestre de la cohorte.", small_style))

        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)

        return buffer.getvalue()

    # TABS
    tab1, tab2 = st.tabs(["Comparativo Global", "Detalle por Cohorte"])

    with tab1:
        st.markdown("### Eficiencia de Egreso (EE) por Cohorte")
        st.info("Considera tanto a los **egresados regulares** de la cohorte como a **egresados de cohortes anteriores** que se gradúan en el mismo periodo.")
        
        fig = px.bar(df_ee, x="cohorte", y="EE (%)", text_auto='.2f', color="EE (%)", color_continuous_scale="Greens")
        st.plotly_chart(fig, use_container_width=True)
        
        df_view = df_ee.rename(columns={
            "cohorte": "Cohorte",
            "periodo_final": "Periodo Final",
            "ECE_reg": "ECE (reg)",
            "ECE_nreg": "ECE (n reg)",
            "Total_Egresados": "Total Egresados"
        })
        st.dataframe(
            df_view.style.format({
                "EE (%)": "{:.2f}%",
                "Periodo Final": "{:.1f}"
            }), 
            width="stretch", 
            hide_index=True
        )
        
        pdf_all = gerar_pdf_ee(df_ee)
        buf_ex = io.BytesIO()
        with pd.ExcelWriter(buf_ex, engine='xlsxwriter') as wr:
            df_ee.to_excel(wr, index=False, sheet_name='EE Global')
        st.divider()
        c1, c2 = st.columns(2)
        c1.download_button("Descargar Reporte (PDF)", data=pdf_all, file_name="Reporte_EE_Global.pdf", mime="application/pdf", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia de Egreso - Global", "PDF"))
        c2.download_button("Descargar Datos (Excel)", data=buf_ex.getvalue(), file_name="Datos_EE_Global.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia de Egreso - Global", "Excel"))

    with tab2:
        cohorte_sel = st.selectbox("Seleccione una Cohorte", sorted(df_ee["cohorte"].tolist()), index=None)
        if cohorte_sel:
            row = df_ee[df_ee["cohorte"] == cohorte_sel].iloc[0]
            t_final = row['periodo_final']
            t_final_str = f"{t_final:.1f}" if pd.notna(t_final) else ""
            
            c_a, c_b, c_c = st.columns(3)
            c_a.metric("Eficiencia de Egreso", f"{row['EE (%)']:.2f}%")
            c_b.metric("Ingresantes (EIIC)", int(row['EIIC']))
            c_c.metric("Total Egresados", int(row['Total_Egresados']))
            
            st.divider()
            
            if row['Total_Egresados'] > 0:
                # Listado de Alumnos Egresados en esta ventana
                # 1. Regulares
                lista_reg = pd.merge(eiic_df[eiic_df[COL_COHORTE] == cohorte_sel], egresados_full, on=COL_ID_ALUMNO, suffixes=('_orig', ''))
                lista_reg = lista_reg[lista_reg[COL_PERIODO_EGRESSO] <= t_final]
                lista_reg["Tipo"] = "Regular (De la Cohorte)"
                
                # 2. No Regulares (De otras cohortes)
                lista_nreg = pd.merge(eiic_df[eiic_df[COL_COHORTE] != cohorte_sel], egresados_full, on=COL_ID_ALUMNO, suffixes=('_orig', ''))
                lista_nreg = lista_nreg[lista_nreg[COL_PERIODO_EGRESSO] == t_final]
                lista_nreg["Tipo"] = "No Regular (Otras Cohortes)"
                
                lista_full = pd.concat([lista_reg, lista_nreg])[[COL_NOMBRE, COL_CATRACA, "Tipo", COL_PERIODO_EGRESSO, COL_ANO_FINAL_COHORTE, COL_ID_ALUMNO]]
                lista_full = lista_full.rename(columns={COL_NOMBRE: "Nombre", COL_CATRACA: "Catraca", COL_PERIODO_EGRESSO: "Periodo Egreso", COL_ANO_FINAL_COHORTE: "Periodo Previsto"})
                
                # --- Filtro por Tipo de Egreso ---
                tipos_disp = sorted(lista_full["Tipo"].unique().tolist())
                tipos_sel = st.multiselect("Filtrar por Tipo de Egreso (Opcional)", options=tipos_disp, help="Si se deja vacío, se mostrarán todos los tipos.")
                
                # Aplicar filtro (opcional) y ordenar por Nombre
                mask = pd.Series(True, index=lista_full.index)
                if tipos_sel:
                    mask &= lista_full["Tipo"].isin(tipos_sel)
                
                if "Nombre" in lista_full.columns:
                    lista_view = lista_full[mask].sort_values("Nombre")
                else:
                    lista_view = lista_full[mask]
                
                st.markdown(f"### Alumnos Egresados en la ventana de la cohorte ({t_final_str})")
                st.dataframe(lista_view.drop(columns=[COL_ID_ALUMNO]), width="stretch", hide_index=True)
                
                # Modal Perfil
                @st.dialog("Perfil Académico del Estudiante", width="large")
                def modal_perfil(uid, dff):
                    ds = dff[dff[raa.COL_ID_ALUMNO] == uid].copy()
                    if not ds.empty: raa.render_alumno_details(ds, dff)
                
                st.divider()
                st.write("#### Consultar Histórico Detallado")
                col_sel, col_btn = st.columns([2, 1])
                
                # Lista de opciones ordenada alfabéticamente
                with col_sel:
                    dic_al = {f"{r['Nombre']} ({r['Catraca']})": r[COL_ID_ALUMNO] for _, r in lista_view.sort_values("Nombre").iterrows()}
                    sel_al = st.selectbox("Busque un alumno para ver su historial", options=list(dic_al.keys()), index=None, placeholder="Escriba el nombre del alumno...")
                
                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Ver Perfil Académico", icon=":material/person_search:", width="stretch", disabled=not sel_al):
                        modal_perfil(dic_al[sel_al], df)
                
                st.divider()
                
                # Reporte PDF y Excel para la cohorte (con listado)
                pdf_sel = gerar_pdf_ee(df_ee, cohorte_sel)
                
                # Lista de Ingresantes (EIIC) para o Excel
                df_ingresantes = eiic_df[eiic_df[COL_COHORTE] == cohorte_sel][[COL_NOMBRE, COL_CATRACA]].rename(
                    columns={COL_NOMBRE: "Nombre", COL_CATRACA: "Catraca"}
                ).sort_values("Nombre")

                buf_ex_sel = io.BytesIO()
                with pd.ExcelWriter(buf_ex_sel, engine='xlsxwriter') as wr:
                    pd.DataFrame([row]).to_excel(wr, index=False, sheet_name='Resumen EE')
                    lista_full.to_excel(wr, index=False, sheet_name='Listado Egresados')
                    df_ingresantes.to_excel(wr, index=False, sheet_name='Ingresantes')
            else:
                st.warning("No se registraron egresados en esta cohorte para el periodo analizado.")
                # Reporte PDF y Excel para la cohorte (solo resumen ya que no hay listado de egresados)
                pdf_sel = gerar_pdf_ee(df_ee, cohorte_sel)
                
                # Lista de Ingresantes (EIIC) para o Excel
                df_ingresantes = eiic_df[eiic_df[COL_COHORTE] == cohorte_sel][[COL_NOMBRE, COL_CATRACA]].rename(
                    columns={COL_NOMBRE: "Nombre", COL_CATRACA: "Catraca"}
                ).sort_values("Nombre")

                buf_ex_sel = io.BytesIO()
                with pd.ExcelWriter(buf_ex_sel, engine='xlsxwriter') as wr:
                    pd.DataFrame([row]).to_excel(wr, index=False, sheet_name='Resumen EE')
                    df_ingresantes.to_excel(wr, index=False, sheet_name='Ingresantes')
            
            # Botões de download aparecem sempre
            c3, c4 = st.columns(2)
            c3.download_button("Descargar Reporte (PDF)", data=pdf_sel, file_name=f"Reporte_EE_{cohorte_sel}.pdf", mime="application/pdf", key="pdf_ee_sel", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia de Egreso", "PDF"))
            c4.download_button("Descargar Datos (Excel)", data=buf_ex_sel.getvalue(), file_name=f"Datos_EE_{cohorte_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="excel_ee_sel", width="stretch", on_click=db_pia.log_export_callback, args=("Eficiencia de Egreso", "Excel"))

    st.divider()
    st.markdown("""
    ### Metodología de Eficiencia de Egreso (EE)
    Se define como la relación cuantitativa de los estudiantes que finalizan la enseñanza en el tiempo previsto en el plan de estudios o en periodos posteriores en relación a su cohorte de entrada.
    """)
    st.latex(r"EE = \frac{ECE(reg) + ECE(n\:reg)}{EIIC} \times 100")
    st.markdown("""
    **Donde:**
    - **ECE(reg):** Estudiantes de la cohorte que egresan en tiempo regular.
    - **ECE(n reg):** Estudiantes de otras cohortes que egresan en el periodo final de la cohorte actual.
    - **EIIC:** Estudiantes matriculados en el primer semestre de la cohorte.
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
