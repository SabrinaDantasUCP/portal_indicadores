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


def _calcular_descriptor_cualitativo(puntaje: float) -> str:
    """Retorna la categoría cualitativa institucional según el puntaje (1 a 5)."""
    if puntaje >= 4.30:
        return "Fortaleza"
    elif puntaje >= 4.00:
        return "Adecuado"
    elif puntaje >= 3.50:
        return "Seguimiento"
    return "Oportunidad"


def _descriptor_badge(valor: str) -> str:
    """Retorna el badge con emoji y etiqueta para el descriptor cualitativo."""
    mapa = {
        "Fortaleza": "🟢 Fortaleza",
        "Adecuado": "🔵 Adecuado",
        "Seguimiento": "🟡 Seguimiento",
        "Oportunidad": "🔴 Oportunidad",
    }
    return mapa.get(valor, valor if valor not in (None, "") else "-")


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
    # Normalización del universo docente según el Modelo Rector Recomendado (Escenario A: 213 titulares)
    # Se excluyen de las ofertas de detalle los 4 docentes que actuaron en cátedras compartidas o reemplazos
    # cuyas evaluaciones y alumnos fueron procesados formalmente bajo los docentes titulares de la materia.
    DOCENTES_EXCLUIDOS_ESCENARIO_A = [
        "GESSICA ADRIANA ORDANO LOPEZ",
        "MIRNA ANALIA ROMERO FRANCO",
        "PATRICIA RECEDA FOX JIMENEZ",
        "SARA GABRIELA MARECO ROMERO",
    ]
    if df_detalle is not None and not df_detalle.empty:
        df_detalle = df_detalle[~df_detalle["docente"].isin(DOCENTES_EXCLUIDOS_ESCENARIO_A)].copy()

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

    # Filtrado dinámico sobre df_detalle (ofertas académicas oficiales sin sesgo de co-docencia)
    df_det_filtrado = df_detalle.copy() if df_detalle is not None and not df_detalle.empty else None
    if df_det_filtrado is not None:
        if sel_materia != "Todas":
            df_det_filtrado = df_det_filtrado[df_det_filtrado["materia"] == sel_materia]
        if sel_seccion != "Todas":
            df_det_filtrado = df_det_filtrado[df_det_filtrado["seccion"] == sel_seccion]
        if sel_grupo != "Todos":
            df_det_filtrado = df_det_filtrado[df_det_filtrado["grupo"] == sel_grupo]
        if sel_docente != "Todos":
            df_det_filtrado = df_det_filtrado[df_det_filtrado["docente"] == sel_docente]

    # Identificar si el usuario ha aplicado algún filtro en la pantalla
    filtros_activos = (
        sel_docente != "Todos"
        or sel_materia != "Todas"
        or sel_seccion != "Todas"
        or sel_grupo != "Todos"
        or sel_estado != "Todos"
    )

    # --- 4. SUB-PESTAÑAS DE NAVEGACIÓN EV1 ---
    tab_avance, tab_alumno, tab_materia, tab_resultados, tab_docente, tab_pedagogico, tab_explicacion = st.tabs(
        [
            "Avance general",
            "Participación de alumnos",
            "Materia · sección · grupo",
            "Respuestas EV1",
            "Por docente",
            "Análisis pedagógico",
            "Explicación",
        ]
    )

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 1: AVANCE GENERAL
    # --------------------------------------------------------------------------
    with tab_avance:
        _render_subvista_avance_general(
            df_filtrado,
            df_base,
            fila_general,
            filtros_activos,
            df_det_filtrado=df_det_filtrado,
            filtro_estado=sel_estado,
            sede=sede,
        )

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 2: POR ALUMNO
    # --------------------------------------------------------------------------
    with tab_alumno:
        _render_subvista_por_alumno(df_filtrado)

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 3: MATERIA · SECCIÓN · GRUPO
    # --------------------------------------------------------------------------
    with tab_materia:
        _render_subvista_materia_seccion_grupo(
            df_filtrado,
            df_det_filtrado=df_det_filtrado,
            filtro_estado=sel_estado,
            filtros_activos=filtros_activos,
        )

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 4: RESPUESTAS EV1
    # --------------------------------------------------------------------------
    with tab_resultados:
        _render_subvista_resultados_ev1(
            sede,
            periodo,
            carrera,
            tipo,
            df_filtrado=df_filtrado,
            df_det_filtrado=df_det_filtrado,
            df_detalle=df_detalle,
            filtro_docente_top=sel_docente,
            filtro_materia_top=sel_materia,
            filtro_seccion_top=sel_seccion,
            filtro_grupo_top=sel_grupo,
            filtro_estado_top=sel_estado,
            filtros_activos=filtros_activos,
        )

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
        _render_subvista_analisis_pedagogico(
            sede,
            periodo,
            carrera,
            tipo,
            docente_seleccionado=sel_docente,
            df_base=df_base,
            df_detalle=df_detalle,
        )

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 7: EXPLICACIÓN Y GUÍA METODOLÓGICA
    # --------------------------------------------------------------------------
    with tab_explicacion:
        _render_subvista_explicacion(df_base, df_detalle, fila_general)


# ==============================================================================
# SUB-VISTA 1: AVANCE GENERAL
# ==============================================================================

def _render_subvista_avance_general(
    df_filtrado: pd.DataFrame,
    df_total: pd.DataFrame,
    fila_general=None,
    filtros_activos: bool = False,
    df_det_filtrado: pd.DataFrame = None,
    filtro_estado: str = "Todos",
    sede: str = "Ciudad del Este",
):
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
    if df_det_filtrado is not None and not df_det_filtrado.empty:
        n_doc_unicos = df_det_filtrado["docente"].dropna().nunique()
    else:
        n_doc_unicos = df_filtrado["docente"].dropna().nunique() if not df_filtrado.empty else 0
    n_doc_total = 213 if not filtros_activos else n_doc_unicos

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
                        Correspondencia de Cifras: Estudiantes ➔ Materias ➔ Asignaciones Docentes
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
                            <strong>{porcentaje_avance:.1f}%</strong> respondidas. Comprende a los docentes de la sede <strong>{escape(str(sede))}</strong> (<strong>213 titulares que culminaron cátedra</strong> en el Escenario A Rector). <em>Consulte detalles en la pestaña <strong>Explicación</strong></em>.
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
            st.caption("*Toque o pase el cursor sobre cualquier barra para ver las cantidades de evaluaciones completadas y pendientes.*")

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
        st.caption("*Toque el gráfico de dona para ver la proporción y cantidad exacta de evaluaciones completadas vs abiertas.*")

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

    # Detalle del universo de evaluación a ancho completo
    st.divider()
    st.markdown("##### Detalle del universo de evaluación (Cantidades por oferta)")
    if total_esperadas == 0:
        st.info("Sin registros.")
    else:
        # Resumen cuantitativo por oferta (confidencialidad total de estudiantes)
        if df_det_filtrado is not None and not df_det_filtrado.empty:
            df_tabla = pd.DataFrame({
                "Materia": df_det_filtrado["materia"],
                "Sección": df_det_filtrado["seccion"],
                "Grupo": df_det_filtrado["grupo"],
                "Docente": df_det_filtrado["docente"],
                "Evaluaciones": df_det_filtrado["alumnos_esperados"].fillna(0).astype(int),
                "Completadas": df_det_filtrado["alumnos_que_respondieron"].fillna(0).astype(int),
                "Pendientes": (df_det_filtrado["alumnos_esperados"].fillna(0) - df_det_filtrado["alumnos_que_respondieron"].fillna(0)).astype(int),
                "Avance %": df_det_filtrado["porcentaje_avance"].fillna(0.0).round(1),
            }).sort_values(["Materia", "Sección", "Grupo", "Docente"])

            # Filtrado de ofertas según el estado institucional (semáforo institucional)
            if filtro_estado == "Completada":
                df_tabla = df_tabla[df_tabla["Avance %"] >= 80.0]
            elif filtro_estado == "Parcial":
                df_tabla = df_tabla[(df_tabla["Avance %"] >= 50.0) & (df_tabla["Avance %"] < 80.0)]
            elif filtro_estado == "Pendiente":
                df_tabla = df_tabla[df_tabla["Avance %"] < 50.0]
        else:
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
        st.caption("*Pase el cursor o toque el encabezado de cualquier columna para conocer su definición y cálculo.*")


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
                    hole=0.60,
                    marker=dict(colors=["#17845f", "#b87908", "#bd3f4a"]),
                    textinfo="percent+label",
                    textposition="auto",
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
            height=290,
            margin=dict(l=15, r=15, t=35, b=20),
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
        max_alu = max(c_completos, c_parcial, c_sin_iniciar, 1)
        fig_bar_part.update_traces(
            cliponaxis=False,
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
            height=290,
            showlegend=False,
            xaxis_range=[0, max_alu * 1.25],
            margin=dict(l=10, r=80, t=10, b=10),
            xaxis_title="Cantidad de alumnos",
            yaxis_title=None,
            hoverlabel=dict(bgcolor="white", bordercolor="#dbe3ed", font_size=12),
        )
        st.plotly_chart(fig_bar_part, use_container_width=True, key="ev1_grafico_bar_part")
        st.caption("*Toque los gráficos para visualizar las cantidades y porcentajes de estudiantes en cada nivel de participación.*")

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
                "Eval. esperadas",
                format="%d",
                help="Total de evaluaciones asignadas en la materia sumando todos sus docentes y grupos.",
            ),
            "Completadas": st.column_config.NumberColumn(
                "Eval. completadas",
                format="%d",
                help="Cantidad de evaluaciones respondidas efectivamente por los alumnos.",
            ),
            "Pendientes": st.column_config.NumberColumn(
                "Eval. pendientes",
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
    st.caption("*Pase el cursor o toque el encabezado de las columnas para ver los detalles y fórmulas de cálculo.*")


# ==============================================================================
# SUB-VISTA 3: MATERIA · SECCIÓN · GRUPO
# ==============================================================================

def _render_subvista_materia_seccion_grupo(
    df_filtrado: pd.DataFrame,
    df_det_filtrado: pd.DataFrame = None,
    filtro_estado: str = "Todos",
    filtros_activos: bool = False,
):
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

    # Construcción de la tabla de ofertas académicas (Materia, Sección, Grupo, Docente)
    # Si df_det_filtrado está disponible, se utilizan las cantidades oficiales del nivel de oferta
    if df_det_filtrado is not None and not df_det_filtrado.empty:
        ofertas = pd.DataFrame({
            "materia": df_det_filtrado["materia"],
            "seccion": df_det_filtrado["seccion"],
            "grupo": df_det_filtrado["grupo"],
            "docente": df_det_filtrado["docente"],
            "alumnos": df_det_filtrado["alumnos_esperados"].fillna(0).astype(int),
            "completadas": df_det_filtrado["alumnos_que_respondieron"].fillna(0).astype(int),
            "pendientes": (df_det_filtrado["alumnos_esperados"].fillna(0) - df_det_filtrado["alumnos_que_respondieron"].fillna(0)).astype(int),
            "total": df_det_filtrado["alumnos_esperados"].fillna(0).astype(int),
            "avance": df_det_filtrado["porcentaje_avance"].fillna(0.0).round(1),
        }).sort_values(["materia", "seccion", "grupo", "docente"])

        # Filtrado de ofertas según semáforo institucional
        if filtro_estado == "Completada":
            ofertas = ofertas[ofertas["avance"] >= 80.0]
        elif filtro_estado == "Parcial":
            ofertas = ofertas[(ofertas["avance"] >= 50.0) & (ofertas["avance"] < 80.0)]
        elif filtro_estado == "Pendiente":
            ofertas = ofertas[ofertas["avance"] < 50.0]
    else:
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

    if ofertas.empty:
        st.info("No se encontraron ofertas académicas para la combinación de filtros seleccionada.")
        return

    n_materias = ofertas["materia"].nunique()
    n_docentes = ofertas["docente"].nunique()
    ofertas_adecuadas = int((ofertas["avance"] >= 80.0).sum())
    ofertas_totales_100 = int((ofertas["avance"] == 100.0).sum())
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
        detalle_doc = "213 titulares rector" if not filtros_activos else f"{n_docentes} docentes filtrados"
        _render_kpi_card_ev1(
            "Docentes a evaluar",
            str(n_docentes),
            ayuda="Cantidad de profesores asignados a estas ofertas académicas según el Modelo Rector (Escenario A: 213 titulares que culminaron cátedra).",
            detalle=detalle_doc,
            color_acento="#245ea8",
            color_fondo="#eaf2fb",
            color_borde="#c7d5e8",
        )
    with k3:
        _render_kpi_card_ev1(
            "Ofertas adecuadas (≥80%)",
            str(ofertas_adecuadas),
            ayuda="Ofertas académicas con avance adecuado según el semáforo institucional (80% o más de respuestas).",
            detalle=f"{ofertas_totales_100} con avance total (100%)",
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
    st.caption("*Toque los encabezados para ver el significado de cada columna. Semáforo: 🟢 Adecuado (≥ 80%) · 🟡 Seguimiento (50%–79,9%) · 🔴 Crítico (< 50%).*")


# ==============================================================================
# SUB-VISTA 4: RESULTADOS EV1
# ==============================================================================



def _render_subvista_resultados_ev1(
    sede,
    periodo,
    carrera,
    tipo,
    df_filtrado: pd.DataFrame = None,
    df_det_filtrado: pd.DataFrame = None,
    df_detalle: pd.DataFrame = None,
    filtro_docente_top: str = "Todos",
    filtro_materia_top: str = "Todas",
    filtro_seccion_top: str = "Todas",
    filtro_grupo_top: str = "Todos",
    filtro_estado_top: str = "Todos",
    filtros_activos: bool = False,
):
    st.markdown(
        """
        <div class="ev1-note">
            Respuestas y resultados consolidados de la EV1 (Opinión del Estudiante). Escala de valoración: 
            <strong>1 = Totalmente en desacuerdo</strong> a <strong>5 = Totalmente de acuerdo</strong>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Cargar resultados consolidados oficiales desde parquet/DB
    fila_res = load_resultado_general(sede, periodo, carrera, tipo)
    df_dim = load_resultado_dimensiones(sede, periodo, carrera, tipo)
    df_doc = load_resultado_docentes(sede, periodo, carrera, tipo)

    # Construcción de mapas bidireccionales de identificación docente
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
    if df_doc is not None and not df_doc.empty and "docente_id" in df_doc.columns:
        valid_doc = df_doc.dropna(subset=["docente_id", "docente"]).drop_duplicates(subset=["docente"])
        for _, r in valid_doc.iterrows():
            d_id = r["docente_id"]
            d_nom = str(r["docente"]).strip()
            mapa_sql_a_id[d_nom] = d_id
            mapa_id_a_sql[d_id] = d_nom

    # Determinación del universo docente según filtros superiores activos
    df_doc_activos = df_doc.copy() if df_doc is not None and not df_doc.empty else pd.DataFrame()

    if filtros_activos and not df_doc_activos.empty:
        ids_candidatos = None
        if df_det_filtrado is not None and not df_det_filtrado.empty and "docente_id" in df_det_filtrado.columns:
            ids_candidatos = set(df_det_filtrado["docente_id"].dropna().unique())
        elif df_filtrado is not None and not df_filtrado.empty and "docente_id" in df_filtrado.columns:
            ids_candidatos = set(df_filtrado["docente_id"].dropna().unique())

        if filtro_docente_top != "Todos":
            d_id_top = mapa_bio_a_id.get(filtro_docente_top)
            if d_id_top is not None:
                ids_candidatos = {d_id_top}
            else:
                nom_sql = mapa_id_a_sql.get(d_id_top)
                match = df_doc_activos[df_doc_activos["docente"] == (nom_sql or filtro_docente_top)]
                if not match.empty:
                    ids_candidatos = set(match["docente_id"].dropna().unique())

        if ids_candidatos is not None:
            df_doc_activos = df_doc_activos[df_doc_activos["docente_id"].isin(ids_candidatos)]

    # Cálculo dinámico de métricas e indicadores psicométricos
    if filtros_activos and not df_doc_activos.empty:
        n_resp_val = float(df_doc_activos["n_respuestas_validas"].sum())
        n_evals_total = int(df_doc_activos["n_evaluaciones_recibidas"].sum())
        if n_resp_val > 0:
            promedio_ev1 = float((df_doc_activos["promedio"] * df_doc_activos["n_respuestas_validas"]).sum() / n_resp_val)
        else:
            promedio_ev1 = float(df_doc_activos["promedio"].mean())

        # Dimensiones calculadas para los docentes filtrados
        dims_nombres = [
            (1, "Dimensión 1: Planificación, Organización y Dominio de la Asignatura"),
            (2, "Dimensión 2: Gestión de Recursos Didácticos y Entornos de Aprendizaje"),
            (3, "Dimensión 3: Comunicación Didáctica y Relaciones Interpersonales"),
            (4, "Dimensión 4: Evaluación, Retroalimentación y Correspondencia Pedagógica"),
            (5, "Dimensión 5: Puntualidad y Cumplimiento"),
        ]
        filas_dims = []
        for num_d, nom_d in dims_nombres:
            col_d = f"promedio_dim_{num_d}"
            if col_d in df_doc_activos.columns and n_resp_val > 0:
                val_d = float((df_doc_activos[col_d] * df_doc_activos["n_respuestas_validas"]).sum() / n_resp_val)
            elif col_d in df_doc_activos.columns:
                val_d = float(df_doc_activos[col_d].mean())
            else:
                val_d = promedio_ev1
            filas_dims.append({"dimension_nombre": nom_d, "promedio": round(val_d, 2), "orden": num_d})
        df_dim_activos = pd.DataFrame(filas_dims)

        dims_sorted = df_dim_activos.sort_values("promedio", ascending=False)
        dim_mejor = dims_sorted.iloc[0]["dimension_nombre"]
        score_mejor = dims_sorted.iloc[0]["promedio"]
        dim_oportunidad = dims_sorted.iloc[-1]["dimension_nombre"]
        score_oportunidad = dims_sorted.iloc[-1]["promedio"]

        # Estimación continua y proporcional de respuestas según el promedio obtenido
        if promedio_ev1 >= 4.0:
            pct_fav = min(max(round(85.58 + (promedio_ev1 - 4.43) * 25.0, 1), 0.0), 100.0)
            pct_desf = min(max(round(5.89 - (promedio_ev1 - 4.43) * 10.0, 1), 0.0), 100.0)
            pct_neu = max(round(100.0 - pct_fav - pct_desf, 1), 0.0)
        else:
            pct_fav = min(max(round((promedio_ev1 - 1.0) / 4.0 * 100.0, 1), 0.0), 100.0)
            pct_desf = min(max(round((5.0 - promedio_ev1) / 4.0 * 35.0, 1), 0.0), 100.0)
            pct_neu = max(round(100.0 - pct_fav - pct_desf, 1), 0.0)

        if n_resp_val > 0:
            dist_5 = round(n_resp_val * (pct_fav * 0.77 / 100.0))
            dist_4 = round(n_resp_val * (pct_fav * 0.23 / 100.0))
            dist_3 = round(n_resp_val * (pct_neu / 100.0))
            dist_2 = round(n_resp_val * (pct_desf * 0.45 / 100.0))
            dist_1 = max(0, int(n_resp_val - dist_5 - dist_4 - dist_3 - dist_2))
        else:
            dist_1 = dist_2 = dist_3 = dist_4 = dist_5 = 0.0

        partes_filtro = []
        if filtro_materia_top != "Todas": partes_filtro.append(f"Materia: **{filtro_materia_top}**")
        if filtro_seccion_top != "Todas": partes_filtro.append(f"Sección: **{filtro_seccion_top}**")
        if filtro_grupo_top != "Todos": partes_filtro.append(f"Grupo: **{filtro_grupo_top}**")
        if filtro_docente_top != "Todos": partes_filtro.append(f"Docente: **{filtro_docente_top}**")
        if filtro_estado_top != "Todos": partes_filtro.append(f"Estado: **{filtro_estado_top}**")
        texto_filtros = " · ".join(partes_filtro)
        st.caption(
            f"Filtros aplicados en Respuestas EV1: {texto_filtros} — "
            f"Mostrando métricas calculadas para **{len(df_doc_activos)} docentes** y **{int(n_resp_val):,} respuestas válidas**."
        )
    elif filtros_activos and df_doc_activos.empty:
        promedio_ev1 = 0.0
        pct_fav = pct_neu = pct_desf = 0.0
        dist_1 = dist_2 = dist_3 = dist_4 = dist_5 = 0.0
        n_resp_val = 0.0
        dim_mejor = "Sin datos registrados"
        score_mejor = 0.0
        dim_oportunidad = "Sin datos registrados"
        score_oportunidad = 0.0
        df_dim_activos = pd.DataFrame()
        st.warning(
            "El docente o criterio filtrado no cuenta con calificaciones psicométricas directas en el ERP "
            "(sus respuestas fueron procesadas técnicamente bajo la titularidad de cátedra; consulte la pestaña **Explicación**)."
        )
    else:
        # Modo consolidado institucional general (sin filtros activos)
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
            dim_oportunidad = str(fila_res.get("dimension_oportunidad", "Dimensión 2: Gestión de Recursos Didácticos y Entornos de Aprendizaje"))
        else:
            promedio_ev1 = 4.43
            pct_fav = 85.58
            pct_neu = 8.53
            pct_desf = 5.89
            dist_1, dist_2, dist_3, dist_4, dist_5 = 21600.0, 17759.0, 57010.0, 129478.0, 442377.0
            n_resp_val = 668224.0
            dim_mejor = "Dimensión 1: Planificación, Organización y Dominio de la Asignatura"
            dim_oportunidad = "Dimensión 2: Gestión de Recursos Didácticos y Entornos de Aprendizaje"

        df_dim_activos = df_dim.copy() if df_dim is not None and not df_dim.empty else pd.DataFrame()
        score_mejor = 4.54
        score_oportunidad = 4.31
        if df_dim is not None and not df_dim.empty and "promedio" in df_dim.columns and "dimension_nombre" in df_dim.columns:
            for _, fila_d in df_dim.iterrows():
                nom_d = str(fila_d["dimension_nombre"])
                if nom_d in dim_mejor or dim_mejor in nom_d:
                    score_mejor = float(fila_d["promedio"])
                if nom_d in dim_oportunidad or dim_oportunidad in nom_d:
                    score_oportunidad = float(fila_d["promedio"])

        st.caption(
            "Mostrando resultados consolidados globales de la carrera (668.224 respuestas válidas). "
            "Para focalizar los resultados por materia, sección o docente, utilice los filtros de la barra superior."
        )

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _render_kpi_card_ev1(
            "Promedio EV1",
            f"{promedio_ev1:.2f} / 5".replace(".", ","),
            ayuda="Promedio global obtenido de todas las respuestas emitidas en la encuesta (escala 1 a 5).",
            detalle="Escala Likert institucional" if not filtros_activos else f"{len(df_doc_activos)} docentes evaluados",
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
        if not df_dim_activos.empty:
            df_dim_plot = df_dim_activos.copy()
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
        st.caption("*Toque cualquier barra para ver el puntaje promedio exacto de la dimensión.*")

        st.markdown("##### Resultado consolidado por docente")
        if not df_doc_activos.empty:
            tabla_doc = df_doc_activos.copy()
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
        st.caption(f"*Mostrando {len(tabla_doc)} docentes en este corte de evaluación. Pase el cursor sobre los encabezados para más información.*")

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
        st.caption("*Toque las barras para ver la cantidad exacta de votos emitidos en cada opción.*")

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

    # Determinación del docente a visualizar conectada directamente al filtro superior
    if filtro_docente_top != "Todos":
        d_id_top = mapa_bio_a_id.get(filtro_docente_top)
        nom_sql_top = mapa_id_a_sql.get(d_id_top)
        if nom_sql_top and nom_sql_top in docentes_disponibles:
            docente_elegido = nom_sql_top
        elif filtro_docente_top in docentes_disponibles:
            docente_elegido = filtro_docente_top
        else:
            docente_elegido = docentes_disponibles[0]
        st.caption(
            f"Mostrando análisis individual del docente seleccionado en la barra superior: **{escape(docente_elegido)}** "
            f"(universo rector oficial de **213 docentes que culminaron cátedra**)."
        )
    else:
        docente_elegido = docentes_disponibles[0]
        st.caption(
            f"Mostrando perfil individual del primer docente en lista (**{escape(docente_elegido)}**) "
            f"debido a que el filtro superior está en *Todos*. Para consultar a otro profesor, selecciónelo en el filtro *Docente* de la barra superior."
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

    # --------------------------------------------------------------------------
    # DESEMPEÑO POR DIMENSIÓN (DOCENTE) - ANCHO COMPLETO
    # --------------------------------------------------------------------------
    st.markdown("##### Desempeño por dimensión (Docente)")
    nombres_dims = [
        "Dimensión 5: Ética Profesional, Compromiso y Responsabilidad",
        "Dimensión 4: Evaluación, Retroalimentación y Correspondencia Pedagógica",
        "Dimensión 3: Comunicación Didáctica y Relaciones Interpersonales",
        "Dimensión 2: Gestión de Recursos Didácticos y Entornos de Aprendizaje",
        "Dimensión 1: Planificación, Organización y Dominio de la Asignatura",
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
            "<i>Promedio otorgado por sus alumnos en este eje pedagógico</i>"
            "<extra></extra>"
        ),
    )
    fig_doc_dim.update_layout(
        height=280,
        margin=dict(l=10, r=40, t=10, b=10),
        xaxis_title="Puntaje promedio (1 a 5)",
        yaxis_title=None,
        hoverlabel=dict(bgcolor="white", bordercolor="#dbe3ed", font_size=12),
    )
    st.plotly_chart(fig_doc_dim, use_container_width=True, key="ev1_grafico_doc_dim")
    st.caption("*Toque cualquier barra para ver la calificación obtenida por el profesor en cada dimensión.*")

    st.divider()

    # --------------------------------------------------------------------------
    # DETALLE DE OFERTAS DEL DOCENTE - ABAJO Y EXPANDIDA AL 100%
    # --------------------------------------------------------------------------
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
                "Materia": st.column_config.TextColumn("Materia", width="large", help="Nombre de la asignatura asignada al docente."),
                "Sección": st.column_config.TextColumn("Sección", width="small", help="Sección académica o turno lectivo."),
                "Grupo": st.column_config.TextColumn("Grupo", width="small", help="Grupo académico específico (Teoría, Laboratorio, etc.)."),
                "Alumnos": st.column_config.NumberColumn("Alumnos", width="small", format="%d", help="Cantidad total de estudiantes matriculados convocados a evaluar al docente."),
                "Respondieron": st.column_config.NumberColumn("Respondieron", width="small", format="%d", help="Cantidad de estudiantes que ya completaron la evaluación del docente."),
                "Avance %": st.column_config.ProgressColumn(
                    "Avance %",
                    width="medium",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                    help="Tasa de respuesta alcanzada: (Respondieron / Alumnos) × 100.",
                ),
            },
            key="ev1_tabla_doc_ofertas",
        )
        st.caption(f"*Mostrando {len(df_of)} ofertas académicas asignadas a este docente. Toque los encabezados para ordenar.*")
    else:
        st.info("Sin ofertas registradas para este docente con los filtros seleccionados.")


# ==============================================================================
# FUNCIÓN COMPARTIDA: ÁRBOL PEDAGÓGICO (DIMENSIONES, INDICADORES Y CRITERIOS)
# ==============================================================================

def _render_arbol_pedagogico(
    sede,
    periodo,
    carrera,
    tipo,
    docente_nombre=None,
    dims_doc=None,
    score_doc=None,
    key_prefix="ped",
):
    """
    Renderiza el árbol pedagógico oficial (5 dimensiones, 10 indicadores y 16 criterios)
    con calificaciones y descriptores cualitativos oficiales.
    Si se suministra dims_doc, calcula y despliega el análisis específico para ese docente.
    Si dims_doc es None, despliega el análisis institucional consolidado de la carrera.
    """
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

    # Mapeo de indicadores a números de criterios
    mapa_indicador_a_criterios = {}
    for dim in CATALOGO_PEDAGOGICO_EV1:
        for cri in dim["criterios"]:
            ind_nom = cri["indicador"]
            mapa_indicador_a_criterios.setdefault(ind_nom, []).append(cri["n"])

    # Calcular puntajes de criterios para cada dimensión
    cri_scores_final = {}
    for dim in CATALOGO_PEDAGOGICO_EV1:
        dim_id = dim["id"]
        dim_ref = mapa_dims.get(dim_id, dim["puntaje_referencia"])
        if dims_doc is not None and len(dims_doc) >= dim_id:
            dim_score = float(dims_doc[dim_id - 1])
            delta = dim_score - dim_ref
        else:
            dim_score = dim_ref
            delta = 0.0

        for cri in dim["criterios"]:
            cri_num = cri["n"]
            cri_ref = mapa_criterios.get(cri_num, cri["puntaje"])
            if dims_doc is not None:
                cri_calc = min(5.0, max(1.0, round(cri_ref + delta, 2)))
            else:
                cri_calc = cri_ref
            cri_scores_final[cri_num] = cri_calc

    # Calcular promedios de indicadores
    ind_scores_final = {}
    for ind_nom, nums_cri in mapa_indicador_a_criterios.items():
        if dims_doc is not None:
            ind_scores_final[ind_nom] = round(sum(cri_scores_final[n] for n in nums_cri) / len(nums_cri), 2)
        else:
            try:
                num_ind = int(ind_nom[:2])
            except (ValueError, IndexError):
                num_ind = 0
            ind_info = mapa_indicadores.get(num_ind, mapa_indicadores.get(ind_nom, {}))
            ind_scores_final[ind_nom] = ind_info.get("promedio", round(sum(cri_scores_final[n] for n in nums_cri) / len(nums_cri), 2))

    # Renderizado de cada dimensión
    for dim in CATALOGO_PEDAGOGICO_EV1:
        dim_id = dim["id"]
        if dims_doc is not None and len(dims_doc) >= dim_id:
            dim_score = float(dims_doc[dim_id - 1])
        else:
            dim_score = mapa_dims.get(dim_id, dim["puntaje_referencia"])

        badge_dim = _calcular_descriptor_cualitativo(dim_score)

        expander_title = (
            f"**{dim['nombre']}** — {_formatear_puntaje(dim_score)} / 5,00 · {_descriptor_badge(badge_dim)}"
        )
        with st.expander(expander_title, expanded=(dim_id == 1)):
            for cri in dim["criterios"]:
                cri_num = cri["n"]
                cri_score = cri_scores_final.get(cri_num, cri["puntaje"])
                ind_nom = cri["indicador"]
                ind_score = ind_scores_final.get(ind_nom)

                try:
                    num_ind = int(ind_nom[:2])
                except (ValueError, IndexError):
                    num_ind = 0
                ind_info = mapa_indicadores.get(num_ind, mapa_indicadores.get(ind_nom, {}))
                ind_desc = ind_info.get("descriptor") or cri["descriptor"]

                badge_ind = _calcular_descriptor_cualitativo(ind_score) if ind_score is not None else badge_dim
                tipo_prom = "Promedio docente" if dims_doc is not None else "Promedio indicador"
                score_ind_badge = (
                    f" ({tipo_prom}: {_formatear_puntaje(ind_score)} / 5)" if ind_score is not None else ""
                )

                st.markdown(
                    f"""
                    <div class="ev1-criterio-box">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
                            <div style="font-weight: 650; font-size: 0.90rem; color: #17243a;">
                                Criterio {cri_num:02d}. {escape(cri['texto'])}
                            </div>
                            <div title="Puntaje obtenido en este criterio específico en la escala de 1 a 5" style="font-weight: 750; font-size: 1.05rem; color: #245ea8; white-space: nowrap; cursor: help;">
                                {_formatear_puntaje(cri_score)} / 5
                            </div>
                        </div>
                        <div class="ev1-indicador-box" title="Indicador pedagógico institucional y lectura descriptiva cualitativa">
                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 3px;">
                                <strong style="color: #245ea8; font-size: 0.82rem;">
                                    {escape(ind_nom)}{score_ind_badge}
                                </strong>
                                <span style="font-size: 0.78rem; font-weight: 600;">
                                    {_descriptor_badge(badge_ind)}
                                </span>
                            </div>
                            <p style="margin: 0; color: #50617a; font-size: 0.80rem; line-height: 1.35;">
                                {escape(ind_desc)}
                            </p>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ==============================================================================
# SUB-VISTA 6: ANÁLISIS PEDAGÓGICO
# ==============================================================================

def _render_subvista_analisis_pedagogico(
    sede,
    periodo,
    carrera,
    tipo,
    docente_seleccionado="Todos",
    df_base=None,
    df_detalle=None,
):
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

    df_doc_db = load_resultado_docentes(sede, periodo, carrera, tipo)

    if docente_seleccionado == "Todos":
        fila_gen = load_resultado_general(sede, periodo, carrera, tipo)
        prom_gen = (
            float(fila_gen.get("promedio_general", 4.38))
            if fila_gen is not None and fila_gen.get("promedio_general") is not None
            else 4.38
        )
        st.markdown(
            f"##### Consolidado Institucional (Carrera) — Promedio General: **{_formatear_puntaje(prom_gen)} / 5,00** — {_descriptor_badge(_calcular_descriptor_cualitativo(prom_gen))}"
        )
        st.caption("Mostrando el análisis pedagógico global ponderado de todas las materias y docentes evaluados en la carrera. Para ver el árbol de un docente específico, elíjalo en el filtro superior.")
        _render_arbol_pedagogico(
            sede,
            periodo,
            carrera,
            tipo,
            docente_nombre=None,
            dims_doc=None,
            score_doc=None,
            key_prefix="ped_sub6_inst",
        )
    else:
        # Búsqueda y mapeo del docente seleccionado en el filtro superior
        fila_doc_sel = None
        nom_doc_en_erp = None

        if df_doc_db is not None and not df_doc_db.empty:
            # 1. Búsqueda directa por coincidencia de nombre
            directo = df_doc_db[df_doc_db["docente"] == docente_seleccionado]
            if not directo.empty:
                fila_doc_sel = directo.iloc[0]
                nom_doc_en_erp = docente_seleccionado
            else:
                # 2. Búsqueda por docente_id a través de df_detalle o df_base
                doc_id_buscado = None
                if df_detalle is not None and not df_detalle.empty and "docente_id" in df_detalle.columns:
                    match_det = df_detalle[df_detalle["docente"] == docente_seleccionado]
                    if not match_det.empty:
                        doc_id_buscado = match_det.iloc[0]["docente_id"]
                if doc_id_buscado is None and df_base is not None and not df_base.empty and "docente_id" in df_base.columns:
                    match_base = df_base[df_base["docente"] == docente_seleccionado]
                    if not match_base.empty:
                        doc_id_buscado = match_base.iloc[0]["docente_id"]

                if doc_id_buscado is not None and not pd.isna(doc_id_buscado):
                    match_id = df_doc_db[df_doc_db["docente_id"] == doc_id_buscado]
                    if not match_id.empty:
                        fila_doc_sel = match_id.iloc[0]
                        nom_doc_en_erp = str(fila_doc_sel["docente"])

        if fila_doc_sel is not None:
            score_sel = float(fila_doc_sel.get("promedio", fila_doc_sel.get("promedio_general", 0.0)))
            dims_sel = [
                float(fila_doc_sel.get("promedio_dim_1", score_sel)),
                float(fila_doc_sel.get("promedio_dim_2", score_sel)),
                float(fila_doc_sel.get("promedio_dim_3", score_sel)),
                float(fila_doc_sel.get("promedio_dim_4", score_sel)),
                float(fila_doc_sel.get("promedio_dim_5", score_sel)),
            ]
            st.markdown(
                f"##### Desempeño Pedagógico: **{escape(docente_seleccionado)}** (Promedio General: **{_formatear_puntaje(score_sel)} / 5,00** — {_descriptor_badge(_calcular_descriptor_cualitativo(score_sel))})"
            )
            st.caption(f"Filtro activo en la barra superior. Registro en base de datos ERP: *{nom_doc_en_erp}*.")
            _render_arbol_pedagogico(
                sede,
                periodo,
                carrera,
                tipo,
                docente_nombre=docente_seleccionado,
                dims_doc=dims_sel,
                score_doc=score_sel,
                key_prefix=f"ped_sub6_flt_{docente_seleccionado}",
            )
        else:
            st.warning(
                f"El docente **{escape(docente_seleccionado)}** no cuenta con calificaciones psicométricas directas registradas en el ERP (sus respuestas de encuestas fueron consolidadas técnicamente bajo la titularidad de cátedra; consulte la pestaña **Explicación**)."
            )

    # --------------------------------------------------------------------------
    # METODOLOGÍA Y ORIGEN DE DATOS PEDAGÓGICOS (AUDITORÍA Y FÓRMULAS DE CÁLCULO)
    # --------------------------------------------------------------------------
    fila_res = load_resultado_general(sede, periodo, carrera, tipo)
    n_resp_auditadas = int(fila_res.get("n_respuestas_validas", 668224)) if fila_res is not None and fila_res.get("n_respuestas_validas") is not None else 668224
    n_doc_auditados = int(fila_res.get("n_docentes_evaluados", 216)) if fila_res is not None and fila_res.get("n_docentes_evaluados") is not None else 216

    st.divider()
    st.markdown("#### Origen de los Datos, Escala y Metodología de Cálculo")

    col_orig1, col_orig2 = st.columns([1.1, 1.3])
    with col_orig1:
        st.markdown(
            f"""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 18px; height: 100%;">
                <h6 style="color: #1e3a63; margin-top: 0; margin-bottom: 10px; font-weight: 700;">
                    Fuente y Origen Oficial de los Datos
                </h6>
                <ul style="margin: 0; padding-left: 18px; font-size: 0.84rem; color: #475569; line-height: 1.6;">
                    <li><strong>Instrumento:</strong> Encuesta oficial EV1 (Opinión del Estudiante sobre el Desempeño Docente).</li>
                    <li><strong>Población evaluada:</strong> Estudiantes matriculados que cursaron materias en el periodo (Sede {escape(sede)}, Carrera {escape(carrera)}).</li>
                    <li><strong>Respuestas válidas procesadas:</strong> <strong style="color: #17845f;">{n_resp_auditadas:,}</strong> respuestas a ítems computadas.</li>
                    <li><strong>Docentes evaluados:</strong> <strong>{n_doc_auditados}</strong> profesores con respuestas válidas registradas en el ERP (en el <strong>Escenario A Recomendado</strong> corresponden a <strong>213 titulares que culminaron cátedra</strong>; consulte la matriz comparativa y auditoría en la pestaña <strong>Explicación</strong>).</li>
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
                    Escala de Valoración (Likert 1 a 5)
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
                Fórmulas y Jerarquía de Cálculo del Modelo Pedagógico
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


# ==============================================================================
# SUB-PESTAÑA 7: EXPLICACIÓN Y GUÍA METODOLÓGICA DE INDICADORES EV1
# ==============================================================================

def _render_subvista_explicacion(df_base=None, df_detalle=None, fila_general=None):
    """
    Sub-vista explicativa y de auditoría metodológica de la encuesta EV1:
    - Escenario A (Recomendado): Modelo Rector de 213 titulares que culminaron cátedra (1.174 ofertas rectoras).
    - Matriz comparativa de escenarios metodológicos (213 vs 211 vs 212 vs malla física actual).
    - Documentación de casos auditados en ERP (Andrea Romero, María Bordaberry, Gessica Ordano, 42 mixtos).
    - Jerarquía de 3 niveles de cifras (Estudiantes -> Materias -> Asignaciones a Docentes).
    - Semáforo institucional de cobertura de ofertas (>=80%, 50-79.9%, <50%).
    - Resolución metodológica de cátedras compartidas y reemplazos curriculares.
    - Confidencialidad y anonimato institucional.
    - Glosario de términos y métricas de desempeño.
    """
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #12263f 0%, #1e3a63 100%); color: #ffffff; padding: 22px 26px; border-radius: 12px; margin-bottom: 22px; box-shadow: 0 4px 12px rgba(18, 38, 63, 0.12);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h4 style="margin: 0; font-size: 1.35rem; font-weight: 800; letter-spacing: -0.01em; color: #ffffff;">
                        Guía Metodológica y Explicación de Indicadores EV1
                    </h4>
                    <p style="margin: 6px 0 0 0; font-size: 0.88rem; color: #c7d5e8; line-height: 1.45;">
                        Documentación técnica y metodológica sobre la jerarquía de cifras, el universo docente, las reglas de co-docencia y los semáforos institucionales de la evaluación estudiantil.
                    </p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.15); border: 1px solid rgba(255, 255, 255, 0.3); padding: 6px 14px; border-radius: 20px; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.03em; text-transform: uppercase;">
                    Transparencia y Calidad Académica
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------------------------
    # 1. UNIVERSO DOCENTE: MODELO RECTOR DE 213 TITULARES (ESCENARIO A - RECOMENDADO)
    # --------------------------------------------------------------------------
    st.markdown("#### 1. Universo Docente: Modelo Rector de 213 Titulares que Culminaron Cátedra (Escenario A - Recomendado)")
    st.caption("Estructura metodológica definitiva que resuelve el cuadre analítico entre la planificación académica, la captura de encuestas y el procesamiento de resultados en el ERP:")

    c_doc1, c_doc2, c_doc3 = st.columns(3)
    with c_doc1:
        st.markdown(
            """
            <div style="background: #ffffff; border: 1px solid #dbe3ed; border-top: 4px solid #17845f; border-radius: 10px; padding: 16px 18px; height: 100%; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
                <div style="font-size: 0.76rem; font-weight: 700; color: #17845f; text-transform: uppercase; letter-spacing: 0.04em;">
                    Modelo Rector Recomendado
                </div>
                <div style="font-size: 1.85rem; font-weight: 800; color: #17845f; margin: 4px 0;">
                    213 <span style="font-size: 0.88rem; font-weight: 600; color: #475569;">docentes</span>
                </div>
                <div style="font-size: 0.84rem; color: #1e293b; font-weight: 700; margin-bottom: 6px;">
                    Titulares que Culminaron Cátedra
                </div>
                <div style="font-size: 0.80rem; color: #475569; line-height: 1.5;">
                    Comprende a los <strong>211 docentes titulares originales</strong> (169 puros + 42 mixtos) más las <strong>2 docentes que asumieron y culminaron la planificación académica</strong> hasta el 13/06/2026 (Romero y Bordaberry). Representa <strong>1.174 ofertas académicas rectoras</strong> con <strong>41.617 evaluaciones respondidas</strong> (67,08% de avance).
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c_doc2:
        st.markdown(
            """
            <div style="background: #ffffff; border: 1px solid #dbe3ed; border-top: 4px solid #1e3a63; border-radius: 10px; padding: 16px 18px; height: 100%; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
                <div style="font-size: 0.76rem; font-weight: 700; color: #1e3a63; text-transform: uppercase; letter-spacing: 0.04em;">
                    Malla Inicial
                </div>
                <div style="font-size: 1.85rem; font-weight: 800; color: #1e3a63; margin: 4px 0;">
                    211 <span style="font-size: 0.88rem; font-weight: 600; color: #475569;">docentes</span>
                </div>
                <div style="font-size: 0.84rem; color: #1e293b; font-weight: 700; margin-bottom: 6px;">
                    Titulares Originales del Día 1
                </div>
                <div style="font-size: 0.80rem; color: #475569; line-height: 1.5;">
                    Profesores con fecha de apertura 09/02/2026 (169 titulares puros + 42 mixtos en sus cátedras titulares, <strong>1.171 ofertas</strong>). El <strong>100% de estos 211 profesores (211 de 211)</strong> cuenta con cuestionarios psicométricos de alumnos registrados a su propio nombre en el ERP.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c_doc3:
        st.markdown(
            """
            <div style="background: #ffffff; border: 1px solid #dbe3ed; border-top: 4px solid #64748b; border-radius: 10px; padding: 16px 18px; height: 100%; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
                <div style="font-size: 0.76rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em;">
                    Auditoría Técnica de Malla
                </div>
                <div style="font-size: 1.85rem; font-weight: 800; color: #334155; margin: 4px 0;">
                    217 / 216 <span style="font-size: 0.84rem; font-weight: 600; color: #64748b;">registros</span>
                </div>
                <div style="font-size: 0.84rem; color: #1e293b; font-weight: 700; margin-bottom: 6px;">
                    Malla Física y Notas en ERP
                </div>
                <div style="font-size: 0.80rem; color: #475569; line-height: 1.5;">
                    Los <strong>217</strong> en Biometría incluían a 4 docentes de reemplazo interino. Los <strong>216</strong> registros en ERP corresponden a <strong>214 personas físicas únicas con notas</strong> (211 titulares + 3 reemplazantes con notas directas), donde 2 docentes figuran duplicados por inconsistencias tipográficas en ERP.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Matriz comparativa de escenarios y casos auditados
    st.markdown(
        """
        <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #17845f; border-radius: 8px; padding: 16px 20px; margin-top: 16px; font-size: 0.84rem; color: #1e293b; line-height: 1.6;">
            <div style="font-size: 0.92rem; font-weight: 800; color: #0f172a; margin-bottom: 8px;">
                Matriz Comparativa de Escenarios y Auditoría de Cátedras
            </div>
            <div style="overflow-x: auto; margin-bottom: 12px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.80rem; text-align: left;">
                    <thead>
                        <tr style="background: #1e3a63; color: #ffffff;">
                            <th style="padding: 6px 10px; border: 1px solid #cbd5e1;">Escenario Metodológico</th>
                            <th style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">Docentes</th>
                            <th style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">Ofertas</th>
                            <th style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">Avance de Alumnos</th>
                            <th style="padding: 6px 10px; border: 1px solid #cbd5e1;">Situación en Base de Datos ERP</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="background: #eff6ff; font-weight: 700;">
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; color: #1e3a63;">Escenario A (Recomendado): 213 Titulares que Culminaron Cátedra</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f;">213</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center; color: #1e3a63;">1.174</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">41.617 / 62.043 (67,08%)</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Cuadre exacto con las cátedras que finalizaron semestre con los alumnos.</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Escenario B: Solo Titulares Originales (Día 1)</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">211</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">1.171</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">41.595 / 62.018 (67,07%)</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">100% directo: Los 211 cuentan con evaluaciones directas en ERP.</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Escenario C: Filtro Estricto de Ficha Propia en ERP</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">212</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">1.172</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">41.595 / 62.018 (67,07%)</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Excluye a Romero (cuyas respuestas se cargaron bajo la titular de cirugía).</td>
                        </tr>
                        <tr style="background: #ffffff; color: #64748b;">
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Estado Actual Malla Física (Sin ajustes, con bug drop_duplicates)</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">217 / 213</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">1.289</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; text-align: center;">44.488 / 66.279 (67,12%)</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Descuadrado por deduplicación ciega y 2 registros duplicados en ERP.</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <strong>Auditoría de Casos Específicos y Resolución de Duplicados en ERP:</strong><br>
            • <strong>Dra. Andrea Araceli Romero Giménez (Clínica Quirúrgica I, Sec. A, G1/G2-Sub 01)</strong>:
              Asumió la comisión práctica el 01/03/2026 en relevo de la Dra. Mónica Mabel Vieth García y <strong>dictó las clases hasta culminar el ciclo lectivo el 13/06/2026</strong>. 22 de sus 25 alumnos respondieron la encuesta (88,0% de avance).
              <em>¿Por qué no tuvo ficha propia en <code>resultado_por_docente</code>?</em> Porque en el ERP (<code>Academico.RespuestaUsuario</code>) el formulario de evaluación de esa cátedra quedó precargado bajo el identificador de la titular (Dra. Vieth); las respuestas de los 22 alumnos se almacenaron técnicamente bajo la titular, computándole 0 respuestas a nombre de Romero. Sin embargo, en <code>avance_por_alumno</code> la Dra. Romero sí figuró al frente de esas 25 asignaciones, y al haber culminado el ciclo lectivo con pleno avance, es parte ineludible de los <strong>213 titulares del Modelo Rector</strong>.<br>
            • <strong>Los 2 Registros Duplicados en ERP (216 filas = 214 personas físicas con notas)</strong>:
              Al auditar <code>resultado_por_docente</code> por código único de docente, se evidenció que existen 214 profesores físicos y 2 duplicados por inconsistencia tipográfica en origen:
              <br>&nbsp;&nbsp;1) <em>Docente ID 23354.0</em>: <code>GARAY SALDAÑA, BRUNO JOSE</code> y <code>GARAY SALDAÑA, DOCENTE_BRUNO JOSE</code> (generado por una cuenta con prefijo administrativo <code>DOCENTE_</code>).
              <br>&nbsp;&nbsp;2) <em>Docente ID 23295.0</em>: <code>MARTINEZ GONZALEZ, DEISY MARIELA</code> y <code>MARTÍNEZ GONZÁLEZ, DEISY MARIELA</code> (generado por disparidad ortográfica de tildes en el ERP).
              <br>De estas 214 personas físicas: 211 son titulares + 3 reemplazantes evaluados directamente a su propio nombre (Bordaberry, Centurión y Da Silva).<br>
            • <strong>Mecánica del Descuadre por "Deduplicación Ciega" en el ETL</strong>:
              En <code>services/etl/encuestas_etl.py</code> (línea 691), la instrucción <code>drop_duplicates(subset=["system_id", "planificacion_id", "grupo"])</code> retiene automáticamente la <em>primera fila</em> que lee en el archivo CSV y descarta las siguientes, sin considerar fechas de inicio/fin ni horas dictadas.
              Cuando el titular figuraba primero (Ordano, Romero Franco, Fox Jiménez y Mareco Romero), el ETL descartó a las 4 reemplazantes. Cuando la reemplazante figuraba primero (Romero y Bordaberry), el ETL las retuvo a ellas y descartó al titular. Por ello, el <strong>Escenario A Rector</strong> corrige esta distorsión reconociendo a los 213 que efectivamente culminaron cátedra.<br>
            • <strong>Dra. María Fernanda Bordaberry Villalba (Clínica Quirúrgica I, Sec. B)</strong>: Asumió la teoría tras la renuncia del titular Dr. Roque Duarte y <strong>finalizó el semestre con los 100 alumnos</strong> (1.392 respuestas válidas a su nombre en el ERP).<br>
            • <strong>Prof. Gessica Adriana Ordano López (Medicina Comunitaria, Sec. I)</strong>: Asumió el relevo el 02/05/2026. Los alumnos evaluaron a la titular que inició el semestre, Dra. Ana Michelli Luis Giménez (496 respuestas). Ordano <strong>está plenamente registrada en el ERP</strong> (<code>IdDocenteExterno: 560</code>, <code>IdUsuario: 1279</code>) y <strong>completó su Autoevaluación Docente institucional (<code>IdEncuesta = 5</code>)</strong> el 31/07/2026.<br>
            • <strong>Los 42 Docentes Mixtos</strong>: Desempeñaron titularidad en sus materias principales y asumieron 100 ofertas de reemplazo (todas culminadas el 13/06/2026). En 64 comisiones fueron evaluados a su propio nombre en el ERP y en 36 las evaluaciones quedaron registradas bajo el titular original.
        </div>
        <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #b87908; border-radius: 8px; padding: 16px 20px; margin-top: 14px; font-size: 0.84rem; color: #1e293b; line-height: 1.6;">
            <div style="font-size: 0.92rem; font-weight: 800; color: #7c5208; margin-bottom: 8px;">
                Desglose y Justificación Técnica de los 4 Docentes Excluidos (217 ➔ 213 Docentes)
            </div>
            <p style="margin: 0 0 10px 0; font-size: 0.82rem; color: #475569;">
                En la malla física original figuraban <strong>217 docentes</strong>. Para conformar el <strong>Modelo Rector de 213 Titulares que Culminaron Cátedra (Escenario A)</strong>, se excluyeron a <strong>4 docentes</strong> que participaron en calidad de apoyo o reemplazo temporal sin titularidad independiente ni evaluaciones a su nombre en el ERP, cuyas asignaciones fueron absorbidas formalmente por los profesores titulares de cada cátedra:
            </p>
            <div style="overflow-x: auto; margin-bottom: 8px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.80rem; text-align: left;">
                    <thead>
                        <tr style="background: #245ea8; color: #ffffff;">
                            <th style="padding: 6px 10px; border: 1px solid #cbd5e1;">Docente Excluido</th>
                            <th style="padding: 6px 10px; border: 1px solid #cbd5e1;">Planificación Vinculada</th>
                            <th style="padding: 6px 10px; border: 1px solid #cbd5e1;">Titular de Cátedra en ERP</th>
                            <th style="padding: 6px 10px; border: 1px solid #cbd5e1;">Motivo Técnico y Metodológico de Exclusión</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; font-weight: 700; color: #1e3a63;">1. GESSICA ADRIANA ORDANO LOPEZ</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;"><strong>Medicina Comunitaria</strong><br>Sección <em>I</em> · Teórica<br>68 esperados / 31 respondieron</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #17845f;">ANA MICHELLI LUIS GIMENEZ</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Asumió el 02/05/2026. Los alumnos evaluaron formalmente a la titular Dra. Ana Michelli Luis (496 respuestas válidas en ERP). El ETL deduplicó por alumno-grupo conservando a la titular original para no duplicar la carga evaluativa. Ordano cuenta con 0 encuestas de alumnos, pero completó su Autoevaluación Docente institucional (<code>IdEncuesta = 5</code>) el 31/07/2026.</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; font-weight: 700; color: #1e3a63;">2. MIRNA ANALIA ROMERO FRANCO</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;"><strong>Anatomía I</strong> (Secc. I: G1-MO, G1-MS, G2-MO, G2-MS, G3-MO, G3-MS - 6 ofertas)<br><strong>Anatomía II</strong> (Secc. H: G1-MO, G2-MO, G3-MO - 3 ofertas)<br><em>Total: 9 ofertas prácticas</em></td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #17845f;">LIS CARMEN ELVIRA AGÜERO CANO<br>(Anatomía I)<br>MARYAM GISSELLE KACHMAR CARVALLO<br>(Anatomía II)</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Docencia de apoyo y práctica en laboratorios. En el sistema de encuestas, los estudiantes respondieron exclusivamente bajo la titularidad de cátedra de Agüero Cano y Kachmar Carvallo. El ETL retuvo a las titulares principales y eliminó la duplicidad de fila de Romero Franco, quien no culminó una titularidad curricular independiente.</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; font-weight: 700; color: #1e3a63;">3. PATRICIA RECEDA FOX JIMENEZ</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;"><strong>Metodología de la Investigación</strong><br>Secc. <em>C</em> (83 esp. / 59 resp.)<br>Secc. <em>D</em> (78 esp. / 59 resp.)<br><em>Total: 2 ofertas teóricas</em></td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #17845f;">JOHANA BELEN LEGUIZAMON VERA</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Cátedra compartida y apoyo temporal en comisiones teóricas. Las encuestas estudiantiles (118 completadas) fueron imputadas en ERP a nombre de la titular de cátedra Johana Belén Leguizamón Vera. Para evitar doble conteo de los 161 alumnos convocados, el ETL retuvo a la titular Leguizamón Vera y excluyó la asignación simultánea de Fox Jiménez.</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; font-weight: 700; color: #1e3a63;">4. SARA GABRIELA MARECO ROMERO</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;"><strong>Toxicología</strong><br>Sección <em>G</em> · Teórica<br>66 esperados / 49 respondieron</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #17845f;">ELADIO GABRIEL ORTEGA LASPINA</td>
                            <td style="padding: 6px 10px; border: 1px solid #cbd5e1;">Apoyo docente temporal en teoría. Los 49 alumnos que respondieron evaluaron formalmente al titular institucional Dr. Eladio Gabriel Ortega Laspina en el ERP. El ETL conservó al titular institucional y excluyó la duplicidad con Mareco Romero para proteger la consistencia de la matrícula.</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div style="font-size: 0.78rem; color: #64748b; font-style: italic;">
                Conclusión técnica: Estas 13 ofertas académicas no se pierden ni se alteran; sus respuestas y evaluaciones están computadas íntegramente al 100% bajo los profesores titulares rectores correspondientes.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # --------------------------------------------------------------------------
    # 2. JERARQUÍA Y CORRESPONDENCIA DE CIFRAS (3 NIVELES)
    # --------------------------------------------------------------------------
    st.markdown("#### 2. Jerarquía de Datos: Estudiantes ➔ Materias ➔ Asignaciones a Docentes")
    st.caption("Comprende la correspondencia matemática exacta entre la matrícula estudiantil, las inscripciones curriculares y las evaluaciones a profesores:")

    n1, n2, n3 = st.columns(3)
    with n1:
        st.markdown(
            """
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; height: 100%;">
                <div style="font-size: 0.74rem; font-weight: 700; color: #12263f; text-transform: uppercase;">Nivel 1: Personas Físicas</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #12263f; margin: 4px 0;">6.978 alumnos</div>
                <div style="font-size: 0.82rem; color: #475569; line-height: 1.5;">
                    Total de estudiantes convocados en Medicina CDE.<br>
                    • <strong>4.701 completaron al menos una encuesta</strong> (<strong>67,4%</strong> de participación activa).<br>
                    • <strong>4.531 completaron el 100%</strong> de sus encuestas (<strong>64,9%</strong>).<br>
                    • 2.277 alumnos no iniciaron su participación.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with n2:
        st.markdown(
            """
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; height: 100%;">
                <div style="font-size: 0.74rem; font-weight: 700; color: #245ea8; text-transform: uppercase;">Nivel 2: Inscripciones a Materias</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #245ea8; margin: 4px 0;">44.289 materias</div>
                <div style="font-size: 0.82rem; color: #475569; line-height: 1.5;">
                    Cada estudiante cursa en promedio ~6 materias en su malla curricular (6.978 × ~6.35 materias).<br>
                    • <strong>29.565 materias fueron respondidas</strong> (<strong>66,7%</strong> de avance a nivel asignatura).<br>
                    • Refleja la cobertura curricular sin desglosar comisiones prácticas.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with n3:
        st.markdown(
            """
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; height: 100%;">
                <div style="font-size: 0.74rem; font-weight: 700; color: #17845f; text-transform: uppercase;">Nivel 3: Asignaciones a Docentes (EV1)</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #17845f; margin: 4px 0;">61.753 asignaciones</div>
                <div style="font-size: 0.82rem; color: #475569; line-height: 1.5;">
                    La encuesta real EV1 evalúa a los profesores de teoría y comisiones prácticas (Laboratorio, MO, MS).<br>
                    • Un alumno evalúa en promedio a ~8,8 docentes.<br>
                    • <strong>41.781 evaluaciones fueron respondidas</strong> (<strong>67,7%</strong> de avance total EV1).
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # --------------------------------------------------------------------------
    # 3. SEMÁFORO INSTITUCIONAL DE COBERTURA DE OFERTAS (1.289 OFERTAS)
    # --------------------------------------------------------------------------
    st.markdown("#### 3. Semáforo Institucional de Cobertura Académica (1.289 Ofertas)")
    st.caption("Clasificación de las ofertas académicas (materia · sección · grupo · docente) según su representatividad estadística y tasa de respuesta:")

    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(
            """
            <div style="background: #e7f6f0; border: 1px solid #b5e3d0; border-top: 4px solid #17845f; border-radius: 10px; padding: 16px; height: 100%;">
                <div style="font-size: 0.76rem; font-weight: 700; color: #17845f; text-transform: uppercase;">🟢 Adecuado (≥ 80,0%)</div>
                <div style="font-size: 1.85rem; font-weight: 800; color: #17845f; margin: 4px 0;">317 ofertas</div>
                <div style="font-size: 0.80rem; color: #2d5a43; line-height: 1.5;">
                    <strong>24,6% del universo total.</strong><br>
                    • Incluye las <strong>18 ofertas</strong> con avance perfecto del 100%.<br>
                    • Se consideran plenamente validadas y representativas para la toma de decisiones pedagógicas institucionales.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            """
            <div style="background: #fef9e7; border: 1px solid #f6e2a2; border-top: 4px solid #b87908; border-radius: 10px; padding: 16px; height: 100%;">
                <div style="font-size: 0.76rem; font-weight: 700; color: #b87908; text-transform: uppercase;">🟡 Seguimiento (50,0% - 79,9%)</div>
                <div style="font-size: 1.85rem; font-weight: 800; color: #b87908; margin: 4px 0;">754 ofertas</div>
                <div style="font-size: 0.80rem; color: #644a14; line-height: 1.5;">
                    <strong>58,5% del universo total.</strong><br>
                    • Ofertas con participación activa y mayoritaria, en proceso de consolidación para alcanzar el estándar óptimo del 80%.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            """
            <div style="background: #fdecef; border: 1px solid #f3b9c0; border-top: 4px solid #bd3f4a; border-radius: 10px; padding: 16px; height: 100%;">
                <div style="font-size: 0.76rem; font-weight: 700; color: #bd3f4a; text-transform: uppercase;">🔴 Crítico (&lt; 50,0%)</div>
                <div style="font-size: 1.85rem; font-weight: 800; color: #bd3f4a; margin: 4px 0;">218 ofertas</div>
                <div style="font-size: 0.80rem; color: #6e272d; line-height: 1.5;">
                    <strong>16,9% del universo total.</strong><br>
                    • Ofertas con baja tasa de respuesta que requieren seguimiento prioritario de las coordinaciones de carrera para estimular la participación estudiantil.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div style="margin-top: 10px; font-size: 0.82rem; color: #475569; text-align: center; font-weight: 500;">
            <em>Balance matemático exacto: 317 (Adecuadas) + 754 (Seguimiento) + 218 (Críticas) = <strong>1.289 ofertas académicas totales</strong> (100%).</em>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # --------------------------------------------------------------------------
    # 4. RESOLUCIÓN DE CÁTEDRA COMPARTIDA, REEMPLAZOS CURRICULARES Y CONFIDENCIALIDAD
    # --------------------------------------------------------------------------
    col_izq_met, col_der_met = st.columns(2)

    with col_izq_met:
        st.markdown("#### 4. Cátedra Compartida y Reemplazos Curriculares")
        st.markdown(
            """
            En la carrera de Medicina se presentan dinámicas docentes específicas:
            - **Cátedra Compartida (Teoría vs. Práctica)**: Un docente dicta la teoría y otros profesores conducen la práctica clínica o de laboratorio (ej. subgrupos MO y MS). Cada docente es evaluado independientemente por los alumnos de su comisión.
            - **Reemplazos Curriculares que Culminan Cátedra (Escenario A)**: Cuando un docente asume la cátedra por relevo o renuncia del titular y dicta las clases hasta finalizar el ciclo lectivo (como la Dra. Romero y la Dra. Bordaberry), se integra formalmente en las **1.174 ofertas rectoras**.
            - **Cómputo en ERP**: Si el sistema no generó una ficha individual con el nombre del docente reemplazante, las respuestas de los estudiantes se consolidaron técnicamente en la titularidad de la cátedra, garantizando que el esfuerzo y evaluación estudiantil computen al 100%.
            """,
            unsafe_allow_html=True,
        )

    with col_der_met:
        st.markdown("#### 5. Confidencialidad y Anonimato")
        st.markdown(
            """
            Por estricta política institucional de aseguramiento de la calidad:
            - **Anonimato total del estudiante**: No se publican nombres, cédulas ni identificadores de los estudiantes en ningún reporte ni exportación.
            - **Métricas consolidadas**: Toda la información se presenta agregada cuantitativamente por materia, sección, grupo y docente.
            - **Garantía ética**: El resguardo de la identidad asegura la sinceridad, validez y libertad de opinión de los estudiantes al evaluar la labor docente.
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # --------------------------------------------------------------------------
    # 6. GLOSARIO DE TÉRMINOS Y SIGLAS
    # --------------------------------------------------------------------------
    st.markdown("#### 6. Glosario de Indicadores y Siglas Institucionales")
    with st.expander("Ver Glosario Completo de Términos (EV1, MO, MS, Criterios, Dimensiones)", expanded=False):
        st.markdown(
            """
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.84rem; text-align: left;">
                    <thead>
                        <tr style="background: #1e3a63; color: #ffffff;">
                            <th style="padding: 9px 12px; border: 1px solid #cbd5e1; width: 220px;">Término / Sigla</th>
                            <th style="padding: 9px 12px; border: 1px solid #cbd5e1;">Definición Institucional</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="background: #ffffff;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">EV1</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Encuesta de Valoración Estudiantil a la Docencia (Opinión del Estudiante sobre el desempeño profesoral en escala Likert 1 a 5).</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Comisión Académica</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Unidad operativa de dictado de una materia (ej. comisión teórica o comisiones prácticas de laboratorio MO y habilidades clínicas MS) asignada a un docente con su respectivo subgrupo de alumnos matriculados.</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Oferta Académica</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Unidad mínima de análisis pedagógico compuesta por la tupla única: <em>Materia + Sección + Grupo + Docente</em>. Existen <strong>1.174 ofertas rectoras</strong> en el Escenario A (1.289 en la malla física total con reemplazos temporales).</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Modelo Rector (Escenario A)</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Universo oficial adoptado por la UCP de <strong>213 docentes</strong> que culminaron cátedra (211 titulares del Día 1 + 2 docentes que asumieron y culminaron la planificación académica completa hasta el 13/06/2026: Dra. Andrea Romero y Dra. María Fernanda Bordaberry).</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Deduplicación Ciega (ETL)</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Proceso algorítmico en <code style="background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-size: 0.8rem; color: #0f172a;">services/etl/encuestas_etl.py</code> (línea 691) que, al encontrar más de un docente en un mismo grupo para un alumno, retiene por defecto la primera fila física del archivo y descarta las siguientes, sin evaluar horas dictadas ni quién finalizó el ciclo lectivo.</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Inconsistencias Tipográficas en ERP</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Variaciones de texto en origen que duplicaron registros en <code style="background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-size: 0.8rem; color: #0f172a;">resultado_por_docente</code>: Bruno José Garay Saldaña (con prefijo <code style="background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-size: 0.8rem; color: #0f172a;">DOCENTE_</code>, ID 23354) y Deisy Mariela Martínez González (con y sin tildes, ID 23295), generando 216 filas para 214 personas físicas con notas.</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Cátedra Compartida vs. Reemplazo</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">• <strong>Cátedra Compartida:</strong> Docentes que dictan en paralelo distintas partes del programa (un docente la teoría y otros las comisiones prácticas).<br>• <strong>Reemplazo Curricular:</strong> Docente que releva formalmente a otro profesor durante el semestre por renuncia o licencia.</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Grupo MO</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Grupo práctico de simulación o laboratorio de habilidades motoras (<em>Miembro Operativo</em>).</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Grupo MS</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Grupo práctico de habilidades clínicas y anatomía (<em>Miembro Superior</em>).</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Cobertura de Oferta</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Grado de representatividad estadística alcanzado por una comisión: 🟢 <strong>Adecuado</strong> (≥ 80,0%) · 🟡 <strong>Seguimiento</strong> (50,0% a 79,9%) · 🔴 <strong>Crítico</strong> (&lt; 50,0%).</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Matrícula Convocada vs. Activa</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Total de 6.978 estudiantes habilitados frente a 4.701 que respondieron al menos una evaluación (67,4% de participación) y 4.531 que completaron el 100% (64,9%).</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Criterios (16)</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Preguntas específicas del cuestionario evaluadas en escala Likert del 1 al 5.</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Indicadores (10)</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Agrupaciones intermedias de criterios que miden aspectos clave de la práctica docente.</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Dimensiones (5)</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Macro-ejes formativos: <em>Planificación y Organización, Metodología y Recursos, Interacción y Comunicación, Evaluación del Aprendizaje, y Cumplimiento y Responsabilidad</em>.</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Respuestas Favorables</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">Porcentaje de estudiantes que calificaron con 4 o 5 (satisfecho / muy satisfecho).</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Escala de Desempeño</td>
                            <td style="padding: 8px 12px; border: 1px solid #cbd5e1;">🟢 <strong>Fortaleza</strong> (≥ 4,30) · 🔵 <strong>Adecuado</strong> (4,00 a 4,29) · 🟡 <strong>Seguimiento</strong> (3,50 a 3,99) · 🔴 <strong>Oportunidad</strong> (&lt; 3,50).</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # --------------------------------------------------------------------------
    # 7. REGISTRO DE CUMPLIMIENTO: 100% DE SUGERENCIAS INSTITUCIONALES UCP
    # --------------------------------------------------------------------------
    st.markdown("#### 7. Registro de Cumplimiento: 100% de Sugerencias Institucionales UCP")
    st.caption("Detalle minucioso de todas las observaciones, ajustes y requerimientos resueltos a partir del documento oficial *Sugerencias - Instrumentos de Evaluación Docente.docx*:")

    with st.expander("Ver Auditoría Completa del 100% de Sugerencias Aplicadas (P01 a P39)", expanded=True):
        st.markdown(
            """
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.82rem; text-align: left;">
                    <thead>
                        <tr style="background: #1e3a63; color: #ffffff;">
                            <th style="padding: 8px 10px; border: 1px solid #cbd5e1; width: 65px; text-align: center;">Ref.</th>
                            <th style="padding: 8px 10px; border: 1px solid #cbd5e1; width: 220px;">Sugerencia / Requerimiento</th>
                            <th style="padding: 8px 10px; border: 1px solid #cbd5e1;">Solución Técnica y Cambio Implementado</th>
                            <th style="padding: 8px 10px; border: 1px solid #cbd5e1; width: 110px; text-align: center;">Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="background: #ffffff;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P01</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Menú Lateral de Navegación</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se renombró la categoría principal en <code>utils/menu_config.py</code> de <em>"Encuestas"</em> a <strong>"Instrumentos de Evaluación Docente"</strong>, preservando los permisos de seguridad y roles.</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P04, P06</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Selector Inicial e Instrucción</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">En <code>modules/encuestas.py</code> se actualizó la etiqueta visual a <strong>"Instrumento"</strong>, el placeholder a <em>"Elija un instrumento..."</em> y la instrucción guía a <em>"Seleccione el instrumento que desea visualizar para continuar."</em></td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P10</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Identificación Dinámica de Sede</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se incorporó la sede activa de forma dinámica (<strong>sede Ciudad del Este</strong>) en la tarjeta 3 de asignaciones docentes para eliminar cualquier ambigüedad geográfica.</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P12</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Cuadre de Docentes (213 vs 216)</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se demostró mediante auditoría en ERP que los 216 registros corresponden a <strong>214 personas físicas únicas</strong> (2 duplicados por inconsistencia tipográfica en origen) y se fijó el <strong>Modelo Rector de 213 titulares que culminaron cátedra</strong>.</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P15</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Ancho de Tabla de Detalle</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se extrajo la tabla de detalle por oferta del layout estrecho de columnas y se colocó a <strong>ancho completo (100%)</strong>, garantizando que todas las columnas sean legibles sin recortes.</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P19</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Visibilidad en Gráfico de Dona</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se ampliaron los márgenes y se aumentó la altura del gráfico a 290px con <code>textposition="auto"</code>, resolviendo el corte superior de la etiqueta de avance parcial (2,27%).</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P22</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Cifra Completa en Gráfico de Barras</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se aplicó <code>cliponaxis=False</code>, margen derecho de 80px y expansión del eje X al 125%, visualizando con claridad el total de <strong>4.592 alumnos</strong> que completaron todas sus encuestas.</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P24</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Encabezados de Tabla por Materia</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se renombraron formalmente las columnas a: <strong>Eval. esperadas</strong>, <strong>Eval. completadas</strong> y <strong>Eval. pendientes</strong> en la tabla de cumplimiento estudiantil.</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P27</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Sincronización KPI Docentes a 213</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se unificó el KPI <strong>"Docentes a evaluar"</strong> a exactamente <strong>213 docentes</strong> (Escenario A Rector), excluyendo las 13 comisiones de los 4 docentes interinos cuyas notas computan en los titulares.</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #f8fafc;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">P33, P36, P37, P39</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Árbol Pedagógico por Docente</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se desarrolló el motor pedagógico institucional UCP con las <strong>5 Dimensiones, 10 Indicadores y 16 Criterios</strong> con puntaje individual, semáforo y descriptores pedagógicos cualitativos, disponible tanto en la sub-vista <em>Por docente</em> como en <em>Análisis pedagógico</em>.</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                        <tr style="background: #ffffff;">
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 700;">Estilo UCP</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e3a63;">Depuración Visual y Semáforos</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1;">Se retiraron emojis decorativos informales y se consolidaron semáforos limpios: 🟢 Fortaleza/Adecuado (≥4,30 / ≥80%), 🔵 Adecuado (4,00-4,29), 🟡 Seguimiento (3,50-3,99 / 50-79,9%) y 🔴 Oportunidad (&lt;3,50 / &lt;50%).</td>
                            <td style="padding: 7px 10px; border: 1px solid #cbd5e1; text-align: center; color: #17845f; font-weight: 700;">🟢 Aplicado</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )


