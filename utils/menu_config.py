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

INDICADORES_VERSION = [
    {
        "name": "Listado de Alumnos",
        "permission": "listado_alumnos",
        "target_category": "Listado de Alumnos",
        "pages": [
            {"title": "Alumnos", "slug": "listado_alumnos", "module": "panel_acad_alumnos"},
        ],
    },
    {
        "name": "Panel Académico",
        "permission": "panel_academico",
        "target_category": "Panel Académico",
        "pages": [
            {"title": "Resumen", "slug": "panel_resumen", "module": "panel_acad_resumen"},
            {"title": "Asistencias", "slug": "panel_asistencias", "module": "panel_acad_asistencias"},
        ],
    },
    {
        "name": "Rendimiento Académico",
        "permission": "rendimiento_academico",
        "target_category": "Rendimiento Académico",
        "pages": [
            {"title": "Estudiante", "slug": "rend_aca_estudiante", "module": "rend_acad_alumno"},
            {"title": "Asignatura", "slug": "rend_aca_asignatura", "module": "rend_acad_asignatura"},
            {"title": "Semestre", "slug": "rend_aca_semestre", "module": "rend_acad_semestre"},
            {"title": "Carrera", "slug": "rend_aca_carrera", "module": "rend_acad_carrera"},
        ],
    },
    {
        "name": "Tasa de Aprobación",
        "permission": "tasa_aprobacion",
        "target_category": "Tasa de Aprobación",
        "pages": [
            {"title": "Asignatura", "slug": "tasa_aprob_asignatura", "module": "tasa_aprobacion_asignatura"},
            {"title": "Carrera", "slug": "tasa_aprob_carrera", "module": "tasa_aprobacion_carrera"},
        ],
    },
    {
        "name": "Eficiencia Académica",
        "permission": "eficiencia_academica",
        "target_category": "Eficiencia Académica",
        "pages": [
            {"title": "Terminal", "slug": "efic_terminal", "module": "eficiencia_terminal"},
            {"title": "Egreso", "slug": "efic_egreso", "module": "eficiencia_egreso"},
            {"title": "Rezago Educativo", "slug": "efic_rezago", "module": "eficiencia_rezago"},
            {"title": "Eficiencia de Titulación", "slug": "efic_titulacion", "module": "eficiencia_titulacion"},
            {"title": "Tasa de Retención", "slug": "tasa_retencion", "module": "tasa_retencion"},
            {"title": "Tiempos Medios de Egreso", "slug": "tiempos_medios", "module": "tiempos_medios"},
        ],
    },
    {
        "name": "Tasa de Deserción",
        "permission": "tasa_desercion",
        "target_category": "Tasa de Deserción",
        "pages": [
            {"title": "Semestral", "slug": "tasa_desercion_sem", "module": "tasa_desercion_semestral"},
            {"title": "Generacional", "slug": "tasa_desercion_gen", "module": "tasa_desercion_generacional"},
        ],
    },
    {
        "name": "Tasa de Promoción",
        "permission": "tasa_promocion",
        "target_category": "Tasa de Promoción",
        "pages": [
            {"title": "Semestral / Anual", "slug": "tasa_promocion_sem", "module": "tasa_promocion_semestral"},
        ],
    },
]

VERSION_GROUPS = [VERSION_1, VERSION_2]

ACCOUNT_PAGES = [
    {"title": "Cambiar Contraseña", "slug": "config_perfil", "module": "config_perfil"},
]

PERMANENCIA_PAGES = [
    {
        "title": "Visión General",
        "slug": "ip_actual",
        "module": "indice_permanencia",
        "custom_render": "render_actual",
    },
    {
        "title": "Fecha de Corte",
        "slug": "ip_corte",
        "module": "indice_permanencia",
        "custom_render": "render_corte",
    },
]

ADMIN_PAGES = [
    {"title": "Gestión de Usuarios", "slug": "admin_usuarios", "module": "admin_usuarios"},
    {"title": "Gestión de Áreas", "slug": "admin_areas", "module": "admin_areas"},
    {"title": "Logs y Auditoría", "slug": "admin_logs", "module": "admin_logs"},
]


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


PERMISOS_SISTEMA = list(VERSION_PERMISSIONS.values()) + version_permission_options() + [INDICE_PERMANENCIA_PERMISSION]


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


def all_module_names():
    return sorted({page_config["module"] for _, page_config in iter_page_configs()})

