import streamlit as st
from datetime import datetime, timedelta
from html import escape
import base64
import importlib
import os
import pandas as pd
import io
import extra_streamlit_components as etc
from services.data.encuestas import get_encuesta_scope, get_encuestas_dataset
from services.data.permanencia import (
    VISTA_FECHA_CORTE,
    VISTA_VISION_GENERAL,
    get_permanencia_dataset,
)
from utils import db_pia
from utils.data_loader import data_file_mtime, get_current_version, set_current_version
from utils.menu_config import (
    ACCOUNT_PAGES,
    ADMINISTRACION,
    ADMIN_ETL_GROUP,
    ADMIN_PAGES,
    CATEGORY_ICONS,
    INDICADORES_VERSION,
    INDICE_PERMANENCIA,
    INDICE_PERMANENCIA_PERMISSION,
    MI_CUENTA,
    PAGE_ICON_DEFAULT,
    PERMANENCIA_PAGES,
    VERSION_GROUPS,
    all_module_names,
    iter_page_configs,
    page_key,
    permission_key,
    slug_lookup,
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


@st.cache_data
def get_logo_base64():
    try:
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo-ucp.png")
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as exc:
        log_exception("No se pudo cargar el logo", exc)
        return None


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

# slug -> (categoría, título) de la página activa, y el conjunto de
# categorías que corresponden a un indicador (para saber, dado el slug
# actual, qué rama del árbol de la barra lateral abrir por defecto).
SLUG_LOOKUP = slug_lookup()
INDICATOR_TARGET_CATEGORIES = {indicator["target_category"] for indicator in INDICADORES_VERSION}

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
        logo_data = get_logo_base64()
        logo_html = (
            f'<img src="data:image/png;base64,{logo_data}" width="220" style="margin-bottom: 20px;">'
            if logo_data else ""
        )
        st.markdown(
            f"""
            <div style="text-align: center; margin-top: 50px; margin-bottom: 30px;">
                {logo_html}
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
    current_slug = getattr(pg, "url_path", "")
    active_category, active_title = SLUG_LOOKUP.get(current_slug, (None, None))

    with st.sidebar:
        st.markdown(
            """
            <style>
            section[data-testid="stSidebar"] { background-color: #F5F7FA; }
            section[data-testid="stSidebar"] p,
            section[data-testid="stSidebar"] span,
            section[data-testid="stSidebar"] label { color: #1e293b; }
            section[data-testid="stSidebar"] hr { border-color: rgba(0,0,0,0.10); }
            section[data-testid="stSidebar"] div[data-testid="stButton"] button {
                background-color: transparent;
                border: none;
                justify-content: flex-start;
                color: #334155;
                font-weight: 500;
                font-size: 14px;
                padding: 7px 10px;
                border-radius: 8px;
                width: 100%;
            }
            section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
                background-color: rgba(0,64,128,0.08);
                color: #004080;
            }
            section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
                background-color: #004080;
                color: #ffffff;
            }
            section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] p,
            section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] span {
                color: #ffffff;
            }
            section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:hover {
                background-color: #0059b3;
            }
            section[data-testid="stSidebar"] div[data-testid="stPopover"] button {
                background-color: #ffffff;
                border: 1px solid rgba(0,0,0,0.15);
                color: #1e293b;
                border-radius: 8px;
            }
            section[data-testid="stSidebar"] div[data-testid="stPopover"] button:hover {
                background-color: rgba(0,64,128,0.06);
                border-color: rgba(0,64,128,0.35);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # --- LOGO ---
        data = get_logo_base64()
        if data:
            st.markdown(
                f"""<div style="display: flex; justify-content: center; margin-bottom: 18px;"><img src="data:image/png;base64,{data}" width="170"></div>""",
                unsafe_allow_html=True
            )

        # --- PERFIL DEL USUARIO ---
        user_data = st.session_state.user or {}
        full_name = " ".join(
            part for part in [user_data.get("nombre", ""), user_data.get("apellido", "")] if part
        ).strip() or "Usuario"
        email = user_data.get("email", "")

        st.markdown(
            f"""
            <div style="display:flex; flex-direction:column; align-items:center; text-align:center; margin-bottom:10px;">
                <div style="width:60px; height:60px; border-radius:50%; background:#dbe4f0;
                            display:flex; align-items:center; justify-content:center; margin-bottom:8px;">
                    <svg width="30" height="30" viewBox="0 0 24 24" fill="#5b7ba8">
                        <path d="M12 12c2.7 0 4.9-2.2 4.9-4.9S14.7 2.2 12 2.2 7.1 4.4 7.1 7.1 9.3 12 12 12zm0 2.5c-3.3 0-9.8 1.6-9.8 4.9v2.4h19.6v-2.4c0-3.3-6.5-4.9-9.8-4.9z"/>
                    </svg>
                </div>
                <div style="font-weight:700; font-size:14px; color:#1e293b;">{escape(full_name)}</div>
                <div style="font-size:12px; color:#64748b;">{escape(email)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.popover("Cuenta", use_container_width=True):
            cambiar_pw_key = page_key(MI_CUENTA, "Cambiar Contraseña")
            if st.button("Cambiar Contraseña", key="btn_cambiar_pw", icon=":material/lock_reset:", use_container_width=True):
                if cambiar_pw_key in ALL_PAGES:
                    st.switch_page(ALL_PAGES[cambiar_pw_key])
            if st.button("Cerrar", key="btn_logout_sidebar", icon=":material/logout:", use_container_width=True):
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

        st.markdown("<hr style='margin: 14px 0;'>", unsafe_allow_html=True)

        # --- ÁRBOL DE NAVEGACIÓN (accordion: sólo el camino activo se abre por defecto) ---
        if "nav_open_sections" not in st.session_state:
            st.session_state.nav_open_sections = set()
        opened = st.session_state.nav_open_sections

        if "nav_sections_seeded" not in st.session_state:
            st.session_state.nav_sections_seeded = True
            if active_category in INDICATOR_TARGET_CATEGORIES:
                for version in VERSION_GROUPS:
                    if version_permission_key(version) == get_current_version():
                        opened.add(f"version::{version}")
                        opened.add(f"indicator::{version}::{active_category}")
            elif active_category == INDICE_PERMANENCIA:
                opened.add("permanencia")
            elif active_category == ADMINISTRACION:
                opened.add("admin")
                if active_title in {p["title"] for p in ADMIN_ETL_GROUP["pages"]}:
                    opened.add("admin_etl_group")

        def _nav_container(indent):
            if not indent:
                return st.container()
            _, col = st.columns([indent, 6])
            return col

        def _render_toggle(title, icon, indent, section_id):
            is_open = section_id in opened
            chevron = "▾" if is_open else "▸"
            with _nav_container(indent):
                clicked = st.button(
                    f"{title}  {chevron}",
                    key=f"toggle_{section_id}",
                    icon=f":material/{icon}:",
                    use_container_width=True,
                )
            if clicked:
                if is_open:
                    opened.discard(section_id)
                else:
                    opened.add(section_id)
                st.rerun()
            return is_open

        def _render_leaf(target_page, title, icon, indent, key, active=False):
            with _nav_container(indent):
                clicked = st.button(
                    title,
                    key=key,
                    icon=f":material/{icon}:",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                )
            if clicked and target_page is not None:
                st.switch_page(target_page)

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

        _render_leaf(p_home, "Inicio", "home", 0, "nav_home", active=(current_slug == "inicio"))

        for version in VERSION_GROUPS:
            visible_indicators = [
                indicator for indicator in INDICADORES_VERSION
                if has_indicator_permission(version, indicator)
            ]
            if not visible_indicators:
                continue

            version_open = _render_toggle(version, CATEGORY_ICONS.get(version, "dataset"), 0, f"version::{version}")
            if version_open:
                for indicator in visible_indicators:
                    ind_section = f"indicator::{version}::{indicator['name']}"
                    ind_open = _render_toggle(indicator["name"], indicator.get("icon", "folder"), 1, ind_section)
                    if ind_open:
                        for page_config in indicator["pages"]:
                            lookup_key = page_key(indicator["target_category"], page_config["title"])
                            target_page = ALL_PAGES.get(lookup_key)
                            is_active = (
                                current_slug == page_config["slug"]
                                and get_current_version() == version_permission_key(version)
                            )
                            btn_key = f"leaf_{version}_{indicator['name']}_{page_config['title']}"
                            with _nav_container(2):
                                clicked = st.button(
                                    page_config["title"],
                                    key=btn_key,
                                    icon=f":material/{page_config.get('icon', PAGE_ICON_DEFAULT)}:",
                                    use_container_width=True,
                                    type="primary" if is_active else "secondary",
                                )
                            if clicked:
                                if target_page is not None:
                                    set_current_version(version_permission_key(version))
                                    st.switch_page(target_page)
                                else:
                                    st.error(f"Página no encontrada: {lookup_key}")

        if has_category_permission(INDICE_PERMANENCIA):
            perm_open = _render_toggle(
                INDICE_PERMANENCIA, CATEGORY_ICONS.get(INDICE_PERMANENCIA, "timeline"), 0, "permanencia"
            )
            if perm_open:
                for page_config in PERMANENCIA_PAGES:
                    lookup_key = page_key(INDICE_PERMANENCIA, page_config["title"])
                    _render_leaf(
                        ALL_PAGES.get(lookup_key),
                        page_config["title"],
                        page_config.get("icon", PAGE_ICON_DEFAULT),
                        1,
                        f"leaf_perm_{page_config['title']}",
                        active=(current_slug == page_config["slug"]),
                    )

        if st.session_state.rol == 'ADMIN':
            admin_open = _render_toggle(
                ADMINISTRACION, CATEGORY_ICONS.get(ADMINISTRACION, "admin_panel_settings"), 0, "admin"
            )
            if admin_open:
                for page_config in ADMIN_PAGES:
                    lookup_key = page_key(ADMINISTRACION, page_config["title"])
                    _render_leaf(
                        ALL_PAGES.get(lookup_key),
                        page_config["title"],
                        page_config.get("icon", PAGE_ICON_DEFAULT),
                        1,
                        f"leaf_admin_{page_config['title']}",
                        active=(current_slug == page_config["slug"]),
                    )

                etl_group_open = _render_toggle(
                    ADMIN_ETL_GROUP["title"], ADMIN_ETL_GROUP.get("icon", "folder"), 1, "admin_etl_group"
                )
                if etl_group_open:
                    for page_config in ADMIN_ETL_GROUP["pages"]:
                        lookup_key = page_key(ADMINISTRACION, page_config["title"])
                        _render_leaf(
                            ALL_PAGES.get(lookup_key),
                            page_config["title"],
                            page_config.get("icon", PAGE_ICON_DEFAULT),
                            2,
                            f"leaf_admin_etl_{page_config['title']}",
                            active=(current_slug == page_config["slug"]),
                        )

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
            "matriculas": [(None, "matriculas")],
            "notas": [(None, "notas")]
        }

        # Las páginas de permanencia dependen del periodo elegido en la propia página.
        IP_PAGES = {
            "ip_actual": ("actual", VISTA_VISION_GENERAL),
            "ip_corte": ("corte", VISTA_FECHA_CORTE),
        }

        # pg es el objeto retornado por st.navigation
        current_slug = pg.url_path if hasattr(pg, "url_path") else ""
        if current_slug in IP_PAGES:
            ip_suffix, ip_vista = IP_PAGES[current_slug]
            # Mientras no se elija un indicador no hay archivo fuente que mostrar.
            ip_periodo = st.session_state.get(f"ip_periodo_{ip_suffix}")
            targets = [("global", get_permanencia_dataset(ip_periodo, ip_vista))] if ip_periodo else []
        elif current_slug == "encuestas_avance":
            # La encuesta depende de la que se elija en la propia página.
            enc_sede = st.session_state.get("encuestas_sede")
            enc_periodo = st.session_state.get("encuestas_periodo")
            enc_carrera = st.session_state.get("encuestas_carrera")
            enc_tipo = st.session_state.get("encuestas_tipo")
            targets = (
                [(
                    get_encuesta_scope(enc_sede, enc_periodo, enc_carrera, enc_tipo),
                    get_encuestas_dataset(enc_sede, enc_periodo, enc_carrera, enc_tipo),
                )]
                if enc_sede and enc_periodo and enc_carrera and enc_tipo
                else []
            )
        else:
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
