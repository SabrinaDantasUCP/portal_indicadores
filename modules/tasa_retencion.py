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
    COL_CATRACA,
    COL_COHORTE,
    COL_ID_ALUMNO,
    COL_NOMBRE,
    COL_SEMESTRE_ALUMNO,
    COL_TIPO_INGRESO,
    calculate_retention,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import modules.rend_acad_alumno as raa

def render():
    render_cabecera_indicador(
        "Tasa de Retención (TR)",
        "Porcentaje de los alumnos que ingresaron en una cohorte que siguen inscriptos en la carrera en cada semestre, aunque repitan asignaturas.",
    )


    df_full = load_current_alumnos(only_cde=False)
    df = load_current_alumnos()

    if df.empty:
        st.error("Archivo de datos no encontrado.")
        return

    retencion_df, missing_cols = calculate_retention(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return
    if retencion_df.empty:
        st.warning("No hay datos suficientes para calcular la tasa de retención.")
        return

    # PDF FUNCTIONS
    def agregar_encabezado_y_pie(canvas, doc):
        canvas.saveState()
        width, height = landscape(A4)
        logo_path = None
        for p in ["assets/logo-ucp-icon.png", "assets/logo-ucp.png", "logo-ucp-icon.png"]:
            if os.path.exists(p): logo_path = p; break
        if logo_path:
            try: canvas.drawImage(logo_path, x=2*cm, y=height-2.5*cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
            except Exception as exc:
                log_exception("Error silencioso tratado en tasa_retencion.py", exc)
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

    def gerar_pdf_tr(df_resumen, cohorte_sel=None):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=2*cm, rightMargin=2*cm, topMargin=4*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()
        
        titulo = "Reporte de Tasa de Retención (TR)" if not cohorte_sel else f"Evolución Retención - Cohorte {cohorte_sel}"
        story.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
        story.append(Spacer(1, 15))
        
        if cohorte_sel:
            ds = df_resumen[df_resumen[COL_COHORTE] == cohorte_sel].sort_values(COL_SEMESTRE_ALUMNO)
            data_rows = [["Semestre", "Alumnos Retidos", "Taxa (%)"]]
            for _, r in ds.iterrows():
                data_rows.append([f"S{int(r[COL_SEMESTRE_ALUMNO])}", str(int(r['EIS'])), f"{r['TR (%)']:.2f}%"])
            t = Table(data_rows, repeatRows=1, colWidths=[5*cm]*3)
        else:
            # Resumen de S1 y S12 por cohorte
            res_list = []
            for c in df_resumen[COL_COHORTE].unique():
                c_data = df_resumen[df_resumen[COL_COHORTE] == c]
                s1 = c_data[c_data[COL_SEMESTRE_ALUMNO] == 1]["TR (%)"].values[0] if 1 in c_data[COL_SEMESTRE_ALUMNO].values else 0
                s12 = c_data[c_data[COL_SEMESTRE_ALUMNO] == 12]["TR (%)"].values[0] if 12 in c_data[COL_SEMESTRE_ALUMNO].values else None
                res_list.append([str(c), f"{s1:.2f}%", f"{s12:.2f}%" if s12 is not None else "N/A"])
            
            data_rows = [["COHORTE", "Retención S1", "Retención S12"]] + res_list
            t = Table(data_rows, repeatRows=1, colWidths=[6*cm]*3)

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

        story.append(Paragraph("<b>Metodología de Tasa de Retención (TR)</b>", small_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "La tasa de retención es el porcentaje de estudiantes retenidos por la institución que siguen activos en la carrera, independientemente de que repitan asignaturas.",
            small_style
        ))
        story.append(Spacer(1, 6))
        
        formula = Paragraph(
            "<para align='center'>TR = [ EIS / EIIC ] x 100</para>",
            small_style
        )
        story.append(formula)
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Donde:</b>", small_style))
        story.append(Paragraph("• <b>EIS (Estudiantes Inscritos en el Semestre):</b> Permanecen en la institución y continúan en la carrera en el semestre evaluado.", small_style))
        story.append(Paragraph("• <b>EIIC (Ingreso Inicial):</b> Estudiantes matriculados en el primer semestre de la cohorte.", small_style))

        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
        return buffer.getvalue()

    # TABS
    # Filtro de Cohortes (se usa en ambas vistas)
    todas_cohortes = opciones_cohorte(retencion_df[COL_COHORTE].unique())
    vista = selector_vista(['Comparativo Global', 'Evolución por Cohorte'], "vista_retencion")

    if vista == 'Comparativo Global':
        
        ultima_por_cohorte = retencion_df.sort_values(COL_SEMESTRE_ALUMNO).groupby(COL_COHORTE).last()
        mejor = ultima_por_cohorte["TR (%)"].idxmax()
        render_tarjetas_kpi([
            {"etiqueta": "Cohortes", "valor": len(todas_cohortes), "detalle": f"De {todas_cohortes[-1]} a {todas_cohortes[0]}"},
            {"etiqueta": "Ingresantes (S1)", "valor": formatear_entero(ultima_por_cohorte["EIIC"].sum()),
             "detalle": "Suma de todas las cohortes"},
            {"etiqueta": "Retención actual promedio", "valor": formatear_porcentaje(ultima_por_cohorte["TR (%)"].mean()),
             "detalle": "Último semestre evaluado de cada cohorte"},
            {"etiqueta": "Mayor retención actual", "valor": formatear_porcentaje(ultima_por_cohorte.loc[mejor, "TR (%)"]),
             "detalle": f"Cohorte {mejor}", "color": COLOR_BUENO},
        ])

        render_titulo_seccion(
            "Curva de retención por cohorte",
            "Cada línea parte del 100% en el 1º semestre y muestra qué parte de la cohorte sigue en la carrera "
            "en los semestres siguientes. Cuanto más plana la línea, mejor la retención.",
        )
        # --- Selector de Cohortes Compacto ---
        with st.container(border=True):
            c_header, c_sel, c_btns = st.columns([1.5, 3, 1])

            with c_header:
                st.markdown("**Cohortes a comparar**")
                st.caption("Elija una o más cohortes:")
            with c_sel:
                # Usar session_state para permitir selección dinámica
                if "sel_cohortes_tr" not in st.session_state:
                    st.session_state.sel_cohortes_tr = todas_cohortes[:5]
                
                st.multiselect(
                    "Cohortes a comparar", 
                    options=todas_cohortes, 
                    key="sel_cohortes_tr",
                    label_visibility="collapsed",
                    placeholder="Elija cohortes para el gráfico..."
                )
            with c_btns:
                def sel_ultimas_5():
                    st.session_state.sel_cohortes_tr = todas_cohortes[:5]
                def limpar_sel():
                    st.session_state.sel_cohortes_tr = []

                st.button("Últimas 5", on_click=sel_ultimas_5, use_container_width=True)
                st.button("Limpiar", on_click=limpar_sel, use_container_width=True)
        
        df_line_chart = retencion_df[retencion_df[COL_COHORTE].isin(st.session_state.sel_cohortes_tr)]
        
        # Gráfico de Líneas Múltiples
        if not df_line_chart.empty:
            fig = px.line(df_line_chart, x=COL_SEMESTRE_ALUMNO, y="TR (%)", color=COL_COHORTE, markers=True,
                         color_discrete_sequence=PALETA_CATEGORICA,
                         labels={COL_SEMESTRE_ALUMNO: "Semestre", "TR (%)": "Retención (%)", COL_COHORTE: "Cohorte"})
            fig.update_traces(hovertemplate="<b>%{fullData.name}</b><br>Semestre %{x}: %{y:.1f}%<extra></extra>")
            estilizar_figura(fig, titulo_x="Semestre", titulo_y="Retención", porcentaje=True, altura=440)
            fig.update_xaxes(dtick=1)
            fig.update_yaxes(range=[0, 105])
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No hay cohortes seleccionadas. Utilice el selector superior para visualizar la comparativa.")
        
        st.divider()

        # --- Cálculos para Exportación (Fuera del expander para velocidad y consistencia) ---
        pivot_tr = retencion_df.pivot(index=COL_COHORTE, columns=COL_SEMESTRE_ALUMNO, values="TR (%)")
        all_sems = range(1, 13)
        pivot_tr = pivot_tr.reindex(columns=all_sems)

        buf_ex = io.BytesIO()
        with pd.ExcelWriter(buf_ex, engine='xlsxwriter') as wr:
            pivot_tr.to_excel(wr, sheet_name='Matriz TR')
            retencion_df.to_excel(wr, index=False, sheet_name='Datos Base TR')
        excel_data = buf_ex.getvalue()
        pdf_all = gerar_pdf_tr(retencion_df)

        # --- Matriz de Retención (Optimización: Expander para aligerar la página) ---
        with st.expander("Ver matriz de retención por cohorte y semestre (%)", expanded=False, icon=":material/grid_on:"):
            st.caption("Verde más intenso = mayor retención. Las celdas vacías son semestres que la cohorte todavía no cursó.")
            st.dataframe(
                pivot_tr.rename_axis(index="COHORTE").style
                .format(lambda v: f"{v:.1f}%" if pd.notnull(v) else "")
                .background_gradient(cmap="YlGn", axis=None, vmin=0, vmax=100)
                .highlight_null(color='white'),
                width="stretch",
                height=400
            )

        st.divider()
        c1, c2 = st.columns(2)
        c1.download_button("Descargar Reporte (PDF)", data=pdf_all, file_name="Reporte_TR_Global.pdf", mime="application/pdf", icon=":material/download:", width="stretch", key="btn_pdf_global", on_click=db_pia.log_export_callback, args=("Tasa de Retención - Global", "PDF"))
        c2.download_button("Descargar Datos (Excel)", data=excel_data, file_name="Datos_TR_Global.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", key="btn_ex_global", on_click=db_pia.log_export_callback, args=("Tasa de Retención - Global", "Excel"))

    if vista == 'Evolución por Cohorte':
        cohorte_sel = st.selectbox("Seleccione una Cohorte", todas_cohortes, index=None)
        if cohorte_sel:
            data_c = retencion_df[retencion_df[COL_COHORTE] == cohorte_sel].sort_values(COL_SEMESTRE_ALUMNO)
            
            # --- Layout Premium: Métricas Compactas ---
            tr_final = data_c["TR (%)"].iloc[-1]
            eiic_val = data_c["EIIC"].iloc[0]
            max_sem_eval = int(data_c[COL_SEMESTRE_ALUMNO].max())
            
            render_tarjetas_kpi([
                {"etiqueta": "Ingreso inicial (S1)", "valor": formatear_entero(eiic_val)},
                {"etiqueta": "Retención actual", "valor": formatear_porcentaje(tr_final, 2),
                 "detalle": f"En el {max_sem_eval}º semestre",
                 "color": COLOR_BUENO if tr_final >= 80 else (COLOR_ATENCION if tr_final >= 60 else COLOR_MALO)},
                {"etiqueta": "Pérdida acumulada", "valor": formatear_porcentaje(100 - tr_final, 2),
                 "detalle": "Desde el 1º semestre", "color": COLOR_MALO},
                {"etiqueta": "Semestres evaluados", "valor": max_sem_eval},
            ])
            
            st.divider()

            # --- Gráfico Local de Evolución ---
            render_titulo_seccion(f"Curva de retención de la cohorte {cohorte_sel}")
            fig_local = px.line(data_c, x=COL_SEMESTRE_ALUMNO, y="TR (%)", markers=True, text=data_c["TR (%)"].map(formatear_porcentaje),
                               labels={COL_SEMESTRE_ALUMNO: "Semestre", "TR (%)": "Retención (%)"})
            fig_local.update_traces(line_color=COLOR_PRIMARIO, textposition="top center",
                                    hovertemplate="Semestre %{x}: %{y:.1f}%<extra></extra>")
            estilizar_figura(fig_local, titulo_x="Semestre", titulo_y="Retención", porcentaje=True, altura=380, leyenda=False)
            fig_local.update_yaxes(range=[0, 110])
            fig_local.update_xaxes(dtick=1)
            st.plotly_chart(fig_local, use_container_width=True, config={"displayModeBar": False})

            st.divider()

            # --- Selector de Semestre Estruturado (2 filas de 6) ---
            render_titulo_seccion("Alumnos por semestre", "Seleccione un semestre para ver el listado de alumnos retenidos.")
            
            semestres_disponibles = sorted(data_c[COL_SEMESTRE_ALUMNO].unique().tolist())
            
            if "sem_audit_tr" not in st.session_state or st.session_state.sem_audit_tr not in semestres_disponibles:
                st.session_state.sem_audit_tr = semestres_disponibles[-1]

            # Mostrar en 2 filas de hasta 6 columnas cada una
            with st.container(border=True):
                # Fila 1 (1-6)
                c_row1 = st.columns(6)
                # Fila 2 (7-12)
                c_row2 = st.columns(6)
                
                for i, s in enumerate(semestres_disponibles):
                    target_col = c_row1[i] if i < 6 else c_row2[i-6]
                    label = f"{int(s)}º Sem"
                    # Resaltar el seleccionado usando el tipo de botón
                    b_type = "primary" if st.session_state.sem_audit_tr == s else "secondary"
                    if target_col.button(label, key=f"btn_sem_{int(s)}", use_container_width=True, type=b_type):
                        st.session_state.sem_audit_tr = s
                        st.rerun()

            sem_sel = st.session_state.sem_audit_tr

            # --- Listado Nominal ---
            lista_ids = df[(df[COL_COHORTE] == cohorte_sel) & (df[COL_SEMESTRE_ALUMNO] == sem_sel)][COL_ID_ALUMNO].unique()
            lista_al = df[df[COL_ID_ALUMNO].isin(lista_ids)].groupby(COL_ID_ALUMNO).first().reset_index()
            lista_view = lista_al[[COL_NOMBRE, COL_CATRACA, COL_TIPO_INGRESO, COL_ID_ALUMNO]].rename(columns={
                COL_NOMBRE: "Nombre", COL_CATRACA: "Número de Matrícula", COL_TIPO_INGRESO: "Tipo Ingreso"
            }).sort_values("Nombre")
            
            st.markdown(f"**Alumnos Retenidos en el Semestre {sem_sel}** — Total: {len(lista_view)}")
            st.dataframe(lista_view.drop(columns=[COL_ID_ALUMNO]), width="stretch", hide_index=True)

            @st.dialog("Perfil Académico del Estudiante", width="large")
            def modal_perfil(uid, dff):
                ds = dff[dff[raa.COL_ID_ALUMNO] == uid].copy()
                if not ds.empty: raa.render_alumno_details(ds, dff)
            
            st.divider()
            render_titulo_seccion("Consultar historial de un alumno")
            col_sel, col_btn = st.columns([2, 1])
            # Lista de opciones basada en la cohorte seleccionada
            with col_sel:
                # Filtrar alumnos que iniciaron en esta cohorte (S1) para el buscador
                lista_est_coh = df[(df[COL_COHORTE] == cohorte_sel) & (df[COL_SEMESTRE_ALUMNO] == 1)][[COL_NOMBRE, COL_CATRACA, COL_ID_ALUMNO]].sort_values(COL_NOMBRE)
                dic_al = {f"{r[COL_NOMBRE]} ({r[COL_CATRACA]})": r[COL_ID_ALUMNO] for _, r in lista_est_coh.iterrows()}
                sel_al = st.selectbox("Busque un alumno para ver su historial", options=list(dic_al.keys()), index=None, placeholder="Escriba el nombre del alumno...", key="sel_hist_tr")
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Ver Perfil Académico", icon=":material/person_search:", width="stretch", disabled=not sel_al, key="btn_perfil_tr"):
                    modal_perfil(dic_al[sel_al], df_full)

            st.divider()
            pdf_sel = gerar_pdf_tr(retencion_df, cohorte_sel)
            buf_ex_sel = io.BytesIO()
            with pd.ExcelWriter(buf_ex_sel, engine='xlsxwriter') as wr:
                data_c.to_excel(wr, index=False, sheet_name='Evolución TR')
                lista_view.drop(columns=[COL_ID_ALUMNO]).to_excel(wr, index=False, sheet_name=f'Alumnos S{sem_sel}')
            
            c3, c4 = st.columns(2)
            c3.download_button("Descargar Reporte (PDF)", data=pdf_sel, file_name=f"Reporte_TR_{cohorte_sel}.pdf", mime="application/pdf", key="pdf_tr_sel", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa de Retención", "PDF"))
            c4.download_button("Descargar Datos (Excel)", data=buf_ex_sel.getvalue(), file_name=f"Datos_TR_{cohorte_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="excel_tr_sel", width="stretch", on_click=db_pia.log_export_callback, args=("Tasa de Retención", "Excel"))

    st.divider()
    with st.expander("¿Cómo se calcula la Tasa de Retención?", icon=":material/functions:"):
        st.markdown("""
        La tasa de retención es el porcentaje de estudiantes retenidos por la institución que siguen activos en la carrera, independientemente de que repitan asignaturas.
        """)
        st.latex(r"TR = \frac{EIS}{EIIC} \times 100")
        st.markdown("""
        **Donde:**
        - **EIS (Estudiantes Inscritos en el Semestre):** Permanecen en la institución y continúan en la carrera en el semestre evaluado.
        - **EIIC (Ingreso Inicial):** Estudiantes matriculados en el primer semestre de la cohorte.
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
