MI_CUENTA = "Mi Cuenta"
VERSION_1 = "Indicadores Versión 1"
VERSION_2 = "Indicadores Versión 2"
INDICE_PERMANENCIA = "Índice de Permanencia"
ADMINISTRACION = "Administración"

INDICE_PERMANENCIA_PERMISSION = "indice_permanencia"
VERSION_PERMISSIONS = {
    VERSION_1: "indicadores_v1",
    VERSION_2: "indicadores_v2",
}

# Iconos Material Symbols (sin ":material/.../" -- eso lo arma quien los consume)
# usados en la barra lateral: uno por categoría de nivel superior y otro por
# cada indicador/página, para que el árbol de navegación se parezca al patrón
# de referencia (icono + texto en cada fila).
CATEGORY_ICONS = {
    VERSION_1: "dataset",
    VERSION_2: "dataset",
    INDICE_PERMANENCIA: "timeline",
    ADMINISTRACION: "admin_panel_settings",
}

PAGE_ICON_DEFAULT = "chevron_right"

INDICADORES_VERSION = [
    {
        "name": "Listado de Alumnos",
        "permission": "listado_alumnos",
        "target_category": "Listado de Alumnos",
        "icon": "groups",
        "pages": [
            {"title": "Alumnos", "slug": "listado_alumnos", "module": "panel_acad_alumnos", "icon": "badge"},
        ],
    },
    {
        "name": "Panel Académico",
        "permission": "panel_academico",
        "target_category": "Panel Académico",
        "icon": "school",
        "pages": [
            {"title": "Resumen", "slug": "panel_resumen", "module": "panel_acad_resumen", "icon": "dashboard"},
            {"title": "Asistencias", "slug": "panel_asistencias", "module": "panel_acad_asistencias", "icon": "event_available"},
        ],
    },
    {
        "name": "Rendimiento Académico",
        "permission": "rendimiento_academico",
        "target_category": "Rendimiento Académico",
        "icon": "trending_up",
        "pages": [
            {"title": "Estudiante", "slug": "rend_aca_estudiante", "module": "rend_acad_alumno", "icon": "person"},
            {"title": "Asignatura", "slug": "rend_aca_asignatura", "module": "rend_acad_asignatura", "icon": "menu_book"},
            {"title": "Semestre", "slug": "rend_aca_semestre", "module": "rend_acad_semestre", "icon": "calendar_month"},
            {"title": "Carrera", "slug": "rend_aca_carrera", "module": "rend_acad_carrera", "icon": "school"},
        ],
    },
    {
        "name": "Tasa de Aprobación",
        "permission": "tasa_aprobacion",
        "target_category": "Tasa de Aprobación",
        "icon": "check_circle",
        "pages": [
            {"title": "Asignatura", "slug": "tasa_aprob_asignatura", "module": "tasa_aprobacion_asignatura", "icon": "menu_book"},
            {"title": "Carrera", "slug": "tasa_aprob_carrera", "module": "tasa_aprobacion_carrera", "icon": "school"},
        ],
    },
    {
        "name": "Eficiencia Académica",
        "permission": "eficiencia_academica",
        "target_category": "Eficiencia Académica",
        "icon": "speed",
        "pages": [
            {"title": "Terminal", "slug": "efic_terminal", "module": "eficiencia_terminal", "icon": "flag"},
            {"title": "Egreso", "slug": "efic_egreso", "module": "eficiencia_egreso", "icon": "workspace_premium"},
            {"title": "Rezago Educativo", "slug": "efic_rezago", "module": "eficiencia_rezago", "icon": "hourglass_bottom"},
            {"title": "Eficiencia de Titulación", "slug": "efic_titulacion", "module": "eficiencia_titulacion", "icon": "military_tech"},
            {"title": "Tasa de Retención", "slug": "tasa_retencion", "module": "tasa_retencion", "icon": "anchor"},
            {"title": "Tiempos Medios de Egreso", "slug": "tiempos_medios", "module": "tiempos_medios", "icon": "schedule"},
        ],
    },
    {
        "name": "Tasa de Deserción",
        "permission": "tasa_desercion",
        "target_category": "Tasa de Deserción",
        "icon": "trending_down",
        "pages": [
            {"title": "Semestral", "slug": "tasa_desercion_sem", "module": "tasa_desercion_semestral", "icon": "calendar_month"},
            {"title": "Generacional", "slug": "tasa_desercion_gen", "module": "tasa_desercion_generacional", "icon": "groups"},
        ],
    },
    {
        "name": "Tasa de Promoción",
        "permission": "tasa_promocion",
        "target_category": "Tasa de Promoción",
        "icon": "arrow_upward",
        "pages": [
            {"title": "Semestral / Anual", "slug": "tasa_promocion_sem", "module": "tasa_promocion_semestral", "icon": "calendar_month"},
        ],
    },
    {
        "name": "Encuestas",
        "permission": "encuestas",
        "target_category": "Encuestas",
        "icon": "poll",
        "pages": [
            {"title": "Avance de Encuesta", "slug": "encuestas_avance", "module": "encuestas", "icon": "fact_check"},
            {"title": "Indicadores", "slug": "encuestas_indicadores", "module": "indicadores_encuestas", "icon": "insights"},
        ],
    },
]

VERSION_GROUPS = [VERSION_1, VERSION_2]

ACCOUNT_PAGES = [
    {"title": "Cambiar Contraseña", "slug": "config_perfil", "module": "config_perfil", "icon": "lock_reset"},
]

PERMANENCIA_PAGES = [
    {
        "title": "Visión General",
        "slug": "ip_actual",
        "module": "indice_permanencia",
        "custom_render": "render_actual",
        "icon": "visibility",
    },
    {
        "title": "Fecha de Corte",
        "slug": "ip_corte",
        "module": "indice_permanencia",
        "custom_render": "render_corte",
        "icon": "event_available",
    },
]

ADMIN_PAGES = [
    {"title": "Gestión de Usuarios", "slug": "admin_usuarios", "module": "admin_usuarios", "icon": "person"},
    {"title": "Gestión de Áreas", "slug": "admin_areas", "module": "admin_areas", "icon": "apartment"},
    {"title": "Logs y Auditoría", "slug": "admin_logs", "module": "admin_logs", "icon": "history"},
]

# "Configuración ETL" es un submenú (no una página propia): al hacer click se
# despliegan sus páginas (Encuestas, Alumnos, Asistencias, Índice de
# Permanencia), cada una con su propio módulo/slug — mismo patrón
# toggle+leaf que INDICADORES_VERSION, ver app.py. "Fechas de Inicio de
# Clases" (antes una página propia de ADMIN_PAGES) ahora vive como sub-tab
# dentro de "Índice de Permanencia" (ver modules/permanencia_config_etl.py).
ADMIN_ETL_GROUP = {
    "title": "Configuración ETL",
    "icon": "sync",
    # Resumen siempre primero; el resto en orden alfabético.
    "pages": [
        {"title": "Resumen", "slug": "admin_etl_resumen", "module": "etl_resumen", "icon": "dashboard"},
        {"title": "Alumnos Activos", "slug": "admin_etl_activos", "module": "activos_config_etl", "icon": "how_to_reg"},
        {"title": "Alumnos", "slug": "admin_etl_alumnos", "module": "alumnos_config_etl", "icon": "groups"},
        {"title": "Asistencias", "slug": "admin_etl_asistencias", "module": "asistencias_config_etl", "icon": "event_available"},
        {"title": "Encuestas", "slug": "admin_etl_encuestas", "module": "encuestas_config_etl", "icon": "poll"},
        {"title": "Índice de Permanencia", "slug": "admin_etl_permanencia", "module": "permanencia_config_etl", "icon": "timeline"},
    ],
}


def permission_key(version, indicator):
    version_permission = VERSION_PERMISSIONS[version]
    indicator_permission = indicator["permission"] if isinstance(indicator, dict) else indicator
    return f"{version_permission}.{indicator_permission}"


def version_permission_key(version):
    return VERSION_PERMISSIONS[version]


def version_permission_options():
    return [
        permission_key(version, indicator)
        for version in VERSION_GROUPS
        for indicator in INDICADORES_VERSION
    ]


PERMISOS_SISTEMA = (
    list(VERSION_PERMISSIONS.values())
    + version_permission_options()
    + [INDICE_PERMANENCIA_PERMISSION]
)


def page_key(category, page_title):
    return f"{category}:{page_title}"


def iter_page_configs():
    for page_config in ACCOUNT_PAGES:
        yield MI_CUENTA, page_config
    for indicator in INDICADORES_VERSION:
        for page_config in indicator["pages"]:
            yield indicator["target_category"], page_config
    for page_config in PERMANENCIA_PAGES:
        yield INDICE_PERMANENCIA, page_config
    for page_config in ADMIN_PAGES:
        yield ADMINISTRACION, page_config
    for page_config in ADMIN_ETL_GROUP["pages"]:
        yield ADMINISTRACION, page_config


def all_module_names():
    return sorted({page_config["module"] for _, page_config in iter_page_configs()})


def slug_lookup():
    """slug -> (categoría, título). Sirve para saber, a partir de la URL
    activa, qué rama del árbol de navegación de la barra lateral hay que
    mostrar expandida."""
    return {
        page_config["slug"]: (category, page_config["title"])
        for category, page_config in iter_page_configs()
    }

