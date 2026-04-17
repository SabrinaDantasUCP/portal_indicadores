import streamlit as st
from datetime import datetime, timedelta
import base64
import importlib
import os
import pandas as pd
import io
import extra_streamlit_components as etc
from utils import db_pia

# -------------------------------
# CONFIGURAÇÃO INICIAL
# -------------------------------
st.set_page_config(
    page_title="Indicadores Académicos",
    page_icon="assets/logo-ucp-icon.png",
    layout="wide"
)
# -------------------------------   
# 1. SISTEMA DE IMPORTAÇÃO SEGURA
# -------------------------------
class ModulePlaceholder:
    def __init__(self, name):
        self.name = name
    
    def render(self):
        st.info("Este módulo está en desarrollo.")

def safe_import_module(module_name):
    """Tenta importar um módulo. Se falhar, retorna um Placeholder."""
    try:
        return importlib.import_module(f"modules.{module_name}")
    except ImportError:
        return ModulePlaceholder(module_name)

# Carregamento dos Módulos (Existentes e Futuros)

# Panel Académico 
panel_acad_resumen     = safe_import_module("panel_acad_resumen") 
panel_acad_asistencia  = safe_import_module("panel_acad_asistencias")

# Rendimento
rend_acad_alumno      = safe_import_module("rend_acad_alumno")
rend_acad_asignatura  = safe_import_module("rend_acad_asignatura")
rend_acad_semestre    = safe_import_module("rend_acad_semestre")
rend_acad_carrera     = safe_import_module("rend_acad_carrera")

# Tasa de Aprobación
tasa_aprob_asignatura = safe_import_module("tasa_aprobacion_asignatura")
tasa_aprob_carrera    = safe_import_module("tasa_aprobacion_carrera")

# Eficiencia Académica (Futuros)
eficiencia_terminal    = safe_import_module("eficiencia_terminal")
eficiencia_egreso      = safe_import_module("eficiencia_egreso")
eficiencia_rezago      = safe_import_module("eficiencia_rezago")
eficiencia_titulacion  = safe_import_module("eficiencia_titulacion")
tasa_retencion         = safe_import_module("tasa_retencion")
tiempos_medios         = safe_import_module("tiempos_medios")
indice_permanencia     = safe_import_module("indice_permanencia")

# Tasa de Deserción (Futuros)
desercion_semestral    = safe_import_module("tasa_desercion_semestral")
desercion_generacional = safe_import_module("tasa_desercion_generacional")

# Tasa de Promoción (Futuros)
promocion_semestral    = safe_import_module("tasa_promocion_semestral")
promocion_anual        = safe_import_module("tasa_promocion_anual")

# Administración
admin_usuarios         = safe_import_module("admin_usuarios")
admin_areas            = safe_import_module("admin_areas")
admin_logs             = safe_import_module("admin_logs")
config_perfil          = safe_import_module("config_perfil")

# -------------------------------
# 2. FUNÇÕES DE PÁGINA (WRAPPERS)
# -------------------------------

def render_page(module):
    """Función genérica para renderizar un módulo o mostrar error."""
    if hasattr(module, 'render'):
        module.render()
    else:
        # Se for um Placeholder, ele tem .render(), então cai no if acima.
        # Se for um módulo real mas sem função render, cai aqui.
        st.warning(f"O módulo '{module.__name__}' foi carregado, mas não possui a função 'render()'.")

def page_home():
    user_name = "Usuario"
    if "user" in st.session_state and st.session_state.user:
        user_name = st.session_state.user.get('nombre', 'Usuario')
        
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: 50px; margin-bottom: 30px;">
            <h1 style="color: #003366; font-size: 42px; margin-bottom: 10px; font-weight: 700;">
                ¡Bienvenido, {user_name}, al Portal de Indicadores Académicos!
            </h1>
        </div>
        """,
        unsafe_allow_html=True
    )

# -------------------------------
# 3. DEFINIÇÃO DAS PÁGINAS (st.Page)
# -------------------------------

# Início
p_home = st.Page(page_home, title="Início", url_path="inicio", default=True)

# Dicionário Geral de Páginas para NAVEGAÇÃO
# Chave = "Categoria:Botão" -> Valor = st.Page(...)
ALL_PAGES = {}

# Função auxiliar para criar e registrar páginas
def create_page(module_obj, title, url_slug, category, custom_render=None):
    # Cria uma função lambda para renderizar este módulo específico
    def page_func():
        if custom_render:
            custom_render()
        else:
            render_page(module_obj)
    
    # Cria la página
    page = st.Page(page_func, title=title, url_path=url_slug)
    
    # Registra no dicionário global usando a chave composta
    key = f"{category}:{title}"
    ALL_PAGES[key] = page
    return page

# --- REGISTRO DAS PÁGINAS ---

# 1. Rendimento Académico
p_ra_est = create_page(rend_acad_alumno,     "Estudiante", "rend_aca_estudiante", "Rendimento Académico")
p_ra_asig= create_page(rend_acad_asignatura, "Asignatura", "rend_aca_asignatura", "Rendimento Académico")
p_ra_sem = create_page(rend_acad_semestre,   "Semestre",   "rend_aca_semestre",   "Rendimento Académico")
p_ra_car = create_page(rend_acad_carrera,    "Carrera",    "rend_aca_carrera",    "Rendimento Académico")

# Panel Académico (New Category)
p_panel_resumen = create_page(panel_acad_resumen, "Resumen", "panel_resumen", "Panel Académico")
p_panel_asist   = create_page(panel_acad_asistencia, "Asistencias", "panel_asistencias", "Panel Académico")

# 2. Tasa de Aprobación
p_ta_asig= create_page(tasa_aprob_asignatura,"Asignatura", "tasa_aprob_asignatura", "Tasa de Aprobación")
p_ta_car = create_page(tasa_aprob_carrera,   "Carrera",    "tasa_aprob_carrera",    "Tasa de Aprobación")

# 3. Eficiencia Académica
p_ea_term = create_page(eficiencia_terminal,   "Terminal",                "efic_terminal",   "Eficiencia Académica")
p_ea_egre = create_page(eficiencia_egreso,     "Egreso",                  "efic_egreso",     "Eficiencia Académica")
p_ea_reza = create_page(eficiencia_rezago,     "Rezago Educativo",        "efic_rezago",     "Eficiencia Académica")
p_ea_titu = create_page(eficiencia_titulacion, "Eficiencia de Titulación","efic_titulacion", "Eficiencia Académica")
p_ea_rete = create_page(tasa_retencion,        "Tasa de Retención",       "tasa_retencion",  "Eficiencia Académica") # Atenção ao nome da categoria se mudar
p_ea_tiem = create_page(tiempos_medios,        "Tiempos Medios de Egreso","tiempos_medios",  "Eficiencia Académica")
p_ip_actual = create_page(indice_permanencia, "Visión General", "ip_actual", "Índice de Permanencia", custom_render=indice_permanencia.render_actual)
p_ip_corte  = create_page(indice_permanencia, "Fecha de Corte",    "ip_corte",  "Índice de Permanencia", custom_render=indice_permanencia.render_corte)

# 4. Tasa de Deserción
p_td_sem = create_page(desercion_semestral,    "Semestral",    "tasa_desercion_sem", "Tasa de Deserción")
p_td_gen = create_page(desercion_generacional, "Generacional", "tasa_desercion_gen", "Tasa de Deserción")

# 5. Tasa de Promoción
p_tp_sem = create_page(promocion_semestral, "Semestral / Anual", "tasa_promocion_sem", "Tasa de Promoción")

# 6. Administración
p_admin_us = create_page(admin_usuarios, "Gestión de Usuarios", "admin_usuarios", "Administración")
p_admin_ar = create_page(admin_areas, "Gestión de Áreas", "admin_areas", "Administración")
p_admin_lo = create_page(admin_logs, "Registro de Descargas", "admin_logs", "Administración")
p_config_perf = create_page(config_perfil, "Cambiar Contraseña", "config_perfil", "Mi Cuenta")

# -------------------------------
# 4. NAVEGAÇÃO "OCULTA" (st.navigation)
# -------------------------------
# Lista plana de todas as páginas para o st.navigation
all_pages_list = [p_home] + list(ALL_PAGES.values())

pg = st.navigation(all_pages_list, position="hidden")

# -------------------------------
# 6. EXECUÇÃO DA PÁGINA E UI
# -------------------------------
def main():
    # Inicializar Base de Datos (Seguro llamarlo siempre)
    db_pia.init_db()
    
    # Cookie Manager para persistencia (F5)
    cookie_manager = etc.CookieManager()
    
    if "user" not in st.session_state:
        st.session_state.user = None

    # --- Lógica de Auto-Login por Cookies ---
    if st.session_state.user is None:
        try:
            # Obtener el ID del usuario de la cookie persistente
            saved_user_id = cookie_manager.get(cookie="pia_uid")
            if saved_user_id:
                # Validar y cargar datos del usuario
                user_data = db_pia.get_user_by_id(saved_user_id)
                if user_data:
                    st.session_state.user = user_data
                    st.session_state.rol = user_data['rol']
                    st.session_state.user_id = user_data['id']
                    st.session_state.permisos = db_pia.get_user_permissions(user_data['id'])
                    st.rerun() 
        except Exception:
             pass

    if st.session_state.user is None:
        # Página de Login
        st.markdown(
            """
            <div style="text-align: center; margin-top: 50px; margin-bottom: 30px;">
                <h1 style="color: #003366; font-size: 48px; margin-bottom: 10px;">
                    Portal de Indicadores Académicos
                </h1>
            </div>
            """, unsafe_allow_html=True
        )
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            with st.form("login_form"):
                email = st.text_input("Correo Electrónico")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("Entrar", use_container_width=True)
                if submitted:
                    user_data = db_pia.authenticate_user(email, password)
                    if user_data:
                        st.session_state.user = user_data
                        st.session_state.rol = user_data['rol']
                        st.session_state.user_id = user_data['id']
                        st.session_state.permisos = db_pia.get_user_permissions(user_data['id'])
                        
                        # Guardar cookie para persistencia (expira en 3 horas)
                        try:
                            cookie_manager.set("pia_uid", str(user_data['id']), key="set_cookie_login", expires_at=datetime.now() + timedelta(hours=3))
                        except:
                            pass
                            
                        st.switch_page(p_home)
                    else:
                        st.error("Credenciales incorrectas o cuenta inactiva.")
        return  # Bloquear la carga de la app real

    # -------------------------------
    # BARRA LATERAL (MENU) PARA USUARIO LOGUEADO
    # -------------------------------
    with st.sidebar:
        # --- LOGO ---
        @st.cache_data
        def get_logo_base64():
            try:
                logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo-ucp.png")
                with open(logo_path, "rb") as f:
                    return base64.b64encode(f.read()).decode()
            except Exception:
                return None

        data = get_logo_base64()
        if data:
            st.markdown(
                f"""<div style="display: flex; justify-content: center; margin-bottom: 40px;"><img src="data:image/png;base64,{data}" width="200"></div>""",
                unsafe_allow_html=True
            )

        # --- ESTRUTURA DO MENU ---
        MENU_ESTRUTURA = {
            "Mi Cuenta": ["Cambiar Contraseña"],
            "Panel Académico": ["Resumen", "Asistencias"],
            "Rendimento Académico": ["Estudiante", "Asignatura", "Semestre", "Carrera"],
            "Índice de Permanencia": ["Visión General", "Fecha de Corte"],
            "Tasa de Aprobación": ["Asignatura", "Carrera"],
            "Eficiencia Académica": ["Terminal", "Egreso", "Rezago Educativo", "Eficiencia de Titulación", "Tasa de Retención", "Tiempos Medios de Egreso"],
            "Tasa de Deserción": ["Semestral", "Generacional"],
            "Tasa de Promoción": ["Semestral / Anual"],
        }
        
        if st.session_state.rol == 'ADMIN':
            MENU_ESTRUTURA["Administración"] = ["Gestión de Usuarios", "Gestión de Áreas", "Registro de Descargas"]

        # Loop y Filtrado de Permisos por Categoría
        for category, buttons in MENU_ESTRUTURA.items():
            # Validación de Permisos para rol Lectura (Excluyendo 'Mi Cuenta' que es universal)
            if st.session_state.rol == 'LEITURA' and category != "Mi Cuenta" and category not in st.session_state.permisos:
                continue
                
            with st.expander(category, expanded=False):
                for btn_name in buttons:
                    lookup_key = f"{category}:{btn_name}"
                    if st.button(btn_name, key=f"btn_{lookup_key}", use_container_width=True):
                        if lookup_key in ALL_PAGES:
                            st.switch_page(ALL_PAGES[lookup_key])
                        else:
                            st.error(f"Página no encontrada: {lookup_key}")

    # Botón de Logout Global en esquina superior derecha
    c_out1, c_out2 = st.columns([9, 1])
    with c_out2:
        if st.button("Salir", icon=":material/logout:", use_container_width=True):
            try:
                cookie_manager.delete("pia_uid", key="delete_cookie_logout")
            except:
                pass
            st.session_state.clear()
            st.rerun()
            
    # Execução da Página (st.navigation)
    pg.run()

    # -------------------------------
    # RODAPÉ
    # -------------------------------
    st.markdown("---")

    # Obtener fecha de última actualización
    try:
        base_dir = os.path.dirname(__file__)
        
        # Mapeo inteligente de página actual -> archivo de datos fuente
        MAP_SOURCES = {
            "ip_actual": ["permanencia_20252.csv"],
            "ip_corte": ["permanencia_20252_05-04-2026.csv"],
            "matriculas": ["matriculados-20251.xlsx"],
            "notas": ["notas.xlsx"]
        }
        
        # pg es el objeto retornado por st.navigation
        current_slug = pg.url_path if hasattr(pg, "url_path") else ""
        targets = MAP_SOURCES.get(current_slug, ["alumnos.csv"])
        
        fechas_list = []
        for target_file in targets:
            data_path = os.path.join(base_dir, "assets", "data", target_file)
            if os.path.exists(data_path):
                mtime = os.path.getmtime(data_path)
                fechas_list.append(datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M"))
        
        # Eliminar duplicados manteniendo el orden
        unique_fechas = []
        for f in fechas_list:
            if f not in unique_fechas:
                unique_fechas.append(f)
                
        if unique_fechas:
            fecha_actualizacion = " | ".join(unique_fechas)
        else:
            fecha_actualizacion = datetime.now().strftime("%d/%m/%Y %H:%M")
    except Exception:
        fecha_actualizacion = datetime.now().strftime("%d/%m/%Y %H:%M")

    try:
        icon_path = os.path.join(base_dir, "assets", "logo-ucp-icon.png")
        if os.path.exists(icon_path):
            with open(icon_path, "rb") as f:
                data_icon = base64.b64encode(f.read()).decode()
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: flex-start; margin-bottom: 25px; gap: 10px;">
                    <img src="data:image/png;base64,{data_icon}" alt="Logo UCP" width="35">
                    <span style="font-size: 14px; color: #555555;">
                        Datos académicos internos de la institución | Última actualización: {fecha_actualizacion}
                    </span>
                </div>
                """, unsafe_allow_html=True
            )
        else:
            st.caption(f"Datos académicos internos de la institución | Última actualización: {fecha_actualizacion}")
    except Exception:
        st.caption(f"Datos académicos internos de la institución | Última actualización: {fecha_actualizacion}")

if __name__ == "__main__":
    main()
