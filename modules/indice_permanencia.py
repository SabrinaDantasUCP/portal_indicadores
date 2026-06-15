import streamlit as st
import pandas as pd
import plotly.express as px
import io
from utils import db_pia
from utils.ui import render_kpi_card
from services.data.permanencia import (
    load_permanencia_fecha_corte,
    load_permanencia_vision_general,
)
from services.calculations.permanencia import (
    calculate_permanencia_indicators,
    prepare_permanencia_source,
)

def render_common_setup():
    st.markdown("""
        <style>
        [data-testid="stElementToolbar"] { display: none; }
        div[data-testid="stDownloadButton"] button {
            min-height: 50px !important;
            font-size: 16px !important;
            border-radius: 8px !important;
        }
        .metric-container {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            font-size: 1.2rem;
            font-weight: bold;
            color: #31333F;
            margin-bottom: 1rem;
        }
        table.custom_table {
            width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 12px;
        }
        table.custom_table th {
            background-color: #4b8cd9; color: white; text-align: center; padding: 5px; border: 1px solid #ddd;
        }
        table.custom_table td {
            text-align: center; padding: 5px; border: 1px solid #ddd;
        }
        .header_explicacion {
            background-color: #66a3ff !important;
        }
        div[data-testid="stCheckbox"] label p {
            font-size: 20px !important;
            font-weight: bold !important;
            color: #1e3a8a !important; /* un azul que destaque */
        }
        div[data-testid="stTabs"] button p {
            font-size: 20px !important;
            font-weight: bold !important;
        }
        </style>
    """, unsafe_allow_html=True)

def render_actual():
    render_common_setup()
    df_act = load_permanencia_vision_general()
    if not df_act.empty:
        render_permanence_module(df_act, "actual")

def render_corte():
    render_common_setup()
    df_cor = load_permanencia_fecha_corte()
    if not df_cor.empty:
        render_permanence_module(df_cor, "corte")

def render():
    # Por defecto cargamos la versión actual si alguien llama a .render()
    render_actual()


def render_permanence_module(df_base, suffix=""):
    df_lista = prepare_permanencia_source(df_base)

    # === Configuración Global de Cálculo ===
    with st.container(border=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1: incluir_convalidados = st.checkbox(f"Incluir alumnos convalidados en el cálculo ({suffix})", value=False, key=f"conv_{suffix}")
        with col_f2: incluir_recursantes = st.checkbox(f"Incluir alumnos recursantes en el cálculo ({suffix})", value=False, key=f"recurs_{suffix}")
        st.markdown("###### Por defecto, estos dos parámetros están desactivados")

    # === TABS UI (Dentro de cada origen de datos) ===
    tab_resumen, tab_lista = st.tabs(["Visión General", "Lista Detallada"])

    with tab_resumen:
        st.markdown("#### Índice de Permanencia")
        df_vp, df_nr, df_todas_nr_list = calculate_permanencia_indicators(
            df_lista,
            incluir_convalidados=incluir_convalidados,
            incluir_recursantes=incluir_recursantes,
        )
        
        # HTML Custom Table para Índice de Permanencia
        html_table = "<table class='custom_table' style='font-size: 16px; margin-bottom: 2rem;'><thead><tr><th>Indicador</th><th>Inicio 2025.2</th><th>Rematrícula 2026.1</th><th>% de Permanencia</th></tr></thead><tbody>"
        
        total_inicio_tbl = 0
        total_rematr_tbl = 0
        
        for _, row in df_vp.iterrows():
            total_inicio_tbl += int(row['Inicio 2025.2'])
            total_rematr_tbl += int(row['Rematrícula 2026.1'])
            html_table += f"<tr><td>{row['Indicador']}</td><td>{row['Inicio 2025.2']}</td><td>{row['Rematrícula 2026.1']}</td><td>{row['% de Permanencia']}</td></tr>"
            
        tasa_total = (total_rematr_tbl / total_inicio_tbl * 100) if total_inicio_tbl > 0 else 0.0
        html_table += f"<tr style='background-color: #e2efd9; font-weight: bold; text-align: center;'><td>TOTAL</td><td>{f'{total_inicio_tbl:,}'.replace(',', '.')}</td><td>{f'{total_rematr_tbl:,}'.replace(',', '.')}</td><td>{tasa_total:.0f}%</td></tr>"
        
        html_table += "</tbody></table>"
        st.markdown(html_table, unsafe_allow_html=True)
        st.caption("2025.2 – Se contabiliza solo a los alumnos que hayan pagado la primera cuota.")

        st.markdown("<br>", unsafe_allow_html=True)
        
        # === Movemos el Gráfico de Barras aquí, debajo de la tabla ===
        st.markdown("**IP por semestre**")
        colors = []
        for _, r in df_vp.iterrows():
            val = r["tasa_num"]
            ip_val = r["Indicador"].replace(" ","")
            if ip_val == "IP1":
                if val < 76: colors.append("#d32f2f") # Rojo
                elif val < 80: colors.append("#fbc02d") # Amarillo
                else: colors.append("#388e3c") # Verde
            else:
                if val < 86: colors.append("#d32f2f")
                elif val < 90: colors.append("#fbc02d")
                else: colors.append("#388e3c")
                
        fig_bar = px.bar(df_vp, x="Indicador", y="tasa_num", text="% de Permanencia")
        fig_bar.update_traces(marker_color=colors, textposition='outside', textfont=dict(size=24, family="Arial Black"))
        fig_bar.update_layout(
            yaxis_range=[0, 110], 
            showlegend=False, 
            margin=dict(t=10, b=0, l=0, r=0), 
            height=300,
            xaxis=dict(tickfont=dict(size=16, family="Arial Black, Helvetica, sans-serif")),
            yaxis=dict(tickfont=dict(size=14))
        )
        st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_chart_{suffix}")
        
        col_metas1, col_metas2 = st.columns([1, 1.2])
        with col_metas1:
            st.markdown("""
            **Metas del Indicador:**
            | Estado | IP 1 | IP 2 al 5 |
            |---|---|---|
            | <span style="color:#d32f2f;">■</span> No alcanzado | < 76% | < 86% |
            | <span style="color:#fbc02d;">■</span> Aceptable / Advertencia | 76% - 79% | 86% - 89% |
            | <span style="color:#388e3c;">■</span> Alcanzada o superada | >= 80% | >= 90% |
            """, unsafe_allow_html=True)
            
        with col_metas2:
            st.markdown("""
            **Descripción de los Indicadores:**
            | Indicador | Descripción |
            |---|---|
            | **IP 1** | Alumnos que inician el 1º semestre en el 2025.2 y al terminar se rematricularon para el 2026.1 |
            | **IP 2** | Alumnos que inician el 2º semestre en el 2025.2 y al terminar se rematricularon para el 2026.1 |
            | **IP 3** | Alumnos que inician el 3º semestre en el 2025.2 y al terminar se rematricularon para el 2026.1 |
            | **IP 4** | Alumnos que inician el 4º semestre en el 2025.2 y al terminar se rematricularon para el 2026.1 |
            | **IP 5** | Alumnos que inician el 5º semestre en el 2025.2 y al terminar se rematricularon para el 2026.1 |
            """)

        st.markdown("---")
        st.markdown("### Detalles")
        
        # Filtro de niveles para la parte inferior
        niveles_opts = df_vp['Indicador'].tolist() # ['IP 1', 'IP 2', 'IP 3', 'IP 4', 'IP 5']
        sel_niveles = st.multiselect(f"Filtrar desglose por indicador ({suffix}):", options=niveles_opts, default=niveles_opts, key=f"flt_niveles_{suffix}")
        
        if not sel_niveles:
            st.warning("Selecciona al menos un indicador para ver el desglose.")
        else:
            # Gráficos e indicadores...
            df_vp_filt = df_vp[df_vp['Indicador'].isin(sel_niveles)]
            niveles_num = [val.replace('IP ', '').strip() for val in sel_niveles]
            df_nr_filt = df_nr[df_nr['Nivel'].isin(niveles_num)]
            
            # Totales Generales Filtrados
            total_inicio = df_vp_filt["Inicio 2025.2"].sum()
            total_rematr = df_vp_filt["Rematrícula 2026.1"].sum()
            total_norem  = total_inicio - total_rematr
            
            pct_rematr = (total_rematr / total_inicio * 100) if total_inicio > 0 else 0
            pct_norem = (total_norem / total_inicio * 100) if total_inicio > 0 else 0
            
            # Totales NR Desglosados Filtrados
            total_abandonos = df_nr_filt["Abandonos"].sum()
            total_trancados = df_nr_filt["Trancados"].sum()
            total_reprobados = df_nr_filt["Reprobados"].sum()
            
            # ====== MÉTRICAS GLOBALES (3 CARDS) ======
            c1, c2, c3 = st.columns(3)
            
            with c1:
                render_kpi_card("Total de Alumnos", f"{total_inicio:,}".replace(",", "."), accent="#385623", background="#e2efd9", border="#a9d08e")
            with c2:
                render_kpi_card("Rematriculados", f"{total_rematr:,}".replace(",", "."), accent="#385623", background="#e2efd9", border="#a9d08e")
            with c3:
                render_kpi_card("No rematriculados", f"{total_norem:,}".replace(",", "."), accent="#385623", background="#e2efd9", border="#a9d08e")

            st.markdown("<br>", unsafe_allow_html=True)

            # ====== TABLA DE MOTIVOS ======
            st.markdown("#### Motivos de No Rematriculación")
            
            row_aban = {" ": "ABANDONO"}
            row_tran = {" ": "TRANCADO"}
            row_repr = {" ": "REPROBADO"}
            
            for _, r in df_nr_filt.iterrows():
                col_name = f"IP {r['Nivel']}"
                row_aban[col_name] = r["Abandonos"]
                row_tran[col_name] = r["Trancados"]
                row_repr[col_name] = r["Reprobados"]
                
            row_aban["TOTAL"] = total_abandonos
            row_tran["TOTAL"] = total_trancados
            row_repr["TOTAL"] = total_reprobados
            
            df_motivos = pd.DataFrame([row_aban, row_tran, row_repr])
            
            # HTML Table for Motivos
            html_motivos = "<table class='custom_table' style='font-size: 16px; margin-bottom: 2rem;'><thead><tr><th>Motivo</th>"
            cols_ip = df_vp_filt['Indicador'].tolist()
            for col in cols_ip:
                html_motivos += f"<th>{col}</th>"
            html_motivos += "<th>TOTAL</th></tr></thead><tbody>"
            
            for _, row in df_motivos.iterrows():
                html_motivos += f"<tr><td style='text-align: left; font-weight: bold;'>{row[' ']}</td>"
                for col in cols_ip:
                    val = row.get(col, 0)
                    html_motivos += f"<td>{val}</td>"
                html_motivos += f"<td style='font-weight: bold; background-color: #f8f9fa;'>{row['TOTAL']}</td></tr>"
                
            html_motivos += "</tbody></table>"
            st.markdown(html_motivos, unsafe_allow_html=True)
            
            # Botón desplegable para ver la lista exacta de No Rematriculados
            if df_todas_nr_list:
                df_nr_export = pd.concat(df_todas_nr_list, ignore_index=True)
                if sel_niveles:
                    df_nr_export = df_nr_export[df_nr_export['Indicador'].isin(sel_niveles)]
                    
                with st.expander(f"Ver lista de alumnos No Rematriculados ({suffix})"):
                    map_nr_cols = {
                        'Indicador': 'Indicador (Base)',
                        'Motivo_NR': 'Motivo Específico',
                        'numero_catraca': 'Nº Catraca',
                        'nombre_apellido': 'Nombre',
                        'estado_matricula': 'Estado Matrícula',
                        'status_academico': 'Estatus Académico',
                        'tipo_matricula': 'Tipo de Matrícula',
                        'es_recursante': '¿Es recursante?',
                        'estado_pago_20252': 'Estado de Pago 2025.2 (1° Cuota)',
                        'estado_pago_20261': 'Estado de Pago 2026.1 (1° Cuota)',
                        'sem_252': 'Semestre 2025.2',
                        'sem_261': 'Semestre 2026.1',
                        'momento_cambio': 'Momento de Cambio',
                        'desc_audit_log': 'Descripción Audit Log'
                    }
                    
                    cols_to_show = [c for c in map_nr_cols.keys() if c in df_nr_export.columns]
                    df_show = df_nr_export[cols_to_show].rename(columns=map_nr_cols)
                    
                    # Capitalizar valores para mejor presentación
                    if 'Estado Matrícula' in df_show.columns:
                        df_show['Estado Matrícula'] = df_show['Estado Matrícula'].astype(str).str.capitalize()
                    if 'Estatus Académico' in df_show.columns:
                        df_show['Estatus Académico'] = df_show['Estatus Académico'].astype(str).str.capitalize()
                    
                    df_show.insert(2, 'Base Inicio 2025.2', '✅')
                    df_show.insert(3, 'Éxito Rematrícula 2026.1', '❌')
                    
                    for col_str in ['Semestre 2025.2', 'Semestre 2026.1']:
                        if col_str in df_show.columns:
                            df_show[col_str] = pd.to_numeric(df_show[col_str], errors='coerce').fillna(-1).astype(int).astype(str).replace('-1', '')
                    
                    st.dataframe(df_show, hide_index=True)
                    
                    buf_nr = io.BytesIO()
                    df_show.to_excel(buf_nr, index=False)
                    st.download_button(
                        "Descargar (Excel)",
                        data=buf_nr.getvalue(),
                        file_name="No_Rematriculados_Desglose.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        icon=":material/download:",
                        key=f"dl_nr_{suffix}",
                        on_click=db_pia.log_export_callback, args=("Detalle de No Rematriculados - IP", "Excel")
                    )

            st.markdown("<br>", unsafe_allow_html=True)
            
            # ====== GRÁFICO CIRCULAR ======
            st.markdown("**% IP GENERAL DEL SEMESTRE**")
            df_pie = pd.DataFrame({
                "Estado": ["Rematriculados", "No Rematriculados"],
                "Valor": [total_rematr, total_norem]
            })
            fig_pie = px.pie(df_pie, names="Estado", values="Valor", hole=0.5, color="Estado",
                             color_discrete_map={"Rematriculados":"#388e3c", "No Rematriculados":"#d32f2f"})
            fig_pie.update_traces(textinfo='percent', textposition='inside', textfont=dict(size=18, color="white", family="Arial Black"))
            fig_pie.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0), height=300, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_chart_{suffix}")

        st.divider()
        buf_ex = io.BytesIO()
        with pd.ExcelWriter(buf_ex, engine='xlsxwriter') as wr:
            df_vp.drop(columns=["tasa_num"]).to_excel(wr, index=False, sheet_name='Vision_Permanencia')
            df_nr.to_excel(wr, index=False, sheet_name='Vision_No_Rematriculados')
        
        st.download_button(
            "Descargar Tablas de Resumen (Excel)",
            data=buf_ex.getvalue(),
            file_name="Reporte_Resumen_Permanencia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            key=f"dl_res_{suffix}",
            on_click=db_pia.log_export_callback, args=("Índice de Permanencia - Resumen", "Excel")
        )

    with tab_lista:
        # Layout de los filtros (3 filas x 3 columnas)
        c_f1, c_f2, c_f3 = st.columns(3)
        c_f4, c_f5, c_f6 = st.columns(3)
        c_f7, c_f8, c_f9 = st.columns(3)
        
        # Opciones
        conval_opts = ["Todos", "Solo Convalidados", "Excluir Convalidados"]
        recurs_opts = ["Todos", "Solo Recursantes", "Excluir Recursantes"]
        sems_252_opts = sorted(list(df_lista['sem_252'].unique()))
        pago_252_opts = ["Todos", "Pagó (Primera cuota Paga)", "No Pagó"]
        pago_261_opts = ["Todos", "Pagó (Primera cuota Paga)", "No Pagó"]
        estados_opts = sorted([str(e).title() for e in df_lista['estado_matricula'].unique() if pd.notna(e) and str(e).strip() != ''])
        cons_opts = ["Todos", "Sí", "No"]
        exito_opts = ["Todos", "Sí", "No"]
        
        with c_f1: flt_conval = st.selectbox("Alumnos Convalidados", options=conval_opts, index=0, key=f"f1_{suffix}")
        with c_f2: flt_recurs = st.selectbox("Alumnos Recursantes", options=recurs_opts, index=0, key=f"f2_{suffix}")
        with c_f3: flt_nombre = st.text_input("Buscar por Nombre", value="", placeholder="Escribe un nombre...", key=f"f3_{suffix}")
        
        with c_f4: flt_pago252= st.selectbox("Estado de Pago 2025.2", options=pago_252_opts, index=0, key=f"f4_{suffix}")
        with c_f5: flt_sem252 = st.multiselect("Semestre en 2025.2", options=sems_252_opts, placeholder="Todos", key=f"f5_{suffix}")
        with c_f6: flt_cons = st.selectbox("Base: ¿Fue Considerado en Inicio?", options=cons_opts, index=0, key=f"f6_{suffix}")
        
        with c_f7: flt_pago261= st.selectbox("Estado de Pago 2026.1", options=pago_261_opts, index=0, key=f"f7_{suffix}")
        with c_f8: flt_estado = st.multiselect("Estado Matrícula", options=estados_opts, placeholder="Todos", key=f"f8_{suffix}")
        with c_f9: flt_exito = st.selectbox("Éxito: ¿Fue Rematriculado?", options=exito_opts, index=0, key=f"f9_{suffix}")
        
        # Aplicamos los filtros al subset local
        df_list_filt = df_lista.copy()
        
        # Calcular si fue considerado en el cálculo principal (ANTES DE FILTRAR)
        es_paga_local = df_list_filt['estado_pago_20252'].astype(str).str.lower().str.contains('paga', na=False) if 'estado_pago_20252' in df_list_filt.columns else pd.Series(False, index=df_list_filt.index)
        es_paga_261_local = df_list_filt['estado_pago_20261'].astype(str).str.lower().str.contains('paga', na=False) if 'estado_pago_20261' in df_list_filt.columns else pd.Series(False, index=df_list_filt.index)
        is_conval_local = df_list_filt['tipo_matricula'].astype(str).str.lower().str.contains('convalid', na=False) if 'tipo_matricula' in df_list_filt.columns else pd.Series(False, index=df_list_filt.index)
        is_recurs_local = df_list_filt['es_recursante'].astype(str).str.strip().str.lower().isin(['si', 'true', '1', 's']) if 'es_recursante' in df_list_filt.columns else pd.Series(False, index=df_list_filt.index)
        v_momento = df_list_filt['momento_cambio'] != 'Antes del inicio de clases'
        v_sem = df_list_filt['sem_252'].isin([1, 2, 3, 4, 5])
        
        # 1) MATEMÁTICA BASE (Inicio 2025.2)
        cons_mask = es_paga_local & v_momento & v_sem
        if not incluir_convalidados: cons_mask &= ~is_conval_local
        if not incluir_recursantes: cons_mask &= ~is_recurs_local
        
        # 2) MATEMÁTICA ÉXITO (Rematrícula 2026.1)
        exito_cond1 = df_list_filt['sem_261'] == df_list_filt['sem_252']
        exito_cond2 = df_list_filt['sem_261'] == (df_list_filt['sem_252'] + 1)
        exito_mask = cons_mask & es_paga_261_local & (exito_cond1 | exito_cond2)
        
        df_list_filt['Considerado_IP'] = cons_mask.apply(lambda x: '✅' if x else '❌')
        df_list_filt['Rematriculado_IP'] = exito_mask.apply(lambda x: '✅' if x else '❌')
        
        # --- APLICACIÓN DE FILTROS EN CASCADA ---
        if flt_conval == "Solo Convalidados": df_list_filt = df_list_filt[is_conval_local]
        elif flt_conval == "Excluir Convalidados": df_list_filt = df_list_filt[~is_conval_local]
            
        if flt_recurs == "Solo Recursantes": df_list_filt = df_list_filt[is_recurs_local]
        elif flt_recurs == "Excluir Recursantes": df_list_filt = df_list_filt[~is_recurs_local]
            
        if flt_pago252 == "Pagó (Primera cuota Paga)": df_list_filt = df_list_filt[es_paga_local]
        elif flt_pago252 == "No Pagó": df_list_filt = df_list_filt[~es_paga_local]
            
        if flt_pago261 == "Pagó (Primera cuota Paga)": df_list_filt = df_list_filt[es_paga_261_local]
        elif flt_pago261 == "No Pagó": df_list_filt = df_list_filt[~es_paga_261_local]
        
        if flt_sem252:
            df_list_filt = df_list_filt[df_list_filt['sem_252'].isin(flt_sem252)]
            
        if flt_estado:
            if 'estado_matricula' in df_list_filt.columns:
                flt_estado_lower = [e.lower() for e in flt_estado]
                df_list_filt = df_list_filt[df_list_filt['estado_matricula'].isin(flt_estado_lower)]
                
        if flt_cons == "Sí": df_list_filt = df_list_filt[df_list_filt['Considerado_IP'] == '✅']
        elif flt_cons == "No": df_list_filt = df_list_filt[df_list_filt['Considerado_IP'] == '❌']
        
        if flt_exito == "Sí": df_list_filt = df_list_filt[df_list_filt['Rematriculado_IP'] == '✅']
        elif flt_exito == "No": df_list_filt = df_list_filt[df_list_filt['Rematriculado_IP'] == '❌']
                
        if flt_nombre.strip():
            if 'nombre_apellido' in df_list_filt.columns:
                df_list_filt = df_list_filt[df_list_filt['nombre_apellido'].astype(str).str.contains(flt_nombre.strip(), case=False, na=False)]
            
        st.markdown(f"<div class='metric-container'>Mostrando {len(df_list_filt)} alumnos filtrados</div>", unsafe_allow_html=True)
        
        # Configurar las columnas esperadas
        cols_finales = []
        map_cols = {
            'Considerado_IP': 'Base Inicio 2025.2',
            'Rematriculado_IP': 'Éxito Rematrícula 2026.1',
            'numero_catraca': 'Nº Catraca',
            'nombre_apellido': 'Nombre',
            'estado_matricula': 'Estado Matrícula',
            'status_academico': 'Estatus Académico',
            'tipo_alumno': 'Tipo Alumno',
            'es_recursante': '¿Es recursante?',
            'semestre_20252': 'Semestre 2025.2',
            'semestre_20261': 'Semestre 2026.1',
            'estado_pago_20252': 'Estado Pago 2025.2',
            'Monto Pagado 2025.2': 'Monto 2025.2',
            'estado_pago_20261': 'Estado Pago 2026.1',
            'Monto Pagado 2026.1': 'Monto 2026.1',
            'tipo_matricula': '¿Es convalidado?',
            'fecha_cambio': 'Fecha Cambio',
            'usuario_cambio': 'Usuario Modificación',
            'desc_audit_log': 'Audit Log'
        }
        
        for k, text in map_cols.items():
            if k in df_list_filt.columns:
                df_list_filt = df_list_filt.rename(columns={k: text})
                cols_finales.append(text)
        # Formato visual de texto (Mayúsculas Iniciales)
        if 'Estado Matrícula' in cols_finales:
            df_list_filt['Estado Matrícula'] = df_list_filt['Estado Matrícula'].str.title()
        if 'Estatus Académico' in cols_finales:
            df_list_filt['Estatus Académico'] = df_list_filt['Estatus Académico'].str.title()
            
        # Convertir a Entero para evitar decimales, y luego a Texto Puro para soportar blancos inmaculados
        for sem_col in ['Semestre 2025.2', 'Semestre 2026.1']:
            if sem_col in cols_finales:
                df_list_filt[sem_col] = pd.to_numeric(df_list_filt[sem_col], errors='coerce').fillna(-1).astype(int).astype(str).replace('-1', '')

        # Convertir nulos o textos 'nan' a espacios en blanco puramente visuales (sólo en columnas de texto)
        for c in cols_finales:
            if str(df_list_filt[c].dtype) != 'Int64':
                df_list_filt[c] = df_list_filt[c].fillna('')
                df_list_filt[c] = df_list_filt[c].replace(['nan', 'NaN', 'None', '<NA>', 'null', 'Null'], '')

        st.dataframe(df_list_filt[cols_finales], width="stretch", hide_index=True)
        
        # Download button para la lista
        buf_list = io.BytesIO()
        df_list_filt[cols_finales].to_excel(buf_list, index=False, sheet_name="Alumnos_Filtrados")
        st.download_button(
            "Descargar Lista (Excel)",
            data=buf_list.getvalue(),
            file_name="Lista_Alumnos_Filtrados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            key=f"btn_dl_lista_{suffix}",
            on_click=db_pia.log_export_callback, args=("Índice de Permanencia - Lista", "Excel")
        )

    # === METODOLOGÍA GLOBAL AL FINAL DE LA PÁGINA ===
    st.divider()
    st.markdown("""
### Criterios y Metodología de Análisis

A continuación se detallan las reglas lógicas y comerciales aplicadas para obtener los resultados del **Índice de Permanencia**.

#### 1. ¿Qué es la Permanencia?
La permanencia mide cuántos alumnos que estudiaron en el periodo **2025.2** continuaron en el siguiente periodo **2026.1**.

- **Quiénes se consideran (base)**:  
  Todos los alumnos que pagaron correctamente su primera cuota en 2025.2.

- **Cuándo se considera que un alumno continuó (éxito)**:  
  Cuando el alumno:
  - Pagó su primera cuota en 2026.1, y  
  - El alumno avanzó de semestre o permaneció en el mismo (recursante).  

---

#### 2. Fechas importantes (bajas de matrícula)

Si el alumno tuvo un cambio de estado a **suspenso** o **trancado**:

- **Antes del inicio de clases**:  
  No se tiene en cuenta en el análisis.  
  - 04/08/2025: alumnos de 1º semestre  
  - 30/07/2025: alumnos antiguos  
- **Después del inicio de clases**:  
  Sí se incluye en el análisis (como retenido o no retenido).

---

#### 3. Alumnos que no continuaron

Los alumnos que estaban en 2025.2 pero no siguieron en 2026.1 se clasifican así:


- **Trancados**: si el alumno tiene el estado **trancado**, se contabiliza en esta categoría.  
- **Reprobados**: si el alumno **no está trancado** y tiene al menos una materia reprobada, se contabiliza aquí.  
- **Abandonos**: si el alumno **no está trancado** y **no tiene materias reprobadas**, se contabiliza en esta categoría.


---

#### 4. Filtros del sistema

El sistema permite activar o desactivar ciertos tipos de alumnos:

- **Convalidados**
- **Recursantes**: alumnos que ya cursaron en 2025.1 y están repitiendo (recursando) **el mismo semestre** en 2025.2.

Si estos filtros están apagados, esos alumnos no se incluyen en el análisis, para que el indicador sea más preciso.

---

#### 5. Exclusiones 

- Alumnos convalidados en su primer semestre están siendo desconsiderados del cálculo; solo se incluyen aquellos alumnos convalidados que ya han cursado al menos un semestre.
    """)
