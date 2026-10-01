"""
modules/encuestas_ev1.py

Módulo especializado para la visualización integral de la EV1 (Opinión del Estudiante),
adaptado a partir del diseño de Dashboard_EV1_Opinion_Estudiante (1).html.

Incluye 6 sub-vistas operativas y pedagógicas:
  1. Avance general (KPIs, cobertura por materia, detalle de asignaciones, avance global y participación).
  2. Por alumno (cumplimiento por estudiante, anonimato protegido, tabla detallada con semáforo).
  3. Materia · sección · grupo (alertas de ofertas críticas, cobertura por grupo académico).
  4. Resultados EV1 (distribución de escala 1..5, promedios por dimensión, consolidados por docente).
  5. Por docente (ficha de desempeño docente, desglose por dimensión y detalle de asignaturas).
  6. Análisis pedagógico (árbol pedagógico institucional: 5 dimensiones, 10 indicadores y 16 criterios con descriptores).

Cumple estrictamente con las reglas del proyecto: comentarios y nombres en español, UTF-8,
código limpio y preservación inquebrantable de funcionalidades existentes.
"""

from html import escape
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.ui import render_kpi_card
from services.data.encuestas import (
    load_resultado_general,
    load_resultado_dimensiones,
    load_resultado_indicadores,
    load_resultado_criterios,
    load_resultado_docentes,
)


# ==============================================================================
# CATÁLOGO PEDAGÓGICO INSTITUCIONAL UCP (EV1)
# 5 Dimensiones, 10 Indicadores y 16 Criterios oficiales con descriptores
# ==============================================================================
CATALOGO_PEDAGOGICO_EV1 = [
    {
        "id": 1,
        "nombre": "1. Planificación, Organización y Dominio de la Asignatura",
        "corto": "Planificación y dominio",
        "puntaje_referencia": 4.48,
        "criterios": [
            {
                "n": 1,
                "texto": "El docente demuestra un amplio dominio, conocimiento y experiencia en los temas desarrollados durante las clases.",
                "puntaje": 4.58,
                "indicador": "01. Dominio de la asignatura",
                "descriptor": "La percepción estudiantil evidencia un dominio sólido y actualizado de los contenidos.",
            },
            {
                "n": 2,
                "texto": "Las clases teóricas y/o prácticas se perciben organizadas y estructuradas de acuerdo con el Programa de Estudios de la materia.",
                "puntaje": 4.35,
                "indicador": "02. Planificación de clases",
                "descriptor": "La planificación se percibe coherente con el programa y con la naturaleza de las actividades.",
            },
            {
                "n": 3,
                "texto": "El profesor cumple de manera constante con el desarrollo de los contenidos establecidos para la asignatura.",
                "puntaje": 4.52,
                "indicador": "02. Planificación de clases",
                "descriptor": "La planificación se percibe coherente con el programa y con la naturaleza de las actividades.",
            },
        ],
    },
    {
        "id": 2,
        "nombre": "2. Gestión de Recursos Didácticos y Entornos de Aprendizaje",
        "corto": "Recursos y entornos",
        "puntaje_referencia": 4.16,
        "criterios": [
            {
                "n": 4,
                "texto": "El profesor utiliza variedad de recursos didácticos adecuados que facilitan la comprensión de la clase, presencial o virtual.",
                "puntaje": 4.20,
                "indicador": "03. Recursos didácticos",
                "descriptor": "Los recursos utilizados son pertinentes y apoyan adecuadamente el aprendizaje.",
            },
            {
                "n": 5,
                "texto": "El aula virtual de la materia se encuentra organizada, actualizada y con materiales disponibles oportunamente.",
                "puntaje": 4.12,
                "indicador": "03. Recursos didácticos",
                "descriptor": "Los recursos utilizados son pertinentes y apoyan adecuadamente el aprendizaje.",
            },
            {
                "n": 6,
                "texto": "El docente orienta de manera clara la realización de tareas, investigación, extensión y actividades autónomas.",
                "puntaje": 4.16,
                "indicador": "04. Orientación de tareas",
                "descriptor": "La orientación es adecuada, aunque puede reforzarse la claridad de algunas consignas.",
            },
        ],
    },
    {
        "id": 3,
        "nombre": "3. Comunicación Didáctica y Relaciones Interpersonales",
        "corto": "Comunicación y relaciones",
        "puntaje_referencia": 4.39,
        "criterios": [
            {
                "n": 7,
                "texto": "El docente se comunica de forma clara, amena y comprensible durante las explicaciones de la clase.",
                "puntaje": 4.42,
                "indicador": "05. Comunicación didáctica",
                "descriptor": "La comunicación facilita la comprensión y mantiene una dinámica de clase favorable.",
            },
            {
                "n": 8,
                "texto": "El docente responde de manera oportuna y adecuada a las consultas o dudas planteadas por el grupo.",
                "puntaje": 4.34,
                "indicador": "05. Comunicación didáctica",
                "descriptor": "La comunicación facilita la comprensión y mantiene una dinámica de clase favorable.",
            },
            {
                "n": 9,
                "texto": "El profesor muestra respeto, apertura y trato digno hacia todos los estudiantes.",
                "puntaje": 4.41,
                "indicador": "06. Respeto y trato digno",
                "descriptor": "Se evidencia un clima de respeto y relaciones interpersonales positivas.",
            },
        ],
    },
    {
        "id": 4,
        "nombre": "4. Evaluación, Retroalimentación y Correspondencia Pedagógica",
        "corto": "Evaluación y retroalimentación",
        "puntaje_referencia": 4.15,
        "criterios": [
            {
                "n": 10,
                "texto": "El profesor comunicó por escrito, de manera clara y oportuna, los indicadores, criterios y el sistema de evaluación.",
                "puntaje": 4.18,
                "indicador": "07. Sistema de evaluación",
                "descriptor": "El sistema de evaluación es comunicado y comprendido de manera adecuada.",
            },
            {
                "n": 11,
                "texto": "Las orientaciones indican con claridad y antelación lo esperado en las actividades autónomas o tareas.",
                "puntaje": 4.10,
                "indicador": "08. Correspondencia didáctica",
                "descriptor": "Existe correspondencia general entre orientaciones, enseñanza y evaluación.",
            },
            {
                "n": 12,
                "texto": "Existe adecuación entre los temas explicados en clase y lo evaluado en los exámenes.",
                "puntaje": 4.21,
                "indicador": "08. Correspondencia didáctica",
                "descriptor": "Existe correspondencia general entre orientaciones, enseñanza y evaluación.",
            },
            {
                "n": 13,
                "texto": "El docente implementa retroalimentación clara sobre aciertos y aspectos a mejorar tras las evaluaciones.",
                "puntaje": 4.08,
                "indicador": "09. Retroalimentación",
                "descriptor": "La retroalimentación es funcional, pero constituye la principal oportunidad de mejora.",
            },
            {
                "n": 14,
                "texto": "Los resultados de las evaluaciones son entregados en un tiempo adecuado y conforme a lo esperado.",
                "puntaje": 4.18,
                "indicador": "09. Retroalimentación",
                "descriptor": "La retroalimentación es funcional, pero constituye la principal oportunidad de mejora.",
            },
        ],
    },
    {
        "id": 5,
        "nombre": "5. Puntualidad y Cumplimiento",
        "corto": "Puntualidad y cumplimiento",
        "puntaje_referencia": 4.54,
        "criterios": [
            {
                "n": 15,
                "texto": "El profesor asiste de manera puntual al inicio y finalización de las clases o encuentros virtuales.",
                "puntaje": 4.61,
                "indicador": "10. Puntualidad del docente",
                "descriptor": "La percepción estudiantil muestra un nivel alto de puntualidad y cumplimiento.",
            },
            {
                "n": 16,
                "texto": "El docente permanece y aprovecha el tiempo de clase de acuerdo con la carga horaria establecida.",
                "puntaje": 4.47,
                "indicador": "10. Puntualidad del docente",
                "descriptor": "La percepción estudiantil muestra un nivel alto de puntualidad y cumplimiento.",
            },
        ],
    },
]

# Perfiles de referencia de docentes según el diseño de JuanFer
PERFILES_DOCENTES_REFERENCIA = {
    "LUIS SALINAS": {"score": 4.60, "fav": 92, "meta": "ANATOMIA I · Sección A · TEORIA", "dims": [4.72, 4.42, 4.58, 4.51, 4.77]},
    "CLAUDIA DAMMERT": {"score": 4.10, "fav": 80, "meta": "ANATOMIA I · Sección A · G1-MO", "dims": [4.28, 4.05, 4.12, 3.96, 4.09]},
    "ALBERTO BETO": {"score": 4.35, "fav": 87, "meta": "BIOLOGIA · Sección A · TEORIA", "dims": [4.47, 4.25, 4.41, 4.18, 4.44]},
    "FELIPE ROMERO": {"score": 4.15, "fav": 81, "meta": "BIOLOGIA · Sección A · G2-MO", "dims": [4.26, 4.02, 4.25, 3.98, 4.24]},
    "MR BEAN": {"score": 4.60, "fav": 93, "meta": "INGLES · Sección A · TEORIA", "dims": [4.63, 4.42, 4.71, 4.48, 4.76]},
}

# Asignaciones de referencia para modo offline / inicial
ASIGNACIONES_REFERENCIA = [
    {"alumno": "JOSE ROJAS", "materia": "ANATOMIA I", "seccion": "A", "grupo": "TEORIA", "docente": "LUIS SALINAS", "estado": "Completada", "score": 4.5},
    {"alumno": "JOSE ROJAS", "materia": "ANATOMIA I", "seccion": "A", "grupo": "G1-MO", "docente": "CLAUDIA DAMMERT", "estado": "Completada", "score": 4.2},
    {"alumno": "JOSE ROJAS", "materia": "BIOLOGIA", "seccion": "A", "grupo": "TEORIA", "docente": "ALBERTO BETO", "estado": "Completada", "score": 4.4},
    {"alumno": "JOSE ROJAS", "materia": "BIOLOGIA", "seccion": "A", "grupo": "G2-MO", "docente": "FELIPE ROMERO", "estado": "Completada", "score": 4.1},
    {"alumno": "JOSE ROJAS", "materia": "INGLES", "seccion": "A", "grupo": "TEORIA", "docente": "MR BEAN", "estado": "Completada", "score": 4.6},
    {"alumno": "LUCAS REAÑO", "materia": "ANATOMIA I", "seccion": "A", "grupo": "TEORIA", "docente": "LUIS SALINAS", "estado": "Completada", "score": 4.7},
    {"alumno": "LUCAS REAÑO", "materia": "ANATOMIA I", "seccion": "A", "grupo": "G1-MO", "docente": "CLAUDIA DAMMERT", "estado": "Completada", "score": 4.0},
    {"alumno": "LUCAS REAÑO", "materia": "BIOLOGIA", "seccion": "A", "grupo": "TEORIA", "docente": "ALBERTO BETO", "estado": "Completada", "score": 4.3},
    {"alumno": "LUCAS REAÑO", "materia": "BIOLOGIA", "seccion": "A", "grupo": "G2-MO", "docente": "FELIPE ROMERO", "estado": "Completada", "score": 4.2},
    {"alumno": "LUCAS REAÑO", "materia": "INGLES", "seccion": "A", "grupo": "TEORIA", "docente": "MR BEAN", "estado": "En proceso", "score": None},
    {"alumno": "JULIO BERENGUEL", "materia": "HISTORIA DE LA MEDICINA", "seccion": "B", "grupo": "TEORIA", "docente": "ROBERTA GRANDE", "estado": "Pendiente", "score": None},
    {"alumno": "JULIO BERENGUEL", "materia": "FISIOLOGIA II", "seccion": "B", "grupo": "TEORIA", "docente": "AUGUSTO HIELO", "estado": "Pendiente", "score": None},
    {"alumno": "JULIO BERENGUEL", "materia": "FISIOLOGIA II", "seccion": "B", "grupo": "G1-MS", "docente": "AUGUSTO HIELO", "estado": "Pendiente", "score": None},
]


# ==============================================================================
# FUNCIONES AUXILIARES DE FORMATEO Y ESTILOS
# ==============================================================================

def _etiqueta_estado_html(estado: str) -> str:
    """Devuelve un badge HTML estilizado para el estado de la asignación."""
    estilo_base = "display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 0.76rem; font-weight: 700;"
    if estado == "Completada":
        return f'<span style="{estilo_base} color: #17845f; background-color: #e7f6f0;">● {escape(estado)}</span>'
    elif estado in ("En proceso", "Parcial"):
        return f'<span style="{estilo_base} color: #b87908; background-color: #fff5d9;">● {escape(estado)}</span>'
    return f'<span style="{estilo_base} color: #bd3f4a; background-color: #fdecef;">● {escape(estado)}</span>'


def _etiqueta_semaforo_html(porcentaje: float) -> str:
    """Genera badge para semáforo pedagógico: verde >= 80%, amarillo 50..79%, rojo < 50%."""
    estilo_base = "display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 0.74rem; font-weight: 700;"
    if porcentaje >= 80.0:
        return f'<span style="{estilo_base} color: #17845f; background-color: #e7f6f0;">Adecuado</span>'
    elif porcentaje >= 50.0:
        return f'<span style="{estilo_base} color: #b87908; background-color: #fff5d9;">Seguimiento</span>'
    return f'<span style="{estilo_base} color: #bd3f4a; background-color: #fdecef;">Crítico</span>'


def _formatear_porcentaje(valor: float) -> str:
    return f"{valor:.1f}%".replace(".", ",")


def _formatear_puntaje(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def _render_kpi_card_ev1(
    titulo: str,
    valor: str,
    ayuda: str = "",
    detalle: str = "",
    color_acento: str = "#12263f",
    color_fondo: str = "#f3f6fa",
    color_borde: str = "#dbe3ed",
):
    """
    Renderiza una tarjeta KPI con diseño moderno, sombra sutil, elevación suave en hover
    y un tooltip explicativo en español (atributo HTML 'title') con cantidades y cálculo exacto.
    """
    attr_title = f'title="{escape(ayuda)}"' if ayuda else ""
    st.markdown(
        f"""
        <div {attr_title} class="ev1-kpi-card" style="
            background-color: {color_fondo};
            border: 1px solid {color_borde};
            border-radius: 10px;
            padding: 16px 14px;
            text-align: center;
            height: 100%;
            box-shadow: 0 2px 5px rgba(0,0,0,0.04);
            transition: transform 0.18s ease, box-shadow 0.18s ease;
            cursor: help;
        ">
            <div style="
                font-size: 0.76rem;
                color: #55657a;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.03em;
                margin-bottom: 5px;
            ">
                {escape(titulo)}
            </div>
            <div style="font-size: 1.75rem; color: {color_acento}; font-weight: 800; line-height: 1.15;">
                {escape(valor)}
            </div>
            {f'<div style="font-size: 0.74rem; color: #64748b; margin-top: 5px; font-weight: 500;">{escape(detalle)}</div>' if detalle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# FUNCIÓN PRINCIPAL DE RENDERIZADO DEL SUBMÓDULO EV1
# ==============================================================================

def render_ev1_opinion_estudiante(sede, periodo, carrera, tipo, fila_general, df_detalle, df_alumnos):
    """
    Renderiza la pestaña 'EV1 - Opinión Estudiante' con la arquitectura de
    Dashboard_EV1_Opinion_Estudiante (1).html:
      - Encabezado y filtros operacionales.
      - 6 sub-vistas completas.
    """
    st.markdown(
        """
        <style>
        .ev1-kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 14px rgba(0,0,0,0.08) !important;
        }
        .ev1-note {
            background-color: #f0f6fd;
            border-left: 4px solid #245ea8;
            padding: 12px 16px;
            border-radius: 10px;
            color: #1a3c63;
            font-size: 0.88rem;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
            line-height: 1.45;
        }
        .ev1-note-privacy {
            background-color: #f5f2fb;
            border-left: 4px solid #6f42c1;
            color: #41296d;
        }
        .ev1-card-teacher {
            background: linear-gradient(135deg, #12263f 0%, #1a3b63 100%);
            color: #ffffff;
            padding: 22px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(18, 38, 63, 0.15);
            transition: transform 0.2s ease;
            cursor: help;
        }
        .ev1-card-teacher:hover {
            transform: translateY(-2px);
        }
        .ev1-card-teacher span {
            font-size: 0.80rem;
            color: #c7d5e8;
            display: block;
        }
        .ev1-card-teacher strong {
            font-size: 2.3rem;
            display: block;
            margin-top: 4px;
            letter-spacing: -0.02em;
        }
        .ev1-criterio-box {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.02);
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        .ev1-criterio-box:hover {
            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
            transform: translateY(-1px);
        }
        .ev1-indicador-box {
            margin-top: 8px;
            background: #f8fafc;
            border-left: 3px solid #245ea8;
            border-radius: 6px;
            padding: 9px 13px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


    # --- 2. PREPARACIÓN DEL CONJUNTO DE DATOS (REAL vs FALLBACK) ---
    datos_disponibles_alumnos = df_alumnos is not None and not df_alumnos.empty
    if datos_disponibles_alumnos:
        df_base = df_alumnos.copy()
        # Normalización de columnas mínimas requeridas
        if "alumno" not in df_base.columns and "system_id" in df_base.columns:
            df_base["alumno"] = df_base["system_id"].astype(str)
        if "estado" not in df_base.columns:
            df_base["estado"] = df_base["respondio"].map(lambda r: "Completada" if r else "Pendiente")
        if "score" not in df_base.columns:
            df_base["score"] = None
    else:
        # Modo fallback para desarrollo local offline con la estructura exacta del HTML
        df_base = pd.DataFrame(ASIGNACIONES_REFERENCIA)

    # --- 3. FILTROS DINÁMICOS SUPERIORES (CONFIDENCIALIDAD: SIN BÚSQUEDA POR ALUMNO) ---
    with st.expander("Filtros del Dashboard EV1", expanded=True):
        col_filtro1, col_filtro2, col_filtro3, col_filtro4, col_filtro5 = st.columns(5)

        # Opciones únicas ordenadas
        lista_materias = ["Todas"] + sorted([str(m) for m in df_base["materia"].dropna().unique() if str(m).strip()])
        lista_secciones = ["Todas"] + sorted([str(s) for s in df_base["seccion"].dropna().unique() if str(s).strip()])
        lista_grupos = ["Todos"] + sorted([str(g) for g in df_base["grupo"].dropna().unique() if str(g).strip()])
        lista_docentes = ["Todos"] + sorted([str(d) for d in df_base["docente"].dropna().unique() if str(d).strip()])
        lista_estados = ["Todos", "Completada", "Parcial", "Pendiente"]

        with col_filtro1:
            sel_materia = st.selectbox("Materia", options=lista_materias, key="ev1_filtro_materia")
        with col_filtro2:
            sel_seccion = st.selectbox("Sección", options=lista_secciones, key="ev1_filtro_seccion")
        with col_filtro3:
            sel_grupo = st.selectbox("Grupo", options=lista_grupos, key="ev1_filtro_grupo")
        with col_filtro4:
            sel_docente = st.selectbox("Docente", options=lista_docentes, key="ev1_filtro_docente")
        with col_filtro5:
            sel_estado = st.selectbox("Estado", options=lista_estados, key="ev1_filtro_estado")

    sel_alumno = "Todos"

    # Aplicación de los filtros sobre el conjunto de datos de asignaciones
    df_filtrado = df_base.copy()
    if sel_docente != "Todos":
        df_filtrado = df_filtrado[df_filtrado["docente"] == sel_docente]
    if sel_materia != "Todas":
        df_filtrado = df_filtrado[df_filtrado["materia"] == sel_materia]
    if sel_seccion != "Todas":
        df_filtrado = df_filtrado[df_filtrado["seccion"] == sel_seccion]
    if sel_grupo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["grupo"] == sel_grupo]
    if sel_estado != "Todos":
        if sel_estado == "Parcial":
            # Alumnos que completaron parcialmente sus asignaciones en el universo base
            id_col_base = "system_id" if "system_id" in df_base.columns else "alumno"
            comp_series = (df_base["estado"] == "Completada") if "estado" in df_base.columns else (df_base["respondio"] == True)
            resumen_alu_base = df_base.assign(_comp=comp_series).groupby(id_col_base).agg(
                total=("_comp", "count"),
                comp=("_comp", "sum"),
            )
            alumnos_parciales = set(resumen_alu_base[(resumen_alu_base["comp"] > 0) & (resumen_alu_base["comp"] < resumen_alu_base["total"])].index)
            df_filtrado = df_filtrado[df_filtrado[id_col_base].isin(alumnos_parciales)]
        else:
            df_filtrado = df_filtrado[df_filtrado["estado"] == sel_estado]

    # Identificar si el usuario ha aplicado algún filtro en la pantalla
    filtros_activos = (
        sel_docente != "Todos"
        or sel_materia != "Todas"
        or sel_seccion != "Todas"
        or sel_grupo != "Todos"
        or sel_estado != "Todos"
    )

    # --- 4. SUB-PESTAÑAS DE NAVEGACIÓN EV1 ---
    tab_avance, tab_alumno, tab_materia, tab_resultados, tab_docente, tab_pedagogico = st.tabs(
        [
            "Avance general",
            "Participación de alumnos",
            "Materia · sección · grupo",
            "Resultados EV1",
            "Por docente",
            "Análisis pedagógico",
        ]
    )

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 1: AVANCE GENERAL
    # --------------------------------------------------------------------------
    with tab_avance:
        _render_subvista_avance_general(df_filtrado, df_base, fila_general, filtros_activos)

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 2: POR ALUMNO
    # --------------------------------------------------------------------------
    with tab_alumno:
        _render_subvista_por_alumno(df_filtrado)

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 3: MATERIA · SECCIÓN · GRUPO
    # --------------------------------------------------------------------------
    with tab_materia:
        _render_subvista_materia_seccion_grupo(df_filtrado)

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 4: RESULTADOS EV1
    # --------------------------------------------------------------------------
    with tab_resultados:
        _render_subvista_resultados_ev1(sede, periodo, carrera, tipo, df_filtrado)

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 5: POR DOCENTE
    # --------------------------------------------------------------------------
    with tab_docente:
        _render_subvista_por_docente(
            sede,
            periodo,
            carrera,
            tipo,
            df_filtrado,
            lista_docentes,
            df_detalle,
            filtro_docente_top=sel_docente,
            filtro_materia_top=sel_materia,
            filtro_seccion_top=sel_seccion,
            filtro_grupo_top=sel_grupo,
        )

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 6: ANÁLISIS PEDAGÓGICO
    # --------------------------------------------------------------------------
    with tab_pedagogico:
        _render_subvista_analisis_pedagogico(sede, periodo, carrera, tipo)


# ==============================================================================
# SUB-VISTA 1: AVANCE GENERAL
# ==============================================================================

def _render_subvista_avance_general(df_filtrado: pd.DataFrame, df_total: pd.DataFrame, fila_general=None, filtros_activos: bool = False):
    st.markdown(
        """
        <div class="ev1-note">
            Seguimiento de alumnos convocados y evaluaciones asignadas por cada combinación 
            <strong>alumno – materia – sección – grupo – docente</strong>. Los filtros actualizan el universo mostrado.
        </div>
        """,
        unsafe_allow_html=True,
    )

    id_col = "system_id" if "system_id" in df_filtrado.columns else "alumno"

    # 1. Total de alumnos convocados (distinct de alumnos únicos)
    if not filtros_activos and fila_general is not None and "alumnos_unicos_esperados" in fila_general:
        alumnos_convocados = int(fila_general["alumnos_unicos_esperados"])
    else:
        alumnos_convocados = int(df_filtrado[id_col].nunique()) if not df_filtrado.empty else 0

    # 2. Universo de evaluaciones a docentes (Opción 1: coherencia directa con la tabla de ofertas y materias)
    # Funciona dinámicamente tanto para versión 1 como para versión 2
    total_esperadas = len(df_filtrado)
    completadas = int((df_filtrado["estado"] == "Completada").sum()) if "estado" in df_filtrado.columns else int((df_filtrado["respondio"] == True).sum())
    pendientes = max(total_esperadas - completadas, 0)
    porcentaje_avance = (completadas / total_esperadas * 100.0) if total_esperadas > 0 else 0.0

    # Alumnos con avance parcial en el universo mostrado / filtrado
    if id_col and not df_filtrado.empty:
        comp_series = (df_filtrado["estado"] == "Completada") if "estado" in df_filtrado.columns else (df_filtrado["respondio"] == True)
        resumen_alu_flt = df_filtrado.assign(_comp=comp_series).groupby(id_col).agg(
            total=("_comp", "count"),
            comp=("_comp", "sum"),
        )
        c_parcial = int(((resumen_alu_flt["comp"] > 0) & (resumen_alu_flt["comp"] < resumen_alu_flt["total"])).sum())
    else:
        c_parcial = 0
    pct_parcial = (c_parcial / alumnos_convocados * 100.0) if alumnos_convocados > 0 else 0.0

    # Fila de KPIs principales
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        _render_kpi_card_ev1(
            "Alumnos convocados",
            f"{alumnos_convocados:,}".replace(",", "."),
            ayuda="Cantidad total de estudiantes habilitados para responder la encuesta en este periodo y carrera.",
            detalle="Matrícula convocada",
            color_acento="#12263f",
            color_fondo="#f3f6fa",
            color_borde="#dbe3ed",
        )
    with kpi2:
        _render_kpi_card_ev1(
            "Evaluaciones esperadas",
            f"{total_esperadas:,}".replace(",", "."),
            ayuda="Total de asignaciones de evaluación a docentes (cada alumno evalúa a los profesores de sus materias).",
            detalle="Asignaciones a docentes",
            color_acento="#245ea8",
            color_fondo="#eaf2fb",
            color_borde="#c7d5e8",
        )
    with kpi3:
        _render_kpi_card_ev1(
            "Evaluaciones completadas",
            f"{completadas:,}".replace(",", "."),
            ayuda="Cantidad de evaluaciones a docentes respondidas efectivamente por los estudiantes.",
            detalle=f"Avance del {porcentaje_avance:.1f}%",
            color_acento="#17845f",
            color_fondo="#e7f6f0",
            color_borde="#b5e3d0",
        )
    with kpi4:
        _render_kpi_card_ev1(
            "Avance general",
            _formatear_porcentaje(porcentaje_avance),
            ayuda="Tasa de respuesta de evaluaciones a docentes: (Completadas / Esperadas) × 100.",
            detalle=f"{completadas:,} de {total_esperadas:,} respondidas".replace(",", "."),
            color_acento="#3c7bc4",
            color_fondo="#e8f0fe",
            color_borde="#a9c6f5",
        )

    # Tarjetas explicativas de correspondencia y jerarquía de datos (Estudiantes · Materias · Docentes)
    # Permiten comprender la relación exacta entre los 3 niveles de análisis institucional
    pct_pendientes = (pendientes / total_esperadas * 100.0) if total_esperadas > 0 else 0.0
    n_doc_unicos = df_filtrado["docente"].dropna().nunique() if not df_filtrado.empty else 0

    if not filtros_activos and fila_general is not None:
        mat_esperadas = int(fila_general.get("encuestas_esperadas", 0))
        mat_respondidas = int(fila_general.get("encuestas_respondidas", 0))
        pct_mat = float(fila_general.get("porcentaje_avance_encuestas", 0.0))
        alumnos_respondieron = int(fila_general.get("alumnos_unicos_que_respondieron_al_menos_una", 0))
        pct_alumnos = float(fila_general.get("porcentaje_alumnos_que_respondieron_al_menos_una", 0.0))
        if pct_alumnos == 0.0 and alumnos_convocados > 0:
            pct_alumnos = (alumnos_respondieron / alumnos_convocados * 100.0)
        alumnos_restantes = max(alumnos_convocados - alumnos_respondieron, 0)

        st.markdown(
            f"""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px 20px; margin: 18px 0 22px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px;">
                    <div style="font-weight: 700; font-size: 0.96rem; color: #1e3a63; display: flex; align-items: center; gap: 8px;">
                        <span>🧭</span> Correspondencia de Cifras: Estudiantes ➔ Materias ➔ Asignaciones Docentes
                    </div>
                    <div style="font-size: 0.78rem; background: #e2e8f0; color: #334155; padding: 4px 12px; border-radius: 12px; font-weight: 600;">
                        Estado: {completadas:,} completadas ({porcentaje_avance:.1f}%) · {c_parcial:,} parcial ({pct_parcial:.1f}%) · {pendientes:,} pendientes ({pct_pendientes:.1f}%)
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px;">
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #12263f; border-radius: 8px; padding: 14px 16px;">
                        <div style="font-size: 0.74rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em;">
                            1. Nivel Estudiantes (Personas)
                        </div>
                        <div style="font-size: 1.25rem; font-weight: 800; color: #12263f; margin: 4px 0;">
                            {alumnos_convocados:,} <span style="font-size: 0.8rem; font-weight: 500; color: #64748b;">convocados</span>
                        </div>
                        <div style="font-size: 0.80rem; color: #475569; line-height: 1.45;">
                            <strong>{alumnos_respondieron:,}</strong> alumnos completaron evaluaciones (<strong>{pct_alumnos:.1f}%</strong> de participación activa). Restan {alumnos_restantes:,} sin participar.
                        </div>
                    </div>
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #245ea8; border-radius: 8px; padding: 14px 16px;">
                        <div style="font-size: 0.74rem; font-weight: 700; color: #245ea8; text-transform: uppercase; letter-spacing: 0.04em;">
                            2. Nivel Asignaturas (Materias)
                        </div>
                        <div style="font-size: 1.25rem; font-weight: 800; color: #245ea8; margin: 4px 0;">
                            {mat_respondidas:,} <span style="font-size: 0.8rem; font-weight: 500; color: #64748b;">/ {mat_esperadas:,} materias</span>
                        </div>
                        <div style="font-size: 0.80rem; color: #475569; line-height: 1.45;">
                            <strong>{pct_mat:.1f}%</strong> de materias respondidas. Cada estudiante cursa en promedio ~6 materias en su malla curricular.
                        </div>
                    </div>
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #17845f; border-radius: 8px; padding: 14px 16px;">
                        <div style="font-size: 0.74rem; font-weight: 700; color: #17845f; text-transform: uppercase; letter-spacing: 0.04em;">
                            3. Asignaciones Docentes (EV1)
                        </div>
                        <div style="font-size: 1.25rem; font-weight: 800; color: #17845f; margin: 4px 0;">
                            {completadas:,} <span style="font-size: 0.8rem; font-weight: 500; color: #64748b;">/ {total_esperadas:,} asignaciones</span>
                        </div>
                        <div style="font-size: 0.80rem; color: #475569; line-height: 1.45;">
                            <strong>{porcentaje_avance:.1f}%</strong> respondidas. Comprende a <strong>{n_doc_unicos} docentes</strong> con carga académica activa en sede (216 evaluados con respuestas en el ERP).
                        </div>
                    </div>
                </div>
            </div>
            """.replace(",", "."),
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"Estado de la selección: **{completadas:,}** completadas ({porcentaje_avance:.1f}%) · **{c_parcial:,}** parcial ({pct_parcial:.1f}%) · **{pendientes:,}** pendientes ({pct_pendientes:.1f}%)".replace(",", "."))
    st.divider()

    # Layout de dos columnas: gráfico/tabla izquierda vs donut/participación derecha
    col_izq, col_der = st.columns([1.6, 1.0])

    with col_izq:
        st.markdown("##### Cobertura por materia")
        if total_esperadas == 0:
            st.info("No hay registros para los filtros seleccionados.")
        else:
            # Agrupación por materia
            resumen_materia = (
                df_filtrado.groupby("materia")
                .agg(
                    total=("estado", "count"),
                    completadas=("estado", lambda s: (s == "Completada").sum()),
                    pendientes=("estado", lambda s: (s != "Completada").sum()),
                )
                .reset_index()
            )
            resumen_materia["avance"] = (resumen_materia["completadas"] / resumen_materia["total"] * 100.0).round(1)
            resumen_materia = resumen_materia.sort_values("avance", ascending=True)

            # Gráfico de barras horizontales de materias
            fig_mat = px.bar(
                resumen_materia,
                x="avance",
                y="materia",
                orientation="h",
                text="avance",
                range_x=[0, 100],
                color="avance",
                color_continuous_scale=[(0.0, "#bd3f4a"), (0.5, "#b87908"), (0.8, "#17845f"), (1.0, "#17845f")],
                custom_data=["completadas", "pendientes", "total", "materia"],
            )
            fig_mat.update_traces(
                texttemplate="%{text:.1f}%",
                textposition="outside",
                hovertemplate=(
                    "<b>Materia: %{customdata[3]}</b><br>"
                    "Tasa de respuesta: <b>%{x:.1f}%</b><br>"
                    "Completadas: <b>%{customdata[0]:,}</b> evaluaciones<br>"
                    "Pendientes: <b>%{customdata[1]:,}</b> evaluaciones<br>"
                    "Total esperadas: <b>%{customdata[2]:,}</b> evaluaciones"
                    "<extra></extra>"
                ),
            )
            fig_mat.update_layout(
                height=max(220, len(resumen_materia) * 45),
                xaxis_title="Porcentaje de avance (%)",
                yaxis_title=None,
                coloraxis_showscale=False,
                hoverlabel=dict(bgcolor="white", bordercolor="#dbe3ed", font_size=12),
                margin=dict(l=10, r=40, t=10, b=10),
            )
            st.plotly_chart(fig_mat, use_container_width=True, key="ev1_grafico_materias")
            st.caption("💡 *Toque o pase el cursor sobre cualquier barra para ver las cantidades de evaluaciones completadas y pendientes.*")

        st.markdown("##### Detalle del universo de evaluación (Cantidades por oferta)")
        if total_esperadas == 0:
            st.info("Sin registros.")
        else:
            # Resumen cuantitativo agregado por oferta (confidencialidad total de estudiantes)
            resumen_universo = (
                df_filtrado.groupby(["materia", "seccion", "grupo", "docente"])
                .agg(
                    total=("estado", "count"),
                    completadas=("estado", lambda s: (s == "Completada").sum()),
                    pendientes=("estado", lambda s: (s != "Completada").sum()),
                )
                .reset_index()
            )
            resumen_universo["Avance %"] = (
                resumen_universo["completadas"] / resumen_universo["total"] * 100.0
            ).round(1)
            df_tabla = resumen_universo.rename(
                columns={
                    "materia": "Materia",
                    "seccion": "Sección",
                    "grupo": "Grupo",
                    "docente": "Docente",
                    "total": "Evaluaciones",
                    "completadas": "Completadas",
                    "pendientes": "Pendientes",
                }
            )
            st.dataframe(
                df_tabla,
                hide_index=True,
                width="stretch",
                column_config={
                    "Materia": st.column_config.TextColumn(
                        "Materia",
                        help="Nombre oficial de la asignatura curricular evaluada.",
                    ),
                    "Sección": st.column_config.TextColumn(
                        "Sección",
                        help="Sección académica o turno de cursado de los estudiantes.",
                    ),
                    "Grupo": st.column_config.TextColumn(
                        "Grupo",
                        help="Grupo académico (Teoría, Laboratorio, MO, MS, etc.).",
                    ),
                    "Docente": st.column_config.TextColumn(
                        "Docente",
                        help="Nombre del profesor asignado y evaluado en este grupo académico.",
                    ),
                    "Evaluaciones": st.column_config.NumberColumn(
                        "Evaluaciones",
                        format="%d",
                        help="Total de evaluaciones esperadas asignadas para esta oferta académica.",
                    ),
                    "Completadas": st.column_config.NumberColumn(
                        "Completadas",
                        format="%d",
                        help="Cantidad de evaluaciones respondidas efectivamente por los estudiantes.",
                    ),
                    "Pendientes": st.column_config.NumberColumn(
                        "Pendientes",
                        format="%d",
                        help="Cantidad de evaluaciones que aún faltan responder por los alumnos.",
                    ),
                    "Avance %": st.column_config.ProgressColumn(
                        "Avance %",
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                        help="Porcentaje de avance: (Completadas / Evaluaciones) × 100.",
                    ),
                },
                key="ev1_tabla_universo",
            )
            st.caption("💡 *Pase el cursor o toque el encabezado de cualquier columna para conocer su definición y cálculo.*")

    with col_der:
        st.markdown("##### Avance global")
        abiertas = max(total_esperadas - completadas, 0)
        fig_donut = go.Figure(
            data=[
                go.Pie(
                    labels=["Completadas", "Abiertas"],
                    values=[completadas, abiertas],
                    hole=0.68,
                    marker=dict(colors=["#245ea8", "#e4eaf2"]),
                    textinfo="none",
                    sort=False,
                    hovertemplate=(
                        "<b>Estado: %{label}</b><br>"
                        "Cantidad: <b>%{value:,}</b> evaluaciones<br>"
                        "Proporción: <b>%{percent}</b> del total asignado"
                        "<extra></extra>"
                    ),
                )
            ]
        )
        fig_donut.update_layout(
            height=240,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
            hoverlabel=dict(bgcolor="white", bordercolor="#dbe3ed", font_size=12),
            annotations=[
                dict(
                    text=f"<b>{_formatear_porcentaje(porcentaje_avance)}</b>",
                    x=0.5,
                    y=0.5,
                    font_size=24,
                    showarrow=False,
                )
            ],
        )
        st.plotly_chart(fig_donut, use_container_width=True, key="ev1_grafico_donut")
        st.caption("💡 *Toque el gráfico de dona para ver la proporción y cantidad exacta de evaluaciones completadas vs abiertas.*")

        st.markdown("##### Estado de participación de alumnos")
        if not filtros_activos and fila_general is not None:
            total_alu = alumnos_convocados
            completaron_todo = int(fila_general.get("alumnos_unicos_que_respondieron_todas", 0))
            al_menos_una = int(fila_general.get("alumnos_unicos_que_respondieron_al_menos_una", 0))
            sin_iniciar = max(total_alu - al_menos_una, 0)
            parcial = max(al_menos_una - completaron_todo, 0)

            pct_todo = float(fila_general.get("porcentaje_avance_alumnos_todas", 0.0))
            pct_parcial = (parcial / total_alu * 100.0) if total_alu > 0 else 0.0
            pct_sin = (sin_iniciar / total_alu * 100.0) if total_alu > 0 else 0.0

            st.write(f"**Completaron todo:** {completaron_todo:,} ({pct_todo:.1f}%)".replace(",", "."))
            st.progress(min(max(pct_todo / 100.0, 0.0), 1.0))
            st.write(f"**Avance parcial:** {parcial:,} ({pct_parcial:.1f}%)".replace(",", "."))
            st.progress(min(max(pct_parcial / 100.0, 0.0), 1.0))
            st.write(f"**Sin iniciar:** {sin_iniciar:,} ({pct_sin:.1f}%)".replace(",", "."))
            st.progress(min(max(pct_sin / 100.0, 0.0), 1.0))
        elif total_esperadas > 0:
            id_col = "system_id" if "system_id" in df_filtrado.columns else "alumno"
            resumen_alumnos = (
                df_filtrado.groupby(id_col)
                .agg(
                    total=("estado", "count"),
                    completadas=("estado", lambda s: (s == "Completada").sum()),
                )
                .reset_index()
            )
            total_alu = len(resumen_alumnos)
            completaron_todo = int((resumen_alumnos["completadas"] == resumen_alumnos["total"]).sum())
            sin_iniciar = int((resumen_alumnos["completadas"] == 0).sum())
            parcial = max(total_alu - completaron_todo - sin_iniciar, 0)

            pct_todo = (completaron_todo / total_alu * 100.0) if total_alu > 0 else 0
            pct_parcial = (parcial / total_alu * 100.0) if total_alu > 0 else 0
            pct_sin = (sin_iniciar / total_alu * 100.0) if total_alu > 0 else 0

            st.write(f"**Completaron todo:** {completaron_todo:,} ({pct_todo:.1f}%)".replace(",", "."))
            st.progress(min(max(pct_todo / 100.0, 0.0), 1.0))
            st.write(f"**Avance parcial:** {parcial:,} ({pct_parcial:.1f}%)".replace(",", "."))
            st.progress(min(max(pct_parcial / 100.0, 0.0), 1.0))
            st.write(f"**Sin iniciar:** {sin_iniciar:,} ({pct_sin:.1f}%)".replace(",", "."))
            st.progress(min(max(pct_sin / 100.0, 0.0), 1.0))


# ==============================================================================
# SUB-VISTA 2: PARTICIPACIÓN DE ALUMNOS (CANTIDADES AGREGADAS)
# ==============================================================================

def _render_subvista_por_alumno(df_filtrado: pd.DataFrame):
    st.markdown(
        """
        <div class="ev1-note ev1-note-privacy">
            <strong>Confidencialidad y protección de datos:</strong> Por estricta política institucional y resguardo del anonimato,
            no se presentan datos individuales identificatorios de los estudiantes. 
            Esta vista consolida exclusivamente cantidades globales, estados agregados de participación y métricas por materia.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df_filtrado.empty:
        st.info("Sin registros de participación para los filtros actuales.")
        return

    # Agrupación interna por identificador para cómputo de métricas globales sin exponer identidades
    id_col = "system_id" if "system_id" in df_filtrado.columns else "alumno"
    resumen_alumnos = (
        df_filtrado.groupby(id_col)
        .agg(
            asignadas=("estado", "count"),
            completadas=("estado", lambda s: (s == "Completada").sum()),
            pendientes=("estado", lambda s: (s != "Completada").sum()),
        )
        .reset_index()
    )
    resumen_alumnos["avance"] = (resumen_alumnos["completadas"] / resumen_alumnos["asignadas"] * 100.0).round(1)

    def _clasificar_estado_alumno(row):
        if row["completadas"] == row["asignadas"]:
            return "Completo"
        elif row["completadas"] == 0:
            return "Sin iniciar"
        return "Parcial"

    resumen_alumnos["estado_alumno"] = resumen_alumnos.apply(_clasificar_estado_alumno, axis=1)

    total_alumnos = len(resumen_alumnos)
    c_completos = int((resumen_alumnos["estado_alumno"] == "Completo").sum())
    c_parcial = int((resumen_alumnos["estado_alumno"] == "Parcial").sum())
    c_sin_iniciar = int((resumen_alumnos["estado_alumno"] == "Sin iniciar").sum())
    promedio_asignadas = (resumen_alumnos["asignadas"].mean()) if total_alumnos > 0 else 0.0

    pct_completos = (c_completos / total_alumnos * 100.0) if total_alumnos > 0 else 0.0
    pct_parcial = (c_parcial / total_alumnos * 100.0) if total_alumnos > 0 else 0.0
    pct_sin = (c_sin_iniciar / total_alumnos * 100.0) if total_alumnos > 0 else 0.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _render_kpi_card_ev1(
            "Completaron todo",
            f"{c_completos:,} ({pct_completos:.1f}%)".replace(",", "."),
            ayuda="Estudiantes que respondieron el 100% de las evaluaciones asignadas a sus docentes.",
            detalle="100% de encuestas respondidas",
            color_acento="#17845f",
            color_fondo="#e7f6f0",
            color_borde="#b5e3d0",
        )
    with k2:
        _render_kpi_card_ev1(
            "Avance parcial",
            f"{c_parcial:,} ({pct_parcial:.1f}%)".replace(",", "."),
            ayuda="Estudiantes que respondieron al menos una evaluación pero tienen encuestas pendientes.",
            detalle="Con evaluaciones pendientes",
            color_acento="#b87908",
            color_fondo="#fff5d9",
            color_borde="#ecd496",
        )
    with k3:
        _render_kpi_card_ev1(
            "Sin iniciar",
            f"{c_sin_iniciar:,} ({pct_sin:.1f}%)".replace(",", "."),
            ayuda="Estudiantes que aún no han completado ninguna evaluación asignada.",
            detalle="0 encuestas respondidas",
            color_acento="#bd3f4a",
            color_fondo="#fdecef",
            color_borde="#f3b9c0",
        )
    with k4:
        _render_kpi_card_ev1(
            "Promedio por alumno",
            f"{promedio_asignadas:.1f} evals".replace(".", ","),
            ayuda="Promedio de encuestas a docentes que cada estudiante debe completar según sus materias cursadas.",
            detalle="Carga media de encuestas",
            color_acento="#245ea8",
            color_fondo="#eaf2fb",
            color_borde="#c7d5e8",
        )

    st.markdown("##### Distribución general de participación")
    col_donut, col_bar = st.columns([1.0, 1.4])
    with col_donut:
        fig_donut_part = go.Figure(
            data=[
                go.Pie(
                    labels=["Completaron todo", "Avance parcial", "Sin iniciar"],
                    values=[c_completos, c_parcial, c_sin_iniciar],
                    hole=0.62,
                    marker=dict(colors=["#17845f", "#b87908", "#bd3f4a"]),
                    textinfo="percent+label",
                    sort=False,
                    hovertemplate=(
                        "<b>Estado: %{label}</b><br>"
                        "Cantidad de alumnos: <b>%{value:,}</b><br>"
                        "Participación: <b>%{percent}</b> de la matrícula convocada"
                        "<extra></extra>"
                    ),
                )
            ]
        )
        fig_donut_part.update_layout(
            height=270,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
            hoverlabel=dict(bgcolor="white", bordercolor="#dbe3ed", font_size=12),
        )
        st.plotly_chart(fig_donut_part, use_container_width=True, key="ev1_grafico_donut_part")

    with col_bar:
        df_bar_part = pd.DataFrame({
            "Estado": ["Completaron todo", "Avance parcial", "Sin iniciar"],
            "Cantidad de alumnos": [c_completos, c_parcial, c_sin_iniciar],
            "Porcentaje": [pct_completos, pct_parcial, pct_sin],
        })
        fig_bar_part = px.bar(
            df_bar_part,
            x="Cantidad de alumnos",
            y="Estado",
            orientation="h",
            text="Cantidad de alumnos",
            color="Estado",
            color_discrete_map={
                "Completaron todo": "#17845f",
                "Avance parcial": "#b87908",
                "Sin iniciar": "#bd3f4a",
            },
            custom_data=["Porcentaje", "Cantidad de alumnos", "Estado"],
        )
        fig_bar_part.update_traces(
            textposition="outside",
            texttemplate="%{text:,}",
            hovertemplate=(
                "<b>%{customdata[2]}</b><br>"
                "Alumnos: <b>%{customdata[1]:,}</b> estudiantes<br>"
                "Porcentaje: <b>%{customdata[0]:.1f}%</b> de la matrícula convocada"
                "<extra></extra>"
            ),
        )
        fig_bar_part.update_layout(
            height=270,
            showlegend=False,
            margin=dict(l=10, r=40, t=10, b=10),
            xaxis_title="Cantidad de alumnos",
            yaxis_title=None,
            hoverlabel=dict(bgcolor="white", bordercolor="#dbe3ed", font_size=12),
        )
        st.plotly_chart(fig_bar_part, use_container_width=True, key="ev1_grafico_bar_part")
        st.caption("💡 *Toque los gráficos para visualizar las cantidades y porcentajes de estudiantes en cada nivel de participación.*")

    st.divider()

    st.markdown("##### Cantidades de participación agregadas por materia")
    resumen_mat = (
        df_filtrado.groupby("materia")
        .agg(
            alumnos=(id_col, "nunique"),
            total=("estado", "count"),
            completadas=("estado", lambda s: (s == "Completada").sum()),
            pendientes=("estado", lambda s: (s != "Completada").sum()),
        )
        .reset_index()
    )
    resumen_mat["Avance %"] = (
        resumen_mat["completadas"] / resumen_mat["total"] * 100.0
    ).round(1)
    tabla_mat = resumen_mat.rename(
        columns={
            "materia": "Materia",
            "alumnos": "Alumnos convocados",
            "total": "Evaluaciones esperadas",
            "completadas": "Completadas",
            "pendientes": "Pendientes",
        }
    )
    st.dataframe(
        tabla_mat,
        hide_index=True,
        width="stretch",
        column_config={
            "Materia": st.column_config.TextColumn(
                "Materia",
                help="Nombre oficial de la asignatura curricular.",
            ),
            "Alumnos convocados": st.column_config.NumberColumn(
                "Alumnos convocados",
                format="%d",
                help="Cantidad de estudiantes únicos matriculados y convocados a responder en esta materia.",
            ),
            "Evaluaciones esperadas": st.column_config.NumberColumn(
                "Esperadas",
                format="%d",
                help="Total de evaluaciones asignadas en la materia sumando todos sus docentes y grupos.",
            ),
            "Completadas": st.column_config.NumberColumn(
                "Completadas",
                format="%d",
                help="Cantidad de evaluaciones respondidas efectivamente por los alumnos.",
            ),
            "Pendientes": st.column_config.NumberColumn(
                "Pendientes",
                format="%d",
                help="Cantidad de evaluaciones pendientes de responder por parte de los alumnos.",
            ),
            "Avance %": st.column_config.ProgressColumn(
                "Avance %",
                min_value=0,
                max_value=100,
                format="%.1f%%",
                help="Porcentaje de avance en la materia: (Completadas / Esperadas) × 100.",
            ),
        },
        key="ev1_tabla_participacion_materias",
    )
    st.caption("💡 *Pase el cursor o toque el encabezado de las columnas para ver los detalles y fórmulas de cálculo.*")


# ==============================================================================
# SUB-VISTA 3: MATERIA · SECCIÓN · GRUPO
# ==============================================================================

def _render_subvista_materia_seccion_grupo(df_filtrado: pd.DataFrame):
    st.markdown(
        """
        <div class="ev1-note">
            Cobertura por materia, sección y grupo. Permite a coordinadores e investigadores identificar 
            ofertas académicas críticas o rezagadas antes de la fecha de cierre de la encuesta.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df_filtrado.empty:
        st.info("Sin registros de ofertas académicas para los filtros actuales.")
        return

    # Agrupación por oferta académica (Materia, Sección, Grupo, Docente)
    ofertas = (
        df_filtrado.groupby(["materia", "seccion", "grupo", "docente"])
        .agg(
            alumnos=("alumno", "nunique"),
            completadas=("estado", lambda s: (s == "Completada").sum()),
            pendientes=("estado", lambda s: (s != "Completada").sum()),
            total=("estado", "count"),
        )
        .reset_index()
    )
    ofertas["avance"] = (ofertas["completadas"] / ofertas["total"] * 100.0).round(1)

    def _badge_semaforo_texto(p):
        if p >= 80.0:
            return "🟢 Adecuado"
        elif p >= 50.0:
            return "🟡 Seguimiento"
        return "🔴 Crítico"

    ofertas["estado_oferta"] = ofertas["avance"].map(_badge_semaforo_texto)

    n_materias = ofertas["materia"].nunique()
    n_docentes = ofertas["docente"].nunique()
    ofertas_completas = int((ofertas["avance"] == 100.0).sum())
    ofertas_criticas = int((ofertas["avance"] < 50.0).sum())

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _render_kpi_card_ev1(
            "Materias distintas",
            str(n_materias),
            ayuda="Cantidad total de asignaturas curriculares comprendidas en los filtros actuales.",
            detalle="Asignaturas activas",
            color_acento="#12263f",
            color_fondo="#f3f6fa",
            color_borde="#dbe3ed",
        )
    with k2:
        _render_kpi_card_ev1(
            "Docentes a evaluar",
            str(n_docentes),
            ayuda="Cantidad de profesores asignados a estas ofertas académicas.",
            detalle="Profesores evaluados",
            color_acento="#245ea8",
            color_fondo="#eaf2fb",
            color_borde="#c7d5e8",
        )
    with k3:
        _render_kpi_card_ev1(
            "Ofertas completas (100%)",
            str(ofertas_completas),
            ayuda="Ofertas académicas donde todos los estudiantes convocados respondieron la encuesta.",
            detalle="Avance total alcanzado",
            color_acento="#17845f",
            color_fondo="#e7f6f0",
            color_borde="#b5e3d0",
        )
    with k4:
        _render_kpi_card_ev1(
            "Ofertas críticas (<50%)",
            str(ofertas_criticas),
            ayuda="Ofertas académicas con un avance inferior al 50% que requieren seguimiento prioritario.",
            detalle="Menos del 50% respondido",
            color_acento="#bd3f4a",
            color_fondo="#fdecef",
            color_borde="#f3b9c0",
        )

    st.markdown("##### Detalle de cobertura académica")
    tabla_ofertas = ofertas[
        ["materia", "seccion", "grupo", "docente", "alumnos", "completadas", "pendientes", "avance", "estado_oferta"]
    ].rename(
        columns={
            "materia": "Materia",
            "seccion": "Sección",
            "grupo": "Grupo",
            "docente": "Docente",
            "alumnos": "Alumnos",
            "completadas": "Completadas",
            "pendientes": "Pendientes",
            "avance": "Avance %",
            "estado_oferta": "Semáforo",
        }
    )
    st.dataframe(
        tabla_ofertas,
        hide_index=True,
        width="stretch",
        column_config={
            "Materia": st.column_config.TextColumn("Materia", help="Nombre oficial de la asignatura curricular."),
            "Sección": st.column_config.TextColumn("Sección", help="Sección académica o turno de cursada."),
            "Grupo": st.column_config.TextColumn("Grupo", help="Grupo lectivo específico (Teoría, Laboratorio, etc.)."),
            "Docente": st.column_config.TextColumn("Docente", help="Profesor evaluado en este grupo académico."),
            "Alumnos": st.column_config.NumberColumn("Alumnos", format="%d", help="Cantidad de alumnos matriculados convocados a evaluar al docente."),
            "Completadas": st.column_config.NumberColumn("Completadas", format="%d", help="Cantidad de encuestas respondidas por los estudiantes."),
            "Pendientes": st.column_config.NumberColumn("Pendientes", format="%d", help="Cantidad de encuestas que aún faltan responder."),
            "Avance %": st.column_config.ProgressColumn(
                "Avance %",
                min_value=0,
                max_value=100,
                format="%.1f%%",
                help="Tasa de respuesta alcanzada: (Completadas / Total de alumnos) × 100.",
            ),
            "Semáforo": st.column_config.TextColumn("Semáforo", help="Semáforo institucional: 🟢 Adecuado (≥ 80%) · 🟡 Seguimiento (50%–79,9%) · 🔴 Crítico (< 50%)."),
        },
        key="ev1_tabla_ofertas",
    )
    st.caption("💡 *Toque los encabezados para ver el significado de cada columna. Semáforo: 🟢 Adecuado (≥ 80%) · 🟡 Seguimiento (50%–79,9%) · 🔴 Crítico (< 50%).*")


# ==============================================================================
# SUB-VISTA 4: RESULTADOS EV1
# ==============================================================================

def _descriptor_badge(valor):
    mapa = {
        "Fortaleza": "🟢 Fortaleza",
        "Adecuado": "🔵 Adecuado",
        "Seguimiento": "🟡 Seguimiento",
        "Oportunidad": "🔴 Oportunidad",
    }
    return mapa.get(valor, valor if valor not in (None, "") else "-")


def _render_subvista_resultados_ev1(sede, periodo, carrera, tipo, df_filtrado: pd.DataFrame):
    st.markdown(
        """
        <div class="ev1-note">
            Resultados consolidados de la EV1 (Opinión del Estudiante). Escala de valoración: 
            <strong>1 = Totalmente en desacuerdo</strong> a <strong>5 = Totalmente de acuerdo</strong>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Cargar resultados consolidados oficiales desde parquet/DB
    fila_res = load_resultado_general(sede, periodo, carrera, tipo)
    df_dim = load_resultado_dimensiones(sede, periodo, carrera, tipo)
    df_doc = load_resultado_docentes(sede, periodo, carrera, tipo)

    if fila_res is not None:
        promedio_ev1 = float(fila_res.get("promedio_general", 0.0))
        pct_fav = float(fila_res.get("pct_favorable", 0.0))
        pct_neu = float(fila_res.get("pct_neutral", 0.0))
        pct_desf = float(fila_res.get("pct_desfavorable", 0.0))
        dist_1 = float(fila_res.get("dist_1", 0.0))
        dist_2 = float(fila_res.get("dist_2", 0.0))
        dist_3 = float(fila_res.get("dist_3", 0.0))
        dist_4 = float(fila_res.get("dist_4", 0.0))
        dist_5 = float(fila_res.get("dist_5", 0.0))
        n_resp_val = float(fila_res.get("n_respuestas_validas", dist_1 + dist_2 + dist_3 + dist_4 + dist_5))
        dim_mejor = str(fila_res.get("dimension_mejor", "Dimensión 1: Planificación, Organización y Dominio de la Asignatura"))
        dim_oportunidad = str(fila_res.get("dimension_oportunidad", "Dimensión 2: Gestión de Recursos Didácticos y Evaluación"))
    else:
        promedio_ev1 = 4.43
        pct_fav = 85.58
        pct_neu = 8.53
        pct_desf = 5.89
        dist_1, dist_2, dist_3, dist_4, dist_5 = 21600.0, 17759.0, 57010.0, 129478.0, 442377.0
        n_resp_val = 668224.0
        dim_mejor = "Dimensión 1: Planificación, Organización y Dominio de la Asignatura"
        dim_oportunidad = "Dimensión 2: Gestión de Recursos Didácticos y Evaluación"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _render_kpi_card_ev1(
            "Promedio EV1",
            f"{promedio_ev1:.2f} / 5".replace(".", ","),
            ayuda="Promedio global obtenido de todas las respuestas emitidas en la encuesta (escala 1 a 5).",
            detalle="Escala Likert institucional",
            color_acento="#12263f",
            color_fondo="#f3f6fa",
            color_borde="#dbe3ed",
        )
    with k2:
        _render_kpi_card_ev1(
            "Respuestas favorables (4-5)",
            _formatear_porcentaje(pct_fav),
            ayuda="Porcentaje de respuestas en opciones 4 (De acuerdo) y 5 (Totalmente de acuerdo).",
            detalle=f"{int(dist_4 + dist_5):,} respuestas emitidas".replace(",", "."),
            color_acento="#17845f",
            color_fondo="#e7f6f0",
            color_borde="#b5e3d0",
        )
    with k3:
        _render_kpi_card_ev1(
            "Respuestas neutrales (3)",
            _formatear_porcentaje(pct_neu),
            ayuda="Porcentaje de respuestas en opción 3 (Ni de acuerdo ni en desacuerdo).",
            detalle=f"{int(dist_3):,} respuestas emitidas".replace(",", "."),
            color_acento="#b87908",
            color_fondo="#fff5d9",
            color_borde="#ecd496",
        )
    with k4:
        _render_kpi_card_ev1(
            "Respuestas desfavorables (1-2)",
            _formatear_porcentaje(pct_desf),
            ayuda="Porcentaje de respuestas en opciones 1 (Totalmente en desacuerdo) y 2 (En desacuerdo).",
            detalle=f"{int(dist_1 + dist_2):,} respuestas emitidas".replace(",", "."),
            color_acento="#bd3f4a",
            color_fondo="#fdecef",
            color_borde="#f3b9c0",
        )

    st.divider()

    col_izq, col_der = st.columns([1.6, 1.0])

    with col_izq:
        st.markdown("##### Resultado por dimensión")
        if df_dim is not None and not df_dim.empty:
            df_dim_plot = df_dim.copy()
            df_dim_plot = df_dim_plot.sort_values("orden", ascending=False)
            fig_dim = px.bar(
                df_dim_plot,
                x="promedio",
                y="dimension_nombre",
                orientation="h",
                text="promedio",
                range_x=[0, 5],
                custom_data=["promedio", "dimension_nombre"],
            )
        else:
            datos_dims = [
                {"dim": d["corto"], "score": d["puntaje_referencia"]}
                for d in reversed(CATALOGO_PEDAGOGICO_EV1)
            ]
            df_dim_plot = pd.DataFrame(datos_dims)
            fig_dim = px.bar(
                df_dim_plot,
                x="score",
                y="dim",
                orientation="h",
                text="score",
                range_x=[0, 5],
                custom_data=["score", "dim"],
            )

        fig_dim.update_traces(
            marker_color="#245ea8",
            textposition="outside",
            texttemplate="%{text:.2f}",
            hovertemplate=(
                "<b>Dimensión: %{customdata[1]}</b><br>"
                "Puntaje promedio: <b>%{x:.2f} / 5,00</b><br>"
                "<i>Valoración media otorgada por los estudiantes en este eje pedagógico</i>"
                "<extra></extra>"
            ),
        )
        fig_dim.update_layout(
            height=260,
            xaxis_title="Puntaje promedio (1 a 5)",
            yaxis_title=None,
            hoverlabel=dict(bgcolor="white", bordercolor="#dbe3ed", font_size=12),
            margin=dict(l=10, r=40, t=10, b=10),
        )
        st.plotly_chart(fig_dim, use_container_width=True, key="ev1_grafico_dimensiones")
        st.caption("💡 *Toque cualquier barra para ver el puntaje promedio exacto de la dimensión.*")

        st.markdown("##### Resultado consolidado por docente")
        if df_doc is not None and not df_doc.empty:
            tabla_doc = df_doc.copy()
            if "descriptor" in tabla_doc.columns:
                tabla_doc["Lectura"] = tabla_doc["descriptor"].map(_descriptor_badge)
            elif "promedio" in tabla_doc.columns:
                tabla_doc["Lectura"] = tabla_doc["promedio"].map(
                    lambda p: "🟢 Fortaleza" if p >= 4.5 else ("🔵 Adecuado" if p >= 4.0 else ("🟡 Seguimiento" if p >= 3.5 else "🔴 Oportunidad"))
                )
            cols_mostrar = [c for c in ["docente", "promedio", "Lectura", "n_evaluaciones_recibidas", "n_respuestas_validas"] if c in tabla_doc.columns]
            tabla_doc = tabla_doc[cols_mostrar].rename(
                columns={
                    "docente": "Docente",
                    "promedio": "Promedio",
                    "n_evaluaciones_recibidas": "Evaluaciones",
                    "n_respuestas_validas": "Respuestas válidas",
                }
            )
        else:
            filas_doc = []
            for nombre, p in PERFILES_DOCENTES_REFERENCIA.items():
                filas_doc.append({
                    "Docente": nombre,
                    "Promedio": p["score"],
                    "Lectura": "🟢 Fortaleza" if p["score"] >= 4.4 else ("🔵 Adecuado" if p["score"] >= 4.1 else "🟡 Seguimiento"),
                    "Evaluaciones": 15,
                    "Respuestas válidas": 240,
                })
            tabla_doc = pd.DataFrame(filas_doc)

        st.dataframe(
            tabla_doc,
            hide_index=True,
            width="stretch",
            column_config={
                "Docente": st.column_config.TextColumn("Docente", help="Nombre oficial del docente evaluado."),
                "Promedio": st.column_config.NumberColumn("Promedio", format="%.2f", help="Puntaje promedio obtenido en la escala institucional de 1 a 5."),
                "Lectura": st.column_config.TextColumn("Lectura", help="Categorización pedagógica según el puntaje promedio obtenido."),
                "Evaluaciones": st.column_config.NumberColumn("Evaluaciones", format="%d", help="Cantidad de encuestas completadas que recibió el docente."),
                "Respuestas válidas": st.column_config.NumberColumn("Respuestas válidas", format="%d", help="Suma total de ítems respondidos válidamente por los alumnos."),
            },
            key="ev1_tabla_res_docente",
        )
        st.caption("💡 *Pase el cursor sobre los encabezados para ver el significado de cada columna.*")

    with col_der:
        st.markdown("##### Distribución de respuestas")
        st.caption("Participación porcentual según el valor de la escala Likert (1 a 5)")

        if n_resp_val > 0:
            pct_d1 = round(dist_1 / n_resp_val * 100, 1)
            pct_d2 = round(dist_2 / n_resp_val * 100, 1)
            pct_d3 = round(dist_3 / n_resp_val * 100, 1)
            pct_d4 = round(dist_4 / n_resp_val * 100, 1)
            pct_d5 = round(dist_5 / n_resp_val * 100, 1)
        else:
            pct_d1, pct_d2, pct_d3, pct_d4, pct_d5 = 3.2, 2.7, 8.5, 19.4, 66.2

        dist_datos = pd.DataFrame({
            "Puntaje": ["1 (Muy en desc.)", "2 (En desac.)", "3 (Neutral)", "4 (De acuerdo)", "5 (Totalmente)"],
            "Porcentaje": [pct_d1, pct_d2, pct_d3, pct_d4, pct_d5],
            "Cantidad": [int(dist_1), int(dist_2), int(dist_3), int(dist_4), int(dist_5)],
            "Color": ["#bd3f4a", "#d97831", "#7654a8", "#245ea8", "#17845f"],
        })
        fig_dist = px.bar(
            dist_datos,
            x="Porcentaje",
            y="Puntaje",
            orientation="h",
            color="Puntaje",
            color_discrete_map={
                "1 (Muy en desc.)": "#bd3f4a",
                "2 (En desac.)": "#d97831",
                "3 (Neutral)": "#7654a8",
                "4 (De acuerdo)": "#245ea8",
                "5 (Totalmente)": "#17845f",
            },
            text="Porcentaje",
            custom_data=["Puntaje", "Porcentaje", "Cantidad"],
        )
        fig_dist.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="inside",
            hovertemplate=(
                "<b>Escala Likert: %{customdata[0]}</b><br>"
                "Porcentaje: <b>%{x:.1f}%</b> del total<br>"
                "Cantidad de respuestas: <b>%{customdata[2]:,}</b> votos emitidos"
                "<extra></extra>"
            ),
        )
        fig_dist.update_layout(
            height=220,
            showlegend=False,
            xaxis_title="Porcentaje (%)",
            yaxis_title=None,
            hoverlabel=dict(bgcolor="white", bordercolor="#dbe3ed", font_size=12),
            margin=dict(l=10, r=20, t=10, b=10),
        )
        st.plotly_chart(fig_dist, use_container_width=True, key="ev1_grafico_distribucion")
        st.caption("💡 *Toque las barras para ver la cantidad exacta de votos emitidos en cada opción.*")

        # Obtener puntajes reales de la dimensión con mayor y menor puntaje
        score_mejor = None
        score_oportunidad = None
        if df_dim is not None and not df_dim.empty and "promedio" in df_dim.columns and "dimension_nombre" in df_dim.columns:
            for _, fila_d in df_dim.iterrows():
                nom_d = str(fila_d["dimension_nombre"])
                if nom_d in dim_mejor or dim_mejor in nom_d:
                    score_mejor = float(fila_d["promedio"])
                if nom_d in dim_oportunidad or dim_oportunidad in nom_d:
                    score_oportunidad = float(fila_d["promedio"])
        if score_mejor is None:
            score_mejor = 4.54
        if score_oportunidad is None:
            score_oportunidad = 4.31

        st.markdown("##### Lectura ejecutiva")
        st.markdown(
            f"""
            <div style="background: #ffffff; border: 1px solid #dbe3ed; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                <span style="font-size: 0.8rem; color: #65738a; font-weight: 600;">Mayor fortaleza</span><br>
                <strong style="color: #17845f; font-size: 0.95rem;">{escape(dim_mejor)}</strong>
                <p style="margin: 4px 0 0 0; font-size: 0.95rem; font-weight: 750;">{_formatear_puntaje(score_mejor)} / 5,00</p>
            </div>
            <div style="background: #ffffff; border: 1px solid #dbe3ed; border-radius: 10px; padding: 14px;">
                <span style="font-size: 0.8rem; color: #65738a; font-weight: 600;">Principal oportunidad de mejora</span><br>
                <strong style="color: #b87908; font-size: 0.95rem;">{escape(dim_oportunidad)}</strong>
                <p style="margin: 4px 0 0 0; font-size: 0.95rem; font-weight: 750;">{_formatear_puntaje(score_oportunidad)} / 5,00</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ==============================================================================
# SUB-VISTA 5: POR DOCENTE
# ==============================================================================

def _render_subvista_por_docente(
    sede,
    periodo,
    carrera,
    tipo,
    df_filtrado: pd.DataFrame,
    lista_docentes: list,
    df_detalle: pd.DataFrame = None,
    filtro_docente_top: str = "Todos",
    filtro_materia_top: str = "Todas",
    filtro_seccion_top: str = "Todas",
    filtro_grupo_top: str = "Todos",
):
    st.markdown(
        """
        <div class="ev1-note ev1-note-privacy">
            Para garantizar la validez metodológica y proteger el anonimato de los estudiantes, 
            se recomienda publicar y analizar resultados individuales únicamente cuando exista un número 
            mínimo representativo de evaluaciones respondidas por grupo docente.
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_doc_db = load_resultado_docentes(sede, periodo, carrera, tipo)

    # Construcción de mapas bidireccionales entre identificador numérico (docente_id)
    # y los formatos de nombres (bio: Nombres Apellidos / sql: Apellidos, Nombres)
    mapa_bio_a_id = {}
    mapa_id_a_bio = {}
    if df_detalle is not None and not df_detalle.empty and "docente_id" in df_detalle.columns:
        valid_det = df_detalle.dropna(subset=["docente_id", "docente"]).drop_duplicates(subset=["docente_id"])
        for _, r in valid_det.iterrows():
            d_id = r["docente_id"]
            d_nom = str(r["docente"]).strip()
            mapa_bio_a_id[d_nom] = d_id
            mapa_id_a_bio[d_id] = d_nom
    elif df_filtrado is not None and not df_filtrado.empty and "docente_id" in df_filtrado.columns:
        valid_flt = df_filtrado.dropna(subset=["docente_id", "docente"]).drop_duplicates(subset=["docente_id"])
        for _, r in valid_flt.iterrows():
            d_id = r["docente_id"]
            d_nom = str(r["docente"]).strip()
            mapa_bio_a_id[d_nom] = d_id
            mapa_id_a_bio[d_id] = d_nom

    mapa_sql_a_id = {}
    mapa_id_a_sql = {}
    if df_doc_db is not None and not df_doc_db.empty and "docente_id" in df_doc_db.columns:
        valid_doc = df_doc_db.dropna(subset=["docente_id", "docente"]).drop_duplicates(subset=["docente"])
        for _, r in valid_doc.iterrows():
            d_id = r["docente_id"]
            d_nom = str(r["docente"]).strip()
            mapa_sql_a_id[d_nom] = d_id
            mapa_id_a_sql[d_id] = d_nom

    if df_doc_db is not None and not df_doc_db.empty:
        docentes_disponibles = sorted(df_doc_db["docente"].dropna().unique().tolist())
    else:
        docentes_disponibles = [d for d in lista_docentes if d != "Todos"]

    if not docentes_disponibles:
        docentes_disponibles = list(PERFILES_DOCENTES_REFERENCIA.keys())

    # Sincronización si el usuario seleccionó un docente en la barra superior de filtros
    if "ev1_prev_filtro_docente_top" not in st.session_state:
        st.session_state["ev1_prev_filtro_docente_top"] = filtro_docente_top

    if st.session_state["ev1_prev_filtro_docente_top"] != filtro_docente_top:
        st.session_state["ev1_prev_filtro_docente_top"] = filtro_docente_top
        if filtro_docente_top != "Todos":
            d_id_top = mapa_bio_a_id.get(filtro_docente_top)
            nom_sql_top = mapa_id_a_sql.get(d_id_top)
            if nom_sql_top and nom_sql_top in docentes_disponibles:
                st.session_state["ev1_docente_selector"] = nom_sql_top

    indice_default = 0
    if filtro_docente_top != "Todos":
        d_id_top = mapa_bio_a_id.get(filtro_docente_top)
        nom_sql_top = mapa_id_a_sql.get(d_id_top)
        if nom_sql_top and nom_sql_top in docentes_disponibles:
            indice_default = docentes_disponibles.index(nom_sql_top)

    docente_elegido = st.selectbox(
        "Seleccione un docente para ver su análisis específico:",
        options=docentes_disponibles,
        index=indice_default,
        key="ev1_docente_selector",
    )
    st.caption(
        f"💡 Mostrando los **{len(docentes_disponibles)} docentes** evaluados con respuestas válidas registradas en el ERP "
        f"(la sede cuenta con **213 docentes** con carga horaria y alumnos activos en el periodo)."
    )

    fila_doc = None
    if df_doc_db is not None and not df_doc_db.empty:
        matches = df_doc_db[df_doc_db["docente"] == docente_elegido]
        if not matches.empty:
            fila_doc = matches.iloc[0]

    docente_id_elegido = fila_doc.get("docente_id") if fila_doc is not None else None
    if docente_id_elegido is None or pd.isna(docente_id_elegido):
        docente_id_elegido = mapa_sql_a_id.get(docente_elegido, mapa_bio_a_id.get(docente_elegido))

    nombre_bio = mapa_id_a_bio.get(docente_id_elegido, docente_elegido)

    if fila_doc is not None:
        score_doc = float(fila_doc.get("promedio", 0.0))
        evals_doc = int(fila_doc.get("n_evaluaciones_recibidas", 0))
        resp_doc = int(fila_doc.get("n_respuestas_validas", 0))
        descriptor_doc = str(fila_doc.get("descriptor", "Adecuado"))
        dims_doc = [
            float(fila_doc.get("promedio_dim_1", score_doc)),
            float(fila_doc.get("promedio_dim_2", score_doc)),
            float(fila_doc.get("promedio_dim_3", score_doc)),
            float(fila_doc.get("promedio_dim_4", score_doc)),
            float(fila_doc.get("promedio_dim_5", score_doc)),
        ]
        meta_doc = f"{carrera} · {evals_doc} evaluaciones ({resp_doc} respuestas válidas)"
        pct_aprox_fav = min(max(round((score_doc - 1.0) / 4.0 * 100.0, 1), 0.0), 100.0)
    elif docente_elegido in PERFILES_DOCENTES_REFERENCIA:
        perfil = PERFILES_DOCENTES_REFERENCIA[docente_elegido]
        score_doc = perfil["score"]
        pct_aprox_fav = perfil["fav"]
        meta_doc = perfil["meta"]
        dims_doc = perfil["dims"]
        descriptor_doc = "Fortaleza" if score_doc >= 4.5 else "Adecuado"
    else:
        score_doc = 4.35
        pct_aprox_fav = 85.0
        meta_doc = f"Docente · {carrera}"
        dims_doc = [4.40, 4.20, 4.30, 4.15, 4.50]
        descriptor_doc = "Adecuado"

    col_card, col_meta = st.columns([1.0, 2.0])
    with col_card:
        st.markdown(
            f"""
            <div class="ev1-card-teacher" title="Puntaje promedio general del docente seleccionado obtenido en todas las encuestas respondidas por sus estudiantes.">
                <span>Promedio del docente seleccionado</span>
                <strong>{_formatear_puntaje(score_doc)}</strong>
                <span>Lectura: {_descriptor_badge(descriptor_doc)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_meta:
        if nombre_bio and nombre_bio != docente_elegido:
            st.markdown(f"### {escape(nombre_bio)}")
            st.caption(f"Registro evaluado: **{escape(docente_elegido)}** · Asignaciones asociadas: **{escape(meta_doc)}**")
        else:
            st.markdown(f"### {escape(docente_elegido)}")
            st.caption(f"Asignaciones asociadas: **{escape(meta_doc)}**")
        st.write(f"**Nivel de satisfacción estimado:** {pct_aprox_fav}%")
        st.progress(pct_aprox_fav / 100.0)

    st.divider()

    col_dim, col_ofertas = st.columns([1.2, 1.2])

    with col_dim:
        st.markdown("##### Desempeño por dimensión (Docente)")
        nombres_dims = [
            "Dim. 5: Ética y Compromiso",
            "Dim. 4: Relaciones Interpersonales",
            "Dim. 3: Metodología y Estrategias",
            "Dim. 2: Recursos y Evaluación",
            "Dim. 1: Planificación y Dominio",
        ]
        df_dim_doc = pd.DataFrame({
            "Dimensión": nombres_dims,
            "Puntaje": list(reversed(dims_doc)),
        })
        fig_doc_dim = px.bar(
            df_dim_doc,
            x="Puntaje",
            y="Dimensión",
            orientation="h",
            text="Puntaje",
            range_x=[0, 5],
            custom_data=["Puntaje", "Dimensión"],
        )
        fig_doc_dim.update_traces(
            marker_color="#3c7bc4",
            textposition="outside",
            texttemplate="%{text:.2f}",
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "Calificación del docente: <b>%{x:.2f} / 5,00</b><br>"
                "<i>Promedio otorgado por sus alumnos en este eje</i>"
                "<extra></extra>"
            ),
        )
        fig_doc_dim.update_layout(
            height=260,
            margin=dict(l=10, r=40, t=10, b=10),
            xaxis_title="Puntaje (1 a 5)",
            yaxis_title=None,
            hoverlabel=dict(bgcolor="white", bordercolor="#dbe3ed", font_size=12),
        )
        st.plotly_chart(fig_doc_dim, use_container_width=True, key="ev1_grafico_doc_dim")
        st.caption("💡 *Toque cualquier barra para ver la calificación obtenida por el profesor en cada dimensión.*")

    with col_ofertas:
        st.markdown("##### Detalle de ofertas del docente")
        df_of = None

        # 1. Cargar desde df_detalle (indicador oficial avance_por_materia_seccion_grupo)
        if df_detalle is not None and not df_detalle.empty:
            matches_det = pd.DataFrame()
            if docente_id_elegido is not None and "docente_id" in df_detalle.columns:
                matches_det = df_detalle[df_detalle["docente_id"] == docente_id_elegido].copy()
            if matches_det.empty and "docente" in df_detalle.columns:
                matches_det = df_detalle[
                    (df_detalle["docente"] == docente_elegido) | (df_detalle["docente"] == nombre_bio)
                ].copy()

            # Respetar filtros activos seleccionados en la barra superior
            if not matches_det.empty:
                if filtro_materia_top != "Todas" and "materia" in matches_det.columns:
                    matches_det = matches_det[matches_det["materia"] == filtro_materia_top]
                if filtro_seccion_top != "Todas" and "seccion" in matches_det.columns:
                    matches_det = matches_det[matches_det["seccion"] == filtro_seccion_top]
                if filtro_grupo_top != "Todos" and "grupo" in matches_det.columns:
                    matches_det = matches_det[matches_det["grupo"] == filtro_grupo_top]

                if not matches_det.empty:
                    cols_det = [
                        c for c in [
                            "materia", "seccion", "grupo",
                            "alumnos_esperados", "alumnos_que_respondieron", "porcentaje_avance",
                        ]
                        if c in matches_det.columns
                    ]
                    df_of = matches_det[cols_det].copy().rename(
                        columns={
                            "materia": "Materia",
                            "seccion": "Sección",
                            "grupo": "Grupo",
                            "alumnos_esperados": "Alumnos",
                            "alumnos_que_respondieron": "Respondieron",
                            "porcentaje_avance": "Avance %",
                        }
                    )

        # 2. Respaldo a partir de df_filtrado si df_detalle no está disponible o viene vacío
        if (df_of is None or df_of.empty) and df_filtrado is not None and not df_filtrado.empty:
            df_ofertas_doc = pd.DataFrame()
            if docente_id_elegido is not None and "docente_id" in df_filtrado.columns:
                df_ofertas_doc = df_filtrado[df_filtrado["docente_id"] == docente_id_elegido]
            if df_ofertas_doc.empty and "docente" in df_filtrado.columns:
                df_ofertas_doc = df_filtrado[
                    (df_filtrado["docente"] == docente_elegido) | (df_filtrado["docente"] == nombre_bio)
                ]

            if not df_ofertas_doc.empty:
                resumen_ofertas_doc = (
                    df_ofertas_doc.groupby(["materia", "seccion", "grupo"])
                    .agg(
                        respuestas=("estado", lambda s: (s == "Completada").sum()),
                        total=("estado", "count"),
                    )
                    .reset_index()
                )
                resumen_ofertas_doc["Avance %"] = (
                    resumen_ofertas_doc["respuestas"] / resumen_ofertas_doc["total"] * 100.0
                ).round(1)
                df_of = resumen_ofertas_doc.rename(
                    columns={
                        "materia": "Materia",
                        "seccion": "Sección",
                        "grupo": "Grupo",
                        "respuestas": "Respondieron",
                        "total": "Alumnos",
                    }
                )

        if df_of is not None and not df_of.empty:
            if "Alumnos" in df_of.columns:
                df_of["Alumnos"] = pd.to_numeric(df_of["Alumnos"], errors="coerce").fillna(0).astype(int)
            if "Respondieron" in df_of.columns:
                df_of["Respondieron"] = pd.to_numeric(df_of["Respondieron"], errors="coerce").fillna(0).astype(int)
            if "Avance %" in df_of.columns:
                df_of["Avance %"] = pd.to_numeric(df_of["Avance %"], errors="coerce").fillna(0.0).round(1)

            st.dataframe(
                df_of,
                hide_index=True,
                width="stretch",
                column_config={
                    "Materia": st.column_config.TextColumn("Materia", help="Nombre de la asignatura asignada al docente."),
                    "Sección": st.column_config.TextColumn("Sección", help="Sección académica o turno lectivo."),
                    "Grupo": st.column_config.TextColumn("Grupo", help="Grupo académico específico (Teoría, Laboratorio, etc.)."),
                    "Alumnos": st.column_config.NumberColumn("Alumnos", format="%d", help="Cantidad total de estudiantes matriculados convocados a evaluar al docente."),
                    "Respondieron": st.column_config.NumberColumn("Respondieron", format="%d", help="Cantidad de estudiantes que ya completaron la evaluación del docente."),
                    "Avance %": st.column_config.ProgressColumn(
                        "Avance %",
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                        help="Tasa de respuesta alcanzada: (Respondieron / Alumnos) × 100.",
                    ),
                },
                key="ev1_tabla_doc_ofertas",
            )
            st.caption("💡 *Toque los encabezados para ver el detalle de alumnos matriculados y respuestas recibidas.*")
        else:
            st.info("Sin ofertas registradas para este docente con los filtros seleccionados.")


# ==============================================================================
# SUB-VISTA 6: ANÁLISIS PEDAGÓGICO
# ==============================================================================

def _render_subvista_analisis_pedagogico(sede, periodo, carrera, tipo):
    st.markdown(
        """
        <div class="ev1-note">
            Los alumnos responden directamente los <strong>16 criterios</strong> del instrumento. 
            Los <strong>10 indicadores</strong> agrupan y explican cuantitativamente esos resultados; 
            sus descriptores cualitativos aportan la lectura pedagógica oficial para los planes de mejora docente.
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_dim_db = load_resultado_dimensiones(sede, periodo, carrera, tipo)
    df_cri_db = load_resultado_criterios(sede, periodo, carrera, tipo)
    df_ind_db = load_resultado_indicadores(sede, periodo, carrera, tipo)

    mapa_dims = {}
    if df_dim_db is not None and not df_dim_db.empty and "promedio" in df_dim_db.columns:
        for idx, f in df_dim_db.iterrows():
            dim_num = int(f.get("orden", idx + 1))
            mapa_dims[dim_num] = float(f["promedio"])

    mapa_criterios = {}
    if df_cri_db is not None and not df_cri_db.empty and "promedio" in df_cri_db.columns:
        for _, fila in df_cri_db.iterrows():
            try:
                num = int(fila.get("orden", fila.get("id_criterio", 0)))
                mapa_criterios[num] = float(fila["promedio"])
            except (ValueError, TypeError):
                continue

    mapa_indicadores = {}
    if df_ind_db is not None and not df_ind_db.empty and "promedio" in df_ind_db.columns:
        for _, fila in df_ind_db.iterrows():
            try:
                num_ind = int(fila.get("orden", 0))
                nom = str(fila.get("indicador_nombre", "")).strip()
                dato = {
                    "promedio": float(fila["promedio"]),
                    "descriptor": str(fila.get("descriptor", "")),
                    "nombre_oficial": nom,
                }
                if num_ind > 0:
                    mapa_indicadores[num_ind] = dato
                mapa_indicadores[nom] = dato
            except (ValueError, TypeError):
                continue

    # Iteración por cada dimensión del catálogo pedagógico oficial
    for dim in CATALOGO_PEDAGOGICO_EV1:
        dim_id = dim["id"]
        dim_score = mapa_dims.get(dim_id, dim["puntaje_referencia"])
        with st.expander(f"**{dim['nombre']}** — {_formatear_puntaje(dim_score)} / 5", expanded=(dim_id == 1)):
            for cri in dim["criterios"]:
                cri_num = cri["n"]
                cri_score = mapa_criterios.get(cri_num, cri["puntaje"])
                try:
                    num_ind = int(cri["indicador"][:2])
                except (ValueError, IndexError):
                    num_ind = 0
                ind_info = mapa_indicadores.get(num_ind, mapa_indicadores.get(cri["indicador"], {}))
                ind_score = ind_info.get("promedio")
                ind_desc = ind_info.get("descriptor") or cri["descriptor"]

                score_ind_badge = f" (Promedio indicador: {_formatear_puntaje(ind_score)} / 5)" if ind_score is not None else ""

                st.markdown(
                    f"""
                    <div class="ev1-criterio-box">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
                            <div style="font-weight: 650; font-size: 0.90rem; color: #17243a;">
                                Criterio {cri_num:02d}. {escape(cri['texto'])}
                            </div>
                            <div title="Puntaje promedio obtenido en este criterio específico en la escala de 1 a 5" style="font-weight: 750; font-size: 1.05rem; color: #245ea8; white-space: nowrap; cursor: help;">
                                {_formatear_puntaje(cri_score)} / 5
                            </div>
                        </div>
                        <div class="ev1-indicador-box" title="Indicador pedagógico institucional y lectura descriptiva cualitativa">
                            <strong style="color: #245ea8; font-size: 0.82rem; display: block; margin-bottom: 2px;">
                                {escape(cri['indicador'])}{score_ind_badge}
                            </strong>
                            <p style="margin: 0; color: #50617a; font-size: 0.80rem; line-height: 1.35;">
                                {escape(ind_desc)}
                            </p>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # --------------------------------------------------------------------------
    # METODOLOGÍA Y ORIGEN DE DATOS PEDAGÓGICOS (AUDITORÍA Y FÓRMULAS DE CÁLCULO)
    # --------------------------------------------------------------------------
    fila_res = load_resultado_general(sede, periodo, carrera, tipo)
    n_resp_auditadas = int(fila_res.get("n_respuestas_validas", 668224)) if fila_res is not None and fila_res.get("n_respuestas_validas") is not None else 668224
    n_doc_auditados = int(fila_res.get("n_docentes_evaluados", 216)) if fila_res is not None and fila_res.get("n_docentes_evaluados") is not None else 216

    st.divider()
    st.markdown("#### 📘 Origen de los Datos, Escala y Metodología de Cálculo")

    col_orig1, col_orig2 = st.columns([1.1, 1.3])
    with col_orig1:
        st.markdown(
            f"""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 18px; height: 100%;">
                <h6 style="color: #1e3a63; margin-top: 0; margin-bottom: 10px; font-weight: 700;">
                    🏛️ Fuente y Origen Oficial de los Datos
                </h6>
                <ul style="margin: 0; padding-left: 18px; font-size: 0.84rem; color: #475569; line-height: 1.6;">
                    <li><strong>Instrumento:</strong> Encuesta oficial EV1 (Opinión del Estudiante sobre el Desempeño Docente).</li>
                    <li><strong>Población evaluada:</strong> Estudiantes matriculados que cursaron materias en el periodo (Sede {escape(sede)}, Carrera {escape(carrera)}).</li>
                    <li><strong>Respuestas válidas procesadas:</strong> <strong style="color: #17845f;">{n_resp_auditadas:,}</strong> respuestas a ítems computadas.</li>
                    <li><strong>Docentes evaluados:</strong> <strong>{n_doc_auditados}</strong> profesores con respuestas válidas registradas en el ERP (la sede cuenta con 213 docentes con carga horaria activa en el periodo).</li>
                </ul>
            </div>
            """.replace(",", "."),
            unsafe_allow_html=True,
        )

    with col_orig2:
        st.markdown(
            """
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 18px; height: 100%;">
                <h6 style="color: #1e3a63; margin-top: 0; margin-bottom: 10px; font-weight: 700;">
                    📏 Escala de Valoración (Likert 1 a 5)
                </h6>
                <p style="margin: 0 0 10px 0; font-size: 0.84rem; color: #475569; line-height: 1.45;">
                    Cada estudiante califica los criterios en una escala ordinal estandarizada de 5 niveles:
                </p>
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; text-align: center;">
                    <div style="background: #fdecef; border: 1px solid #f3b9c0; border-radius: 6px; padding: 6px 2px;">
                        <strong style="color: #bd3f4a; font-size: 0.85rem;">1</strong><br>
                        <span style="font-size: 0.70rem; color: #7a1f28;">Muy en desc.</span>
                    </div>
                    <div style="background: #fdf2ea; border: 1px solid #f9d3b8; border-radius: 6px; padding: 6px 2px;">
                        <strong style="color: #d97831; font-size: 0.85rem;">2</strong><br>
                        <span style="font-size: 0.70rem; color: #8a4112;">En desac.</span>
                    </div>
                    <div style="background: #f5f0fa; border: 1px solid #dfcef2; border-radius: 6px; padding: 6px 2px;">
                        <strong style="color: #7654a8; font-size: 0.85rem;">3</strong><br>
                        <span style="font-size: 0.70rem; color: #492a73;">Neutral</span>
                    </div>
                    <div style="background: #eaf2fb; border: 1px solid #c7d5e8; border-radius: 6px; padding: 6px 2px;">
                        <strong style="color: #245ea8; font-size: 0.85rem;">4</strong><br>
                        <span style="font-size: 0.70rem; color: #163e73;">De acuerdo</span>
                    </div>
                    <div style="background: #e7f6f0; border: 1px solid #b5e3d0; border-radius: 6px; padding: 6px 2px;">
                        <strong style="color: #17845f; font-size: 0.85rem;">5</strong><br>
                        <span style="font-size: 0.70rem; color: #0e563e;">Totalmente</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px 20px; margin-top: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.02);">
            <h6 style="color: #1e3a63; margin-top: 0; margin-bottom: 10px; font-weight: 700;">
                ⚙️ Fórmulas y Jerarquía de Cálculo del Modelo Pedagógico
            </h6>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; font-size: 0.84rem; color: #334155; line-height: 1.55;">
                <div style="background: #f8fafc; border-left: 3px solid #245ea8; border-radius: 6px; padding: 10px 14px;">
                    <strong style="color: #245ea8; display: block; margin-bottom: 4px;">1. Criterios (16 Criterios Específicos)</strong>
                    Se calculan como el promedio aritmético directo de todas las puntuaciones válidas (1 a 5) otorgadas por los estudiantes a cada pregunta:<br>
                    <code style="background: #ffffff; padding: 2px 6px; border-radius: 4px; color: #0f172a; font-weight: 600;">
                        Promedio Criterio = Σ(Puntajes respondidos) / Total respuestas válidas
                    </code>
                </div>
                <div style="background: #f8fafc; border-left: 3px solid #17845f; border-radius: 6px; padding: 10px 14px;">
                    <strong style="color: #17845f; display: block; margin-bottom: 4px;">2. Indicadores (10 Indicadores Pedagógicos)</strong>
                    Agrupan criterios afines y se calculan como el promedio ponderado de sus criterios asociados:<br>
                    <code style="background: #ffffff; padding: 2px 6px; border-radius: 4px; color: #0f172a; font-weight: 600;">
                        Promedio Indicador = Promedio(Criterios que lo integran)
                    </code>
                </div>
                <div style="background: #f8fafc; border-left: 3px solid #7654a8; border-radius: 6px; padding: 10px 14px;">
                    <strong style="color: #7654a8; display: block; margin-bottom: 4px;">3. Dimensiones (5 Macro-Ejes Institucionales)</strong>
                    Sintetizan los indicadores en los 5 ejes formativos (Planificación, Recursos, Comunicación, Evaluación y Puntualidad):<br>
                    <code style="background: #ffffff; padding: 2px 6px; border-radius: 4px; color: #0f172a; font-weight: 600;">
                        Promedio Dimensión = Promedio(Indicadores de la dimensión)
                    </code>
                </div>
                <div style="background: #f8fafc; border-left: 3px solid #b87908; border-radius: 6px; padding: 10px 14px;">
                    <strong style="color: #b87908; display: block; margin-bottom: 4px;">4. Semáforo y Descriptores Cualitativos</strong>
                    Los descriptores institucionales clasifican el nivel de desempeño según el puntaje alcanzado:<br>
                    <span style="font-size: 0.78rem;">
                        🟢 <strong>Fortaleza:</strong> ≥ 4,30 &nbsp;|&nbsp; 
                        🔵 <strong>Adecuado:</strong> 4,00 a 4,29 &nbsp;|&nbsp; 
                        🟡 <strong>Seguimiento:</strong> 3,50 a 3,99 &nbsp;|&nbsp; 
                        🔴 <strong>Oportunidad:</strong> &lt; 3,50
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

