import streamlit as st
from datetime import datetime, timedelta
import base64
import importlib
import os
import pandas as pd
import io
import extra_streamlit_components as etc
from utils import db_pia
from utils.data_loader import data_file_mtime, set_current_version
from utils.menu_config import (
    ACCOUNT_PAGES,
    ADMINISTRACION,
    ADMIN_PAGES,
    INDICADORES_VERSION,
    INDICE_PERMANENCIA,
    INDICE_PERMANENCIA_PERMISSION,
    MI_CUENTA,
    PERMANENCIA_PAGES,
    VERSION_GROUPS,
    all_module_names,
    iter_page_configs,
    page_key,
    permission_key,
    version_permission_key,
)
from utils.system_logging import log_exception

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
    except ImportError as exc:
        log_exception(f"No se pudo importar el módulo {module_name}", exc)
        return ModulePlaceholder(module_name)

# Carregamento dos Módulos declarados no catálogo de navegação
MODULES = {module_name: safe_import_module(module_name) for module_name in all_module_names()}

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
    key = page_key(category, title)
    ALL_PAGES[key] = page
    return page

def register_page_from_config(category, page_config):
    module_obj = MODULES[page_config["module"]]
    custom_render_name = page_config.get("custom_render")
    custom_render = getattr(module_obj, custom_render_name) if custom_render_name else None
    return create_page(module_obj, page_config["title"], page_config["slug"], category, custom_render=custom_render)


# --- REGISTRO DAS PÁGINAS ---
for category, page_config in iter_page_configs():
    register_page_from_config(category, page_config)

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
        except Exception as exc:
            log_exception("Error durante auto-login por cookie", exc)

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
                        db_pia.log_audit_event(
                            "login_success",
                            target_usuario_id=user_data["id"],
                            actor_usuario_id=user_data["id"],
                            detalle={"email": email},
                        )
                        st.session_state.user = user_data
                        st.session_state.rol = user_data['rol']
                        st.session_state.user_id = user_data['id']
                        st.session_state.permisos = db_pia.get_user_permissions(user_data['id'])
                        
                        # Guardar cookie para persistencia (expira en 3 horas)
                        try:
                            cookie_manager.set("pia_uid", str(user_data['id']), key="set_cookie_login", expires_at=datetime.now() + timedelta(hours=3))
                        except Exception as exc:
                            log_exception("No se pudo guardar la cookie de login", exc)
                            
                        st.switch_page(p_home)
                    else:
                        db_pia.log_audit_event(
                            "login_failed",
                            detalle={"email": email},
                            actor_usuario_id=None,
                        )
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
            except Exception as exc:
                log_exception("No se pudo cargar el logo del sidebar", exc)
                return None

        data = get_logo_base64()
        if data:
            st.markdown(
                f"""<div style="display: flex; justify-content: center; margin-bottom: 40px;"><img src="data:image/png;base64,{data}" width="200"></div>""",
                unsafe_allow_html=True
            )

        user_perms = set(st.session_state.permisos or [])

        def has_indicator_permission(version, indicator):
            if st.session_state.rol != 'LEITURA':
                return True
            return (
                version_permission_key(version) in user_perms
                or permission_key(version, indicator) in user_perms
            )

        def has_category_permission(category):
            if st.session_state.rol != 'LEITURA' or category == MI_CUENTA:
                return True
            if category == INDICE_PERMANENCIA:
                return INDICE_PERMANENCIA_PERMISSION in user_perms
            return False

        with st.expander(MI_CUENTA, expanded=False):
            for page_config in ACCOUNT_PAGES:
                lookup_key = page_key(MI_CUENTA, page_config["title"])
                if st.button(page_config["title"], key=f"btn_{lookup_key}", use_container_width=True):
                    st.switch_page(ALL_PAGES[lookup_key])

        for version in VERSION_GROUPS:
            visible_indicators = [
                indicator for indicator in INDICADORES_VERSION
                if has_indicator_permission(version, indicator)
            ]
            if not visible_indicators:
                continue

            with st.expander(version, expanded=False):
                for indicator in visible_indicators:
                    st.markdown(f"**{indicator['name']}**")
                    for page_config in indicator["pages"]:
                        lookup_key = page_key(indicator["target_category"], page_config["title"])
                        button_key = f"btn_{version}_{indicator['name']}_{page_config['title']}"
                        if st.button(page_config["title"], key=button_key, use_container_width=True):
                            if lookup_key in ALL_PAGES:
                                set_current_version(version_permission_key(version))
                                st.switch_page(ALL_PAGES[lookup_key])
                            else:
                                st.error(f"Página no encontrada: {lookup_key}")

        if has_category_permission(INDICE_PERMANENCIA):
            with st.expander(INDICE_PERMANENCIA, expanded=False):
                for page_config in PERMANENCIA_PAGES:
                    lookup_key = page_key(INDICE_PERMANENCIA, page_config["title"])
                    if st.button(page_config["title"], key=f"btn_{lookup_key}", use_container_width=True):
                        st.switch_page(ALL_PAGES[lookup_key])

        if st.session_state.rol == 'ADMIN':
            with st.expander(ADMINISTRACION, expanded=False):
                for page_config in ADMIN_PAGES:
                    lookup_key = page_key(ADMINISTRACION, page_config["title"])
                    if st.button(page_config["title"], key=f"btn_{lookup_key}", use_container_width=True):
                        st.switch_page(ALL_PAGES[lookup_key])

    # Botón de Logout Global en esquina superior derecha
    c_out1, c_out2 = st.columns([9, 1])
    with c_out2:
        if st.button("Salir", icon=":material/logout:", use_container_width=True):
            logout_user_id = st.session_state.get("user_id")
            if logout_user_id:
                db_pia.log_audit_event(
                    "logout",
                    target_usuario_id=logout_user_id,
                    actor_usuario_id=logout_user_id,
                )
            try:
                cookie_manager.delete("pia_uid", key="delete_cookie_logout")
            except Exception as exc:
                log_exception("No se pudo eliminar la cookie de logout", exc)
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
            "ip_actual": [("global", "permanencia_vision_general")],
            "ip_corte": [("global", "permanencia_fecha_corte")],
            "matriculas": [(None, "matriculas")],
            "notas": [(None, "notas")]
        }
        
        # pg es el objeto retornado por st.navigation
        current_slug = pg.url_path if hasattr(pg, "url_path") else ""
        targets = MAP_SOURCES.get(current_slug, [(None, "alumnos")])
        
        fechas_list = []
        for scope, dataset_name in targets:
            mtime = data_file_mtime(dataset_name, scope)
            if mtime:
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
    except Exception as exc:
        log_exception("No se pudo calcular la última actualización de datos", exc)
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
    except Exception as exc:
        log_exception("No se pudo renderizar el icono del pie de página", exc)
        st.caption(f"Datos académicos internos de la institución | Última actualización: {fecha_actualizacion}")

if __name__ == "__main__":
    main()
