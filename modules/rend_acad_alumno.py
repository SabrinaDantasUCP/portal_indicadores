import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime
from utils import db_pia
from utils.system_logging import log_exception
from services.data.alumnos import load_current_alumnos
from services.calculations.rendimiento_academico import (
    calculate_student_general_performance,
    prepare_rendimiento_source,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.graphics.shapes import Drawing, String, Line
from reportlab.graphics import renderPDF


# ------------------------------------------------------------
# Configurações iniciais
# ------------------------------------------------------------
# ------------------------------------------------------------
# Configurações iniciais
# ------------------------------------------------------------

# --- Nomes de colunas (Escopo Global para reuso em outros módulos)
COL_PERIODO = "ano_periodo_letivo"        
COL_SUBPERIODO = "periodo_anual_periodo_letivo" 
COL_SEMESTRE_ALUMNO = "semestre_alumno"
COL_ALUMNO = "nome_sobrenome"
COL_CATRACA = "numero_catraca" 
COL_ID_ALUMNO = "usuarios_id"
COL_COHORTE = "cohorte"
COL_TIPO_ALUMNO = "tipo_ingresso"
COL_STATUS_ALUMNO = "nombre_status_actual"
COL_CALIFICACION = "calificacion_final_1a5"
COL_DISCIPLINA = "disciplina"
COL_SECCION = "turma"
COL_FILIAL = "filial_periodo_letivo"
COL_TIPO_DISCIPLINA = "tipo_disciplina"
COL_RESULTADO = "resultado_final" 
COL_EGRESO = "periodo_egresso_format"
COL_ESTADO_TITULO = "estado_titulacion"
COL_FECHA_TITULO = "fecha_titulacion"
COL_DETALLE_TITULO = "detalle"

# ------------------------------------------------------------
# Função modular para renderizar os detalhes de um aluno
# ------------------------------------------------------------
def render_alumno_details(df_estudiante, df_completo):
    """
    Renderiza KPIs e Tabelas de rendimento de um aluno específico.
    df_estudiante: DF já filtrado para o aluno/filtros atuais.
    df_completo: DF original para cálculos globais (ex: Rendimento Geral).
    """
    alumno_nome = df_estudiante[COL_ALUMNO].iloc[0]
    catraca_num = df_estudiante[COL_CATRACA].iloc[0]
    cohorte = df_estudiante[COL_COHORTE].iloc[0]
    tipo_alumno = df_estudiante[COL_TIPO_ALUMNO].iloc[0]
    status_alumno = df_estudiante[COL_STATUS_ALUMNO].iloc[0]
    
    # --- Determinar status de egreso y titulación ---
    def get_col_val(df, col_name, default=None):
        if col_name in df.columns:
            val = df[col_name].iloc[0]
            return val if not pd.isna(val) else default
        return default

    periodo_egreso = get_col_val(df_estudiante, COL_EGRESO)
    estado_titulacion = str(get_col_val(df_estudiante, COL_ESTADO_TITULO, "")).strip().upper()
    fecha_titulacion = get_col_val(df_estudiante, COL_FECHA_TITULO, "")
    detalle_titulacion = get_col_val(df_estudiante, COL_DETALLE_TITULO, "")

    info_egreso_titulacion = []
    status_exibicao = status_alumno

    if estado_titulacion == "SI":
        status_exibicao = "Titulado"
        if periodo_egreso:
            info_egreso_titulacion.append(("Egresado en", periodo_egreso))
        if fecha_titulacion:
            info_egreso_titulacion.append(("Titulado en", fecha_titulacion))
    elif periodo_egreso:
        status_exibicao = "Egresado"
        info_egreso_titulacion.append(("Egresado en", periodo_egreso))
        if detalle_titulacion:
            info_egreso_titulacion.append(("Titulado en", detalle_titulacion))

    # Estilos según el status
    cores_status = {
            "Activo":     {"bg": "#E8F5E9", "color": "#2E7D32"}, 
            "Trancado":   {"bg": "#FFEBEE", "color": "#C62828"}, 
            "Suspenso":   {"bg": "#FFFDE7", "color": "#F9A825"}, 
            "Finalizado": {"bg": "#E3F2FD", "color": "#1565C0"}, 
            "Egresado":  {"bg": "#F3E5F5", "color": "#7B1FA2"}, 
            "Titulado":   {"bg": "#E0F7FA", "color": "#006064"}, 
        }

    padrao = {"bg": "#F5F5F5", "color": "#616161"}
    estilo = cores_status.get(status_exibicao, padrao)

    status_html = (
            f'<div style="flex:1; padding:8px 14px; '
            f'background-color:{estilo["bg"]}; '
            f'border-left:5px solid {estilo["color"]}; '
            f'border-radius:6px; '
            f'font-size:18px; font-weight:700; '
            f'color:{estilo["color"]}; text-align:center;">'
            f'{status_exibicao}' 
            f'</div>'
        )
        
    is_convalidado = tipo_alumno.strip().upper() != "NORMAL"
    tipo_html = (
            f'<div style="flex:1; padding:8px 14px; background-color:#E3F2FD; '
            f'border-left:5px solid #1565C0; border-radius:6px; '
            f'font-size:18px; font-weight:700; color:#0D47A1; text-align:center;">'
            f'{tipo_alumno}' 
            f'</div>'
        ) if is_convalidado else ""

    # Rendimento geral (Apenas Regulares)
    rendimiento_general, missing_cols = calculate_student_general_performance(df_completo, alumno_nome)
    if missing_cols or pd.isna(rendimiento_general):
        rendimiento_general = 0.0

    color = "#2E7D32" if rendimiento_general >= 2 else "#C62828"
    bg_color = "#E8F5E9" if rendimiento_general >= 2 else "#FFEBEE"

    info_egreso_html = "".join([f'<p style="font-size:22px; margin:0;"><span style="font-weight:600;">{label}:</span> {value}</p>' for label, value in info_egreso_titulacion])

    # --- Layout principal ---
    st.markdown(f"""
<div style="display:flex; gap:20px; align-items:stretch; margin:20px 0; flex-wrap:nowrap;">
<div style="flex:1; box-sizing:border-box; border:2px solid #ddd; border-radius:10px; padding:20px 25px; background:#f9f9f9; box-shadow:0 1px 3px rgba(0,0,0,.1); display:flex; flex-direction:column; justify-content:center; min-height:160px;">
<p style="font-size:22px; margin:0;"><span style="font-weight:600;">Estudiante:</span> {alumno_nome}</p>
<p style="font-size:22px; margin:0;"><span style="font-weight:600;">Catraca:</span> {catraca_num}</p>
<p style="font-size:22px; margin:0;"><span style="font-weight:600;">Cohorte:</span> {cohorte}</p>
{info_egreso_html}
<div style="display:flex; gap:10px; margin-top:10px; flex-wrap:wrap;">{status_html} {tipo_html}</div>
</div>
<div style="flex:0.4; box-sizing:border-box; border:2px solid {color}; border-radius:10px; padding:20px; background:{bg_color}; text-align:center; display:flex; flex-direction:column; justify-content:center; align-items:center; box-shadow:0 1px 4px rgba(0,0,0,.1); transition:all .3s ease-in-out; min-height:160px;">
<p style="font-size:20px; margin:0; font-weight:600; color:{color};">Rendimiento General</p>
<p style="font-size:38px; margin:0; font-weight:700; color:{color};">{rendimiento_general:.2f}</p>
</div>
</div>
""", unsafe_allow_html=True)

    # Agrupar por semestre e renderizar tabelas
    grupos = df_estudiante.groupby([COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE_ALUMNO])
    st.divider()
    
    for (periodo, subperiodo, semestre), df_grupo in grupos:
        mask_regular = df_grupo[COL_TIPO_DISCIPLINA].astype(str).str.strip() == "Regular"
        df_regulares = df_grupo[mask_regular]
        df_extracurriculares = df_grupo[~mask_regular]

        if not df_regulares.empty:
            rendimiento_asignatura = df_regulares.groupby([COL_DISCIPLINA, COL_SECCION])[COL_CALIFICACION].mean().reset_index(name="rendimiento_asignatura")
            rendimiento_semestral = rendimiento_asignatura["rendimiento_asignatura"].mean()
        else:
            rendimiento_semestral = 0.0

        if rendimiento_semestral >= 2:
            bg_color_sem, border_color, text_color = "#E8F5E9", "#1B5E20", "#2E7D32"
        else:
            bg_color_sem, border_color, text_color = "#FFEBEE", "#8E0000", "#C62828"

        filial = df_grupo[COL_FILIAL].iloc[0] if not df_grupo[COL_FILIAL].empty else "N/A"

        st.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center; gap:20px; flex-wrap:wrap; margin-top:25px; margin-bottom:20px;">
        <div style="flex:1; border:1px solid #ddd; border-radius:10px; background-color:#f9f9f9; padding:14px 20px; box-shadow:0 1px 3px rgba(0,0,0,0.1); display:flex; align-items:center; font-size:20px; font-weight:600;">
            <span>Año: {periodo}</span> <span style="margin:0 12px;">|</span>
            <span>Período: {subperiodo}</span> <span style="margin:0 12px;">|</span>
            <span> {semestre}º Semestre</span> <span style="margin:0 12px;">|</span>
            <span>Sede: {filial}</span>
        </div>
        <div style="flex:0.4; display:flex; align-items:center; background-color:{bg_color_sem}; border-left:6px solid {border_color}; padding:10px 16px; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1); gap:10px; justify-content:center;">
            <span style="font-size:18px; font-weight:600; color:{text_color};">Rendimiento Semestral:</span>
            <span style="font-size:24px; font-weight:700; color:{border_color};">{rendimiento_semestral:.2f}</span>
        </div>
        </div>
        """, unsafe_allow_html=True)

        if not df_regulares.empty:
            df_reg_exibir = df_regulares.groupby([COL_DISCIPLINA, COL_SECCION])[COL_CALIFICACION].mean().reset_index(name="rendimiento_asignatura")
            df_reg_exibir["rendimiento_asignatura"] = df_reg_exibir["rendimiento_asignatura"].fillna(0).round().astype(int)
            df_reg_exibir = df_reg_exibir.rename(columns={COL_DISCIPLINA: "Asignatura", COL_SECCION: "Sección", "rendimiento_asignatura": "Calificación Final"}).sort_values(by=["Sección", "Asignatura", "Calificación Final"])
            st.dataframe(df_reg_exibir.style.set_properties(**{'text-align': 'center'}), width="stretch", hide_index=True)

        if not df_extracurriculares.empty:
            st.markdown("<h5 style='margin-top: 15px; color: #555;'>Disciplinas Extracurriculares</h5>", unsafe_allow_html=True)
            df_ext_exibir = df_extracurriculares.groupby([COL_DISCIPLINA, COL_SECCION])[COL_RESULTADO].first().reset_index()
            df_ext_exibir = df_ext_exibir.rename(columns={COL_DISCIPLINA: "Asignatura", COL_SECCION: "Sección", COL_RESULTADO: "Calificación Final"}).sort_values(by=["Sección", "Asignatura"])
            st.dataframe(df_ext_exibir.style.set_properties(**{'text-align': 'center'}), width="stretch", hide_index=True)

    return rendimiento_general, grupos, alumno_nome, catraca_num, is_convalidado, status_exibicao, info_egreso_titulacion, cohorte

def render():
    st.subheader("Rendimiento Académico por Estudiante")

    st.markdown("""
        <style>
        [data-testid="stElementToolbar"] { display: none; }
        </style>
    """, unsafe_allow_html=True)
    
    df = load_current_alumnos(only_cde=False)
    if df.empty:
        st.error("Archivo de datos no encontrado.")
        return

    df, missing_cols = prepare_rendimiento_source(df)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return

    # Função de Callback para Limpar (Garante que limpe visualmente)
    def limpar_filtros():
        st.session_state["catraca_value"] = ""
        st.session_state["alumno_value"] = ""
        # Força visualmente os widgets a ficarem vazios
        if "widget_catraca" in st.session_state: st.session_state["widget_catraca"] = ""
        if "widget_alumno" in st.session_state: st.session_state["widget_alumno"] = ""

    # Inicializa variáveis
    if "catraca_value" not in st.session_state: st.session_state["catraca_value"] = ""
    if "alumno_value" not in st.session_state: st.session_state["alumno_value"] = ""

    catraca_value = st.session_state["catraca_value"]
    alumno_value = st.session_state["alumno_value"]

    # Prepara Listas (Cruzamento de dados)
    catraca_vals_all = sorted(df[COL_CATRACA].dropna().unique().tolist())
    alumno_vals_all  = sorted(df[COL_ALUMNO].dropna().unique().tolist())
    
    catraca_opts = [""] + [str(c) for c in catraca_vals_all]
    alumno_opts = [""] + alumno_vals_all
    
    # Lógica Cruzada: Se selecionou um, filtra o outro
    if catraca_value and not alumno_value:
        df_temp = df[df[COL_CATRACA] == int(catraca_value)]
        alumnos_rel = sorted(df_temp[COL_ALUMNO].dropna().unique().tolist())
        alumno_opts = [""] + alumnos_rel
    elif alumno_value and not catraca_value:
        df_temp = df[df[COL_ALUMNO] == alumno_value]
        catracas_rel = sorted(df_temp[COL_CATRACA].dropna().unique().tolist())
        catraca_opts = [""] + [str(c) for c in catracas_rel]

    # Desenha colunas
    col1, col2, col3 = st.columns([1, 1, 0.5])

    # Flag para saber se precisamos rodar o rerun
    need_rerun = False

    with col1:
        val_c = str(catraca_value) if catraca_value else ""
        if "" not in catraca_opts: catraca_opts.insert(0, "")
        idx_c = catraca_opts.index(val_c) if val_c in catraca_opts else 0
        
        new_catraca = st.selectbox("Catraca", catraca_opts, index=idx_c, key="widget_catraca")

    with col2:
        val_a = alumno_value if alumno_value else ""
        if "" not in alumno_opts: alumno_opts.insert(0, "")
        idx_a = alumno_opts.index(val_a) if val_a in alumno_opts else 0
        
        new_alumno = st.selectbox("Alumno", alumno_opts, index=idx_a, key="widget_alumno")

    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        # Callback no botão limpar
        st.button("Limpiar", icon=":material/refresh:", on_click=limpar_filtros)

    # Atualiza sessão se houve mudança nos widgets
    if new_catraca != str(catraca_value):
        st.session_state["catraca_value"] = new_catraca
        need_rerun = True
        
    if new_alumno != alumno_value:
        st.session_state["alumno_value"] = new_alumno
        need_rerun = True

    if need_rerun:
        st.rerun()

    # ------------------------------------------------------------
    # BLOQUEIO OBRIGATÓRIO (Do jeito que você pediu)
    # ------------------------------------------------------------
    # Agora pegamos os valores atualizados
    catraca_value = st.session_state["catraca_value"]
    alumno_value = st.session_state["alumno_value"]

    if not alumno_value or not catraca_value:
        st.divider()
        # Mensagens de orientação
        if catraca_value and not alumno_value:
            st.warning("Falta seleccionar el **Alumno** para continuar.")
        elif alumno_value and not catraca_value:
            st.warning("Falta seleccionar la **Catraca** para continuar.")
        else:
            st.info("Seleccione **Catraca** y **Alumno** para visualizar los datos.")
            
        st.stop() 
        
    # --- Base filtrada ---
    df_base = df.copy()
    if alumno_value:
        df_base = df_base[df_base[COL_ALUMNO] == alumno_value]
    if catraca_value:
        df_base = df_base[df_base[COL_CATRACA] == int(catraca_value)]
    # -------------------------------------------
    # 2) Cascata real: Año ⇄ Período ⇄ Semestre
    # -------------------------------------------

    # utilitários de estado
    def _ensure_state(key, default):
        if key not in st.session_state:
            st.session_state[key] = default

    def _sanitize_selection(key, valid_opts):
        sel = st.session_state.get(key, [])
        if isinstance(sel, str):  # selectbox antigo etc.
            sel = [sel] if sel else []
        new_sel = [v for v in sel if v in valid_opts]
        if new_sel != sel:
            st.session_state[key] = new_sel

    _ensure_state("f_ano", [])
    _ensure_state("f_periodo", [])
    _ensure_state("f_semestre", [])

    # opções iniciais (sem restrições mútuas)
    anos_all      = sorted(df_base[COL_PERIODO].dropna().unique().tolist())
    periodos_all  = sorted(df_base[COL_SUBPERIODO].dropna().unique().tolist())
    semestres_all = sorted(df_base[COL_SEMESTRE_ALUMNO].dropna().unique().tolist())

    # 2.1 calcule opções condicionais de cada filtro com base nos OUTROS dois
    def options_condicionais(df_scope, anos_sel, periodos_sel, semestres_sel):
        # para Año: restringe pelos outros dois
        df_ano = df_scope.copy()
        if periodos_sel:
            df_ano = df_ano[df_ano[COL_SUBPERIODO].isin(periodos_sel)]
        if semestres_sel:
            df_ano = df_ano[df_ano[COL_SEMESTRE_ALUMNO].isin(semestres_sel)]
        anos_opts = sorted(df_ano[COL_PERIODO].dropna().unique().tolist())

        # para Período: restringe por Año e Semestre
        df_per = df_scope.copy()
        if anos_sel:
            df_per = df_per[df_per[COL_PERIODO].isin(anos_sel)]
        if semestres_sel:
            df_per = df_per[df_per[COL_SEMESTRE_ALUMNO].isin(semestres_sel)]
        periodos_opts = sorted(df_per[COL_SUBPERIODO].dropna().unique().tolist())

        # para Semestre: restringe por Año e Período
        df_sem = df_scope.copy()
        if anos_sel:
            df_sem = df_sem[df_sem[COL_PERIODO].isin(anos_sel)]
        if periodos_sel:
            df_sem = df_sem[df_sem[COL_SUBPERIODO].isin(periodos_sel)]
        semestres_opts = sorted(df_sem[COL_SEMESTRE_ALUMNO].dropna().unique().tolist())

        return anos_opts, periodos_opts, semestres_opts

    # 2.2 primeiro passe com o que estiver (ou vazio)
    anos_sel      = st.session_state["f_ano"]
    periodos_sel  = st.session_state["f_periodo"]
    semestres_sel = st.session_state["f_semestre"]

    anos_opts, periodos_opts, semestres_opts = options_condicionais(
        df_base, anos_sel, periodos_sel, semestres_sel
    )

    # saneia seleções que ficaram inválidas
    _sanitize_selection("f_ano", anos_opts)
    _sanitize_selection("f_periodo", periodos_opts)
    _sanitize_selection("f_semestre", semestres_opts)

    anos_sel      = st.session_state["f_ano"]
    periodos_sel  = st.session_state["f_periodo"]
    semestres_sel = st.session_state["f_semestre"]

    # 2.3 desenha os widgets com as opções já filtradas
    c3, c4, c5 = st.columns(3)

    # Nota: O Streamlit usa o 'key' para vincular ao st.session_state automaticamente
    anos_sel_ui = c3.multiselect("Año", anos_opts, key="f_ano")
    periodos_sel_ui = c4.multiselect("Período", periodos_opts, key="f_periodo")
    
    # FORMAT_FUNC aplicado aqui para exibição visual apenas
    semestres_sel_ui = c5.multiselect(
        "Semestre", 
        semestres_opts, 
        key="f_semestre",
        format_func=lambda x: f"{x}º Semestre"
    )

    # 2.4 aplica filtros finais conforme seleções (interseção)
    df_estudiante = df_base.copy()
    if st.session_state["f_ano"]:
        df_estudiante = df_estudiante[df_estudiante[COL_PERIODO].isin(st.session_state["f_ano"])]
    if st.session_state["f_periodo"]:
        df_estudiante = df_estudiante[df_estudiante[COL_SUBPERIODO].isin(st.session_state["f_periodo"])]
    if st.session_state["f_semestre"]:
        df_estudiante = df_estudiante[df_estudiante[COL_SEMESTRE_ALUMNO].isin(st.session_state["f_semestre"])]

    # valida
    if df_estudiante.empty:
        st.warning("No se encontraron datos para los filtros seleccionados.")
        st.stop()

    # ------------------------------------------------------------
    # 👩‍🎓 Exibir informações do aluno
    # ------------------------------------------------------------
    st.divider()
    # --- Renderização modular dos detalhes ---
    # Chamamos a função extraída para exibir os dados
    res_vals = render_alumno_details(df_estudiante, df)
    rendimiento_general, grupos, alumno_nome, catraca_num, is_convalidado, status_exibicao, info_egreso_titulacion, cohorte = res_vals

    # ------------------------------------------------------------
    # 🔹 Explicacao no final da pagina
    # ------------------------------------------------------------




    # ------------------------------------------------------------
    # 📄 Função auxiliar: Cabeçalho e rodapé
    # ------------------------------------------------------------
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

        # --- Logo ---
        if logo_path:
            try:
                logo_width = 2 * cm
                logo_height = 2 * cm
                canvas.drawImage(
                    logo_path,
                    x=2 * cm,
                    y=height - 2.5 * cm,
                    width=logo_width,
                    height=logo_height,
                    preserveAspectRatio=True,
                    mask='auto'
                )
            except Exception as exc:
                log_exception("Error silencioso tratado en rend_acad_alumno.py", exc)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#004080"))
        canvas.drawString(5 * cm, height - 1.5 * cm, "Universidad Central del Paraguay")

        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.black)
        canvas.drawString(5 * cm, height - 2.1 * cm, "Facultad de Ciencias de la Salud — Carrera de Medicina")

        # --- Linha abaixo do cabeçalho ---
        canvas.setStrokeColor(colors.HexColor("#004080"))
        canvas.setLineWidth(1)
        canvas.line(2 * cm, height - 3.0 * cm, width - 2 * cm, height - 3.0 * cm)

        # --- Rodapé ---
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(width - 2 * cm, 1.2 * cm, f"Página {doc.page}")

        canvas.restoreState()
    # ------------------------------------------------------------
    # 📘 Função principal: Gerar PDF
    # ------------------------------------------------------------
    def gerar_pdf_estudiante(df_estudiante, rendimiento_general, grupos, alumno_nome, catraca_num, convalidado, status_exibicao, info_egreso, cohorte):
        buffer = io.BytesIO()
        # Aumentar margen superior para no chocar con el encabezado fijo
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=4.5 * cm, 
            bottomMargin=2 * cm
        )
 
        story = []
        styles = getSampleStyleSheet()
 
        # Título principal
        title_style = styles["Title"]
        title_style.alignment = 1 # Center
        story.append(Paragraph("<b>REPORTE DE RENDIMIENTO ACADÉMICO</b>", title_style))
        story.append(Spacer(1, 15))
 
        # --- Tabla de Información del Estudiante ---
        # Preparar los datos en pares (Rótulo: Valor)
        info_data = [
            [Paragraph(f"<b>Estudiante:</b> {alumno_nome}", styles["Normal"]), 
             Paragraph(f"<b>Catraca:</b> {catraca_num}", styles["Normal"])],
            
            [Paragraph(f"<b>Estado:</b> {status_exibicao}", styles["Normal"]), 
             Paragraph(f"<b>Cohorte:</b> {cohorte}", styles["Normal"])],
             
            [Paragraph(f"<b>Rendimiento General:</b> {rendimiento_general:.2f}", styles["Normal"]), ""]
        ]

        # Agregar información de egreso/titulación si existe
        for label, value in info_egreso:
            info_data.append([Paragraph(f"<b>{label}:</b> {value}", styles["Normal"]), ""])

        # Agregar Tipo de Ingreso si es convalidado
        if convalidado:
            info_data.append([Paragraph("<b>Tipo de Ingreso:</b> Convalidado", styles["Normal"]), ""])

        # Crear y estilizar la tabla de info
        info_table = Table(info_data, colWidths=[12 * cm, 12 * cm])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 15))

        for (periodo, subperiodo, semestre), df_grupo in grupos:
            # Agrupar datos para el PDF, separando por tipo para aplicar la lógica de calificación
            rendimiento_asignatura_df = (
                df_grupo.groupby([COL_DISCIPLINA, COL_SECCION, COL_TIPO_DISCIPLINA])
                .agg({COL_CALIFICACION: 'mean', COL_RESULTADO: 'first'})
                .reset_index()
            )
            
            # Calcular rendimiento semestral considerando solo materias regulares
            rend_regulares = rendimiento_asignatura_df[
                rendimiento_asignatura_df[COL_TIPO_DISCIPLINA].astype(str).str.strip().str.upper() == "REGULAR"
            ][COL_CALIFICACION]
            
            rendimiento_semestral = rend_regulares.mean() if not rend_regulares.empty else 0.0

            def format_calif_pdf(row):
                tipo = str(row[COL_TIPO_DISCIPLINA]).strip().upper()
                if tipo == "REGULAR":
                    val = row[COL_CALIFICACION]
                    return str(int(round(val))) if pd.notna(val) else "0"
                else:
                    return str(row[COL_RESULTADO]).strip().upper()

            rendimiento_asignatura_df["Calificación Final"] = rendimiento_asignatura_df.apply(format_calif_pdf, axis=1)
            rendimiento_asignatura_df = rendimiento_asignatura_df.rename(columns={COL_DISCIPLINA: "Asignatura", COL_SECCION: "Sección"})
            
            # --- Separar en tablas Regulares y Extracurriculares para el PDF ---
            df_reg_pdf = rendimiento_asignatura_df[rendimiento_asignatura_df[COL_TIPO_DISCIPLINA].astype(str).str.strip().str.upper() == "REGULAR"]
            df_ext_pdf = rendimiento_asignatura_df[rendimiento_asignatura_df[COL_TIPO_DISCIPLINA].astype(str).str.strip().str.upper() != "REGULAR"]

            story.append(Paragraph(
                f"<b>Año:</b> {periodo} | <b>Período:</b> {subperiodo} | {semestre}º Semestre — "
                f"<b>Rendimiento Semestral:</b> {rendimiento_semestral:.2f}",
                styles["Heading4"]
            ))
            story.append(Spacer(1, 6))

            # --- Tabla de Materias Regulares ---
            if not df_reg_pdf.empty:
                data_reg = [["Asignatura", "Sección", "Calificación Final"]] + df_reg_pdf[["Asignatura", "Sección", "Calificación Final"]].values.tolist()
                tabla_reg = Table(data_reg, repeatRows=1, colWidths=[14 * cm, 7 * cm, 4 * cm])
                tabla_reg.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004080')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
                ]))
                story.append(tabla_reg)
                story.append(Spacer(1, 10))

            # --- Tabla de Materias Extracurriculares ---
            if not df_ext_pdf.empty:
                story.append(Paragraph("<b>Disciplinas Extracurriculares</b>", styles["Heading5"]))
                story.append(Spacer(1, 4))
                data_ext = [["Asignatura", "Sección", "Calificación Final"]] + df_ext_pdf[["Asignatura", "Sección", "Calificación Final"]].values.tolist()
                tabla_ext = Table(data_ext, repeatRows=1, colWidths=[14 * cm, 7 * cm, 4 * cm])
                tabla_ext.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#555555')), # Gris para diferenciar
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
                ]))
                story.append(tabla_ext)
                story.append(Spacer(1, 14))

        # --- Rodapé e Explicações ---
        story.append(Spacer(1, 20))
        small_style = styles["Normal"].clone('small')
        small_style.fontSize = 9
        small_style.leading = 12 
        small_style.textColor = colors.grey

        story.append(Paragraph("<b>Tasa de Rendimiento Académico (TRA)</b>", small_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Está definido por el promedio de la calificación obtenido por el estudiante "
            "en las materias en las cuales ha presentado exámenes, independientemente del tipo de examen "
            "(<i>Chaín, 1995</i>).", small_style))

        story.append(Paragraph(
            "Se calcula por estudiante, por asignatura, por semestre y general, por generación o cohorte.",
            small_style))
        story.append(Spacer(1, 8))

        story.append(Paragraph("<b>Tasa de Rendimiento Académico Semestral por Estudiante (TRASE)</b>", small_style))
        story.append(Spacer(1, 8))

        formula = Paragraph(
            "<para align='center'>"
            "<b>TRASE<sub>(1)</sub> = "
            "<font face='Courier-Bold'>[CEA<sub>(1)</sub> + CEA<sub>(2)</sub> + CEA<sub>(3)</sub> + ... + CEA<sub>(n)</sub>] / N</font></b>"
            "</para>",
            small_style
        )

        story.append(formula)
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Donde:</b>", small_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "<b>TRASE(1):</b> Tasa de Rendimiento Académico Semestral por Estudiante "
            "(debe ser calculada para cada estudiante).", small_style))
        story.append(Spacer(1, 2))

        story.append(Paragraph("<b>CEA(1):</b> Calificación del Estudiante 1 en la Asignatura 1 al final del semestre.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>CEA(2):</b> Calificación del Estudiante 1 en la Asignatura 2 al final del semestre.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>CEA(3):</b> Calificación del Estudiante 1 en la Asignatura 3 al final del semestre.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>CEA(n):</b> Calificación del Estudiante 1 en la Asignatura “n” al final del semestre.", small_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("<b>N:</b> Número de datos (cantidad de asignaturas examinadas).", small_style))
        story.append(Spacer(1, 10))
        
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)

        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes

    # ------------------------------------------------------------
    # 📥 GERAÇÃO DOS ARQUIVOS (Processamento Imediato)
    # ------------------------------------------------------------
    
    dados_pdf = gerar_pdf_estudiante(df_estudiante, rendimiento_general, grupos, alumno_nome, catraca_num, is_convalidado, status_exibicao, info_egreso_titulacion, cohorte)

    # 2. Preparar Excel con lógica diferenciada por tipo de asignatura
    df_excel = df_estudiante.copy()
    
    def format_excel_calif(row):
        tipo = str(row[COL_TIPO_DISCIPLINA]).strip().upper()
        if tipo == "REGULAR":
            val = row[COL_CALIFICACION]
            return int(round(val)) if pd.notna(val) else 0
        else:
            return str(row[COL_RESULTADO]).strip().upper()

    df_excel["Calificación Final"] = df_excel.apply(format_excel_calif, axis=1)

    colunas_desejadas = {
        COL_ALUMNO: "Estudiante",
        COL_CATRACA: "Catraca",
        COL_COHORTE: "Cohorte",
        COL_PERIODO: "Año",
        COL_SUBPERIODO: "Periodo",
        COL_SEMESTRE_ALUMNO: "Semestre",
        COL_DISCIPLINA: "Asignatura",
        COL_SECCION: "Sección",
        "Calificación Final": "Calificación Final"
    }
    df_export = df_excel[list(colunas_desejadas.keys())].rename(columns=colunas_desejadas)

    buffer_excel = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer_excel, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Rendimiento')
            worksheet = writer.sheets['Rendimiento']
            for i, col in enumerate(df_export.columns):
                max_len = max(df_export[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, max_len)
    except Exception as exc:
        log_exception("No se pudo generar Excel con xlsxwriter en rendimiento por alumno", exc)
        with pd.ExcelWriter(buffer_excel) as writer:
            df_export.to_excel(writer, index=False, sheet_name='Rendimiento')
            
    dados_excel = buffer_excel.getvalue()

    # ------------------------------------------------------------
    # 🔘 Botões de Download
    # ------------------------------------------------------------
    st.divider()

    col_pdf, col_excel = st.columns(2, gap="medium")

    with col_pdf:
        st.download_button(
            label="Descargar Reporte (PDF)",
            data=dados_pdf,
            file_name=f"Reporte_{catraca_num}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            icon=":material/download:",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Rendimiento Estudiante", "PDF")
        )

    with col_excel:
        st.download_button(
            label="Descargar Datos (Excel)",
            data=dados_excel,
            file_name=f"Dados_{catraca_num}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Rendimiento Estudiante", "Excel")  
        )

    # ------------------------------------------------------------
    # 🔹 Explicacao no final da pagina
    # ------------------------------------------------------------

    st.divider()
    
    st.markdown("""        
    La *Tasa de Rendimiento Académico (TRA)* está definida por el promedio de la calificación obtenido por el estudiante en las materias en las cuales ha presentado exámenes, independientemente del tipo de examen (*Chaín, 1995*).
    En este caso **se calcula el rendimiento académico por estudiantes en forma individual, por asignatura, por semestre y general, por generación o cohorte.**
    De acuerdo con el razonamiento anterior, los cálculos quedan como sigue:
                
    """)
    st.markdown("""          
    #### Tasa de Rendimiento Académico Semestral por Estudiante, promedio (TRASE)               
    """)

    st.latex(r"""
    \text{TRASE(1)} = \frac{\text{CEA}_{(1)} + \text{CEA}_{(2)} + \text{CEA}_{(3)} + \dots + \text{CEA}_{(n)}}{N}
    """)

    st.markdown("""
    **Donde:**

    - **TRASE(1):** Tasa de Rendimiento Académico Semestral por Estudiante (debe ser calculada para cada estudiante).  
    - **CEA(1):** Calificación del Estudiante 1 en la Asignatura 1 al final del semestre.  
    - **CEA(2):** Calificación del Estudiante 1 en la Asignatura 2 al final del semestre.  
    - **CEA(3):** Calificación del Estudiante 1 en la Asignatura 3 al final del semestre.  
    - **CEA(n):** Calificación del Estudiante 1 en la Asignatura “n” al final del semestre.  
    - **N:** Número de datos (cantidad de asignaturas examinadas).  
    """)
