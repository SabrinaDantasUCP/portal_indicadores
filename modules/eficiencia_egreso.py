import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from datetime import datetime
from utils import db_pia
from utils.system_logging import log_exception
from utils.ui import (
    selector_vista,
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
    COL_ANO_FINAL_COHORTE,
    COL_CATRACA,
    COL_COHORTE,
    COL_ID_ALUMNO,
    COL_NOMBRE,
    COL_PERIODO_EGRESSO,
    build_efficiency_context,
    calculate_egress_efficiency,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import modules.rend_acad_alumno as raa

def render():
    render_cabecera_indicador(
        "Eficiencia de Egreso (EE)",
        "Porcentaje de egresados respecto de los ingresantes de cada cohorte, contando a quienes egresan en tiempo y también a los de cohortes anteriores que egresan en el periodo final de la cohorte.",
    )

    
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
    df_ee = calculate_egress_efficiency(efficiency_context)
    if df_ee.empty:
        st.warning("No hay datos suficientes para calcular la eficiencia de egreso.")
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
                log_exception("Error silencioso tratado en eficiencia_egreso.py", exc)
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
    vista = selector_vista(['Comparativo Global', 'Detalle por Cohorte'], "vista_eficiencia_egreso")

    if vista == 'Comparativo Global':
        total_eiic = int(df_ee["EIIC"].sum())
        total_egr = int(df_ee["Total_Egresados"].sum())
        render_tarjetas_kpi([
            {"etiqueta": "Cohortes", "valor": len(df_ee), "detalle": "Con periodo final definido"},
            {"etiqueta": "Ingresantes (EIIC)", "valor": formatear_entero(total_eiic)},
            {"etiqueta": "Egresados", "valor": formatear_entero(total_egr), "detalle": "Regulares + de otras cohortes"},
            {"etiqueta": "EE global", "valor": formatear_porcentaje(total_egr / total_eiic * 100 if total_eiic else 0),
             "detalle": "Egresados ÷ ingresantes"},
        ])
        render_titulo_seccion(
            "Eficiencia de Egreso por cohorte",
            "Barras apiladas: <b>en tiempo</b> (egresados regulares de la cohorte) y <b>de otras cohortes</b> "
            "(alumnos atrasados que egresan en el periodo final de esta cohorte).",
        )
        eiic_validos = df_ee["EIIC"].where(df_ee["EIIC"] > 0)
        df_plot = df_ee.assign(
            **{"En tiempo": df_ee["ECE_reg"] / eiic_validos * 100,
               "De otras cohortes": df_ee["ECE_nreg"] / eiic_validos * 100}
        ).melt(id_vars=["cohorte"], value_vars=["En tiempo", "De otras cohortes"], var_name="Tipo", value_name="Porcentaje")
        fig = px.bar(
            df_plot, x="cohorte", y="Porcentaje", color="Tipo",
            color_discrete_map={"En tiempo": COLOR_PRIMARIO, "De otras cohortes": COLOR_ATENCION},
            labels={"cohorte": "Cohorte"},
        )
        fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.2f}%<extra></extra>")
        totales = df_ee.set_index("cohorte")["EE (%)"]
        fig.add_scatter(
            x=totales.index, y=totales.values, mode="text", text=[formatear_porcentaje(v) for v in totales.values],
            textposition="top center", showlegend=False, hoverinfo="skip",
        )
        estilizar_figura(fig, titulo_y="Eficiencia de Egreso", porcentaje=True, altura=400)
        fig.update_layout(barmode="stack")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        
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

    if vista == 'Detalle por Cohorte':
        cohorte_sel = st.selectbox("Seleccione una Cohorte", opciones_cohorte(df_ee["cohorte"]), index=None)
        if cohorte_sel:
            row = df_ee[df_ee["cohorte"] == cohorte_sel].iloc[0]
            t_final = row['periodo_final']
            t_final_str = f"{t_final:.1f}" if pd.notna(t_final) else ""
            
            render_tarjetas_kpi([
                {"etiqueta": "Eficiencia de Egreso", "valor": formatear_porcentaje(row["EE (%)"], 2)},
                {"etiqueta": "Ingresantes (EIIC)", "valor": formatear_entero(row["EIIC"])},
                {"etiqueta": "Egresados en tiempo", "valor": formatear_entero(row["ECE_reg"]), "color": COLOR_BUENO},
                {"etiqueta": "Egresados de otras cohortes", "valor": formatear_entero(row["ECE_nreg"]), "color": COLOR_ATENCION},
            ])
            
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
                lista_full = lista_full.rename(columns={COL_NOMBRE: "Nombre", COL_CATRACA: "Número de Matrícula", COL_PERIODO_EGRESSO: "Periodo Egreso", COL_ANO_FINAL_COHORTE: "Periodo Previsto"})
                
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
                
                render_titulo_seccion(f"Egresados en el periodo final de la cohorte ({t_final_str})")
                st.dataframe(lista_view.drop(columns=[COL_ID_ALUMNO]), width="stretch", hide_index=True)
                
                # Modal Perfil
                @st.dialog("Perfil Académico del Estudiante", width="large")
                def modal_perfil(uid, dff):
                    ds = dff[dff[raa.COL_ID_ALUMNO] == uid].copy()
                    if not ds.empty: raa.render_alumno_details(ds, dff)
                
                st.divider()
                render_titulo_seccion("Consultar historial de un alumno")
                col_sel, col_btn = st.columns([2, 1])
                
                # Lista de opciones ordenada alfabéticamente
                with col_sel:
                    dic_al = {f"{r['Nombre']} ({r['Número de Matrícula']})": r[COL_ID_ALUMNO] for _, r in lista_view.sort_values("Nombre").iterrows()}
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
                    columns={COL_NOMBRE: "Nombre", COL_CATRACA: "Número de Matrícula"}
                ).sort_values("Nombre")

                buf_ex_sel = io.BytesIO()
                with pd.ExcelWriter(buf_ex_sel, engine='xlsxwriter') as wr:
                    pd.DataFrame([row]).to_excel(wr, index=False, sheet_name='Resumen EE')
                    lista_full.drop(columns=[COL_ID_ALUMNO]).to_excel(wr, index=False, sheet_name='Listado Egresados')
                    df_ingresantes.to_excel(wr, index=False, sheet_name='Ingresantes')
            else:
                st.warning("No se registraron egresados en esta cohorte para el periodo analizado.")
                # Reporte PDF y Excel para la cohorte (solo resumen ya que no hay listado de egresados)
                pdf_sel = gerar_pdf_ee(df_ee, cohorte_sel)
                
                # Lista de Ingresantes (EIIC) para o Excel
                df_ingresantes = eiic_df[eiic_df[COL_COHORTE] == cohorte_sel][[COL_NOMBRE, COL_CATRACA]].rename(
                    columns={COL_NOMBRE: "Nombre", COL_CATRACA: "Número de Matrícula"}
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
    with st.expander("¿Cómo se calcula la Eficiencia de Egreso?", icon=":material/functions:"):
        st.markdown("""
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
