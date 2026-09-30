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

    # Identificar si el usuario ha aplicado algún filtro en la pantalla
    filtros_activos = (
        sel_alumno != "Todos"
        or sel_docente != "Todos"
        or sel_materia != "Todas"
        or sel_seccion != "Todas"
        or sel_grupo != "Todos"
        or sel_estado != "Todos"
    )

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

    # Si no hay filtros aplicados y se dispone de la fila general oficial, usamos sus valores
    # consolidados para que coincidan 100% con la pestaña de Cobertura académica tanto en v1 como en v2.
    if not filtros_activos and fila_general is not None:
        alumnos_convocados = int(fila_general.get("alumnos_unicos_esperados", 0))
        total_esperadas = int(fila_general.get("encuestas_esperadas", 0))
        completadas = int(fila_general.get("encuestas_respondidas", 0))
        en_proceso = 0
        pendientes = int(fila_general.get("encuestas_pendientes", max(total_esperadas - completadas, 0)))
        porcentaje_avance = float(fila_general.get("porcentaje_avance_encuestas", 0.0))
    else:
        id_col = "system_id" if "system_id" in df_filtrado.columns else "alumno"
        if "system_id" in df_filtrado.columns and "planificacion_id" in df_filtrado.columns:
            pares_filtrados = df_filtrado.drop_duplicates(subset=["system_id", "planificacion_id"])
        else:
            pares_filtrados = df_filtrado

        total_esperadas = len(pares_filtrados)
        alumnos_convocados = pares_filtrados[id_col].nunique() if total_esperadas > 0 else 0
        completadas = int((pares_filtrados["estado"] == "Completada").sum()) if "estado" in pares_filtrados.columns else int((pares_filtrados["respondio"] == True).sum())
        en_proceso = int((pares_filtrados["estado"] == "En proceso").sum()) if "estado" in pares_filtrados.columns else 0
        pendientes = max(total_esperadas - completadas, 0)
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
            cols_mostrar = [c for c in ["alumno", "materia", "seccion", "grupo", "docente", "estado"] if c in df_filtrado.columns]
            df_tabla = df_filtrado[cols_mostrar].copy()
            df_tabla.columns = [c.capitalize() for c in cols_mostrar]
            st.dataframe(
                df_tabla,
                hide_index=True,
                width="stretch",
                key="ev1_tabla_universo",
            )

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
                    en_proceso=("estado", lambda s: (s == "En proceso").sum()),
                )
                .reset_index()
            )
            total_alu = len(resumen_alumnos)
            completaron_todo = int((resumen_alumnos["completadas"] == resumen_alumnos["total"]).sum())
            sin_iniciar = int(((resumen_alumnos["completadas"] == 0) & (resumen_alumnos["en_proceso"] == 0)).sum())
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

        st.dataframe(tabla_doc, hide_index=True, width="stretch", key="ev1_tabla_res_docente")

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
        fig_dist.update_traces(texttemplate="%{text:.1f}%", textposition="inside")
        fig_dist.update_layout(
            height=220,
            showlegend=False,
            xaxis_title="Porcentaje (%)",
            yaxis_title=None,
            margin=dict(l=10, r=20, t=10, b=10),
        )
        st.plotly_chart(fig_dist, use_container_width=True, key="ev1_grafico_distribucion")

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
            <div class="ev1-card-teacher">
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
        )
        fig_doc_dim.update_traces(marker_color="#3c7bc4", textposition="outside", texttemplate="%{text:.2f}")
        fig_doc_dim.update_layout(height=260, margin=dict(l=10, r=40, t=10, b=10), xaxis_title="Puntaje (1 a 5)", yaxis_title=None)
        st.plotly_chart(fig_doc_dim, use_container_width=True, key="ev1_grafico_doc_dim")

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
                    "Alumnos": st.column_config.NumberColumn("Alumnos", format="%d"),
                    "Respondieron": st.column_config.NumberColumn("Respondieron", format="%d"),
                    "Avance %": st.column_config.ProgressColumn(
                        "Avance %",
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                    ),
                },
                key="ev1_tabla_doc_ofertas",
            )
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
                nom = str(fila.get("indicador_nombre", ""))
                mapa_indicadores[nom] = {
                    "promedio": float(fila["promedio"]),
                    "descriptor": str(fila.get("descriptor", "")),
                }
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
                ind_info = mapa_indicadores.get(cri["indicador"], {})
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
                            <div style="font-weight: 750; font-size: 1.05rem; color: #245ea8; white-space: nowrap;">
                                {_formatear_puntaje(cri_score)}
                            </div>
                        </div>
                        <div class="ev1-indicador-box">
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

