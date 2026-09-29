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
    elif estado == "En proceso":
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
        .ev1-topbar {
            background-color: #12263f;
            color: #ffffff;
            padding: 16px 22px;
            border-radius: 10px;
            margin-bottom: 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .ev1-topbar h2 {
            margin: 0;
            font-size: 1.35rem;
            color: #ffffff;
            font-weight: 750;
        }
        .ev1-topbar p {
            margin: 4px 0 0 0;
            font-size: 0.86rem;
            color: #c7d5e8;
        }
        .ev1-badge-demo {
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 5px 12px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
        }
        .ev1-note {
            background-color: #eaf2fb;
            border-left: 4px solid #245ea8;
            padding: 11px 15px;
            border-radius: 8px;
            color: #1a4270;
            font-size: 0.86rem;
            margin-bottom: 15px;
        }
        .ev1-note-privacy {
            background-color: #f1eef9;
            border-left: 4px solid #7654a8;
            color: #4b3273;
        }
        .ev1-card-teacher {
            background-color: #12263f;
            color: #ffffff;
            padding: 22px;
            border-radius: 12px;
            text-align: center;
        }
        .ev1-card-teacher span {
            font-size: 0.78rem;
            color: #c7d5e8;
            display: block;
        }
        .ev1-card-teacher strong {
            font-size: 2.2rem;
            display: block;
            margin-top: 4px;
        }
        .ev1-criterio-box {
            background: #ffffff;
            border: 1px solid #dbe3ed;
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 12px;
        }
        .ev1-indicador-box {
            margin-top: 8px;
            background: #f6f8fb;
            border-left: 3px solid #3c7bc4;
            border-radius: 6px;
            padding: 8px 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- 1. BANNER INSTITUCIONAL EV1 ---
    st.markdown(
        f"""
        <div class="ev1-topbar">
            <div>
                <h2>EV1 · Opinión del Estudiante</h2>
                <p>ENCUESTA ALUMNOS A DOCENTES · Sede: {escape(str(sede))} · Periodo: {escape(str(periodo))} · Carrera: {escape(str(carrera))}</p>
            </div>
            <div class="ev1-badge-demo">
                Evaluación Docente · Cobertura y Resultados
            </div>
        </div>
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

    # --- 3. FILTROS DINÁMICOS SUPERIORES ---
    with st.expander("Filtros del Dashboard EV1", expanded=True):
        col_filtro1, col_filtro2, col_filtro3, col_filtro4, col_filtro5, col_filtro6 = st.columns(6)

        # Opciones únicas ordenadas
        lista_alumnos = ["Todos"] + sorted([str(a) for a in df_base["alumno"].dropna().unique() if str(a).strip()])
        lista_docentes = ["Todos"] + sorted([str(d) for d in df_base["docente"].dropna().unique() if str(d).strip()])
        lista_materias = ["Todas"] + sorted([str(m) for m in df_base["materia"].dropna().unique() if str(m).strip()])
        lista_secciones = ["Todas"] + sorted([str(s) for s in df_base["seccion"].dropna().unique() if str(s).strip()])
        lista_grupos = ["Todos"] + sorted([str(g) for g in df_base["grupo"].dropna().unique() if str(g).strip()])
        lista_estados = ["Todos", "Completada", "En proceso", "Pendiente"]

        with col_filtro1:
            sel_alumno = st.selectbox("Alumno", options=lista_alumnos, key="ev1_filtro_alumno")
        with col_filtro2:
            sel_docente = st.selectbox("Docente", options=lista_docentes, key="ev1_filtro_docente")
        with col_filtro3:
            sel_materia = st.selectbox("Materia", options=lista_materias, key="ev1_filtro_materia")
        with col_filtro4:
            sel_seccion = st.selectbox("Sección", options=lista_secciones, key="ev1_filtro_seccion")
        with col_filtro5:
            sel_grupo = st.selectbox("Grupo", options=lista_grupos, key="ev1_filtro_grupo")
        with col_filtro6:
            sel_estado = st.selectbox("Estado", options=lista_estados, key="ev1_filtro_estado")

    # Aplicación de los filtros sobre el conjunto de datos de asignaciones
    df_filtrado = df_base.copy()
    if sel_alumno != "Todos":
        df_filtrado = df_filtrado[df_filtrado["alumno"] == sel_alumno]
    if sel_docente != "Todos":
        df_filtrado = df_filtrado[df_filtrado["docente"] == sel_docente]
    if sel_materia != "Todas":
        df_filtrado = df_filtrado[df_filtrado["materia"] == sel_materia]
    if sel_seccion != "Todas":
        df_filtrado = df_filtrado[df_filtrado["seccion"] == sel_seccion]
    if sel_grupo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["grupo"] == sel_grupo]
    if sel_estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["estado"] == sel_estado]

    # --- 4. SUB-PESTAÑAS DE NAVEGACIÓN EV1 ---
    tab_avance, tab_alumno, tab_materia, tab_resultados, tab_docente, tab_pedagogico = st.tabs(
        [
            "Avance general",
            "Por alumno",
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
        _render_subvista_avance_general(df_filtrado, df_base)

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
        _render_subvista_por_docente(sede, periodo, carrera, tipo, df_filtrado, lista_docentes)

    # --------------------------------------------------------------------------
    # SUB-PESTAÑA 6: ANÁLISIS PEDAGÓGICO
    # --------------------------------------------------------------------------
    with tab_pedagogico:
        _render_subvista_analisis_pedagogico(sede, periodo, carrera, tipo)


# ==============================================================================
# SUB-VISTA 1: AVANCE GENERAL
# ==============================================================================

def _render_subvista_avance_general(df_filtrado: pd.DataFrame, df_total: pd.DataFrame):
    st.markdown(
        """
        <div class="ev1-note">
            Seguimiento de alumnos convocados y evaluaciones asignadas por cada combinación 
            <strong>alumno – materia – sección – grupo – docente</strong>. Los filtros actualizan el universo mostrado.
        </div>
        """,
        unsafe_allow_html=True,
    )

    total_esperadas = len(df_filtrado)
    alumnos_convocados = df_filtrado["alumno"].nunique() if total_esperadas > 0 else 0
    completadas = int((df_filtrado["estado"] == "Completada").sum())
    en_proceso = int((df_filtrado["estado"] == "En proceso").sum())
    pendientes = int((df_filtrado["estado"] == "Pendiente").sum())
    porcentaje_avance = (completadas / total_esperadas * 100.0) if total_esperadas > 0 else 0.0

    # Fila de KPIs principales
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        render_kpi_card("Alumnos convocados", f"{alumnos_convocados:,}".replace(",", "."), accent="#12263f", background="#f3f6fa", border="#dbe3ed")
    with kpi2:
        render_kpi_card("Evaluaciones esperadas", f"{total_esperadas:,}".replace(",", "."), accent="#245ea8", background="#eaf2fb", border="#c7d5e8")
    with kpi3:
        render_kpi_card("Evaluaciones completadas", f"{completadas:,}".replace(",", "."), accent="#17845f", background="#e7f6f0", border="#b5e3d0")
    with kpi4:
        render_kpi_card("Avance general", _formatear_porcentaje(porcentaje_avance), accent="#3c7bc4", background="#e8f0fe", border="#a9c6f5")

    st.caption(f"Detalle actual: **{en_proceso}** en proceso · **{pendientes}** pendientes")
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
            )
            fig_mat.update_traces(
                texttemplate="%{text:.1f}%",
                textposition="outside",
            )
            fig_mat.update_layout(
                height=max(220, len(resumen_materia) * 45),
                xaxis_title="Porcentaje de avance (%)",
                yaxis_title=None,
                coloraxis_showscale=False,
                margin=dict(l=10, r=40, t=10, b=10),
            )
            st.plotly_chart(fig_mat, use_container_width=True, key="ev1_grafico_materias")

        st.markdown("##### Detalle del universo de evaluación")
        if total_esperadas == 0:
            st.info("Sin registros.")
        else:
            df_tabla = df_filtrado[["alumno", "materia", "seccion", "grupo", "docente", "estado"]].copy()
            df_tabla.columns = ["Alumno", "Materia", "Sección", "Grupo", "Docente", "Estado"]
            st.dataframe(
                df_tabla,
                hide_index=True,
                width="stretch",
                key="ev1_tabla_universo",
            )

    with col_der:
        st.markdown("##### Avance global")
        abiertas = total_esperadas - completadas
        fig_donut = go.Figure(
            data=[
                go.Pie(
                    labels=["Completadas", "Abiertas"],
                    values=[completadas, abiertas],
                    hole=0.68,
                    marker=dict(colors=["#245ea8", "#e4eaf2"]),
                    textinfo="none",
                    sort=False,
                )
            ]
        )
        fig_donut.update_layout(
            height=240,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
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

        st.markdown("##### Estado de participación de alumnos")
        if total_esperadas > 0:
            resumen_alumnos = (
                df_filtrado.groupby("alumno")
                .agg(
                    total=("estado", "count"),
                    completadas=("estado", lambda s: (s == "Completada").sum()),
                    en_proceso=("estado", lambda s: (s == "En proceso").sum()),
                )
                .reset_index()
            )
            total_alu = len(resumen_alumnos)
            completaron_todo = int((resumen_alumnos["completadas"] == resumen_alumnos["total"]).sum())
            sin_iniciar = int(((resumen_alumnos["completadas"] == 0) & (resumen_alumnos["en_proceso"] == 0)).sum())
            parcial = total_alu - completaron_todo - sin_iniciar

            pct_todo = (completaron_todo / total_alu * 100.0) if total_alu > 0 else 0
            pct_parcial = (parcial / total_alu * 100.0) if total_alu > 0 else 0
            pct_sin = (sin_iniciar / total_alu * 100.0) if total_alu > 0 else 0

            st.write(f"**Completaron todo:** {completaron_todo} ({pct_todo:.1f}%)")
            st.progress(pct_todo / 100.0)
            st.write(f"**Avance parcial:** {parcial} ({pct_parcial:.1f}%)")
            st.progress(pct_parcial / 100.0)
            st.write(f"**Sin iniciar:** {sin_iniciar} ({pct_sin:.1f}%)")
            st.progress(pct_sin / 100.0)


# ==============================================================================
# SUB-VISTA 2: POR ALUMNO
# ==============================================================================

def _render_subvista_por_alumno(df_filtrado: pd.DataFrame):
    st.markdown(
        """
        <div class="ev1-note ev1-note-privacy">
            <strong>Protección del anonimato:</strong> El sistema permite identificar si una evaluación fue completada 
            por motivos de control y seguimiento operativo, pero las respuestas y puntajes otorgados permanecen 
            completamente anónimos y separados de la identidad del estudiante.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df_filtrado.empty:
        st.info("Sin registros de alumnos para los filtros actuales.")
        return

    # Cálculo por alumno
    resumen_alumnos = (
        df_filtrado.groupby("alumno")
        .agg(
            asignadas=("estado", "count"),
            completadas=("estado", lambda s: (s == "Completada").sum()),
            en_proceso=("estado", lambda s: (s == "En proceso").sum()),
            pendientes=("estado", lambda s: (s == "Pendiente").sum()),
        )
        .reset_index()
    )
    resumen_alumnos["avance"] = (resumen_alumnos["completadas"] / resumen_alumnos["asignadas"] * 100.0).round(1)

    def _clasificar_estado_alumno(row):
        if row["completadas"] == row["asignadas"]:
            return "Completo"
        elif row["completadas"] == 0 and row["en_proceso"] == 0:
            return "Sin iniciar"
        return "Parcial"

    resumen_alumnos["estado_alumno"] = resumen_alumnos.apply(_clasificar_estado_alumno, axis=1)

    total_alumnos = len(resumen_alumnos)
    c_completos = int((resumen_alumnos["estado_alumno"] == "Completo").sum())
    c_parcial = int((resumen_alumnos["estado_alumno"] == "Parcial").sum())
    c_sin_iniciar = int((resumen_alumnos["estado_alumno"] == "Sin iniciar").sum())
    promedio_asignadas = (resumen_alumnos["asignadas"].mean()) if total_alumnos > 0 else 0.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("Completaron todo", str(c_completos), accent="#17845f", background="#e7f6f0", border="#b5e3d0")
    with k2:
        render_kpi_card("Avance parcial", str(c_parcial), accent="#b87908", background="#fff5d9", border="#ecd496")
    with k3:
        render_kpi_card("Sin iniciar", str(c_sin_iniciar), accent="#bd3f4a", background="#fdecef", border="#f3b9c0")
    with k4:
        render_kpi_card("Promedio por alumno", f"{promedio_asignadas:.1f}".replace(".", ","), accent="#245ea8", background="#eaf2fb", border="#c7d5e8")

    st.markdown("##### Estado de los alumnos convocados")
    tabla_mostrar = resumen_alumnos.rename(
        columns={
            "alumno": "Alumno",
            "asignadas": "Asignadas",
            "completadas": "Completadas",
            "en_proceso": "En proceso",
            "pendientes": "Pendientes",
            "avance": "Avance %",
            "estado_alumno": "Estado",
        }
    )
    st.dataframe(
        tabla_mostrar,
        hide_index=True,
        width="stretch",
        column_config={
            "Avance %": st.column_config.ProgressColumn(
                "Avance %",
                min_value=0,
                max_value=100,
                format="%.1f%%",
            )
        },
        key="ev1_tabla_alumnos",
    )


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
        render_kpi_card("Materias distintas", str(n_materias), accent="#12263f", background="#f3f6fa", border="#dbe3ed")
    with k2:
        render_kpi_card("Docentes a evaluar", str(n_docentes), accent="#245ea8", background="#eaf2fb", border="#c7d5e8")
    with k3:
        render_kpi_card("Ofertas completas (100%)", str(ofertas_completas), accent="#17845f", background="#e7f6f0", border="#b5e3d0")
    with k4:
        render_kpi_card("Ofertas críticas (<50%)", str(ofertas_criticas), accent="#bd3f4a", background="#fdecef", border="#f3b9c0")

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
            "Avance %": st.column_config.ProgressColumn(
                "Avance %",
                min_value=0,
                max_value=100,
                format="%.1f%%",
            )
        },
        key="ev1_tabla_ofertas",
    )
    st.caption("Semáforo institucional sugerido: 🟢 Verde ≥ 80% · 🟡 Amarillo 50%–79,9% · 🔴 Rojo < 50%.")


# ==============================================================================
# SUB-VISTA 4: RESULTADOS EV1
# ==============================================================================

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

    # Intentar cargar resultados consolidados de parquet/DB
    fila_res = load_resultado_general(sede, periodo, carrera, tipo)
    df_dim = load_resultado_dimensiones(sede, periodo, carrera, tipo)
    df_doc = load_resultado_docentes(sede, periodo, carrera, tipo)

    # Valores de referencia si no hay parquet cargado aún
    promedio_ev1 = float(fila_res.get("promedio_general", 4.31)) if fila_res is not None else 4.31
    pct_fav = float(fila_res.get("pct_favorable", 84.0)) if fila_res is not None else 84.0
    pct_neu = float(fila_res.get("pct_neutral", 10.0)) if fila_res is not None else 10.0
    pct_desf = float(fila_res.get("pct_desfavorable", 6.0)) if fila_res is not None else 6.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("Promedio EV1", f"{promedio_ev1:.2f} / 5".replace(".", ","), accent="#12263f", background="#f3f6fa", border="#dbe3ed")
    with k2:
        render_kpi_card("Respuestas favorables (4-5)", _formatear_porcentaje(pct_fav), accent="#17845f", background="#e7f6f0", border="#b5e3d0")
    with k3:
        render_kpi_card("Respuestas neutrales (3)", _formatear_porcentaje(pct_neu), accent="#b87908", background="#fff5d9", border="#ecd496")
    with k4:
        render_kpi_card("Respuestas desfavorables (1-2)", _formatear_porcentaje(pct_desf), accent="#bd3f4a", background="#fdecef", border="#f3b9c0")

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
            )
        else:
            # Fallback con el catálogo pedagógico institucional
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
            )

        fig_dim.update_traces(
            marker_color="#245ea8",
            textposition="outside",
            texttemplate="%{text:.2f}",
        )
        fig_dim.update_layout(
            height=260,
            xaxis_title="Puntaje promedio (1 a 5)",
            yaxis_title=None,
            margin=dict(l=10, r=40, t=10, b=10),
        )
        st.plotly_chart(fig_dim, use_container_width=True, key="ev1_grafico_dimensiones")

        st.markdown("##### Resultado consolidado por docente")
        if df_doc is not None and not df_doc.empty:
            tabla_doc = df_doc[["docente", "promedio", "descriptor", "n_respuestas_validas"]].rename(
                columns={
                    "docente": "Docente",
                    "promedio": "Promedio",
                    "descriptor": "Lectura",
                    "n_respuestas_validas": "Respuestas",
                }
            )
        else:
            # Fallback con perfiles de referencia
            filas_doc = []
            for nombre, p in PERFILES_DOCENTES_REFERENCIA.items():
                filas_doc.append({
                    "Docente": nombre,
                    "Materia / grupo": p["meta"],
                    "Respuestas": 15,
                    "Promedio": p["score"],
                    "% Favorable": f"{p['fav']}%",
                    "Lectura": "🟢 Fortaleza" if p["score"] >= 4.4 else ("🔵 Adecuado" if p["score"] >= 4.1 else "🟡 Seguimiento"),
                })
            tabla_doc = pd.DataFrame(filas_doc)

        st.dataframe(tabla_doc, hide_index=True, width="stretch", key="ev1_tabla_res_docente")

    with col_der:
        st.markdown("##### Distribución de respuestas")
        st.caption("Participación porcentual según el valor de la escala Likert (1 a 5)")

        # Distribución de la escala
        dist_datos = pd.DataFrame({
            "Puntaje": ["1 (Muy en desc.)", "2 (En desac.)", "3 (Neutral)", "4 (De acuerdo)", "5 (Totalmente)"],
            "Porcentaje": [2.0, 4.0, 10.0, 38.0, 46.0],
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
        )
        fig_dist.update_traces(texttemplate="%{text:.0f}%", textposition="inside")
        fig_dist.update_layout(
            height=220,
            showlegend=False,
            xaxis_title="Porcentaje (%)",
            yaxis_title=None,
            margin=dict(l=10, r=20, t=10, b=10),
        )
        st.plotly_chart(fig_dist, use_container_width=True, key="ev1_grafico_distribucion")

        st.markdown("##### Lectura ejecutiva")
        st.markdown(
            """
            <div style="background: #ffffff; border: 1px solid #dbe3ed; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                <span style="font-size: 0.8rem; color: #65738a; font-weight: 600;">Mayor fortaleza</span><br>
                <strong style="color: #17845f; font-size: 1.05rem;">Dominio de la asignatura</strong>
                <p style="margin: 4px 0 0 0; font-size: 0.95rem; font-weight: 750;">4,58 / 5,00</p>
            </div>
            <div style="background: #ffffff; border: 1px solid #dbe3ed; border-radius: 10px; padding: 14px;">
                <span style="font-size: 0.8rem; color: #65738a; font-weight: 600;">Principal oportunidad de mejora</span><br>
                <strong style="color: #b87908; font-size: 1.05rem;">Retroalimentación pedagógica</strong>
                <p style="margin: 4px 0 0 0; font-size: 0.95rem; font-weight: 750;">4,08 / 5,00</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ==============================================================================
# SUB-VISTA 5: POR DOCENTE
# ==============================================================================

def _render_subvista_por_docente(sede, periodo, carrera, tipo, df_filtrado: pd.DataFrame, lista_docentes: list):
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

    docentes_disponibles = [d for d in lista_docentes if d != "Todos"]
    if not docentes_disponibles:
        docentes_disponibles = list(PERFILES_DOCENTES_REFERENCIA.keys())

    docente_elegido = st.selectbox(
        "Seleccione un docente para ver su análisis específico:",
        options=docentes_disponibles,
        key="ev1_docente_selector",
    )

    # Buscar perfil en datos de referencia o calcular
    if docente_elegido in PERFILES_DOCENTES_REFERENCIA:
        perfil = PERFILES_DOCENTES_REFERENCIA[docente_elegido]
        score_doc = perfil["score"]
        fav_doc = perfil["fav"]
        meta_doc = perfil["meta"]
        dims_doc = perfil["dims"]
    else:
        score_doc = 4.35
        fav_doc = 85
        meta_doc = f"Docente · {carrera}"
        dims_doc = [4.40, 4.20, 4.30, 4.15, 4.50]

    # Card principal de resumen docente
    col_card, col_meta = st.columns([1.0, 2.0])
    with col_card:
        st.markdown(
            f"""
            <div class="ev1-card-teacher">
                <span>Promedio del docente seleccionado</span>
                <strong>{_formatear_puntaje(score_doc)}</strong>
                <span>Escala Likert de 1 a 5</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_meta:
        st.markdown(f"### {escape(docente_elegido)}")
        st.caption(f"Asignaciones asociadas: **{escape(meta_doc)}**")
        st.write(f"**Respuestas favorables:** {fav_doc}%")
        st.progress(fav_doc / 100.0)

    st.divider()

    col_dim, col_ofertas = st.columns([1.2, 1.2])

    with col_dim:
        st.markdown("##### Desempeño por dimensión (Docente)")
        df_dim_doc = pd.DataFrame({
            "Dimensión": [d["corto"] for d in reversed(CATALOGO_PEDAGOGICO_EV1)],
            "Puntaje": list(reversed(dims_doc)),
        })
        fig_doc_dim = px.bar(
            df_dim_doc,
            x="Puntaje",
            y="Dimensión",
            orientation="h",
            text="Puntaje",
            range_x=[0, 5],
        )
        fig_doc_dim.update_traces(marker_color="#3c7bc4", textposition="outside", texttemplate="%{text:.2f}")
        fig_doc_dim.update_layout(height=260, margin=dict(l=10, r=40, t=10, b=10), xaxis_title="Puntaje", yaxis_title=None)
        st.plotly_chart(fig_doc_dim, use_container_width=True, key="ev1_grafico_doc_dim")

    with col_ofertas:
        st.markdown("##### Detalle de ofertas del docente")
        # Filtrar ofertas del docente en df_filtrado
        df_ofertas_doc = df_filtrado[df_filtrado["docente"] == docente_elegido]
        if not df_ofertas_doc.empty:
            resumen_ofertas_doc = (
                df_ofertas_doc.groupby(["materia", "seccion", "grupo"])
                .agg(
                    respuestas=("estado", lambda s: (s == "Completada").sum()),
                    total=("estado", "count"),
                )
                .reset_index()
            )
            resumen_ofertas_doc["Promedio"] = score_doc
            resumen_ofertas_doc = resumen_ofertas_doc.rename(
                columns={
                    "materia": "Materia",
                    "seccion": "Sección",
                    "grupo": "Grupo",
                    "respuestas": "Completadas",
                    "total": "Esperadas",
                }
            )
            st.dataframe(resumen_ofertas_doc, hide_index=True, width="stretch", key="ev1_tabla_doc_ofertas")
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

    df_cri_db = load_resultado_criterios(sede, periodo, carrera, tipo)
    mapa_puntajes_criterios = {}
    if df_cri_db is not None and not df_cri_db.empty and "orden" in df_cri_db.columns and "promedio" in df_cri_db.columns:
        for _, fila in df_cri_db.iterrows():
            try:
                num = int(fila["orden"])
                mapa_puntajes_criterios[num] = float(fila["promedio"])
            except (ValueError, TypeError):
                continue

    # Iteración por cada dimensión del catálogo pedagógico oficial
    for dim in CATALOGO_PEDAGOGICO_EV1:
        dim_score = dim["puntaje_referencia"]
        with st.expander(f"**{dim['nombre']}** — {_formatear_puntaje(dim_score)} / 5", expanded=(dim["id"] == 1)):
            for cri in dim["criterios"]:
                cri_num = cri["n"]
                # Usar valor real de la base de datos si existe, o valor de catálogo
                cri_score = mapa_puntajes_criterios.get(cri_num, cri["puntaje"])

                st.markdown(
                    f"""
                    <div class="ev1-criterio-box">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
                            <div style="font-weight: 650; font-size: 0.90rem; color: #17243a;">
                                Criterio {cri_num:02d}. {escape(cri['texto'])}
                            </div>
                            <div style="font-weight: 750; font-size: 1.05rem; color: #245ea8; white-space: nowrap;">
                                {_formatear_puntaje(cri_score)}
                            </div>
                        </div>
                        <div class="ev1-indicador-box">
                            <strong style="color: #245ea8; font-size: 0.82rem; display: block; margin-bottom: 2px;">
                                {escape(cri['indicador'])}
                            </strong>
                            <p style="margin: 0; color: #50617a; font-size: 0.80rem; line-height: 1.35;">
                                {escape(cri['descriptor'])}
                            </p>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
