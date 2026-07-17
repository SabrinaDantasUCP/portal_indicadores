import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import io
from utils import db_pia
from utils.ui import render_kpi_card
from services.data.permanencia import (
    VISTA_FECHA_CORTE,
    VISTA_VISION_GENERAL,
    get_periodo_config_efectivo,
    load_permanencia_lista,
)
from services.calculations.permanencia import (
    PERIODO_DEFAULT,
    calculate_permanencia_indicators,
    es_convalidado,
    es_pago,
    es_recursante,
    evaluar_base,
    listar_periodos,
)


@st.cache_data(show_spinner=False, max_entries=8, ttl=600)
def excel_bytes(df, sheet_name="Datos"):
    """Arma el Excel una sola vez por combinación de datos.

    st.download_button exige los bytes por adelantado, así que sin cache el
    archivo se generaba en cada rerun aunque nadie lo descargara.
    """
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


@st.cache_data(show_spinner=False, max_entries=8, ttl=600)
def excel_resumen_bytes(df_vp, df_nr):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as wr:
        df_vp.to_excel(wr, index=False, sheet_name='Vision_Permanencia')
        df_nr.to_excel(wr, index=False, sheet_name='Vision_No_Rematriculados')
    return buffer.getvalue()

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
        .ip_header {
            background: linear-gradient(90deg, #1e3a8a 0%, #4b8cd9 100%);
            color: white;
            padding: 18px 26px;
            border-radius: 10px;
            margin: 10px 0 25px 0;
            box-shadow: 0 2px 5px rgba(0,0,0,.15);
        }
        .ip_header_title {
            font-size: 32px; font-weight: 800; line-height: 1.2; margin: 0;
        }
        .ip_header_sub {
            font-size: 17px; opacity: .92; margin-top: 6px;
        }
        </style>
    """, unsafe_allow_html=True)

# Nombre de cada vista, para mostrarlo en el título del indicador.
VISTA_LABELS = {
    "actual": "Visión General",
    "corte": "Fecha de Corte",
}

VISTA_POR_SUFIJO = {
    "actual": VISTA_VISION_GENERAL,
    "corte": VISTA_FECHA_CORTE,
}

# Lo que se muestra en la tabla cuando no hay dato.
SIN_DATO = "-"


def select_periodo(suffix):
    """Selector obligatorio del periodo: sin selección no se muestra ningún dato."""
    with st.container(border=True):
        periodo = st.selectbox(
            "Seleccione el indicador que desea visualizar",
            options=listar_periodos(),
            index=None,
            placeholder="Elija un indicador para ver los datos...",
            key=f"ip_periodo_{suffix}",
            format_func=lambda p: f"Índice de Permanencia {p}",
        )

    if not periodo:
        st.info("Seleccione el **indicador** que desea visualizar para continuar.")

    return periodo

def render_actual():
    render_common_setup()
    periodo = select_periodo("actual")
    if periodo:
        render_permanence_module("actual", periodo)

def render_corte():
    render_common_setup()
    periodo = select_periodo("corte")
    if periodo:
        render_permanence_module("corte", periodo)

def render():
    # Por defecto cargamos la versión actual si alguien llama a .render()
    render_actual()


def render_permanence_module(suffix="", periodo=PERIODO_DEFAULT):
    # Las fechas pueden estar configuradas por un admin; si no, son las del código.
    config = get_periodo_config_efectivo(periodo)
    p_base = periodo
    p_dest = config["destino"]
    p_ant = config["anterior"]
    # Las claves de los widgets llevan el periodo para que los filtros se
    # reinicien al cambiar de indicador.
    k = f"{suffix}_{p_base}"

    df_lista = load_permanencia_lista(
        periodo,
        VISTA_POR_SUFIJO[suffix],
        config["limite_primer_semestre"],
        config["limite_otros_semestres"],
    )
    if df_lista.empty:
        st.warning(f"No hay datos de permanencia disponibles para el periodo {periodo}.")
        return

    # === Título del indicador que se está viendo ===
    st.markdown(f"""
        <div class="ip_header">
            <div class="ip_header_title">Índice de Permanencia {p_base}</div>
            <div class="ip_header_sub">{VISTA_LABELS.get(suffix, suffix)} · Inicio {p_base} → Rematrícula {p_dest}</div>
        </div>
    """, unsafe_allow_html=True)

    # === Configuración Global de Cálculo ===
    with st.container(border=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1: incluir_convalidados = st.checkbox(f"Incluir alumnos convalidados en el cálculo ({suffix})", value=False, key=f"conv_{k}")
        with col_f2: incluir_recursantes = st.checkbox(f"Incluir alumnos recursantes en el cálculo ({suffix})", value=False, key=f"recurs_{k}")
        st.markdown("###### Por defecto, estos dos parámetros están desactivados")

    # === TABS UI (Dentro de cada origen de datos) ===
    tab_resumen, tab_lista = st.tabs(["Visión General", "Lista Detallada"])

    with tab_resumen:
        st.markdown("#### Índice de Permanencia")
        df_vp, df_nr, df_todas_nr_list = calculate_permanencia_indicators(
            df_lista,
            incluir_convalidados=incluir_convalidados,
            incluir_recursantes=incluir_recursantes,
            periodo=periodo,
        )

        # HTML Custom Table para Índice de Permanencia
        html_table = f"<table class='custom_table' style='font-size: 16px; margin-bottom: 2rem;'><thead><tr><th>Indicador</th><th>Inicio {p_base}</th><th>Rematrícula {p_dest}</th><th>% de Permanencia</th></tr></thead><tbody>"

        total_inicio_tbl = 0
        total_rematr_tbl = 0

        for _, row in df_vp.iterrows():
            total_inicio_tbl += int(row['Inicio'])
            total_rematr_tbl += int(row['Rematrícula'])
            html_table += f"<tr><td>{row['Indicador']}</td><td>{row['Inicio']}</td><td>{row['Rematrícula']}</td><td>{row['% de Permanencia']}</td></tr>"
            
        tasa_total = (total_rematr_tbl / total_inicio_tbl * 100) if total_inicio_tbl > 0 else 0.0
        html_table += f"<tr style='background-color: #e2efd9; font-weight: bold; text-align: center;'><td>TOTAL</td><td>{f'{total_inicio_tbl:,}'.replace(',', '.')}</td><td>{f'{total_rematr_tbl:,}'.replace(',', '.')}</td><td>{tasa_total:.0f}%</td></tr>"
        
        html_table += "</tbody></table>"
        st.markdown(html_table, unsafe_allow_html=True)
        st.caption(f"{p_base} – Se contabiliza solo a los alumnos que hayan pagado la primera cuota.")

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
        st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_chart_{k}")
        
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
            filas_desc = "\n".join(
                f"            | **IP {n}** | Alumnos que inician el {n}º semestre en el {p_base} y al terminar se rematricularon para el {p_dest} |"
                for n in range(1, 6)
            )
            st.markdown(f"""
            **Descripción de los Indicadores:**
            | Indicador | Descripción |
            |---|---|
{filas_desc}
            """)

        st.markdown("---")
        st.markdown("### Detalles")
        
        # Filtro de niveles para la parte inferior
        niveles_opts = df_vp['Indicador'].tolist() # ['IP 1', 'IP 2', 'IP 3', 'IP 4', 'IP 5']
        sel_niveles = st.multiselect(f"Filtrar desglose por indicador ({suffix}):", options=niveles_opts, default=niveles_opts, key=f"flt_niveles_{k}")
        
        if not sel_niveles:
            st.warning("Selecciona al menos un indicador para ver el desglose.")
        else:
            # Gráficos e indicadores...
            df_vp_filt = df_vp[df_vp['Indicador'].isin(sel_niveles)]
            niveles_num = [val.replace('IP ', '').strip() for val in sel_niveles]
            df_nr_filt = df_nr[df_nr['Nivel'].isin(niveles_num)]
            
            # Totales Generales Filtrados
            total_inicio = df_vp_filt["Inicio"].sum()
            total_rematr = df_vp_filt["Rematrícula"].sum()
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
                    
                with st.expander(f"Ver lista de alumnos No Rematriculados ({suffix} · {p_base})"):
                    map_nr_cols = {
                        'Indicador': 'Indicador (Base)',
                        'Motivo_NR': 'Motivo Específico',
                        'numero_catraca': 'Número de Matrícula',
                        'nombre_apellido': 'Nombre',
                        'estado_matricula': 'Estado Matrícula',
                        'status_academico': 'Estatus Académico',
                        'tipo_matricula': 'Tipo de Matrícula',
                        'es_recursante': '¿Es recursante?',
                        'estado_pago_atual': f'Estado de Pago {p_base} (1° Cuota)',
                        'estado_pago_proximo': f'Estado de Pago {p_dest} (1° Cuota)',
                        'sem_atual': f'Semestre {p_base}',
                        'sem_proximo': f'Semestre {p_dest}',
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
                    
                    df_show.insert(2, f'Base Inicio {p_base}', '✅')
                    df_show.insert(3, f'Éxito Rematrícula {p_dest}', '❌')

                    for col_str in [f'Semestre {p_base}', f'Semestre {p_dest}']:
                        if col_str in df_show.columns:
                            df_show[col_str] = pd.to_numeric(df_show[col_str], errors='coerce').fillna(-1).astype(int).astype(str).replace('-1', '')
                    
                    st.dataframe(df_show, hide_index=True)
                    
                    st.download_button(
                        "Descargar (Excel)",
                        data=excel_bytes(df_show, "No_Rematriculados"),
                        file_name=f"No_Rematriculados_Desglose_{p_base}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        icon=":material/download:",
                        key=f"dl_nr_{k}",
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
            st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_chart_{k}")

        st.divider()
        df_vp_export = df_vp.drop(columns=["tasa_num"]).rename(
            columns={"Inicio": f"Inicio {p_base}", "Rematrícula": f"Rematrícula {p_dest}"}
        )
        st.download_button(
            "Descargar Tablas de Resumen (Excel)",
            data=excel_resumen_bytes(df_vp_export, df_nr),
            file_name=f"Reporte_Resumen_Permanencia_{p_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            key=f"dl_res_{k}",
            on_click=db_pia.log_export_callback, args=("Índice de Permanencia - Resumen", "Excel")
        )

    with tab_lista:
        # --- Marcas del indicador (misma regla que la tabla de resumen) ---
        cons_mask, motivos = evaluar_base(df_lista, incluir_convalidados, incluir_recursantes, p_base)

        es_paga_atual = es_pago(df_lista, 'estado_pago_atual')
        es_paga_proximo = es_pago(df_lista, 'estado_pago_proximo')
        is_conval = es_convalidado(df_lista)
        is_recurs = es_recursante(df_lista)

        avanzo_o_repite = (
            (df_lista['sem_proximo'] == df_lista['sem_atual'])
            | (df_lista['sem_proximo'] == (df_lista['sem_atual'] + 1))
        )
        exito_mask = cons_mask & es_paga_proximo & avanzo_o_repite

        df_list_filt = df_lista.copy()
        df_list_filt['Considerado_IP'] = np.where(cons_mask, '✅', '❌')
        df_list_filt['Rematriculado_IP'] = np.where(exito_mask, '✅', '❌')
        df_list_filt['Motivo_exclusion'] = motivos

        # --- Filtros (plegados para que la tabla quede a la vista) ---
        conval_opts = ["Todos", "Solo Convalidados", "Excluir Convalidados"]
        recurs_opts = ["Todos", "Solo Recursantes", "Excluir Recursantes"]
        sems_atual_opts = sorted(list(df_lista['sem_atual'].unique()))
        pago_atual_opts = ["Todos", "Pagó (Primera cuota Paga)", "No Pagó"]
        pago_proximo_opts = ["Todos", "Pagó (Primera cuota Paga)", "No Pagó"]
        estados_opts = sorted([str(e).title() for e in df_lista['estado_matricula'].unique() if pd.notna(e) and str(e).strip() != ''])
        cons_opts = ["Todos", "Sí", "No"]
        exito_opts = ["Todos", "Sí", "No"]

        filtros_keys = [f"f{i}_{k}" for i in range(1, 10)]

        def limpiar_filtros():
            for filtro_key in filtros_keys:
                st.session_state.pop(filtro_key, None)

        # Se lee de session_state porque la etiqueta se arma antes que los widgets.
        activos = sum([
            st.session_state.get(f"f1_{k}", "Todos") != "Todos",
            st.session_state.get(f"f2_{k}", "Todos") != "Todos",
            bool(str(st.session_state.get(f"f3_{k}", "")).strip()),
            st.session_state.get(f"f4_{k}", "Todos") != "Todos",
            bool(st.session_state.get(f"f5_{k}", [])),
            st.session_state.get(f"f6_{k}", "Todos") != "Todos",
            st.session_state.get(f"f7_{k}", "Todos") != "Todos",
            bool(st.session_state.get(f"f8_{k}", [])),
            st.session_state.get(f"f9_{k}", "Todos") != "Todos",
        ])
        etiqueta_filtros = "Filtros de búsqueda" if not activos else f"Filtros de búsqueda · {activos} activo(s)"

        # Arranca plegado para que la tabla quede a la vista, pero se abre solo si
        # hay filtros puestos: así nunca queda oculto por qué la lista está recortada.
        with st.expander(etiqueta_filtros, expanded=bool(activos)):
            c_f1, c_f2, c_f3 = st.columns(3)
            c_f4, c_f5, c_f6 = st.columns(3)
            c_f7, c_f8, c_f9 = st.columns(3)

            with c_f1: flt_conval = st.selectbox("Alumnos Convalidados", options=conval_opts, index=0, key=f"f1_{k}", help="Solo filtra lo que ves en la tabla; no cambia el cálculo del indicador.")
            with c_f2: flt_recurs = st.selectbox("Alumnos Recursantes", options=recurs_opts, index=0, key=f"f2_{k}", help="Solo filtra lo que ves en la tabla; no cambia el cálculo del indicador.")
            with c_f3: flt_busqueda = st.text_input("Buscar por Nombre o Matrícula", value="", placeholder="Nombre o número de matrícula...", key=f"f3_{k}")

            with c_f4: flt_pago_atual = st.selectbox(f"Estado de Pago {p_base}", options=pago_atual_opts, index=0, key=f"f4_{k}")
            with c_f5: flt_sem_atual = st.multiselect(f"Semestre en {p_base}", options=sems_atual_opts, placeholder="Todos", key=f"f5_{k}")
            with c_f6: flt_cons = st.selectbox("Base: ¿Fue Considerado en Inicio?", options=cons_opts, index=0, key=f"f6_{k}")

            with c_f7: flt_pago_proximo = st.selectbox(f"Estado de Pago {p_dest}", options=pago_proximo_opts, index=0, key=f"f7_{k}")
            with c_f8: flt_estado = st.multiselect("Estado Matrícula", options=estados_opts, placeholder="Todos", key=f"f8_{k}")
            with c_f9: flt_exito = st.selectbox("Éxito: ¿Fue Rematriculado?", options=exito_opts, index=0, key=f"f9_{k}")

            st.button(
                "Limpiar filtros",
                icon=":material/refresh:",
                key=f"clear_{k}",
                on_click=limpiar_filtros,
                disabled=not activos,
            )

        # --- APLICACIÓN DE FILTROS EN CASCADA ---
        if flt_conval == "Solo Convalidados": df_list_filt = df_list_filt[is_conval]
        elif flt_conval == "Excluir Convalidados": df_list_filt = df_list_filt[~is_conval]

        if flt_recurs == "Solo Recursantes": df_list_filt = df_list_filt[is_recurs]
        elif flt_recurs == "Excluir Recursantes": df_list_filt = df_list_filt[~is_recurs]

        if flt_pago_atual == "Pagó (Primera cuota Paga)": df_list_filt = df_list_filt[es_paga_atual]
        elif flt_pago_atual == "No Pagó": df_list_filt = df_list_filt[~es_paga_atual]

        if flt_pago_proximo == "Pagó (Primera cuota Paga)": df_list_filt = df_list_filt[es_paga_proximo]
        elif flt_pago_proximo == "No Pagó": df_list_filt = df_list_filt[~es_paga_proximo]

        if flt_sem_atual:
            df_list_filt = df_list_filt[df_list_filt['sem_atual'].isin(flt_sem_atual)]

        if flt_estado:
            if 'estado_matricula' in df_list_filt.columns:
                flt_estado_lower = [e.lower() for e in flt_estado]
                df_list_filt = df_list_filt[df_list_filt['estado_matricula'].isin(flt_estado_lower)]

        if flt_cons == "Sí": df_list_filt = df_list_filt[df_list_filt['Considerado_IP'] == '✅']
        elif flt_cons == "No": df_list_filt = df_list_filt[df_list_filt['Considerado_IP'] == '❌']

        if flt_exito == "Sí": df_list_filt = df_list_filt[df_list_filt['Rematriculado_IP'] == '✅']
        elif flt_exito == "No": df_list_filt = df_list_filt[df_list_filt['Rematriculado_IP'] == '❌']

        if flt_busqueda.strip():
            texto = flt_busqueda.strip()
            por_nombre = df_list_filt['nombre_apellido'].astype(str).str.contains(texto, case=False, na=False)
            por_matricula = df_list_filt['numero_catraca'].astype(str).str.contains(texto, case=False, na=False)
            df_list_filt = df_list_filt[por_nombre | por_matricula]

        # --- Resumen de lo que se está viendo ---
        n_listados = len(df_list_filt)
        n_base = int((df_list_filt['Considerado_IP'] == '✅').sum())
        n_remat = int((df_list_filt['Rematriculado_IP'] == '✅').sum())

        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
        with c_kpi1:
            render_kpi_card("Alumnos listados", f"{n_listados:,}".replace(",", "."), accent="#385623", background="#e2efd9", border="#a9d08e")
        with c_kpi2:
            render_kpi_card(f"En la base ({p_base})", f"{n_base:,}".replace(",", "."), accent="#385623", background="#e2efd9", border="#a9d08e")
        with c_kpi3:
            render_kpi_card(f"Rematriculados ({p_dest})", f"{n_remat:,}".replace(",", "."), accent="#385623", background="#e2efd9", border="#a9d08e")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- Columnas ---
        map_cols = {
            'Considerado_IP': f'Base Inicio {p_base}',
            'Motivo_exclusion': 'Motivo de exclusión',
            'Rematriculado_IP': f'Éxito Rematrícula {p_dest}',
            'numero_catraca': 'Número de Matrícula',
            'nombre_apellido': 'Nombre',
            'estado_matricula': 'Estado Matrícula',
            'semestre_atual': f'Semestre {p_base}',
            'semestre_proximo': f'Semestre {p_dest}',
            'estado_pago_atual': f'Estado Pago {p_base}',
            'estado_pago_proximo': f'Estado Pago {p_dest}',
            'status_academico': 'Estatus Académico',
            'tipo_alumno': 'Tipo Alumno',
            'es_recursante': '¿Es recursante?',
            'monto_pagado_atual': f'Monto {p_base}',
            'monto_pagado_proximo': f'Monto {p_dest}',
            'tipo_matricula': '¿Es convalidado?',
            'fecha_cambio': 'Fecha Cambio',
            'usuario_cambio': 'Usuario Modificación',
            'desc_audit_log': 'Audit Log',
        }
        # El resto queda disponible en el selector, para no arrancar con 19 columnas.
        cols_por_defecto = [
            f'Base Inicio {p_base}', 'Motivo de exclusión', f'Éxito Rematrícula {p_dest}',
            'Número de Matrícula', 'Nombre', 'Estado Matrícula',
            f'Semestre {p_base}', f'Semestre {p_dest}',
            f'Estado Pago {p_base}', f'Estado Pago {p_dest}',
        ]

        cols_finales = []
        for col_origen, etiqueta in map_cols.items():
            if col_origen in df_list_filt.columns:
                df_list_filt = df_list_filt.rename(columns={col_origen: etiqueta})
                cols_finales.append(etiqueta)

        # Formato visual de texto (Mayúsculas Iniciales)
        if 'Estado Matrícula' in cols_finales:
            df_list_filt['Estado Matrícula'] = df_list_filt['Estado Matrícula'].str.title()
        if 'Estatus Académico' in cols_finales:
            df_list_filt['Estatus Académico'] = df_list_filt['Estatus Académico'].str.title()

        # Semestre sin dato -> "-". Van como texto de un solo dígito (1 a 6), así que
        # el orden alfabético sigue coincidiendo con el numérico.
        for sem_col in [f'Semestre {p_base}', f'Semestre {p_dest}']:
            if sem_col in cols_finales:
                df_list_filt[sem_col] = (
                    pd.to_numeric(df_list_filt[sem_col], errors='coerce')
                    .astype('Int64').astype(str).replace('<NA>', SIN_DATO)
                )

        # Nulos y textos 'nan' a "-", solo en columnas de texto (no tocar números).
        for c in cols_finales:
            if pd.api.types.is_object_dtype(df_list_filt[c]):
                df_list_filt[c] = df_list_filt[c].fillna(SIN_DATO)
                df_list_filt[c] = df_list_filt[c].replace(
                    ['', 'nan', 'NaN', 'None', '<NA>', 'null', 'Null'], SIN_DATO
                )

        cols_visibles = st.multiselect(
            "Columnas a mostrar",
            options=cols_finales,
            default=[c for c in cols_por_defecto if c in cols_finales],
            key=f"cols_{k}",
            help="Las columnas de auditoría (Audit Log, Usuario, Fecha de Cambio) están disponibles acá.",
        )
        if not cols_visibles:
            st.info("Seleccione al menos una columna para ver la tabla.")
        else:
            column_config = {
                f'Semestre {p_base}': st.column_config.TextColumn(width="small"),
                f'Semestre {p_dest}': st.column_config.TextColumn(width="small"),
                f'Monto {p_base}': st.column_config.NumberColumn(label=f"Monto {p_base} (Gs.)", format="localized"),
                f'Monto {p_dest}': st.column_config.NumberColumn(label=f"Monto {p_dest} (Gs.)", format="localized"),
                'Nombre': st.column_config.TextColumn(width="medium", pinned=True),
                'Motivo de exclusión': st.column_config.TextColumn(
                    width="large",
                    help="Por qué el alumno no entra en la base del indicador. Vacío = sí entra.",
                ),
            }
            df_view = df_list_filt[cols_visibles]
            st.dataframe(df_view, width="stretch", hide_index=True, column_config=column_config)

            st.download_button(
                "Descargar Lista (Excel)",
                data=excel_bytes(df_view, "Alumnos_Filtrados"),
                file_name=f"Lista_Alumnos_Filtrados_{p_base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                icon=":material/download:",
                width="stretch",
                key=f"btn_dl_lista_{k}",
                on_click=db_pia.log_export_callback, args=("Índice de Permanencia - Lista", "Excel")
            )

    # === METODOLOGÍA GLOBAL AL FINAL DE LA PÁGINA ===
    st.divider()
    lim_primer_sem = pd.to_datetime(config["limite_primer_semestre"]).strftime("%d/%m/%Y")
    lim_otros_sem = pd.to_datetime(config["limite_otros_semestres"]).strftime("%d/%m/%Y")
    st.markdown(f"""
### Criterios y Metodología de Análisis

A continuación se detallan las reglas lógicas y comerciales aplicadas para obtener los resultados del **Índice de Permanencia {p_base}**.

#### 1. ¿Qué es la Permanencia?
La permanencia mide cuántos alumnos que estudiaron en el periodo **{p_base}** continuaron en el siguiente periodo **{p_dest}**.

- **Quiénes se consideran (base)**:
  Todos los alumnos que pagaron correctamente su primera cuota en {p_base}.

- **Cuándo se considera que un alumno continuó (éxito)**:
  Cuando el alumno:
  - Pagó su primera cuota en {p_dest}, y
  - El alumno avanzó de semestre o permaneció en el mismo (recursante).

---

#### 2. Fechas importantes (bajas de matrícula)

Si el alumno tuvo un cambio de estado a **suspenso** o **trancado**:

- **Antes del inicio de clases**:
  No se tiene en cuenta en el análisis.
  - {lim_primer_sem}: alumnos de 1º semestre
  - {lim_otros_sem}: alumnos antiguos
- **Después del inicio de clases**:
  Sí se incluye en el análisis (como retenido o no retenido).

---

#### 3. Alumnos que no continuaron

Los alumnos que estaban en {p_base} pero no siguieron en {p_dest} se clasifican así:


- **Trancados**: si el alumno tiene el estado **trancado**, se contabiliza en esta categoría.  
- **Reprobados**: si el alumno **no está trancado** y tiene al menos una materia reprobada, se contabiliza aquí.  
- **Abandonos**: si el alumno **no está trancado** y **no tiene materias reprobadas**, se contabiliza en esta categoría.


---

#### 4. Filtros del sistema

El sistema permite activar o desactivar ciertos tipos de alumnos:

- **Convalidados**
- **Recursantes**: alumnos que ya cursaron en {p_ant} y están repitiendo (recursando) **el mismo semestre** en {p_base}.

Si estos filtros están apagados, esos alumnos no se incluyen en el análisis, para que el indicador sea más preciso.

---

#### 5. Exclusiones 

- Alumnos convalidados en su primer semestre están siendo desconsiderados del cálculo; solo se incluyen aquellos alumnos convalidados que ya han cursado al menos un semestre.
    """)
