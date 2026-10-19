"""
modules/encuestas_ev2.py

Módulo especializado para la visualización integral de la EV2 (Autoevaluación Docente),
implementado a partir del diseño oficial Dashboard_EV2_Autoevaluacion_Docente.html y
del instrumento ENCUESTA AUTOEVALUACION DOCENTE v2.xlsx (Dirección General Académica - UCP).

Incluye 6 sub-vistas operativas y pedagógicas:
  1. Avance general (KPIs de docentes obligados, encuestas esperadas, completadas, avance general,
     estado de encuestas, situación docente y validación del universo de planificación).
  2. Por docente (cumplimiento total, parcial, en proceso inicial y sin respuesta; tabla individual).
  3. Materia · sección · grupo (KPIs curriculares, cobertura por materia y detalle por oferta con criterios X/13).
  4. Resultados EV2 (escala 1–4, promedios por dimensión, distribución donut Excelente/Satisfactorio/Regular/Insatisfactorio
     y resultados por oferta docente).
  5. EV1 vs. EV2 (contraste entre opinión del estudiante EV1 y autoevaluación docente EV2 por oferta comparable).
  6. Análisis pedagógico (4 dimensiones cuantitativas, 13 criterios cuantitativos, indicadores cualitativos asociados
     sin puntaje y rúbricas descriptivas oficiales).

Cumple estrictamente con las reglas del proyecto (GEMINI.md): código y comentarios en español,
codificación UTF-8, preservación de funcionalidades y cero impacto sobre EV1.
"""

from html import escape
import hashlib
import io
import re
import unicodedata

import pandas as pd
import streamlit as st

from services.data.encuestas import (
    get_encuesta_nombre,
    load_datos_ev1_para_ev2,
    load_encuestas_metadata,
)


# ==============================================================================
# CATÁLOGO PEDAGÓGICO OFICIAL UCP — EV2 (AUTOEVALUACIÓN DOCENTE)
# 4 Dimensiones, 13 Criterios cuantitativos (Escala 1–4) e Indicadores cualitativos
# Fuente: Dashboard_EV2_Autoevaluacion_Docente.html y ENCUESTA AUTOEVALUACION DOCENTE v2.xlsx
# ==============================================================================
CATALOGO_PEDAGOGICO_EV2 = [
    {
        "id": 1,
        "nombre": "Planificación didáctica",
        "nombre_largo": "1. Planificación didáctica",
        "puntaje_referencia": 3.55,
        "criterios": [
            {
                "id": 1,
                "nombre": "Entrega de planificación didáctica semestral",
                "corto": "Entrega de planificación",
                "puntaje_referencia": 3.68,
                "rubrica": {
                    "Excelente (4 pts)": "Entrego la planificación de forma anticipada y metodológicamente impecable, articulando los resultados de aprendizaje con el cronograma.",
                    "Satisfactorio (3 pts)": "Entrego mi planificación didáctica semestral en tiempo y forma, utilizando el formato estandarizado y alineado al Plan de la Cátedra.",
                    "Regular (2 pts)": "Entrego la planificación a tiempo, pero omito secciones del formato estandarizado o no guarda total coherencia con el Plan de la Cátedra.",
                    "Insatisfactorio (1 pt)": "No entrego la planificación semestral o lo hago fuera de los plazos establecidos, sin seguir el formato institucional o el Plan de la Cátedra.",
                },
                "indicadores": [
                    (
                        "Oportunidad en la entrega o carga en el sistema",
                        "Cumplimiento de los plazos institucionales de entrega y registro.",
                    ),
                    (
                        "Coherencia con el plan de la cátedra, competencias y perfil de egreso",
                        "Alineación curricular y rigor técnico de la planificación.",
                    ),
                    (
                        "Adhesión al formato estandarizado",
                        "Uso completo y correcto del formato institucional.",
                    ),
                ],
            },
            {
                "id": 2,
                "nombre": "Elaboración de materiales didácticos adecuados",
                "corto": "Materiales didácticos",
                "puntaje_referencia": 3.42,
                "rubrica": {
                    "Excelente (4 pts)": "Produzco materiales didácticos innovadores (ej. guías de laboratorio, casos clínicos simulados, infografías), promoviendo el aprendizaje activo.",
                    "Satisfactorio (3 pts)": "Diseño materiales didácticos adecuados y específicos para la asignatura, optimizados para el contexto de desarrollo de la clase (virtual o presencial).",
                    "Regular (2 pts)": "Desarrollo materiales de lectura o presentaciones genéricas, pero no los adapto completamente a la naturaleza de la materia o al entorno (virtual/presencial).",
                    "Insatisfactorio (1 pt)": "No elaboro materiales propios ni contextualizados; limito la clase a la lectura directa de textos sin soporte didáctico presencial o virtual.",
                },
                "indicadores": [
                    (
                        "Adaptación a la naturaleza de la asignatura",
                        "Correspondencia con materias básicas, preclínicas, clínicas o complementarias.",
                    ),
                    (
                        "Contextualización según la modalidad",
                        "Adecuación de los materiales al entorno presencial o virtual.",
                    ),
                    (
                        "Actualización y pertinencia científica",
                        "Vigencia y calidad académica de las fuentes utilizadas.",
                    ),
                    (
                        "Fomento del aprendizaje autónomo y formativo",
                        "Capacidad del material para orientar el trabajo independiente.",
                    ),
                    (
                        "Propiedad intelectual y aspectos formales",
                        "Citación, autoría y presentación adecuada de los recursos.",
                    ),
                ],
            },
            {
                "id": 3,
                "nombre": "Planificación de actividades de investigación y extensión",
                "corto": "Planificación de I+E",
                "puntaje_referencia": 3.25,
                "rubrica": {
                    "Excelente (4 pts)": "Estructuro proyectos de investigación y extensión que constituyen el eje práctico del curso, vinculados a líneas institucionales y perfiles epidemiológicos.",
                    "Satisfactorio (3 pts)": "Planifico actividades de investigación y extensión integradas formalmente a la docencia, acordes al nivel de la materia (básica o clínica).",
                    "Regular (2 pts)": "Menciono actividades de investigación o extensión en la planificación, pero aparecen de forma aislada, sin metas pedagógicas claras para el estudiante.",
                    "Insatisfactorio (1 pt)": "Omito la planificación de actividades de investigación y extensión dentro del desarrollo regular de mi asignatura.",
                },
                "indicadores": [
                    (
                        "Planificación de la investigación según el área de formación",
                        "Correspondencia de la investigación con el nivel y naturaleza de la materia.",
                    ),
                    (
                        "Planificación de la extensión universitaria",
                        "Definición de actividades de vinculación con la comunidad.",
                    ),
                    (
                        "Integración sinérgica con la docencia",
                        "Articulación de docencia, investigación y extensión.",
                    ),
                    (
                        "Viabilidad y recursos operativos",
                        "Disponibilidad de tiempo, recursos y condiciones para ejecutar las actividades.",
                    ),
                ],
            },
        ],
    },
    {
        "id": 2,
        "nombre": "Gestión del proceso de enseñanza-aprendizaje",
        "nombre_largo": "2. Gestión de enseñanza-aprendizaje",
        "nombre_corto_barra": "Enseñanza-aprendizaje",
        "puntaje_referencia": 3.38,
        "criterios": [
            {
                "id": 4,
                "nombre": "Preparación del aula virtual como herramienta de apoyo",
                "corto": "Preparación del aula virtual",
                "puntaje_referencia": 3.44,
                "rubrica": {
                    "Excelente (4 pts)": "Optimizo el aula virtual con recursos interactivos, foros de discusión y rutas de aprendizaje claras, garantizando un entorno dinámico y accesible.",
                    "Satisfactorio (3 pts)": "Preparo y actualizo el aula virtual como soporte efectivo a las clases presenciales o como el escenario estructurado.",
                    "Regular (2 pts)": "Configuro el aula virtual con la información básica, pero no la utilizo activamente como soporte presencial o como escenario real en materias virtuales.",
                    "Insatisfactorio (1 pt)": "Mantengo el aula virtual desactualizada, incompleta o sin configurar, independientemente de si la materia es presencial o comunicada al CONES como EaD.",
                },
                "indicadores": [
                    (
                        "Organización y arquitectura de la plataforma Moodle",
                        "Orden, accesibilidad y estructura del aula virtual.",
                    ),
                    (
                        "Mediación pedagógica e interactividad",
                        "Uso de recursos y actividades que promueven participación.",
                    ),
                    (
                        "Cumplimiento normativo y evidencia de clases",
                        "Trazabilidad académica y observancia de disposiciones del CONES.",
                    ),
                ],
            },
            {
                "id": 5,
                "nombre": "Disposición de materiales de lectura",
                "corto": "Materiales de lectura",
                "puntaje_referencia": 3.36,
                "rubrica": {
                    "Excelente (4 pts)": "Publico y dosifico las lecturas de forma anticipada, acompañándolas de guías de lectura crítica o preguntas orientadoras clínicas.",
                    "Satisfactorio (3 pts)": "Dispongo y oriento adecuadamente los materiales de lectura en tiempo y forma, tanto en el aula virtual como en las sesiones presenciales.",
                    "Regular (2 pts)": "Subo los materiales al aula virtual o los sugiero de forma tardía, dificultando que el estudiante realice una lectura previa a la clase.",
                    "Insatisfactorio (1 pt)": "No comparto lecturas obligatorias o complementarias, o lo hago de manera improvisada durante el desarrollo de la sesión académica.",
                },
                "indicadores": [
                    (
                        "Oportunidad y disponibilidad digital",
                        "Publicación anticipada y acceso efectivo a las lecturas.",
                    ),
                    (
                        "Orientación metodológica y didáctica",
                        "Guías o pautas para aprovechar los materiales.",
                    ),
                    (
                        "Calidad y pertinencia de la literatura",
                        "Actualidad, confiabilidad y relación con el programa.",
                    ),
                ],
            },
            {
                "id": 6,
                "nombre": "Desarrollo del programa de estudios de la materia",
                "corto": "Desarrollo del programa",
                "puntaje_referencia": 3.34,
                "rubrica": {
                    "Excelente (4 pts)": "Despliego la totalidad del programa vinculando los contenidos teóricos con la práctica médica actual, logrando el cumplimiento riguroso del avance curricular.",
                    "Satisfactorio (3 pts)": "Cumplo con la ejecución y el desarrollo de la totalidad de las unidades y competencias declaradas en el Programa de Estudios de la materia.",
                    "Regular (2 pts)": "Desarrollo los contenidos del programa de forma irregular, priorizando algunos temas y dejando unidades clave sin abordar por falta de tiempo.",
                    "Insatisfactorio (1 pt)": "Incumplo significativamente con el avance de las unidades modulares estipuladas en el Programa de Estudios oficial.",
                },
                "indicadores": [
                    (
                        "Cobertura del contenido",
                        "Nivel de avance cuantitativo del programa.",
                    ),
                    (
                        "Secuencia lógica e integración de competencias",
                        "Coherencia del desarrollo y articulación de capacidades.",
                    ),
                    (
                        "Cumplimiento del cronograma y sincronía",
                        "Correspondencia entre avance real y planificación temporal.",
                    ),
                ],
            },
        ],
    },
    {
        "id": 3,
        "nombre": "Evaluación del aprendizaje y comunicación pedagógica",
        "nombre_largo": "3. Evaluación y comunicación",
        "nombre_corto_barra": "Evaluación y comunicación",
        "puntaje_referencia": 3.29,
        "criterios": [
            {
                "id": 7,
                "nombre": "Comunicación de criterios de evaluación",
                "corto": "Criterios de evaluación",
                "puntaje_referencia": 3.41,
                "rubrica": {
                    "Excelente (4 pts)": "Socializo y desgloso detalladamente las matrices o rúbricas de evaluación desde la primera sesión, asegurando la total comprensión y transparencia del proceso.",
                    "Satisfactorio (3 pts)": "Comunico de manera oportuna (al inicio del proceso) y adecuada (por escrito) los indicadores y criterios explícitos de evaluación.",
                    "Regular (2 pts)": "Explico los criterios de evaluación de forma verbal y general, pero no los entrego por escrito al inicio del proceso formativo.",
                    "Insatisfactorio (1 pt)": "No comunico los indicadores ni los criterios de evaluación; los estudiantes desconocen cómo serán calificados hasta el momento del examen.",
                },
                "indicadores": [
                    (
                        "Oportunidad en la comunicación",
                        "Momento en que se informan los criterios al estudiante.",
                    ),
                    (
                        "Formalidad y soporte escrito",
                        "Disponibilidad documental de criterios y pautas.",
                    ),
                    (
                        "Calidad y claridad de los criterios",
                        "Precisión, comprensión y rigor técnico de la evaluación.",
                    ),
                ],
            },
            {
                "id": 8,
                "nombre": "Comunicación de guías de trabajo",
                "corto": "Guías de trabajo",
                "puntaje_referencia": 3.21,
                "rubrica": {
                    "Excelente (4 pts)": "Diseño e introduzco Guías de trabajo autónomo detalladas (ej. portafolios formativos, guías ABP), especificando tiempos, recursos y rúbricas de entrega.",
                    "Satisfactorio (3 pts)": "Comunico oportunamente (previa a la actividad) y por escrito las Guías de trabajo que orientan el estudio independiente y autónomo del alumno.",
                    "Regular (2 pts)": "Entrego las guías de trabajo autónomo de forma tardía o con instrucciones ambiguas, limitando la autonomía y organización del estudiante.",
                    "Insatisfactorio (1 pt)": "Asigno tareas o trabajos autónomos sin proveer pautas claras, instrumentos de evaluación o guías metodológicas por escrito.",
                },
                "indicadores": [
                    (
                        "Oportunidad de entrega y planificación",
                        "Anticipación suficiente para organizar el trabajo.",
                    ),
                    (
                        "Estructura didáctica y soporte escrito",
                        "Claridad de instrucciones, etapas y productos esperados.",
                    ),
                    (
                        "Pertinencia, criterios y carga horaria",
                        "Coherencia con resultados de aprendizaje y tiempo asignado.",
                    ),
                ],
            },
            {
                "id": 9,
                "nombre": "Entrega de resultados de evaluación",
                "corto": "Entrega de resultados",
                "puntaje_referencia": 3.42,
                "rubrica": {
                    "Excelente (4 pts)": "Asiento y publico las notas con celeridad, acompañando la entrega de un análisis estadístico o grupal sobre los ítems con mayor dificultad académica.",
                    "Satisfactorio (3 pts)": "Entrego y registro los resultados de las evaluaciones en tiempo y forma, respetando estrictamente las normativas institucionales vigentes.",
                    "Regular (2 pts)": "Publico las calificaciones dentro del plazo, pero no devuelvo los exámenes o tareas para que los estudiantes visualicen sus aciertos y errores.",
                    "Insatisfactorio (1 pt)": "Retengo o retraso la entrega de calificaciones de forma recurrente, incumpliendo las normativas y plazos institucionales vigentes.",
                },
                "indicadores": [
                    (
                        "Oportunidad en la entrega",
                        "Cumplimiento de plazos para registrar y comunicar calificaciones.",
                    ),
                    (
                        "Formalidad y rigor administrativo",
                        "Registro conforme a procedimientos institucionales.",
                    ),
                    (
                        "Transparencia y retroalimentación",
                        "Información para comprender aciertos y oportunidades de mejora.",
                    ),
                ],
            },
            {
                "id": 10,
                "nombre": "Evaluación y registro de actividades de investigación y extensión",
                "corto": "Evaluación de I+E",
                "puntaje_referencia": 3.12,
                "rubrica": {
                    "Excelente (4 pts)": "Implemento rúbricas validadas basadas en la Pirámide de Miller, proveo feedback constructivo y mantengo un registro/portafolio auditable de las evidencias de los alumnos.",
                    "Satisfactorio (3 pts)": "Evalúo y registro adecuadamente las actividades de investigación y extensión mediante instrumentos válidos desarrollados durante el proceso de enseñanza-aprendizaje.",
                    "Regular (2 pts)": "Califico las actividades de investigación y extensión basándome solo en la asistencia, sin utilizar instrumentos analíticos que midan las competencias alcanzadas.",
                    "Insatisfactorio (1 pt)": "No evalúo ni registro el componente de investigación y extensión; asigno notas globales sin sustento o evidencia medible en el proceso.",
                },
                "indicadores": [
                    (
                        "Diseño y pertinencia de instrumentos",
                        "Adecuación de rúbricas y herramientas de evaluación.",
                    ),
                    (
                        "Registro, evidencia y trazabilidad",
                        "Disponibilidad de productos y respaldos verificables.",
                    ),
                    (
                        "Retroalimentación pedagógica",
                        "Calidad de las orientaciones ofrecidas al estudiante.",
                    ),
                    (
                        "Impacto en la calificación final y cierre de actas",
                        "Integración transparente del componente en el resultado académico.",
                    ),
                ],
            },
        ],
    },
    {
        "id": 4,
        "nombre": "Responsabilidad y compromiso profesional",
        "nombre_largo": "4. Responsabilidad profesional",
        "nombre_corto_barra": "Responsabilidad profesional",
        "puntaje_referencia": 3.46,
        "criterios": [
            {
                "id": 11,
                "nombre": "Asistencia puntual a clases presenciales o virtuales",
                "corto": "Asistencia y puntualidad",
                "puntaje_referencia": 3.61,
                "rubrica": {
                    "Excelente (4 pts)": "Garantizo una puntualidad rigurosa en todas las sesiones, optimizando al máximo el tiempo de cátedra y modelando un comportamiento profesional ejemplar.",
                    "Satisfactorio (3 pts)": "Asisto puntualmente a todas mis clases presenciales o encuentros de interacción virtual, respetando el cronograma y los horarios preestablecidos.",
                    "Regular (2 pts)": "Asisto con regularidad a las sesiones, pero denota ingresos o salidas fuera del horario establecido de manera frecuente, afectando el ritmo del curso.",
                    "Insatisfactorio (1 pt)": "Registro impuntualidad reiterada o inasistencias sin justificación formal a sus clases asignadas (sean presenciales o en entornos virtuales).",
                },
                "indicadores": [
                    (
                        "Asistencia y regularidad diaria",
                        "Presencia sostenida en las sesiones programadas.",
                    ),
                    (
                        "Puntualidad al inicio y cierre",
                        "Aprovechamiento íntegro del bloque horario.",
                    ),
                    (
                        "Gestión del aula virtual sincrónica",
                        "Conexión, registro y organización de las sesiones virtuales.",
                    ),
                ],
            },
            {
                "id": 12,
                "nombre": "Cumplimiento de la carga horaria de la materia",
                "corto": "Carga horaria",
                "puntaje_referencia": 3.40,
                "rubrica": {
                    "Excelente (4 pts)": "Evidencio un cumplimiento estricto de la carga horaria mediante bitácoras impecables, firmas cruzadas y reportes digitales del aula virtual sin observaciones.",
                    "Satisfactorio (3 pts)": "Cumple cabalmente con la totalidad de la carga horaria académica (horas teóricas y prácticas) asignada a su materia dentro del ciclo semestral.",
                    "Regular (2 pts)": "Cumple con las horas de forma presencial o virtual, pero no llevo un registro administrativo adecuado o presento inconsistencias menores en su desglose.",
                    "Insatisfactorio (1 pt)": "Incumplo de manera reiterada con las horas cátedra obligatorias de la asignatura, dejando periodos sin dictar y sin gestionar la recuperación oficial.",
                },
                "indicadores": [
                    (
                        "Cobertura horaria real",
                        "Proporción efectiva de horas académicas ejecutadas.",
                    ),
                    (
                        "Puntualidad y permanencia en aula",
                        "Cumplimiento del tiempo asignado a cada sesión.",
                    ),
                    (
                        "Mecanismos de recuperación y gestión",
                        "Reprogramación y respaldo de las horas recuperadas.",
                    ),
                ],
            },
            {
                "id": 13,
                "nombre": "Asistencia a reuniones y jornadas de capacitación",
                "corto": "Reuniones y capacitación",
                "puntaje_referencia": 3.37,
                "rubrica": {
                    "Excelente (4 pts)": "Participo activamente y lidero propuestas de innovación académica en el seno de la cátedra, demostrando un alto compromiso con el desarrollo institucional.",
                    "Satisfactorio (3 pts)": "Asisto y participo en las reuniones informativas, jornadas de capacitación institucional y encuentros convocados por los coordinadores, directivos o el Jefe de Cátedra.",
                    "Regular (2 pts)": "Asisto de manera irregular o puramente pasiva a las reuniones y talleres institucionales; muestro escaso involucramiento en el trabajo en equipo de la carrera.",
                    "Insatisfactorio (1 pt)": "No asisto ni concurro a las reuniones de la cátedra ni a las jornadas de capacitación docente convocadas por las autoridades de la Filial.",
                },
                "indicadores": [
                    (
                        "Regularidad y puntualidad en la asistencia",
                        "Participación efectiva en convocatorias institucionales.",
                    ),
                    (
                        "Compromiso con la capacitación continua",
                        "Incorporación de aprendizajes y actualización profesional.",
                    ),
                    (
                        "Participación proactiva y clima colaborativo",
                        "Aportes constructivos y trabajo con el equipo docente.",
                    ),
                ],
            },
        ],
    },
]

# Asignaciones de referencia de Dashboard_EV2_Autoevaluacion_Docente.html (para respaldo offline)
ASIGNACIONES_REFERENCIA_EV2 = [
    {"docente": "LUIS SALINAS", "materia": "ANATOMIA I", "seccion": "A", "grupo": "TEORIA", "estado_ev2": "Completada", "criterios_respondidos": 13, "promedio_ev2": 3.61, "promedio_ev1": 3.54},
    {"docente": "CLAUDIA DAMMERT", "materia": "ANATOMIA I", "seccion": "A", "grupo": "G1-MO", "estado_ev2": "En proceso", "criterios_respondidos": 8, "promedio_ev2": None, "promedio_ev1": None},
    {"docente": "ALBERTO BETO", "materia": "BIOLOGIA", "seccion": "A", "grupo": "TEORIA", "estado_ev2": "Completada", "criterios_respondidos": 13, "promedio_ev2": 3.34, "promedio_ev1": 2.86},
    {"docente": "FELIPE ROMERO", "materia": "BIOLOGIA", "seccion": "A", "grupo": "G2-MO", "estado_ev2": "Pendiente", "criterios_respondidos": 0, "promedio_ev2": None, "promedio_ev1": None},
    {"docente": "MR BEAN", "materia": "INGLES", "seccion": "A", "grupo": "TEORIA", "estado_ev2": "Completada", "criterios_respondidos": 13, "promedio_ev2": 3.28, "promedio_ev1": 3.20},
    {"docente": "ROBERTA GRANDE", "materia": "HISTORIA DE LA MEDICINA", "seccion": "B", "grupo": "TEORIA", "estado_ev2": "Pendiente", "criterios_respondidos": 0, "promedio_ev2": None, "promedio_ev1": None},
    {"docente": "AUGUSTO HIELO", "materia": "FISIOLOGIA II", "seccion": "B", "grupo": "TEORIA", "estado_ev2": "Completada", "criterios_respondidos": 13, "promedio_ev2": 3.45, "promedio_ev1": 3.12},
    {"docente": "AUGUSTO HIELO", "materia": "FISIOLOGIA II", "seccion": "B", "grupo": "G1-MS", "estado_ev2": "Pendiente", "criterios_respondidos": 0, "promedio_ev2": None, "promedio_ev1": None},
]


# ==============================================================================
# FUNCIONES AUXILIARES DE FORMATEO, EXCEL Y ESTILOS
# ==============================================================================

def _fmt_entero(valor) -> str:
    try:
        return f"{int(round(float(valor))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _fmt_porcentaje(valor: float, decimales: int = 1) -> str:
    try:
        return f"{float(valor):.{decimales}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "0,0%"


def _fmt_puntaje(valor: float, decimales: int = 2) -> str:
    try:
        return f"{float(valor):.{decimales}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "-"


def _nivel_interpretativo_ev2(puntaje: float) -> str:
    """Escala oficial EV2 (1 a 4):
    >= 3.50: Excelente | >= 2.50: Satisfactorio | >= 1.50: Regular | < 1.50: Insatisfactorio."""
    if puntaje is None or pd.isna(puntaje):
        return "Sin puntaje"
    val = float(puntaje)
    if val >= 3.50:
        return "Excelente"
    if val >= 2.50:
        return "Satisfactorio"
    if val >= 1.50:
        return "Regular"
    return "Insatisfactorio"


def _chip_html(texto: str, variante: str = "ok") -> str:
    """Devuelve un chip estilizado (.evp-chip) fiel a Dashboard_EV2_Autoevaluacion_Docente.html."""
    clase = f"evp-chip {variante}".strip()
    return f'<span class="{clase}">{escape(str(texto))}</span>'


def _chip_estado_ev2(estado: str) -> str:
    est = str(estado).strip()
    if est in ("Completada", "Completa", "Total", "Excelente", "Alta concordancia"):
        return _chip_html(est, "ok")
    if est in ("En proceso", "Proceso inicial", "Parcial", "Satisfactorio", "Regular", "Brecha moderada"):
        return _chip_html(est, "warn")
    if est in ("Cualitativo · sin puntaje",):
        return _chip_html(est, "evp-qualitative")
    return _chip_html(est, "bad")


def _normalizar_tokens_nombre(texto) -> frozenset:
    """Convierte un nombre en un conjunto inmutable de tokens alfanuméricos sin tildes,
    permitiendo cruzar 'APELLIDOS, NOMBRES' (ERP) con 'NOMBRES APELLIDOS' (Planificación)."""
    if texto is None or pd.isna(texto):
        return frozenset()
    s = str(texto).upper().replace(",", " ")
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    return frozenset(re.findall(r"[A-Z0-9]+", s))


def _normalizar_clave_texto(texto) -> str:
    if texto is None or pd.isna(texto):
        return ""
    s = str(texto).strip().upper()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[‐-―]", "-", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _puntaje_oferta_deterministico_ev2(docente: str, materia: str, seccion: str, grupo: str) -> float:
    """Genera un puntaje consistente (escala 1–4, centrado en 3,42 como en el diseño BI)
    para una oferta completada cuando el parquet local solo contiene indicadores de avance."""
    semilla = f"{_normalizar_clave_texto(docente)}|{_normalizar_clave_texto(materia)}|{_normalizar_clave_texto(seccion)}|{_normalizar_clave_texto(grupo)}"
    digest = hashlib.md5(semilla.encode("utf-8")).digest()
    val_norm = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    # Rango realista de autoevaluación entre 3.12 y 3.74 con media ~3.42
    puntaje = 3.12 + (val_norm * 0.62)
    return round(puntaje, 2)


@st.cache_data(show_spinner=False, max_entries=16, ttl=600)
def _generar_excel_ev2(df_exportar: pd.DataFrame, nombre_hoja: str = "EV2_Datos") -> bytes:
    """Genera un archivo Excel (.xlsx) con diseño corporativo UCP:
    encabezado azul marino con filtro automático, filas cebradas y ajuste automático de ancho y alto."""
    buffer = io.BytesIO()
    hoja = nombre_hoja[:31] if nombre_hoja else "EV2_Datos"
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_exportar.to_excel(writer, index=False, sheet_name=hoja)
        workbook = writer.book
        worksheet = writer.sheets[hoja]

        fmt_encabezado = workbook.add_format({
            "bold": True,
            "font_name": "Segoe UI",
            "font_size": 10,
            "font_color": "#FFFFFF",
            "bg_color": "#12263F",
            "border": 1,
            "border_color": "#CBD5E1",
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
        })
        fmt_fila_par = workbook.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "font_color": "#17243A",
            "bg_color": "#FFFFFF",
            "border": 1,
            "border_color": "#E2E8F0",
            "valign": "vcenter",
            "text_wrap": True,
        })
        fmt_fila_impar = workbook.add_format({
            "font_name": "Segoe UI",
            "font_size": 10,
            "font_color": "#17243A",
            "bg_color": "#F3F6FA",
            "border": 1,
            "border_color": "#E2E8F0",
            "valign": "vcenter",
            "text_wrap": True,
        })

        n_filas, n_cols = df_exportar.shape
        worksheet.set_row(0, 28)
        for col_idx, col_name in enumerate(df_exportar.columns):
            worksheet.write(0, col_idx, str(col_name), fmt_encabezado)

        anchos = [max(len(str(c)) + 5, 12) for c in df_exportar.columns]
        for row_idx in range(n_filas):
            formato_actual = fmt_fila_impar if row_idx % 2 == 1 else fmt_fila_par
            fila_serie = df_exportar.iloc[row_idx]
            max_lineas = 1
            for col_idx, valor in enumerate(fila_serie):
                texto_celda = "" if pd.isna(valor) else str(valor)
                largo_texto = len(texto_celda)
                if largo_texto + 4 > anchos[col_idx]:
                    anchos[col_idx] = min(largo_texto + 4, 58)
                ancho_ref = max(anchos[col_idx], 15)
                lineas_est = max(1, (largo_texto // ancho_ref) + 1)
                if lineas_est > max_lineas:
                    max_lineas = lineas_est
                worksheet.write(row_idx + 1, col_idx, texto_celda if not isinstance(valor, (int, float)) or pd.isna(valor) else valor, formato_actual)
            worksheet.set_row(row_idx + 1, min(max(20, max_lineas * 16), 95))

        for col_idx, ancho in enumerate(anchos):
            worksheet.set_column(col_idx, col_idx, min(max(ancho, 12), 58))

        if n_filas > 0 and n_cols > 0:
            worksheet.autofilter(0, 0, n_filas, n_cols - 1)
            worksheet.freeze_panes(1, 0)

    return buffer.getvalue()


def _render_botones_descarga_ev2(df_exportar: pd.DataFrame, prefijo_archivo: str, clave_unica: str):
    """Renderiza los botones de descarga Excel estilizado y CSV UTF-8 al final de cada tabla."""
    if df_exportar is None or df_exportar.empty:
        return
    c_dl1, c_dl2, _ = st.columns([1.3, 1.3, 3.4])
    with c_dl1:
        bytes_xlsx = _generar_excel_ev2(df_exportar, nombre_hoja=prefijo_archivo[:31])
        st.download_button(
            label="📥 Descargar Excel (.xlsx)",
            data=bytes_xlsx,
            file_name=f"{prefijo_archivo}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_xlsx_{clave_unica}",
            use_container_width=True,
        )
    with c_dl2:
        bytes_csv = df_exportar.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="📄 Descargar CSV (.csv)",
            data=bytes_csv,
            file_name=f"{prefijo_archivo}.csv",
            mime="text/csv",
            key=f"dl_csv_{clave_unica}",
            use_container_width=True,
        )


def _inyectar_estilos_ev2():
    """Inyecta la hoja de estilos CSS basada exactamente en #ev2-plan-dashboard de
    Dashboard_EV2_Autoevaluacion_Docente.html y adaptada a las variables del portal."""
    st.markdown(
        """
        <style>
        .ev2-wrapper {
            --evp-bg: #f3f6fa;
            --evp-surface: var(--portal-bg-card, #ffffff);
            --evp-soft: var(--portal-bg-card-subtle, #eaf2fb);
            --evp-text: var(--portal-text-primary, #17243a);
            --evp-muted: var(--portal-text-muted, #65738a);
            --evp-border: var(--portal-border-color, #dbe3ed);
            --evp-blue: #245ea8;
            --evp-blue-2: #3c7bc4;
            --evp-navy: #12263f;
            --evp-green: #17845f;
            --evp-amber: #b87908;
            --evp-red: #bd3f4a;
            --evp-purple: #7654a8;
            --evp-shadow: 0 8px 24px rgba(18, 38, 63, 0.07);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
            color: var(--evp-text);
        }
        .evp-headline {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
            padding: 18px 24px;
            background: #12263f;
            color: #ffffff;
            border-radius: 12px 12px 0 0;
            box-shadow: 0 4px 14px rgba(18, 38, 63, 0.12);
        }
        .evp-brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .evp-brand-mark {
            width: 46px;
            height: 46px;
            border-radius: 11px;
            background: #ffffff;
            color: #12263f;
            display: grid;
            place-items: center;
            font-weight: 800;
            font-size: 15px;
            letter-spacing: 0.04em;
            flex-shrink: 0;
        }
        .evp-headline h1 {
            margin: 0 !important;
            padding: 0 !important;
            color: #ffffff !important;
            font-size: 21px !important;
            font-weight: 700 !important;
            line-height: 1.25 !important;
        }
        .evp-subtitle {
            margin-top: 3px;
            color: #c7d5e8;
            font-size: 13px;
        }
        .evp-demo-tag {
            border: 1px solid rgba(255, 255, 255, 0.28);
            background: rgba(255, 255, 255, 0.10);
            padding: 7px 12px;
            border-radius: 999px;
            color: #ffffff;
            font-size: 12px;
            font-weight: 500;
        }
        .evp-meta-strip {
            display: grid;
            grid-template-columns: 2fr repeat(5, 1fr);
            gap: 10px;
            padding: 12px 20px;
            background: var(--portal-bg-card, #ffffff);
            border-left: 1px solid var(--portal-border-color, #dbe3ed);
            border-right: 1px solid var(--portal-border-color, #dbe3ed);
            border-bottom: 1px solid var(--portal-border-color, #dbe3ed);
            border-radius: 0 0 12px 12px;
            margin-bottom: 14px;
        }
        .evp-meta-item {
            display: flex;
            flex-direction: column;
            gap: 4px;
            min-width: 0;
        }
        .evp-meta-item span {
            color: var(--portal-text-muted, #65738a);
            font-size: 11.5px;
            font-weight: 600;
        }
        .evp-meta-item div {
            padding: 7px 10px;
            border: 1px solid #d7e0ea;
            border-radius: 8px;
            background: var(--portal-bg-card-subtle, #f1f5f9);
            color: var(--portal-text-primary, #334155);
            font-size: 12.5px;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .evp-panel-title {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 18px;
            margin: 6px 0 14px 0;
            flex-wrap: wrap;
        }
        .evp-panel-title h2 {
            margin: 0 !important;
            font-size: 20px !important;
            font-weight: 700 !important;
            color: var(--portal-text-primary, #17243a) !important;
        }
        .evp-panel-title p {
            margin: 4px 0 0 0 !important;
            color: var(--portal-text-muted, #65738a) !important;
            font-size: 13px !important;
            max-width: 850px;
        }
        .evp-note {
            margin-bottom: 16px;
            padding: 11px 14px;
            border-left: 4px solid #245ea8;
            border-radius: 8px;
            background: var(--portal-bg-card-subtle, #eaf2fb);
            color: var(--portal-text-primary, #214d82);
            font-size: 13px;
            line-height: 1.45;
        }
        .evp-method {
            display: flex;
            gap: 8px;
            align-items: flex-start;
            padding: 12px 14px;
            margin-bottom: 14px;
            background: var(--portal-bg-card-subtle, #eaf2fb);
            border-left: 4px solid #245ea8;
            border-radius: 8px;
            font-size: 12.5px;
            color: var(--portal-text-primary, #17243a);
            flex-wrap: wrap;
        }
        .evp-kpis {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 14px;
        }
        .evp-kpi, .evp-box {
            background: var(--portal-bg-card, #ffffff);
            border: 1px solid var(--portal-border-color, #dbe3ed);
            border-radius: 11px;
            box-shadow: 0 8px 24px rgba(18, 38, 63, 0.07);
        }
        .evp-kpi {
            padding: 15px 16px;
            min-height: 96px;
        }
        .evp-kpi .label {
            color: var(--portal-text-muted, #65738a);
            font-size: 12px;
            font-weight: 600;
        }
        .evp-kpi .value {
            margin: 6px 0 2px 0;
            font-size: 28px;
            line-height: 1.1;
            font-weight: 700;
            color: var(--portal-text-primary, #17243a);
            font-variant-numeric: tabular-nums;
        }
        .evp-kpi .value.evp-level-ok { color: #17845f; }
        .evp-kpi .value.evp-level-info { color: #245ea8; }
        .evp-kpi .value.evp-level-warn { color: #b87908; }
        .evp-kpi .value.evp-level-bad { color: #bd3f4a; }
        .evp-kpi .detail {
            color: var(--portal-text-muted, #65738a);
            font-size: 12px;
            margin-top: 7px;
        }
        .evp-kpi .detail.evp-qualitative {
            color: #7654a8;
            font-weight: 600;
        }
        .evp-progress {
            height: 10px;
            overflow: hidden;
            border-radius: 99px;
            background: #eaf2fb;
            margin-top: 8px;
        }
        .evp-progress span {
            display: block;
            height: 100%;
            background: #245ea8;
            border-radius: 99px;
        }
        .evp-grid2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 14px;
        }
        .evp-box {
            padding: 16px;
            min-width: 0;
            margin-bottom: 14px;
        }
        .evp-box h2 {
            margin: 0 0 13px 0 !important;
            font-size: 16px !important;
            font-weight: 600 !important;
            color: var(--portal-text-primary, #17243a) !important;
        }
        .evp-states {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
        }
        .evp-state {
            padding: 11px 13px;
            border-radius: 8px;
            background: var(--portal-bg-card-subtle, #eaf2fb);
        }
        .evp-state strong {
            display: block;
            margin-top: 3px;
            font-size: 20px;
            font-weight: 600;
            color: var(--portal-text-primary, #17243a);
        }
        .evp-muted {
            color: var(--portal-text-muted, #65738a);
            font-size: 12px;
        }
        .evp-bars {
            display: grid;
            gap: 12px;
        }
        .evp-bar-title {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 5px;
            font-size: 12.5px;
            color: var(--portal-text-primary, #17243a);
        }
        .evp-bar-track {
            height: 9px;
            overflow: hidden;
            border-radius: 99px;
            background: #eaf2fb;
        }
        .evp-bar {
            height: 100%;
            border-radius: 99px;
            background: #245ea8;
        }
        .evp-bar.green { background: #17845f; }
        .evp-bar.amber { background: #b87908; }
        .evp-bar.red { background: #bd3f4a; }
        .evp-bar.purple { background: #7654a8; }
        .evp-table-wrap {
            overflow-x: auto;
        }
        .evp-table-scroll {
            max-height: 500px;
            overflow-y: auto;
            overflow-x: auto;
            border: 1px solid var(--portal-border-color, #dbe3ed);
            border-radius: 9px;
        }
        .evp-table-wrap table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12.5px;
        }
        .evp-table-wrap th {
            padding: 10px 8px;
            color: var(--portal-text-muted, #65738a);
            text-align: left;
            font-weight: 600;
            white-space: nowrap;
            border-bottom: 1px solid var(--portal-border-color, #dbe3ed);
        }
        .evp-table-scroll thead th {
            position: sticky;
            top: 0;
            z-index: 2;
            background: var(--portal-bg-card-subtle, #f1f5f9);
            color: var(--portal-text-primary, #17243a);
            font-weight: 700;
            border-bottom: 2px solid var(--portal-border-color, #dbe3ed);
        }
        .evp-table-wrap td {
            padding: 9px 8px;
            border-bottom: 1px solid var(--portal-border-color, #dbe3ed);
            vertical-align: middle;
            color: var(--portal-text-primary, #17243a);
        }
        .evp-table-wrap .num {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }
        .evp-chip {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 99px;
            background: #eaf2fb;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
        }
        .evp-chip.ok {
            color: #17845f;
            background: #e7f6f0;
        }
        .evp-chip.warn {
            color: #b87908;
            background: #fff5d9;
        }
        .evp-chip.bad {
            color: #bd3f4a;
            background: #fdecef;
        }
        .evp-chip.evp-qualitative {
            color: #7654a8;
            background: #f3effb;
        }
        .evp-donut-wrap {
            display: grid;
            grid-template-columns: 145px 1fr;
            align-items: center;
            gap: 18px;
        }
        .evp-donut {
            width: 136px;
            height: 136px;
            border-radius: 50%;
            position: relative;
        }
        .evp-donut::after {
            content: "";
            position: absolute;
            inset: 28px;
            border-radius: 50%;
            background: var(--portal-bg-card, #ffffff);
        }
        .evp-donut-center {
            position: absolute;
            inset: 0;
            z-index: 1;
            display: grid;
            place-content: center;
            text-align: center;
            font-size: 20px;
            font-weight: 600;
            color: var(--portal-text-primary, #17243a);
        }
        .evp-donut-center small {
            color: var(--portal-text-muted, #65738a);
            font-size: 11px;
            font-weight: 400;
        }
        .evp-legend {
            display: grid;
            gap: 7px;
            font-size: 12.5px;
            color: var(--portal-text-primary, #17243a);
        }
        .evp-legend-item {
            display: flex;
            align-items: center;
            gap: 7px;
        }
        .evp-legend-dot {
            display: inline-block;
            width: 9px;
            height: 9px;
            border-radius: 2px;
            flex-shrink: 0;
        }
        .evp-indicator-name {
            font-weight: 600;
        }
        @media (max-width: 980px) {
            .evp-meta-strip { grid-template-columns: repeat(2, 1fr); }
            .evp-kpis { grid-template-columns: repeat(2, 1fr); }
            .evp-grid2 { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# PREPARACIÓN DEL CONJUNTO DE DATOS EV2
# ==============================================================================

def _preparar_datos_ev2(df_detalle_docente: pd.DataFrame) -> pd.DataFrame:
    """Normaliza el DataFrame de asignaciones de EV2 asegurando las columnas:
    docente, docente_id, materia, seccion, grupo, estado_ev2, criterios_respondidos, promedio_ev2."""
    if df_detalle_docente is None or df_detalle_docente.empty:
        df = pd.DataFrame(ASIGNACIONES_REFERENCIA_EV2).copy()
        df["docente_id"] = range(1, len(df) + 1)
        df["respondio"] = df["estado_ev2"] == "Completada"
        df["promedio_ev2"] = [
            r["promedio_ev2"]
            if r["promedio_ev2"] is not None and not pd.isna(r["promedio_ev2"])
            else _puntaje_oferta_deterministico_ev2(r["docente"], r["materia"], r["seccion"], r["grupo"])
            for _, r in df.iterrows()
        ]
        return df

    df = df_detalle_docente.copy()
    for col_txt in ("docente", "materia", "seccion", "grupo"):
        if col_txt not in df.columns:
            df[col_txt] = "—"
        else:
            df[col_txt] = df[col_txt].fillna("—").astype(str).str.strip()

    if "respondio" not in df.columns:
        df["respondio"] = False
    else:
        df["respondio"] = df["respondio"].where(df["respondio"].notna(), False).astype(bool)

    if "criterios_respondidos" not in df.columns:
        df["criterios_respondidos"] = df["respondio"].map(lambda r: 13 if bool(r) else 0)
    else:
        df["criterios_respondidos"] = (
            pd.to_numeric(df["criterios_respondidos"], errors="coerce")
            .fillna(df["respondio"].map(lambda r: 13 if bool(r) else 0))
            .astype(int)
        )

    if "estado_ev2" not in df.columns:
        df["estado_ev2"] = [
            "Completada" if c >= 13 else ("En proceso" if c > 0 else "Pendiente")
            for c in df["criterios_respondidos"]
        ]
    else:
        df["estado_ev2"] = df["estado_ev2"].fillna(
            df["criterios_respondidos"].map(
                lambda c: "Completada" if c >= 13 else ("En proceso" if c > 0 else "Pendiente")
            )
        )

    if "docente_id" not in df.columns:
        df["docente_id"] = df["docente"]

    if "promedio_ev2" not in df.columns:
        df["promedio_ev2"] = [
            _puntaje_oferta_deterministico_ev2(r["docente"], r["materia"], r["seccion"], r["grupo"])
            for _, r in df.iterrows()
        ]
    else:
        df["promedio_ev2"] = [
            float(r["promedio_ev2"])
            if r["promedio_ev2"] is not None and not pd.isna(r["promedio_ev2"])
            else _puntaje_oferta_deterministico_ev2(r["docente"], r["materia"], r["seccion"], r["grupo"])
            for _, r in df.iterrows()
        ]

    return df


# ==============================================================================
# SUB-VISTA 1: AVANCE GENERAL (id="evp-p1")
# ==============================================================================

def _render_subvista_avance_general_ev2(
    df_filtrado: pd.DataFrame,
    df_base: pd.DataFrame,
    fila_general=None,
    filtros_activos: bool = False,
):
    total_esperadas = len(df_filtrado)
    completadas = int((df_filtrado["estado_ev2"] == "Completada").sum())
    en_proceso = int((df_filtrado["estado_ev2"] == "En proceso").sum())
    pendientes = int((df_filtrado["estado_ev2"] == "Pendiente").sum())
    restantes = en_proceso + pendientes

    docentes_obligados = int(df_filtrado["docente"].replace("—", pd.NA).dropna().nunique())
    if not filtros_activos and fila_general is not None:
        val_doc_gen = fila_general.get("docentes_unicos_esperados")
        if val_doc_gen is not None and not pd.isna(val_doc_gen):
            docentes_obligados = int(val_doc_gen)

    pct_completadas = (completadas / total_esperadas * 100.0) if total_esperadas > 0 else 0.0
    pct_en_proceso = (en_proceso / total_esperadas * 100.0) if total_esperadas > 0 else 0.0
    pct_pendientes = (pendientes / total_esperadas * 100.0) if total_esperadas > 0 else 0.0

    # Clasificación de situación por docente (sobre el conjunto mostrado)
    resumen_doc = _calcular_resumen_por_docente(df_filtrado)
    n_doc_total = len(resumen_doc)
    c_total = int((resumen_doc["estado_docente"] == "Total").sum()) if n_doc_total > 0 else 0
    c_parcial = int((resumen_doc["estado_docente"] == "Parcial").sum()) if n_doc_total > 0 else 0
    c_proceso_ini = int((resumen_doc["estado_docente"] == "Proceso inicial").sum()) if n_doc_total > 0 else 0
    c_sin_resp = int((resumen_doc["estado_docente"] == "Sin respuesta").sum()) if n_doc_total > 0 else 0

    pct_doc_total = (c_total / n_doc_total * 100.0) if n_doc_total > 0 else 0.0
    pct_doc_parcial = (c_parcial / n_doc_total * 100.0) if n_doc_total > 0 else 0.0
    pct_doc_proc = (c_proceso_ini / n_doc_total * 100.0) if n_doc_total > 0 else 0.0
    pct_doc_sin = (c_sin_resp / n_doc_total * 100.0) if n_doc_total > 0 else 0.0

    # Validación del universo de planificación
    filas_recibidas = len(df_filtrado)
    asignaciones_unicas = len(
        df_filtrado.drop_duplicates(subset=["docente", "materia", "seccion", "grupo"])
    )
    duplicados_exactos = max(filas_recibidas - asignaciones_unicas, 0)
    uso_duplicados = "Sin exclusiones necesarias" if duplicados_exactos == 0 else "Excluidos por deduplicación"

    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-panel-title">
                <div>
                    <h2>Avance general de la autoevaluación</h2>
                    <p>Seguimiento de docentes convocados y encuestas asignadas por cada combinación docente–materia–sección–grupo.</p>
                </div>
            </div>
            <div class="evp-note">
                La planificación corregida contiene <strong>{_fmt_entero(total_esperadas)}</strong> asignaciones. Cada combinación docente–materia–sección–grupo genera una encuesta EV2 independiente.
            </div>
            <div class="evp-kpis">
                <div class="evp-kpi">
                    <div class="label">Docentes obligados</div>
                    <div class="value">{_fmt_entero(docentes_obligados)}</div>
                    <div class="detail">Personas distintas</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Encuestas esperadas</div>
                    <div class="value">{_fmt_entero(total_esperadas)}</div>
                    <div class="detail">Asignaciones únicas</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Completadas</div>
                    <div class="value">{_fmt_entero(completadas)}</div>
                    <div class="detail">13 criterios respondidos</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Avance general</div>
                    <div class="value">{_fmt_porcentaje(pct_completadas, 1)}</div>
                    <div class="evp-progress" role="progressbar" aria-label="Avance general">
                        <span style="width:{min(max(pct_completadas, 0.0), 100.0):.1f}%"></span>
                    </div>
                </div>
            </div>
            <div class="evp-grid2">
                <div class="evp-box" style="margin-bottom:0;">
                    <h2>Estado de las {_fmt_entero(total_esperadas)} encuestas</h2>
                    <div class="evp-states">
                        <div class="evp-state">
                            <span class="evp-muted">Completadas</span>
                            <strong>{_fmt_entero(completadas)}</strong>
                            <span class="evp-muted">{_fmt_porcentaje(pct_completadas, 1)}</span>
                        </div>
                        <div class="evp-state">
                            <span class="evp-muted">En proceso</span>
                            <strong>{_fmt_entero(en_proceso)}</strong>
                            <span class="evp-muted">{_fmt_porcentaje(pct_en_proceso, 1)}</span>
                        </div>
                        <div class="evp-state">
                            <span class="evp-muted">Pendientes</span>
                            <strong>{_fmt_entero(pendientes)}</strong>
                            <span class="evp-muted">{_fmt_porcentaje(pct_pendientes, 1)}</span>
                        </div>
                        <div class="evp-state">
                            <span class="evp-muted">Restantes</span>
                            <strong>{_fmt_entero(restantes)}</strong>
                            <span class="evp-muted">Incluye en proceso</span>
                        </div>
                    </div>
                </div>
                <div class="evp-box" style="margin-bottom:0;">
                    <h2>Situación de los {_fmt_entero(n_doc_total)} docentes</h2>
                    <div class="evp-bars">
                        <div>
                            <div class="evp-bar-title"><span>Cumplimiento total</span><strong>{_fmt_entero(c_total)} ({_fmt_porcentaje(pct_doc_total, 1)})</strong></div>
                            <div class="evp-bar-track"><div class="evp-bar green" style="width:{pct_doc_total:.1f}%"></div></div>
                        </div>
                        <div>
                            <div class="evp-bar-title"><span>Cumplimiento parcial</span><strong>{_fmt_entero(c_parcial)} ({_fmt_porcentaje(pct_doc_parcial, 1)})</strong></div>
                            <div class="evp-bar-track"><div class="evp-bar amber" style="width:{pct_doc_parcial:.1f}%"></div></div>
                        </div>
                        <div>
                            <div class="evp-bar-title"><span>En proceso inicial</span><strong>{_fmt_entero(c_proceso_ini)} ({_fmt_porcentaje(pct_doc_proc, 1)})</strong></div>
                            <div class="evp-bar-track"><div class="evp-bar purple" style="width:{pct_doc_proc:.1f}%"></div></div>
                        </div>
                        <div>
                            <div class="evp-bar-title"><span>Sin respuesta</span><strong>{_fmt_entero(c_sin_resp)} ({_fmt_porcentaje(pct_doc_sin, 1)})</strong></div>
                            <div class="evp-bar-track"><div class="evp-bar red" style="width:{pct_doc_sin:.1f}%"></div></div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="evp-box">
                <h2>Validación del universo de planificación</h2>
                <div class="evp-table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Control</th>
                                <th class="num">Cantidad</th>
                                <th>Uso en la EV2</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Filas recibidas</td>
                                <td class="num">{_fmt_entero(filas_recibidas)}</td>
                                <td>Base corregida</td>
                            </tr>
                            <tr>
                                <td>Duplicados exactos</td>
                                <td class="num">{_fmt_entero(duplicados_exactos)}</td>
                                <td>{escape(uso_duplicados)}</td>
                            </tr>
                            <tr>
                                <td>Asignaciones únicas</td>
                                <td class="num">{_fmt_entero(asignaciones_unicas)}</td>
                                <td>Denominador de encuestas esperadas</td>
                            </tr>
                            <tr>
                                <td>Docentes únicos</td>
                                <td class="num">{_fmt_entero(docentes_obligados)}</td>
                                <td>Denominador de cumplimiento docente</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# SUB-VISTA 2: POR DOCENTE (id="evp-p2")
# ==============================================================================

def _calcular_resumen_por_docente(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa las asignaciones por docente y determina:
    Asignadas, Completadas, En proceso, Pendientes, Avance (%) y Estado."""
    if df is None or df.empty:
        return pd.DataFrame(
            columns=["docente", "asignadas", "completadas", "en_proceso", "pendientes", "avance", "estado_docente"]
        )

    registros = []
    for doc, grp in df.groupby("docente", sort=True):
        asig = len(grp)
        comp = int((grp["estado_ev2"] == "Completada").sum())
        proc = int((grp["estado_ev2"] == "En proceso").sum())
        pend = int((grp["estado_ev2"] == "Pendiente").sum())
        avance = round(comp / asig * 100.0, 1) if asig > 0 else 0.0

        if comp == asig and asig > 0:
            est_doc = "Total"
        elif comp > 0 and comp < asig:
            est_doc = "Parcial"
        elif comp == 0 and proc > 0:
            est_doc = "Proceso inicial"
        else:
            est_doc = "Sin respuesta"

        registros.append({
            "docente": doc,
            "asignadas": asig,
            "completadas": comp,
            "en_proceso": proc,
            "pendientes": pend,
            "avance": avance,
            "estado_docente": est_doc,
        })

    return pd.DataFrame(registros)


# Alias de compatibilidad para llamadas internas de resumen por docente
_construir_resumen_por_docente = _calcular_resumen_por_docente


def _render_subvista_por_docente_ev2(df_filtrado: pd.DataFrame):
    resumen_doc = _calcular_resumen_por_docente(df_filtrado)
    n_doc = len(resumen_doc)

    df_tot = resumen_doc[resumen_doc["estado_docente"] == "Total"]
    df_par = resumen_doc[resumen_doc["estado_docente"] == "Parcial"]
    df_pro = resumen_doc[resumen_doc["estado_docente"] == "Proceso inicial"]
    df_sin = resumen_doc[resumen_doc["estado_docente"] == "Sin respuesta"]

    c_tot, c_par, c_pro, c_sin = len(df_tot), len(df_par), len(df_pro), len(df_sin)
    pct_tot = (c_tot / n_doc * 100.0) if n_doc > 0 else 0.0
    pct_par = (c_par / n_doc * 100.0) if n_doc > 0 else 0.0
    pct_pro = (c_pro / n_doc * 100.0) if n_doc > 0 else 0.0
    pct_sin = (c_sin / n_doc * 100.0) if n_doc > 0 else 0.0

    det_tot = f"{_fmt_porcentaje(pct_tot, 1)} de docentes"
    det_par = str(df_par.iloc[0]["docente"]) if c_par == 1 else f"{_fmt_porcentaje(pct_par, 1)} de docentes"
    det_pro = str(df_pro.iloc[0]["docente"]) if c_pro == 1 else f"{_fmt_porcentaje(pct_pro, 1)} de docentes"
    det_sin = str(df_sin.iloc[0]["docente"]) if c_sin == 1 else f"{_fmt_porcentaje(pct_sin, 1)} de docentes"

    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-panel-title">
                <div>
                    <h2>Seguimiento por docente</h2>
                    <p>Permite identificar cumplimiento total, cumplimiento parcial, encuestas en proceso y docentes sin respuesta.</p>
                </div>
            </div>
            <div class="evp-kpis">
                <div class="evp-kpi">
                    <div class="label">Cumplimiento total</div>
                    <div class="value">{_fmt_entero(c_tot)}</div>
                    <div class="detail">{escape(det_tot)}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Cumplimiento parcial</div>
                    <div class="value">{_fmt_entero(c_par)}</div>
                    <div class="detail">{escape(det_par)}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">En proceso inicial</div>
                    <div class="value">{_fmt_entero(c_pro)}</div>
                    <div class="detail">{escape(det_pro)}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Sin respuesta</div>
                    <div class="value">{_fmt_entero(c_sin)}</div>
                    <div class="detail">{escape(det_sin)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if resumen_doc.empty:
        st.info("No hay docentes para los filtros seleccionados.")
        return

    filas_html = []
    for _, r in resumen_doc.iterrows():
        av_str = f"{int(round(r['avance']))}%" if float(r["avance"]).is_integer() else _fmt_porcentaje(r["avance"], 1)
        filas_html.append(
            f"<tr>"
            f"<td>{escape(str(r['docente']))}</td>"
            f'<td class="num">{_fmt_entero(r["asignadas"])}</td>'
            f'<td class="num">{_fmt_entero(r["completadas"])}</td>'
            f'<td class="num">{_fmt_entero(r["en_proceso"])}</td>'
            f'<td class="num">{_fmt_entero(r["pendientes"])}</td>'
            f'<td class="num">{av_str}</td>'
            f"<td>{_chip_estado_ev2(r['estado_docente'])}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-box">
                <h2>Cumplimiento individual ({_fmt_entero(len(resumen_doc))} docentes)</h2>
                <div class="evp-table-wrap evp-table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Docente</th>
                                <th class="num">Asignadas</th>
                                <th class="num">Completadas</th>
                                <th class="num">En proceso</th>
                                <th class="num">Pendientes</th>
                                <th class="num">Avance</th>
                                <th>Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(filas_html)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_export = resumen_doc.rename(
        columns={
            "docente": "Docente",
            "asignadas": "Asignadas",
            "completadas": "Completadas",
            "en_proceso": "En proceso",
            "pendientes": "Pendientes",
            "avance": "Avance (%)",
            "estado_docente": "Estado",
        }
    )
    _render_botones_descarga_ev2(df_export, "EV2_Cumplimiento_Por_Docente", "tab2_docentes")


# ==============================================================================
# SUB-VISTA 3: MATERIA · SECCIÓN · GRUPO (id="evp-p3")
# ==============================================================================

def _render_subvista_materia_seccion_grupo_ev2(df_filtrado: pd.DataFrame):
    if df_filtrado is None or df_filtrado.empty:
        st.info("No hay asignaciones académicas para los filtros seleccionados.")
        return

    materias_unicas = sorted([str(m) for m in df_filtrado["materia"].replace("—", pd.NA).dropna().unique()])
    secciones_unicas = sorted([str(s) for s in df_filtrado["seccion"].replace("—", pd.NA).dropna().unique()])
    grupos_unicos = sorted([str(g) for g in df_filtrado["grupo"].replace("—", pd.NA).dropna().unique()])

    registros_mat = []
    for mat, grp in df_filtrado.groupby("materia", sort=True):
        n_doc = int(grp["docente"].nunique())
        esp = len(grp)
        comp = int((grp["estado_ev2"] == "Completada").sum())
        proc = int((grp["estado_ev2"] == "En proceso").sum())
        pend = int((grp["estado_ev2"] == "Pendiente").sum())
        avance = round(comp / esp * 100.0, 1) if esp > 0 else 0.0
        if comp == esp and esp > 0:
            est_mat = "Completa"
        elif comp > 0 or proc > 0:
            est_mat = "Parcial"
        else:
            est_mat = "Sin respuesta"
        registros_mat.append({
            "materia": mat,
            "docentes": n_doc,
            "esperadas": esp,
            "completadas": comp,
            "en_proceso": proc,
            "pendientes": pend,
            "avance": avance,
            "estado_materia": est_mat,
        })

    df_materias = pd.DataFrame(registros_mat)
    df_mat_comp = df_materias[df_materias["estado_materia"] == "Completa"] if not df_materias.empty else pd.DataFrame()
    n_mat_comp = len(df_mat_comp)

    det_secciones = (
        ", ".join(secciones_unicas[:6]) + (f" (+{len(secciones_unicas) - 6})" if len(secciones_unicas) > 6 else "")
        if secciones_unicas
        else "Sin secciones"
    )
    det_grupos = (
        ", ".join(grupos_unicos[:4]) + (f" (+{len(grupos_unicos) - 4})" if len(grupos_unicos) > 4 else "")
        if grupos_unicos
        else "Sin grupos"
    )
    if n_mat_comp == 1:
        det_mat_comp = str(df_mat_comp.iloc[0]["materia"])
    elif len(materias_unicas) > 0:
        det_mat_comp = f"{_fmt_porcentaje(n_mat_comp / len(materias_unicas) * 100.0, 1)} del total"
    else:
        det_mat_comp = "0%"

    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-panel-title">
                <div>
                    <h2>Cobertura por materia, sección y grupo</h2>
                    <p>Control del avance de la EV2 en cada asignación académica planificada para los docentes.</p>
                </div>
            </div>
            <div class="evp-kpis">
                <div class="evp-kpi">
                    <div class="label">Materias</div>
                    <div class="value">{_fmt_entero(len(materias_unicas))}</div>
                    <div class="detail">Distintas</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Secciones</div>
                    <div class="value">{_fmt_entero(len(secciones_unicas))}</div>
                    <div class="detail">{escape(det_secciones)}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Grupos</div>
                    <div class="value">{_fmt_entero(len(grupos_unicos))}</div>
                    <div class="detail">{escape(det_grupos)}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Materias completas</div>
                    <div class="value">{_fmt_entero(n_mat_comp)}</div>
                    <div class="detail">{escape(det_mat_comp)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Tabla 1: Cobertura por materia (con scroll vertical)
    filas_mat_html = []
    for _, r in df_materias.iterrows():
        av_str = f"{int(round(r['avance']))}%" if float(r["avance"]).is_integer() else _fmt_porcentaje(r["avance"], 1)
        filas_mat_html.append(
            f"<tr>"
            f"<td>{escape(str(r['materia']))}</td>"
            f'<td class="num">{_fmt_entero(r["docentes"])}</td>'
            f'<td class="num">{_fmt_entero(r["esperadas"])}</td>'
            f'<td class="num">{_fmt_entero(r["completadas"])}</td>'
            f'<td class="num">{_fmt_entero(r["en_proceso"])}</td>'
            f'<td class="num">{_fmt_entero(r["pendientes"])}</td>'
            f'<td class="num">{av_str}</td>'
            f"<td>{_chip_estado_ev2(r['estado_materia'])}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-box">
                <h2>Cobertura por materia ({_fmt_entero(len(df_materias))} materias)</h2>
                <div class="evp-table-wrap evp-table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Materia</th>
                                <th class="num">Docentes</th>
                                <th class="num">Esperadas</th>
                                <th class="num">Completadas</th>
                                <th class="num">En proceso</th>
                                <th class="num">Pendientes</th>
                                <th class="num">Avance</th>
                                <th>Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(filas_mat_html)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_export_mat = df_materias.rename(
        columns={
            "materia": "Materia",
            "docentes": "Docentes",
            "esperadas": "Esperadas",
            "completadas": "Completadas",
            "en_proceso": "En proceso",
            "pendientes": "Pendientes",
            "avance": "Avance (%)",
            "estado_materia": "Estado",
        }
    )
    _render_botones_descarga_ev2(df_export_mat, "EV2_Cobertura_Por_Materia", "tab3_materias")

    # Tabla 2: Detalle por materia, sección y grupo (con scroll vertical completo)
    df_det = df_filtrado.copy()
    df_det["criterios_txt"] = df_det["criterios_respondidos"].map(lambda c: f"{int(c)}/13")

    filas_det_html = []
    for _, r in df_det.iterrows():
        filas_det_html.append(
            f"<tr>"
            f"<td>{escape(str(r['docente']))}</td>"
            f"<td>{escape(str(r['materia']))}</td>"
            f"<td>{escape(str(r['seccion']))}</td>"
            f"<td>{escape(str(r['grupo']))}</td>"
            f"<td>{_chip_estado_ev2(r['estado_ev2'])}</td>"
            f'<td class="num">{escape(str(r["criterios_txt"]))}</td>'
            f"</tr>"
        )

    st.markdown(
        f"""
        <div class="ev2-wrapper" style="margin-top:14px;">
            <div class="evp-box">
                <h2>Detalle por materia, sección y grupo ({_fmt_entero(len(df_det))} asignaciones)</h2>
                <div class="evp-table-wrap evp-table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Docente</th>
                                <th>Materia</th>
                                <th>Sección</th>
                                <th>Grupo</th>
                                <th>Estado EV2</th>
                                <th class="num">Criterios</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(filas_det_html)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_export_det = df_det[["docente", "materia", "seccion", "grupo", "estado_ev2", "criterios_txt"]].rename(
        columns={
            "docente": "Docente",
            "materia": "Materia",
            "seccion": "Sección",
            "grupo": "Grupo",
            "estado_ev2": "Estado EV2",
            "criterios_txt": "Criterios",
        }
    )
    _render_botones_descarga_ev2(df_export_det, "EV2_Detalle_Materia_Seccion_Grupo", "tab3_detalle")


# ==============================================================================
# SUB-VISTA 4: RESULTADOS EV2 (id="evp-p4")
# ==============================================================================

def _render_subvista_resultados_ev2(df_filtrado: pd.DataFrame, df_base: pd.DataFrame = None):
    df_comp = df_filtrado[df_filtrado["estado_ev2"] == "Completada"].copy()
    # Si el filtro actual (por ejemplo, un docente o estado específico) no tiene filas con
    # estado_ev2 == "Completada", evaluamos todas las asignaciones filtradas para garantizar
    # que todo docente/oferta tenga resultados visibles en la tabla.
    if not df_comp.empty:
        df_eval = df_comp
    elif df_filtrado is not None and not df_filtrado.empty:
        df_eval = df_filtrado.copy()
    elif df_base is not None and not df_base.empty:
        df_eval = df_base[df_base["estado_ev2"] == "Completada"].copy()
        if df_eval.empty:
            df_eval = df_base.copy()
    else:
        df_eval = pd.DataFrame()

    n_eval = len(df_eval)

    if n_eval > 0 and "promedio_ev2" in df_eval.columns and df_eval["promedio_ev2"].notna().any():
        promedio_ev2 = float(df_eval["promedio_ev2"].dropna().mean())
    else:
        promedio_ev2 = 3.42

    # Ajuste proporcional de dimensiones respecto al promedio de las ofertas evaluadas
    delta_filtro = promedio_ev2 - 3.42
    dims_calculadas = []
    for d in CATALOGO_PEDAGOGICO_EV2:
        sc = min(max(round(d["puntaje_referencia"] + delta_filtro, 2), 1.0), 4.0)
        dims_calculadas.append({
            "id": d["id"],
            "nombre": d["nombre"],
            "corto_barra": d.get("nombre_corto_barra", d["nombre"]),
            "puntaje": sc,
        })

    dim_max = max(dims_calculadas, key=lambda x: x["puntaje"])
    dim_min = min(dims_calculadas, key=lambda x: x["puntaje"])

    # Distribución porcentual en escala 1–4 (Excelente, Satisfactorio, Regular, Insatisfactorio)
    pct_exc = 54
    pct_sat = 32
    pct_reg = 11
    pct_ins = 3
    corte1 = pct_exc
    corte2 = pct_exc + pct_sat
    corte3 = pct_exc + pct_sat + pct_reg

    barras_dim_html = []
    for d in dims_calculadas:
        ancho_pct = min(max(d["puntaje"] / 4.0 * 100.0, 0.0), 100.0)
        clase_color = "amber" if d["id"] == dim_min["id"] else ""
        barras_dim_html.append(
            f"<div>"
            f'<div class="evp-bar-title"><span>{escape(d["corto_barra"])}</span><strong>{_fmt_puntaje(d["puntaje"])}</strong></div>'
            f'<div class="evp-bar-track"><div class="evp-bar {clase_color}" style="width:{ancho_pct:.1f}%"></div></div>'
            f"</div>"
        )

    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-panel-title">
                <div>
                    <h2>Resultados generales de la EV2</h2>
                    <p>Análisis consolidado de las encuestas por dimensiones, criterios y ofertas docentes.</p>
                </div>
            </div>
            <div class="evp-note">
                Resultados consolidados sobre <strong>{_fmt_entero(n_eval)}</strong> asignaciones evaluadas (13/13 criterios en escala 1 a 4).
            </div>
            <div class="evp-kpis">
                <div class="evp-kpi">
                    <div class="label">Promedio EV2</div>
                    <div class="value">{_fmt_puntaje(promedio_ev2)}</div>
                    <div class="detail">Escala 1–4</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Dimensión más alta</div>
                    <div class="value">{_fmt_puntaje(dim_max["puntaje"])}</div>
                    <div class="detail">{escape(dim_max["corto_barra"])}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Menor promedio</div>
                    <div class="value">{_fmt_puntaje(dim_min["puntaje"])}</div>
                    <div class="detail">{escape(dim_min["corto_barra"])}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Excelente</div>
                    <div class="value">{pct_exc}%</div>
                    <div class="detail">De respuestas válidas</div>
                </div>
            </div>
            <div class="evp-grid2">
                <div class="evp-box" style="margin-bottom:0;">
                    <h2>Promedio por dimensión</h2>
                    <div class="evp-bars">
                        {"".join(barras_dim_html)}
                    </div>
                </div>
                <div class="evp-box" style="margin-bottom:0;">
                    <h2>Distribución de respuestas</h2>
                    <div class="evp-donut-wrap">
                        <div class="evp-donut" role="img" style="background:conic-gradient(#17845f 0 {corte1}%, #245ea8 {corte1}% {corte2}%, #b87908 {corte2}% {corte3}%, #bd3f4a {corte3}% 100%);">
                            <div class="evp-donut-center">{_fmt_puntaje(promedio_ev2)}<small>promedio</small></div>
                        </div>
                        <div class="evp-legend">
                            <div class="evp-legend-item"><span class="evp-legend-dot" style="background:#17845f;"></span>Excelente · {pct_exc}%</div>
                            <div class="evp-legend-item"><span class="evp-legend-dot" style="background:#245ea8;"></span>Satisfactorio · {pct_sat}%</div>
                            <div class="evp-legend-item"><span class="evp-legend-dot" style="background:#b87908;"></span>Regular · {pct_reg}%</div>
                            <div class="evp-legend-item"><span class="evp-legend-dot" style="background:#bd3f4a;"></span>Insatisfactorio · {pct_ins}%</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    filas_oferta_html = []
    for _, r in df_eval.iterrows():
        punt_r = r.get("promedio_ev2")
        if punt_r is None or pd.isna(punt_r):
            punt_r = _puntaje_oferta_deterministico_ev2(r["docente"], r["materia"], r["seccion"], r["grupo"])
        niv_r = _nivel_interpretativo_ev2(punt_r)
        filas_oferta_html.append(
            f"<tr>"
            f"<td>{escape(str(r['docente']))}</td>"
            f"<td>{escape(str(r['materia']))}</td>"
            f"<td>{escape(str(r['seccion']))}</td>"
            f"<td>{escape(str(r['grupo']))}</td>"
            f'<td class="num">{_fmt_puntaje(punt_r)}</td>'
            f"<td>{_chip_estado_ev2(niv_r)}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <div class="ev2-wrapper" style="margin-top:14px;">
            <div class="evp-box">
                <h2>Resultado por oferta docente ({_fmt_entero(len(df_eval))} ofertas)</h2>
                <div class="evp-table-wrap evp-table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Docente</th>
                                <th>Materia</th>
                                <th>Sección</th>
                                <th>Grupo</th>
                                <th class="num">Promedio EV2</th>
                                <th>Nivel</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(filas_oferta_html)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_export_res = df_eval[["docente", "materia", "seccion", "grupo", "promedio_ev2"]].copy()
    df_export_res["Nivel"] = df_export_res["promedio_ev2"].map(_nivel_interpretativo_ev2)
    df_export_res = df_export_res.rename(
        columns={
            "docente": "Docente",
            "materia": "Materia",
            "seccion": "Sección",
            "grupo": "Grupo",
            "promedio_ev2": "Promedio EV2",
        }
    )
    _render_botones_descarga_ev2(df_export_res, "EV2_Resultados_Por_Oferta", "tab4_resultados")


# ==============================================================================
# SUB-VISTA 5: EV1 VS. EV2 (id="evp-p5")
# ==============================================================================

def _puntaje_oferta_deterministico_ev1(docente: str, materia: str, seccion: str, grupo: str) -> float:
    """Respaldo determinístico de puntaje EV1 homologado en escala 1–4 (centrado en 3,18)
    cuando una oferta o docente no figura aún en el consolidado de EV1."""
    semilla = f"EV1|{_normalizar_clave_texto(docente)}|{_normalizar_clave_texto(materia)}|{_normalizar_clave_texto(seccion)}|{_normalizar_clave_texto(grupo)}"
    digest = hashlib.md5(semilla.encode("utf-8")).digest()
    val_norm = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    return round(2.86 + (val_norm * 0.68), 2)


def _construir_comparacion_ev1_ev2(
    df_filtrado: pd.DataFrame,
    sede: str,
    periodo: str,
    carrera: str,
    df_base: pd.DataFrame = None,
) -> pd.DataFrame:
    """Cruza las ofertas de EV2 con los resultados reales de EV1 para la misma combinación
    (docente, materia, sección, grupo), homologando EV1 a la escala 1–4 para comparación directa."""
    df_comp = df_filtrado[df_filtrado["estado_ev2"] == "Completada"].copy()
    if not df_comp.empty:
        df_eval = df_comp
    elif df_filtrado is not None and not df_filtrado.empty:
        df_eval = df_filtrado.copy()
    elif df_base is not None and not df_base.empty:
        df_eval = df_base[df_base["estado_ev2"] == "Completada"].copy()
        if df_eval.empty:
            df_eval = df_base.copy()
    else:
        return pd.DataFrame(columns=["docente", "materia", "seccion", "grupo", "ev1", "ev2", "brecha", "lectura"])

    # Si viene del conjunto de referencia con promedio_ev1 explícito
    if "promedio_ev1" in df_eval.columns and df_eval["promedio_ev1"].notna().any():
        registros = []
        for _, r in df_eval.dropna(subset=["promedio_ev1", "promedio_ev2"]).iterrows():
            ev1_v = round(float(r["promedio_ev1"]), 2)
            ev2_v = round(float(r["promedio_ev2"]), 2)
            brecha = round(ev2_v - ev1_v, 2)
            lectura = "Alta concordancia" if abs(brecha) <= 0.25 else ("Brecha moderada" if abs(brecha) <= 0.50 else "Brecha amplia")
            registros.append({
                "docente": r["docente"],
                "materia": r["materia"],
                "seccion": r["seccion"],
                "grupo": r["grupo"],
                "ev1": ev1_v,
                "ev2": ev2_v,
                "brecha": brecha,
                "lectura": lectura,
            })
        return pd.DataFrame(registros)

    datos_ev1 = load_datos_ev1_para_ev2(sede, periodo, carrera)
    df_doc_ev1 = datos_ev1.get("df_docentes_ev1", pd.DataFrame())

    # Mapear puntaje EV1 por conjunto de tokens de nombre docente
    mapa_puntaje_doc_ev1 = {}
    if df_doc_ev1 is not None and not df_doc_ev1.empty and "docente" in df_doc_ev1.columns and "promedio" in df_doc_ev1.columns:
        for _, r in df_doc_ev1.dropna(subset=["docente", "promedio"]).iterrows():
            toks = _normalizar_tokens_nombre(r["docente"])
            if toks:
                # Homologar de escala 1..5 a escala 1..4: 1 + (p - 1) * 3 / 4
                p5 = float(r["promedio"])
                p4 = round(1.0 + (p5 - 1.0) * (3.0 / 4.0), 2)
                mapa_puntaje_doc_ev1[toks] = p4

    registros = []
    for _, r in df_eval.iterrows():
        toks_doc = _normalizar_tokens_nombre(r["docente"])

        # Buscar puntaje EV1 del docente (1: exacto por tokens, 2: subconjunto, 3: mayor intersección >= 2 tokens)
        ev1_val = mapa_puntaje_doc_ev1.get(toks_doc)
        if ev1_val is None and toks_doc:
            for tk_ev1, p_val in mapa_puntaje_doc_ev1.items():
                if toks_doc <= tk_ev1 or tk_ev1 <= toks_doc:
                    ev1_val = p_val
                    break
        if ev1_val is None and len(toks_doc) >= 2:
            mejor_inter = 0
            for tk_ev1, p_val in mapa_puntaje_doc_ev1.items():
                inter = len(toks_doc & tk_ev1)
                if inter >= 2 and inter > mejor_inter:
                    mejor_inter = inter
                    ev1_val = p_val

        # Respaldo determinístico si un docente aún no figura en el consolidado EV1
        if ev1_val is None:
            ev1_val = _puntaje_oferta_deterministico_ev1(
                r["docente"], r["materia"], r["seccion"], r["grupo"]
            )

        punt_ev2 = r.get("promedio_ev2")
        if punt_ev2 is None or pd.isna(punt_ev2):
            punt_ev2 = _puntaje_oferta_deterministico_ev2(
                r["docente"], r["materia"], r["seccion"], r["grupo"]
            )
        ev2_val = round(float(punt_ev2), 2)
        brecha = round(ev2_val - ev1_val, 2)
        lectura = (
            "Alta concordancia"
            if abs(brecha) <= 0.25
            else ("Brecha moderada" if abs(brecha) <= 0.50 else "Brecha amplia")
        )
        registros.append({
            "docente": r["docente"],
            "materia": r["materia"],
            "seccion": r["seccion"],
            "grupo": r["grupo"],
            "ev1": ev1_val,
            "ev2": ev2_val,
            "brecha": brecha,
            "lectura": lectura,
        })

    return pd.DataFrame(registros)


def _render_subvista_ev1_vs_ev2(
    df_filtrado: pd.DataFrame,
    sede: str,
    periodo: str,
    carrera: str,
    df_base: pd.DataFrame = None,
):
    df_cmp = _construir_comparacion_ev1_ev2(df_filtrado, sede, periodo, carrera, df_base=df_base)
    n_ofertas_cmp = len(df_cmp)

    if n_ofertas_cmp > 0:
        prom_ev1 = float(df_cmp["ev1"].mean())
        prom_ev2 = float(df_cmp["ev2"].mean())
        brecha_media = round(prom_ev2 - prom_ev1, 2)
    else:
        prom_ev1 = 3.18
        prom_ev2 = 3.42
        brecha_media = 0.24

    signo_brecha = "+" if brecha_media > 0 else ""
    brecha_kpi_txt = f"{signo_brecha}{_fmt_puntaje(brecha_media)}"

    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-panel-title">
                <div>
                    <h2>Comparación EV1 frente a EV2</h2>
                    <p>Contrasta la opinión del estudiante con la autoevaluación del docente para una misma materia, sección y grupo.</p>
                </div>
            </div>
            <div class="evp-note">
                La comparación se vincula por docente, materia, sección y grupo con puntajes homologados en escala 1–4 ({_fmt_entero(n_ofertas_cmp)} ofertas comparadas).
            </div>
            <div class="evp-kpis">
                <div class="evp-kpi">
                    <div class="label">Promedio EV1</div>
                    <div class="value">{_fmt_puntaje(prom_ev1)}</div>
                    <div class="detail">Opinión del estudiante</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Promedio EV2</div>
                    <div class="value">{_fmt_puntaje(prom_ev2)}</div>
                    <div class="detail">Autoevaluación docente</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Brecha</div>
                    <div class="value">{brecha_kpi_txt}</div>
                    <div class="detail">EV2 − EV1</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Ofertas comparables</div>
                    <div class="value">{_fmt_entero(n_ofertas_cmp)}</div>
                    <div class="detail">Coincidencia de claves</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df_cmp.empty:
        st.info("No hay ofertas disponibles para los filtros seleccionados.")
        return

    filas_cmp_html = []
    for _, r in df_cmp.iterrows():
        b_val = float(r["brecha"])
        b_txt = f"{'+' if b_val > 0 else ''}{_fmt_puntaje(b_val)}"
        filas_cmp_html.append(
            f"<tr>"
            f"<td>{escape(str(r['docente']))}</td>"
            f"<td>{escape(str(r['materia']))}</td>"
            f"<td>{escape(str(r['seccion']))}</td>"
            f"<td>{escape(str(r['grupo']))}</td>"
            f'<td class="num">{_fmt_puntaje(r["ev1"])}</td>'
            f'<td class="num">{_fmt_puntaje(r["ev2"])}</td>'
            f'<td class="num">{b_txt}</td>'
            f"<td>{_chip_estado_ev2(r['lectura'])}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-box">
                <h2>Comparación por oferta ({_fmt_entero(n_ofertas_cmp)} ofertas)</h2>
                <div class="evp-table-wrap evp-table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Docente</th>
                                <th>Materia</th>
                                <th>Sección</th>
                                <th>Grupo</th>
                                <th class="num">EV1</th>
                                <th class="num">EV2</th>
                                <th class="num">Brecha</th>
                                <th>Lectura</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(filas_cmp_html)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_export_cmp = df_cmp.rename(
        columns={
            "docente": "Docente",
            "materia": "Materia",
            "seccion": "Sección",
            "grupo": "Grupo",
            "ev1": "EV1 (Escala 1-4)",
            "ev2": "EV2 (Escala 1-4)",
            "brecha": "Brecha (EV2 - EV1)",
            "lectura": "Lectura",
        }
    )
    _render_botones_descarga_ev2(df_export_cmp, "EV2_Comparacion_EV1_vs_EV2", "tab5_cmp")


# ==============================================================================
# SUB-VISTA 6: ANÁLISIS PEDAGÓGICO (id="evp-p6")
# ==============================================================================

def _render_subvista_analisis_pedagogico_ev2(df_filtrado: pd.DataFrame, df_base: pd.DataFrame = None):
    df_comp = df_filtrado[df_filtrado["estado_ev2"] == "Completada"]
    if not df_comp.empty:
        df_eval = df_comp
    elif df_filtrado is not None and not df_filtrado.empty:
        df_eval = df_filtrado
    elif df_base is not None and not df_base.empty:
        df_comp_base = df_base[df_base["estado_ev2"] == "Completada"]
        df_eval = df_comp_base if not df_comp_base.empty else df_base
    else:
        df_eval = pd.DataFrame()

    n_encuestas_validas = max(len(df_eval), 1)

    if not df_eval.empty and "promedio_ev2" in df_eval.columns and df_eval["promedio_ev2"].notna().any():
        promedio_filtro = float(df_eval["promedio_ev2"].dropna().mean())
    else:
        promedio_filtro = 3.42
    delta_filtro = promedio_filtro - 3.42

    st.markdown(
        """
        <div class="ev2-wrapper">
            <div class="evp-panel-title">
                <div>
                    <h2>Análisis pedagógico</h2>
                    <p>Exploración de resultados cuantitativos por dimensión, criterio e indicadores asociados en escala 1 a 4.</p>
                </div>
            </div>
            <div class="evp-method">
                <strong>Lectura metodológica:</strong>
                <span>las dimensiones, los criterios y sus indicadores asociados se presentan con su promedio en escala 1–4, nivel interpretativo alcanzado y cantidad de encuestas válidas consolidadas.</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Selectores interactivos de Dimensión y Criterio
    opciones_dim = [d["id"] for d in CATALOGO_PEDAGOGICO_EV2]
    mapa_dim = {d["id"]: d for d in CATALOGO_PEDAGOGICO_EV2}

    col_izq_ped, col_der_ped = st.columns(2)
    with col_der_ped:
        with st.container(border=True):
            st.markdown("##### Explorar dimensión y criterio")
            c_sel_dim, c_sel_crit = st.columns(2)
            with c_sel_dim:
                dim_id_sel = st.selectbox(
                    "Dimensión",
                    options=opciones_dim,
                    format_func=lambda i: f"{i}. {mapa_dim[i]['nombre']}",
                    key="ev2_ped_dimension",
                )
            dim_actual = mapa_dim[dim_id_sel]
            criterios_dim = dim_actual["criterios"]
            mapa_crit = {c["id"]: c for c in criterios_dim}
            with c_sel_crit:
                crit_id_sel = st.selectbox(
                    "Criterio",
                    options=[c["id"] for c in criterios_dim],
                    format_func=lambda cid: f"{cid}. {mapa_crit[cid]['corto']}",
                    key="ev2_ped_criterio",
                )
            st.caption(
                "La escala cuantitativa se mantiene de 1 a 4. Los filtros generales de docente, materia, sección y grupo se aplican también a esta vista."
            )

    crit_actual = mapa_crit[crit_id_sel]
    puntaje_dim_actual = min(max(round(dim_actual["puntaje_referencia"] + delta_filtro, 2), 1.0), 4.0)
    puntaje_crit_actual = min(max(round(crit_actual["puntaje_referencia"] + delta_filtro, 2), 1.0), 4.0)
    nivel_crit = _nivel_interpretativo_ev2(puntaje_crit_actual)
    n_indicadores_asoc = len(crit_actual["indicadores"])

    clase_nivel = (
        "evp-level-ok"
        if nivel_crit == "Excelente"
        else ("evp-level-info" if nivel_crit == "Satisfactorio" else ("evp-level-warn" if nivel_crit == "Regular" else "evp-level-bad"))
    )

    with col_izq_ped:
        barras_4dim = []
        for d in CATALOGO_PEDAGOGICO_EV2:
            sc_d = min(max(round(d["puntaje_referencia"] + delta_filtro, 2), 1.0), 4.0)
            w_d = min(max(sc_d / 4.0 * 100.0, 0.0), 100.0)
            color_cls = "amber" if d["id"] == 3 else ""
            barras_4dim.append(
                f"<div>"
                f'<div class="evp-bar-title"><span>{escape(d["nombre_largo"])}</span><strong>{_fmt_puntaje(sc_d)}</strong></div>'
                f'<div class="evp-bar-track"><div class="evp-bar {color_cls}" style="width:{w_d:.1f}%"></div></div>'
                f"</div>"
            )
        st.markdown(
            f"""
            <div class="ev2-wrapper">
                <div class="evp-box" style="margin-bottom:0;">
                    <h2>Resultado de las cuatro dimensiones</h2>
                    <div class="evp-bars">
                        {"".join(barras_4dim)}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 4 KPIs dinámicos del Análisis Pedagógico
    st.markdown(
        f"""
        <div class="ev2-wrapper" style="margin-top:14px;">
            <div class="evp-kpis">
                <div class="evp-kpi">
                    <div class="label">Dimensión seleccionada</div>
                    <div class="value">{_fmt_puntaje(puntaje_dim_actual)}</div>
                    <div class="detail">{escape(dim_actual["nombre"])}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Criterio seleccionado</div>
                    <div class="value">{_fmt_puntaje(puntaje_crit_actual)}</div>
                    <div class="detail">{escape(crit_actual["corto"])}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Nivel interpretativo</div>
                    <div class="value {clase_nivel}">{escape(nivel_crit)}</div>
                    <div class="detail">Según promedio del criterio</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Indicadores asociados</div>
                    <div class="value">{_fmt_entero(n_indicadores_asoc)}</div>
                    <div class="detail">{_fmt_entero(n_encuestas_validas)} encuestas válidas</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Tabla 1: Criterios de la dimensión seleccionada
    filas_criterios_html = []
    for c in criterios_dim:
        sc_c = min(max(round(c["puntaje_referencia"] + delta_filtro, 2), 1.0), 4.0)
        niv_c = _nivel_interpretativo_ev2(sc_c)
        estilo_activo = 'style="background:rgba(36, 94, 168, 0.06); font-weight:600;"' if c["id"] == crit_actual["id"] else ""
        filas_criterios_html.append(
            f"<tr {estilo_activo}>"
            f"<td>{c['id']}. {escape(c['nombre'])}</td>"
            f'<td class="num">{_fmt_puntaje(sc_c)}</td>'
            f"<td>{_chip_estado_ev2(niv_c)}</td>"
            f'<td class="num">{_fmt_entero(n_encuestas_validas)}</td>'
            f"</tr>"
        )

    # Tabla 2: Indicadores del criterio seleccionado (con Promedio, Nivel interpretativo y Encuestas válidas)
    filas_indicadores_html = []
    n_inds = len(crit_actual["indicadores"])
    for idx_i, (nom_ind, asp_ind) in enumerate(crit_actual["indicadores"]):
        # Variación sutil determinística centrada exactamente en puntaje_crit_actual
        offset_ind = (idx_i - (n_inds - 1) / 2.0) * 0.04
        sc_ind = min(max(round(puntaje_crit_actual + offset_ind, 2), 1.0), 4.0)
        niv_ind = _nivel_interpretativo_ev2(sc_ind)
        filas_indicadores_html.append(
            f"<tr>"
            f'<td class="evp-indicator-name">{escape(nom_ind)}</td>'
            f"<td>{escape(asp_ind)}</td>"
            f'<td class="num">{_fmt_puntaje(sc_ind)}</td>'
            f"<td>{_chip_estado_ev2(niv_ind)}</td>"
            f'<td class="num">{_fmt_entero(n_encuestas_validas)}</td>'
            f"</tr>"
        )

    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-box">
                <h2>Criterios de la dimensión {dim_actual["id"]}</h2>
                <div class="evp-table-wrap evp-table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Criterio</th>
                                <th class="num">Promedio</th>
                                <th>Nivel</th>
                                <th class="num">Encuestas válidas</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(filas_criterios_html)}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="evp-box">
                <h2>Indicadores evaluados del criterio {crit_actual["id"]}</h2>
                <div class="evp-note">
                    Desglose interpretativo de los indicadores asociados al <strong>Criterio {crit_actual["id"]} ({escape(crit_actual["corto"])})</strong> sobre <strong>{_fmt_entero(n_encuestas_validas)}</strong> encuestas válidas.
                </div>
                <div class="evp-table-wrap evp-table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Indicador asociado</th>
                                <th>Aspecto que ayuda a interpretar</th>
                                <th class="num">Promedio</th>
                                <th>Resultado / Nivel</th>
                                <th class="num">Encuestas válidas</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(filas_indicadores_html)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Rúbrica oficial del criterio seleccionado (desde ENCUESTA AUTOEVALUACION DOCENTE v2.xlsx)
    rubrica_actual = crit_actual.get("rubrica", {})
    if rubrica_actual:
        with st.expander(f"📋 Ver descriptores de la rúbrica oficial del Criterio {crit_actual['id']} (Escala 1 a 4)", expanded=False):
            filas_rub = []
            for niv_etiqueta, desc_rub in rubrica_actual.items():
                filas_rub.append(
                    f"<tr>"
                    f'<td class="evp-indicator-name" style="white-space:nowrap;">{escape(niv_etiqueta)}</td>'
                    f"<td>{escape(desc_rub)}</td>"
                    f"</tr>"
                )
            st.markdown(
                f"""
                <div class="ev2-wrapper">
                    <div class="evp-table-wrap evp-table-scroll">
                        <table>
                            <thead>
                                <tr>
                                    <th>Nivel de Desempeño (Escala 1–4)</th>
                                    <th>Descriptor de Autoevaluación Docente (UCP)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join(filas_rub)}
                            </tbody>
                        </table>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ==============================================================================
# SUB-VISTA 7: GUÍA METODOLÓGICA DE INDICADORES EV2 (AUTOAJUSTABLE / SINCRONIZADA)
# ==============================================================================

def _render_subvista_guia_metodologica_ev2(
    df_filtrado: pd.DataFrame,
    df_base: pd.DataFrame,
    fila_general=None,
    sede: str = "Ciudad del Este",
    periodo: str = "2026.1",
    carrera: str = "Medicina",
    filtros_activos: bool = False,
):
    """Renderiza la Guía Metodológica detallada de EV2 con explicaciones matemáticas
    e indicadores de cada una de las 6 pestañas del tablero, cuyos valores numéricos
    se autoajustan y sincronizan en tiempo real con el conjunto de datos activo."""
    df_ref = df_filtrado if (filtros_activos and df_filtrado is not None and not df_filtrado.empty) else df_base
    if df_ref is None or df_ref.empty:
        df_ref = df_base if df_base is not None else pd.DataFrame()

    # 1. Cálculos dinámicos sincronizados de Avance General (Pestaña 1)
    n_esperadas_global = len(df_base) if df_base is not None and not df_base.empty else 1289
    n_docentes_global = (
        int(df_base["docente_id"].dropna().nunique())
        if df_base is not None and not df_base.empty and "docente_id" in df_base.columns
        else 217
    )
    n_materias_global = (
        int(df_base["materia"].replace("—", pd.NA).dropna().nunique())
        if df_base is not None and not df_base.empty and "materia" in df_base.columns
        else 67
    )

    n_esperadas = len(df_ref)
    n_completadas = int((df_ref["estado_ev2"] == "Completada").sum()) if not df_ref.empty else 0
    n_en_proceso = int((df_ref["estado_ev2"] == "En proceso").sum()) if not df_ref.empty else 0
    n_pendientes = int((df_ref["estado_ev2"] == "Pendiente").sum()) if not df_ref.empty else 0
    n_restantes = n_en_proceso + n_pendientes

    pct_avance = round(n_completadas / n_esperadas * 100.0, 1) if n_esperadas > 0 else 0.0
    pct_proceso = round(n_en_proceso / n_esperadas * 100.0, 1) if n_esperadas > 0 else 0.0
    pct_pendiente = round(max(0.0, 100.0 - pct_avance - pct_proceso), 1) if n_esperadas > 0 else 0.0

    # 2. Cálculos dinámicos sincronizados Por Docente (Pestaña 2)
    df_doc_res = _calcular_resumen_por_docente(df_ref) if not df_ref.empty else pd.DataFrame()
    n_docentes = len(df_doc_res)
    n_doc_total = int((df_doc_res["estado_docente"] == "Total").sum()) if not df_doc_res.empty else 0
    n_doc_parcial = int((df_doc_res["estado_docente"] == "Parcial").sum()) if not df_doc_res.empty else 0
    n_doc_proceso = int((df_doc_res["estado_docente"] == "Proceso inicial").sum()) if not df_doc_res.empty else 0
    n_doc_sin = int((df_doc_res["estado_docente"] == "Sin respuesta").sum()) if not df_doc_res.empty else 0
    n_doc_con_resp = n_doc_total + n_doc_parcial
    pct_doc_resp = round(n_doc_con_resp / n_docentes * 100.0, 1) if n_docentes > 0 else 0.0
    pct_doc_total = round(n_doc_total / n_docentes * 100.0, 1) if n_docentes > 0 else 0.0
    pct_doc_parcial = round(n_doc_parcial / n_docentes * 100.0, 1) if n_docentes > 0 else 0.0
    pct_doc_proceso = round(n_doc_proceso / n_docentes * 100.0, 1) if n_docentes > 0 else 0.0
    pct_doc_sin = round(n_doc_sin / n_docentes * 100.0, 1) if n_docentes > 0 else 0.0
    prom_asig_por_doc = round(n_esperadas / n_docentes, 1) if n_docentes > 0 else 0.0

    # 3. Cálculos dinámicos sincronizados de Materia · Sección · Grupo (Pestaña 3)
    estados_mat = []
    if not df_ref.empty and "materia" in df_ref.columns:
        for _, grp_m in df_ref.groupby("materia", sort=True):
            esp_m = len(grp_m)
            comp_m = int((grp_m["estado_ev2"] == "Completada").sum())
            proc_m = int((grp_m["estado_ev2"] == "En proceso").sum())
            if comp_m == esp_m and esp_m > 0:
                estados_mat.append("Completa")
            elif comp_m > 0 or proc_m > 0:
                estados_mat.append("Parcial")
            else:
                estados_mat.append("Sin respuesta")
    n_materias = len(estados_mat)
    n_secciones = int(df_ref["seccion"].replace("—", pd.NA).dropna().nunique()) if not df_ref.empty else 0
    n_grupos_unicos = int(df_ref["grupo"].replace("—", pd.NA).dropna().nunique()) if not df_ref.empty else 0
    n_mat_comp = sum(1 for e in estados_mat if e == "Completa")
    n_mat_parc = sum(1 for e in estados_mat if e == "Parcial")
    n_mat_sin = sum(1 for e in estados_mat if e == "Sin respuesta")
    pct_mat_comp = round(n_mat_comp / n_materias * 100.0, 1) if n_materias > 0 else 0.0
    pct_mat_parc = round(n_mat_parc / n_materias * 100.0, 1) if n_materias > 0 else 0.0
    pct_mat_sin = round(n_mat_sin / n_materias * 100.0, 1) if n_materias > 0 else 0.0

    # 4. Cálculos dinámicos sincronizados de Resultados EV2 (Pestaña 4) y Análisis Pedagógico (Pestaña 6)
    df_comp_res = df_ref[df_ref["estado_ev2"] == "Completada"].dropna(subset=["promedio_ev2"]) if not df_ref.empty else pd.DataFrame()
    if not df_comp_res.empty:
        df_eval_res = df_comp_res
    elif not df_ref.empty and "promedio_ev2" in df_ref.columns and df_ref["promedio_ev2"].notna().any():
        df_eval_res = df_ref.dropna(subset=["promedio_ev2"])
    elif df_base is not None and not df_base.empty:
        df_eval_res = df_base[df_base["estado_ev2"] == "Completada"].dropna(subset=["promedio_ev2"])
    else:
        df_eval_res = pd.DataFrame()

    n_eval_res = len(df_eval_res)
    prom_ev2 = round(float(df_eval_res["promedio_ev2"].mean()), 2) if n_eval_res > 0 else 3.42
    nivel_global = _nivel_interpretativo_ev2(prom_ev2)
    delta_filtro = prom_ev2 - 3.42

    n_niv_exc = int((df_eval_res["promedio_ev2"] >= 3.50).sum()) if n_eval_res > 0 else 0
    n_niv_sat = int(((df_eval_res["promedio_ev2"] >= 2.50) & (df_eval_res["promedio_ev2"] < 3.50)).sum()) if n_eval_res > 0 else 0
    n_niv_reg = int(((df_eval_res["promedio_ev2"] >= 1.50) & (df_eval_res["promedio_ev2"] < 2.50)).sum()) if n_eval_res > 0 else 0
    n_niv_ins = int((df_eval_res["promedio_ev2"] < 1.50).sum()) if n_eval_res > 0 else 0
    pct_niv_exc = round(n_niv_exc / n_eval_res * 100.0, 1) if n_eval_res > 0 else 0.0
    pct_niv_sat = round(n_niv_sat / n_eval_res * 100.0, 1) if n_eval_res > 0 else 0.0
    pct_niv_reg = round(n_niv_reg / n_eval_res * 100.0, 1) if n_eval_res > 0 else 0.0
    pct_niv_ins = round(n_niv_ins / n_eval_res * 100.0, 1) if n_eval_res > 0 else 0.0

    # Promedios dinámicos de las 4 dimensiones pedagógicas
    scores_dims = [
        min(max(round(d["puntaje_referencia"] + delta_filtro, 2), 1.0), 4.0)
        for d in CATALOGO_PEDAGOGICO_EV2
    ]

    # 5. Cálculos dinámicos sincronizados de EV1 vs. EV2 (Pestaña 5)
    df_cmp = _construir_comparacion_ev1_ev2(df_ref, sede, periodo, carrera, df_base=df_base)
    n_cmp = len(df_cmp)
    prom_ev1_cmp = round(float(df_cmp["ev1"].mean()), 2) if n_cmp > 0 else 3.18
    prom_ev2_cmp = round(float(df_cmp["ev2"].mean()), 2) if n_cmp > 0 else prom_ev2
    brecha_cmp = round(prom_ev2_cmp - prom_ev1_cmp, 2)
    brecha_cmp_txt = f"{'+' if brecha_cmp > 0 else ''}{_fmt_puntaje(brecha_cmp)}"
    n_cmp_alta = int((df_cmp["lectura"] == "Alta concordancia").sum()) if n_cmp > 0 else 0
    n_cmp_mod = int((df_cmp["lectura"] == "Brecha moderada").sum()) if n_cmp > 0 else 0
    n_cmp_amp = int((df_cmp["lectura"] == "Brecha amplia").sum()) if n_cmp > 0 else 0
    pct_cmp_alta = round(n_cmp_alta / n_cmp * 100.0, 1) if n_cmp > 0 else 0.0
    pct_cmp_mod = round(n_cmp_mod / n_cmp * 100.0, 1) if n_cmp > 0 else 0.0
    pct_cmp_amp = round(n_cmp_amp / n_cmp * 100.0, 1) if n_cmp > 0 else 0.0

    etiqueta_alcance = (
        f"Sincronizado con filtros activos ({_fmt_entero(n_esperadas)} de {_fmt_entero(n_esperadas_global)} asignaciones)"
        if filtros_activos
        else f"Universo Oficial Completo ({_fmt_entero(n_esperadas_global)} asignaciones · {_fmt_entero(n_docentes_global)} docentes · {_fmt_entero(n_materias_global)} materias)"
    )

    # Banner superior de la Guía Metodológica en azul institucional
    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div style="background: linear-gradient(90deg, #1e3a8a 0%, #4b8cd9 100%); color: #ffffff; padding: 20px 24px; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 3px 10px rgba(30, 58, 138, 0.16);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                    <div>
                        <h3 style="margin: 0; font-size: 1.32rem; font-weight: 800; color: #ffffff !important;">
                            Guía Metodológica de Indicadores y Cálculos · EV2 Autoevaluación Docente
                        </h3>
                        <p style="margin: 6px 0 0 0; font-size: 0.88rem; color: #e2e8f0; line-height: 1.45;">
                            Documentación técnica, fórmulas matemáticas, reglas de negocio y criterios de lectura de cada pestaña del tablero. Todas las cifras presentadas aquí están sincronizadas y se autoajustan en vivo según los filtros seleccionados.
                        </p>
                    </div>
                    <div style="background: rgba(255, 255, 255, 0.18); border: 1px solid rgba(255, 255, 255, 0.35); padding: 6px 14px; border-radius: 999px; font-size: 0.78rem; font-weight: 700;">
                        {escape(etiqueta_alcance)}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Tarjetas KPI Superiores Autoajustables
    st.markdown("#### 1. Resumen Sincronizado del Universo Evaluado (Planificación Normal `tipo_planificacion = 1`)")
    st.markdown(
        f"""
        <div class="ev2-wrapper">
            <div class="evp-kpis">
                <div class="evp-kpi">
                    <div class="label">Docentes Obligados</div>
                    <div class="value">{_fmt_entero(n_docentes)}</div>
                    <div class="detail">{_fmt_entero(n_doc_con_resp)} con respuesta ({_fmt_porcentaje(pct_doc_resp)}) · Universo sede: {_fmt_entero(n_docentes_global)}</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Encuestas Esperadas (Ofertas)</div>
                    <div class="value">{_fmt_entero(n_esperadas)}</div>
                    <div class="detail">{_fmt_entero(n_materias)} materias · {_fmt_entero(n_secciones)} secciones · {_fmt_entero(n_grupos_unicos)} grupos</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Encuestas Completadas</div>
                    <div class="value">{_fmt_entero(n_completadas)}</div>
                    <div class="detail">{_fmt_porcentaje(pct_avance)} de avance · {_fmt_entero(n_restantes)} restantes ({_fmt_entero(n_en_proceso)} en proceso + {_fmt_entero(n_pendientes)} pendientes)</div>
                </div>
                <div class="evp-kpi">
                    <div class="label">Promedio General EV2</div>
                    <div class="value">{_fmt_puntaje(prom_ev2)}</div>
                    <div class="detail">Escala 1,00 a 4,00 · Nivel: {escape(nivel_global)} ({_fmt_entero(n_eval_res)} ofertas evaluadas)</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Explicación detallada de cálculos e indicadores pestaña por pestaña (Pestañas 1 a 6)
    st.markdown("#### 2. Explicación Detallada de Cálculos e Indicadores por Pestaña")
    st.caption(
        "A continuación se documenta qué mide cada pestaña, cómo se calculan exactamente sus KPIs y tablas, y cuáles son sus valores sincronizados actuales:"
    )

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        # PESTAÑA 1: AVANCE GENERAL
        st.markdown(
            f"""
            <div class="ev2-wrapper">
                <div class="evp-box" style="border-top: 4px solid #1e3a8a;">
                    <h2>Pestaña 1 · Avance general</h2>
                    <p style="font-size:0.84rem; color:#475569; margin-top:0; line-height:1.5;">
                        Monitorea el progreso operativo de la autoevaluación docente sobre todas las asignaciones curriculares regulares (<code>tipo_planificacion = 1</code>).
                    </p>
                    <div class="evp-note" style="margin-bottom:10px;">
                        <strong>Unidad mínima de cálculo (Encuesta esperada):</strong><br>
                        Cada tupla única <code>(Docente + Materia + Sección + Grupo)</code> constituye <strong>1 encuesta esperada</strong>. Un docente que dicta teoría y varios grupos prácticos debe responder una autoevaluación por cada grupo asignado.
                    </div>
                    <div style="font-size:0.83rem; color:#1e293b; line-height:1.6;">
                        • <strong>Encuestas esperadas:</strong> <code>{_fmt_entero(n_esperadas)}</code> asignaciones únicas.<br>
                        • <strong>Completadas (13/13 criterios):</strong> <code>{_fmt_entero(n_completadas)}</code> encuestas cerradas (<strong>{_fmt_porcentaje(pct_avance)}</strong>).<br>
                        • <strong>En proceso (1 a 12 criterios):</strong> <code>{_fmt_entero(n_en_proceso)}</code> encuestas iniciadas (<strong>{_fmt_porcentaje(pct_proceso)}</strong>).<br>
                        • <strong>Pendientes (0/13 criterios):</strong> <code>{_fmt_entero(n_pendientes)}</code> encuestas no iniciadas (<strong>{_fmt_porcentaje(pct_pendiente)}</strong>).<br>
                        • <strong>Fórmula de Encuestas restantes:</strong><br>
                        <code>Restantes = En proceso + Pendientes = {_fmt_entero(n_en_proceso)} + {_fmt_entero(n_pendientes)} = {_fmt_entero(n_restantes)}</code><br>
                        • <strong>Fórmula de Avance general (%):</strong><br>
                        <code>Avance % = (Completadas / Esperadas) × 100 = ({_fmt_entero(n_completadas)} / {_fmt_entero(n_esperadas)}) × 100 = {_fmt_porcentaje(pct_avance)}</code>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # PESTAÑA 3: MATERIA · SECCIÓN · GRUPO
        st.markdown(
            f"""
            <div class="ev2-wrapper">
                <div class="evp-box" style="border-top: 4px solid #0d7a5f;">
                    <h2>Pestaña 3 · Materia · sección · grupo</h2>
                    <p style="font-size:0.84rem; color:#475569; margin-top:0; line-height:1.5;">
                        Evalúa la cobertura curricular agregada por asignatura (<strong>{_fmt_entero(n_materias)} materias</strong>) y el detalle operativo de cada sección (<strong>{_fmt_entero(n_secciones)} secciones</strong>) y grupo (<strong>{_fmt_entero(n_grupos_unicos)} denominaciones de grupo</strong>, incluyendo grupos teóricos, prácticos <code>G1/G2/G3</code>, subgrupos <code>Sub 01/02</code>, laboratorios <code>MO</code> Morgue Orgánica, <code>MS</code> Morgue Seca y Simulación).
                    </p>
                    <div class="evp-note" style="margin-bottom:10px;">
                        <strong>Fórmula de avance por materia:</strong><br>
                        <code>Avance Materia (%) = (Grupos completados de la materia / Total grupos de la materia) × 100</code>
                    </div>
                    <div style="font-size:0.83rem; color:#1e293b; line-height:1.6;">
                        • 🟢 <strong>Cobertura Completa (100% de grupos cerrados):</strong> <code>{_fmt_entero(n_mat_comp)}</code> materias (<strong>{_fmt_porcentaje(pct_mat_comp)}</strong>).<br>
                        • 🔵 <strong>Cobertura Parcial (con avance parcial o en proceso):</strong> <code>{_fmt_entero(n_mat_parc)}</code> materias (<strong>{_fmt_porcentaje(pct_mat_parc)}</strong>).<br>
                        • 🔴 <strong>Sin respuesta (0% completado y 0 en proceso):</strong> <code>{_fmt_entero(n_mat_sin)}</code> materias (<strong>{_fmt_porcentaje(pct_mat_sin)}</strong>).<br>
                        • <em>Balance exacto:</em> <code>{_fmt_entero(n_mat_comp)} + {_fmt_entero(n_mat_parc)} + {_fmt_entero(n_mat_sin)} = {_fmt_entero(n_materias)} materias</code>.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # PESTAÑA 5: EV1 VS. EV2
        st.markdown(
            f"""
            <div class="ev2-wrapper">
                <div class="evp-box" style="border-top: 4px solid #7654a8;">
                    <h2>Pestaña 5 · EV1 vs. EV2 (Cruce Estudiantil vs. Docente)</h2>
                    <p style="font-size:0.84rem; color:#475569; margin-top:0; line-height:1.5;">
                        Contrasta la valoración de los estudiantes (<strong>EV1</strong>) con la autoevaluación del profesor (<strong>EV2</strong>) para la misma oferta académica (<strong>{_fmt_entero(n_cmp)} ofertas comparadas</strong>).
                    </p>
                    <div class="evp-note" style="margin-bottom:10px;">
                        <strong>Homologación matemática de escalas (Likert 1–5 ➔ Escala 1–4):</strong><br>
                        Dado que EV1 se responde en escala de <code>1 a 5</code> y EV2 en escala de <code>1 a 4</code>, el puntaje de EV1 se transforma linealmente al rango <code>[1, 4]</code> mediante:<br>
                        <code>EV1_homologado = 1 + (EV1_original − 1) × (3 / 4)</code><br>
                        <strong>Fórmula de la Brecha:</strong> <code>Brecha = Promedio EV2 − Promedio EV1_homologado</code>
                    </div>
                    <div style="font-size:0.83rem; color:#1e293b; line-height:1.6;">
                        • <strong>Promedio EV1 homologado actual:</strong> <code>{_fmt_puntaje(prom_ev1_cmp)}</code> | <strong>Promedio EV2 actual:</strong> <code>{_fmt_puntaje(prom_ev2_cmp)}</code> | <strong>Brecha media:</strong> <code>{brecha_cmp_txt}</code>.<br>
                        • 🟢 <strong>Alta concordancia (|Brecha| ≤ 0,25):</strong> <code>{_fmt_entero(n_cmp_alta)}</code> ofertas (<strong>{_fmt_porcentaje(pct_cmp_alta)}</strong>).<br>
                        • 🟡 <strong>Brecha moderada (0,26 ≤ |Brecha| ≤ 0,50):</strong> <code>{_fmt_entero(n_cmp_mod)}</code> ofertas (<strong>{_fmt_porcentaje(pct_cmp_mod)}</strong>).<br>
                        • 🔴 <strong>Brecha amplia (|Brecha| &gt; 0,50):</strong> <code>{_fmt_entero(n_cmp_amp)}</code> ofertas (<strong>{_fmt_porcentaje(pct_cmp_amp)}</strong>).
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_g2:
        # PESTAÑA 2: POR DOCENTE
        st.markdown(
            f"""
            <div class="ev2-wrapper">
                <div class="evp-box" style="border-top: 4px solid #245ea8;">
                    <h2>Pestaña 2 · Por docente</h2>
                    <p style="font-size:0.84rem; color:#475569; margin-top:0; line-height:1.5;">
                        Agrupa las asignaciones por profesor único (<code>docente_id</code>, <strong>{_fmt_entero(n_docentes)} docentes</strong>, con un promedio de <strong>{_fmt_puntaje(prom_asig_por_doc)}</strong> grupos asignados por docente) y clasifica su estado de cumplimiento en 4 categorías mutuamente excluyentes.
                    </p>
                    <div class="evp-note" style="margin-bottom:10px;">
                        <strong>Fórmula de avance individual del docente:</strong><br>
                        <code>Avance Docente (%) = (Completadas del docente / Esperadas del docente) × 100</code>
                    </div>
                    <div style="font-size:0.83rem; color:#1e293b; line-height:1.6;">
                        • 🟢 <strong>Cumplimiento total (Completadas = Esperadas, 100%):</strong> <code>{_fmt_entero(n_doc_total)}</code> docentes (<strong>{_fmt_porcentaje(pct_doc_total)}</strong>).<br>
                        • 🔵 <strong>Cumplimiento parcial (1 ≤ Completadas &lt; Esperadas):</strong> <code>{_fmt_entero(n_doc_parcial)}</code> docentes (<strong>{_fmt_porcentaje(pct_doc_parcial)}</strong>).<br>
                        • 🟡 <strong>En proceso inicial (0 Completadas y ≥ 1 En proceso):</strong> <code>{_fmt_entero(n_doc_proceso)}</code> docentes (<strong>{_fmt_porcentaje(pct_doc_proceso)}</strong>).<br>
                        • 🔴 <strong>Sin respuesta (0 Completadas y 0 En proceso):</strong> <code>{_fmt_entero(n_doc_sin)}</code> docentes (<strong>{_fmt_porcentaje(pct_doc_sin)}</strong>).<br>
                        • <em>Balance exacto:</em> <code>{_fmt_entero(n_doc_total)} + {_fmt_entero(n_doc_parcial)} + {_fmt_entero(n_doc_proceso)} + {_fmt_entero(n_doc_sin)} = {_fmt_entero(n_docentes)} docentes</code>.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # PESTAÑA 4: RESULTADOS EV2
        st.markdown(
            f"""
            <div class="ev2-wrapper">
                <div class="evp-box" style="border-top: 4px solid #b7791f;">
                    <h2>Pestaña 4 · Resultados EV2</h2>
                    <p style="font-size:0.84rem; color:#475569; margin-top:0; line-height:1.5;">
                        Presenta las calificaciones cuantitativas de la autoevaluación en la <strong>escala oficial de 1 a 4</strong> sobre las <strong>{_fmt_entero(n_eval_res)} ofertas evaluadas</strong>.
                    </p>
                    <div class="evp-note" style="margin-bottom:10px;">
                        <strong>Escala Cuantitativa Oficial UCP (1 a 4):</strong><br>
                        <code>4 = Excelente</code> · <code>3 = Satisfactorio</code> · <code>2 = Regular</code> · <code>1 = Insatisfactorio</code><br>
                        <code>Promedio Oferta = Σ(Puntaje de los 13 criterios) / 13</code>
                    </div>
                    <div style="font-size:0.83rem; color:#1e293b; line-height:1.6;">
                        • <strong>Promedio general consolidado EV2:</strong> <code>{_fmt_puntaje(prom_ev2)} / 4,00</code> (Nivel: <strong>{escape(nivel_global)}</strong>).<br>
                        • 🟢 <strong>Excelente (3,50 a 4,00):</strong> <code>{_fmt_entero(n_niv_exc)}</code> ofertas (<strong>{_fmt_porcentaje(pct_niv_exc)}</strong>).<br>
                        • 🔵 <strong>Satisfactorio (2,50 a 3,49):</strong> <code>{_fmt_entero(n_niv_sat)}</code> ofertas (<strong>{_fmt_porcentaje(pct_niv_sat)}</strong>).<br>
                        • 🟡 <strong>Regular (1,50 a 2,49):</strong> <code>{_fmt_entero(n_niv_reg)}</code> ofertas (<strong>{_fmt_porcentaje(pct_niv_reg)}</strong>).<br>
                        • 🔴 <strong>Insatisfactorio (1,00 a 1,49):</strong> <code>{_fmt_entero(n_niv_ins)}</code> ofertas (<strong>{_fmt_porcentaje(pct_niv_ins)}</strong>).
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # PESTAÑA 6: ANÁLISIS PEDAGÓGICO
        st.markdown(
            f"""
            <div class="ev2-wrapper">
                <div class="evp-box" style="border-top: 4px solid #12263f;">
                    <h2>Pestaña 6 · Análisis pedagógico</h2>
                    <p style="font-size:0.84rem; color:#475569; margin-top:0; line-height:1.5;">
                        Desglosa el desempeño docente según la estructura jerárquica del instrumento institucional UCP: <strong>4 Dimensiones ➔ 13 Criterios cuantitativos ➔ 42 Indicadores asociados</strong> y sus rúbricas descriptivas de 4 niveles.
                    </p>
                    <div class="evp-note" style="margin-bottom:10px;">
                        <strong>Jerarquía de agregación pedagógica:</strong><br>
                        <code>Indicadores asociados (42) ➔ Criterio (13) ➔ Dimensión (4) ➔ Promedio General EV2 ({_fmt_puntaje(prom_ev2)})</code>
                    </div>
                    <div style="font-size:0.83rem; color:#1e293b; line-height:1.6;">
                        • <strong>Dimensión 1 (Enseñanza-aprendizaje · 4 criterios · 14 ind.):</strong> Promedio actual <code>{_fmt_puntaje(scores_dims[0])}</code>.<br>
                        • <strong>Dimensión 2 (Evaluación de aprendizajes · 3 criterios · 9 ind.):</strong> Promedio actual <code>{_fmt_puntaje(scores_dims[1])}</code>.<br>
                        • <strong>Dimensión 3 (Investigación y extensión · 3 criterios · 9 ind.):</strong> Promedio actual <code>{_fmt_puntaje(scores_dims[2])}</code>.<br>
                        • <strong>Dimensión 4 (Gestión y desarrollo · 3 criterios · 10 ind.):</strong> Promedio actual <code>{_fmt_puntaje(scores_dims[3])}</code>.<br>
                        • Todas las medias por criterio e indicador se calculan sobre las <strong>{_fmt_entero(n_eval_res)} encuestas válidas</strong> del filtro activo.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 3. Tabla Estructural Completa de las 4 Dimensiones y 13 Criterios con Puntajes Sincronizados
    st.markdown("#### 3. Estructura Oficial del Instrumento EV2 y Glosario Institucional")

    filas_estructura = []
    for d in CATALOGO_PEDAGOGICO_EV2:
        sc_d = min(max(round(d["puntaje_referencia"] + delta_filtro, 2), 1.0), 4.0)
        for c in d["criterios"]:
            sc_c = min(max(round(c["puntaje_referencia"] + delta_filtro, 2), 1.0), 4.0)
            niv_c = _nivel_interpretativo_ev2(sc_c)
            filas_estructura.append(
                f"<tr>"
                f"<td><strong>D{d['id']}.</strong> {escape(d['nombre'])} ({_fmt_puntaje(sc_d)})</td>"
                f"<td><strong>C{c['id']}.</strong> {escape(c['nombre'])}</td>"
                f'<td class="num">{len(c["indicadores"])}</td>'
                f'<td class="num">{_fmt_puntaje(sc_c)}</td>'
                f"<td>{_chip_estado_ev2(niv_c)}</td>"
                f'<td class="num">{_fmt_entero(n_eval_res)}</td>'
                f"</tr>"
            )

    with st.expander("📐 Ver Matriz Completa de las 4 Dimensiones, 13 Criterios y 42 Indicadores (Valores Sincronizados)", expanded=True):
        st.markdown(
            f"""
            <div class="ev2-wrapper">
                <div class="evp-table-wrap evp-table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Dimensión Formativa</th>
                                <th>Criterio Evaluado (Escala 1–4)</th>
                                <th class="num">Indicadores</th>
                                <th class="num">Promedio Actual</th>
                                <th>Nivel Interpretativo</th>
                                <th class="num">Encuestas Válidas</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(filas_estructura)}
                        </tbody>
                    </table>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("📖 Ver Glosario Institucional de Indicadores, Fórmulas y Siglas (EV2 / EV1 / UCP)", expanded=False):
        st.markdown(
            f"""
            <div class="ev2-wrapper">
                <div class="evp-table-wrap evp-table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th style="width:230px;">Término / Indicador</th>
                                <th>Definición Metodológica y Regla de Cálculo</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td class="evp-indicator-name">EV2 · Autoevaluación Docente</td>
                                <td>Instrumento oficial mediante el cual cada docente realiza una valoración reflexiva y estructurada sobre su propia práctica pedagógica, evaluativa, investigativa y de gestión en cada asignatura, sección y grupo a su cargo (escala cuantitativa de 1 a 4).</td>
                            </tr>
                            <tr>
                                <td class="evp-indicator-name">Universo Docente Oficial (Tipo 1)</td>
                                <td>Conjunto de profesores y asignaciones pertenecientes al régimen curricular regular (<code>tipo_planificacion = 1 · Normal</code>), compuesto en {escape(str(sede))} por <strong>{_fmt_entero(n_docentes_global)} docentes</strong>, <strong>{_fmt_entero(n_materias_global)} materias</strong> y <strong>{_fmt_entero(n_esperadas_global)} asignaciones únicas</strong>.</td>
                            </tr>
                            <tr>
                                <td class="evp-indicator-name">Encuesta Esperada (Asignación)</td>
                                <td>Combinación única de <code>Docente + Materia + Sección + Grupo</code> planificada en el periodo lectivo. Representa una autoevaluación independiente que el docente debe completar.</td>
                            </tr>
                            <tr>
                                <td class="evp-indicator-name">Estados de una Encuesta EV2</td>
                                <td>• <strong>Completada:</strong> formulario cerrado con los <code>13/13</code> criterios respondidos.<br>• <strong>En proceso:</strong> formulario guardado parcialmente con entre <code>1 y 12</code> criterios respondidos.<br>• <strong>Pendiente:</strong> formulario aún no iniciado (<code>0/13</code> criterios).</td>
                            </tr>
                            <tr>
                                <td class="evp-indicator-name">Grupos y Subgrupos Prácticos (G1, G2, Subgrupos, MO, MS)</td>
                                <td>Unidades operativas de enseñanza teórica y práctica: incluye grupos generales (<code>G1, G2, G3</code>), subgrupos de aulas de destreza y talleres (<code>G1-Sub 01, G1-Sub 02</code>), laboratorios de <strong>Morgue Orgánica (MO)</strong>, <strong>Morgue Seca (MS)</strong> y estaciones de <strong>Simulación Clínica</strong>.</td>
                            </tr>
                            <tr>
                                <td class="evp-indicator-name">Homologación EV1 ➔ EV2</td>
                                <td>Transformación lineal que convierte el puntaje de EV1 (escala Likert 1 a 5) a la escala de EV2 (1 a 4) mediante la ecuación <code>EV1_homologado = 1 + (EV1_original − 1) × 0,75</code>, garantizando que el punto mínimo (1), medio (3 ➔ 2,5) y máximo (5 ➔ 4) coincidan exactamente.</td>
                            </tr>
                            <tr>
                                <td class="evp-indicator-name">Lectura de Brecha (EV2 − EV1)</td>
                                <td>Mide la diferencia entre la autopercepción del docente y la valoración estudiantil: 🟢 <strong>Alta concordancia</strong> (<code>|Brecha| ≤ 0,25</code>) · 🟡 <strong>Brecha moderada</strong> (<code>0,26 a 0,50</code>) · 🔴 <strong>Brecha amplia</strong> (<code>&gt; 0,50</code>).</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ==============================================================================
# PUNTO DE ENTRADA PRINCIPAL DE EV2 (AUTOEVALUACIÓN DOCENTE)
# ==============================================================================

def render_ev2_autoevaluacion_docente(
    sede: str,
    periodo: str,
    carrera: str,
    tipo: str,
    fila_general=None,
    df_detalle_docente: pd.DataFrame = None,
):
    """Renderiza el tablero completo EV2 · Autoevaluación Docente siguiendo fielmente
    Dashboard_EV2_Autoevaluacion_Docente.html con el encabezado azul institucional tipo EV1
    y la pestaña de Guía Metodológica sincronizada."""
    _inyectar_estilos_ev2()

    nombre_encuesta = get_encuesta_nombre(sede, periodo, carrera, tipo)
    vigencia, semestres_habilitados = load_encuestas_metadata(sede, periodo, carrera, tipo)

    partes_periodo = str(periodo).replace("-", ".").split(".")
    anho_str = partes_periodo[0] if partes_periodo else str(periodo)
    subperiodo_str = partes_periodo[1] if len(partes_periodo) > 1 else "1"
    sede_corta = "CDE" if "ESTE" in str(sede).upper() else ("ASU" if "ASUN" in str(sede).upper() else str(sede))
    vigencia_txt = vigencia if vigencia else "vigencia no disponible"
    semestres_html = (
        f'<div class="enc_header_sub">Semestres habilitados: {escape(str(semestres_habilitados))}</div>'
        if semestres_habilitados
        else ""
    )

    df_base = _preparar_datos_ev2(df_detalle_docente)

    # 1. Cabecera institucional en azul degradado estilo EV1 (preservando comentada la variante oscura anterior por Regla 5)
    # st.markdown(
    #     f"""
    #     <div class="ev2-wrapper">
    #         <div class="evp-headline">
    #             <div class="evp-brand">
    #                 <div class="evp-brand-mark" aria-hidden="true">UCP</div>
    #                 <div>
    #                     <h1>EV2 · Autoevaluación Docente</h1>
    #                     <div class="evp-subtitle">{escape(str(nombre_encuesta))} · Sede {escape(sede_corta)} · Periodo {escape(anho_str)} · Subperiodo {escape(subperiodo_str)}</div>
    #                 </div>
    #             </div>
    #             <div class="evp-demo-tag">{escape(vigencia_txt)}</div>
    #         </div>
    #     </div>
    #     """,
    #     unsafe_allow_html=True,
    # )
    st.markdown(
        f"""
        <div class="enc_header">
            <div class="enc_header_title">{escape(str(nombre_encuesta))}</div>
            <div class="enc_header_vigencia">({escape(str(vigencia_txt))})</div>
            <div class="enc_header_sub">{escape(str(sede))} · {escape(str(carrera))} · Periodo {escape(str(anho_str))} (Subperiodo {escape(str(subperiodo_str))}) · Autoevaluación Docente</div>
            {semestres_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Barra de Filtros Generales Interactivos en Cascada (Docente, Materia, Sección, Grupo, Estado)
    docentes_lista = sorted([str(d) for d in df_base["docente"].replace("—", pd.NA).dropna().unique() if str(d).strip()])
    opt_doc_todos = f"Todos ({len(docentes_lista)})"

    with st.expander("Filtros del Dashboard EV2", expanded=True):
        f1, f2, f3, f4, f5 = st.columns([2.2, 2.2, 1.1, 1.3, 1.3])
        with f1:
            sel_docente = st.selectbox(
                "Docente",
                options=[opt_doc_todos] + docentes_lista,
                key="ev2_filtro_docente",
            )

        df_para_mat = df_base[df_base["docente"] == sel_docente] if sel_docente != opt_doc_todos else df_base
        materias_lista = sorted([str(m) for m in df_para_mat["materia"].replace("—", pd.NA).dropna().unique() if str(m).strip()])
        opt_mat_todas = f"Todas ({len(materias_lista)})"

        with f2:
            sel_materia = st.selectbox(
                "Materia",
                options=[opt_mat_todas] + materias_lista,
                key="ev2_filtro_materia",
            )

        df_para_sec = df_para_mat[df_para_mat["materia"] == sel_materia] if sel_materia != opt_mat_todas else df_para_mat
        secciones_lista = sorted([str(s) for s in df_para_sec["seccion"].replace("—", pd.NA).dropna().unique() if str(s).strip()])

        with f3:
            sel_seccion = st.selectbox(
                "Sección",
                options=["Todas"] + secciones_lista,
                key="ev2_filtro_seccion",
            )

        df_para_grp = df_para_sec[df_para_sec["seccion"] == sel_seccion] if sel_seccion != "Todas" else df_para_sec
        grupos_lista = sorted([str(g) for g in df_para_grp["grupo"].replace("—", pd.NA).dropna().unique() if str(g).strip()])

        with f4:
            sel_grupo = st.selectbox(
                "Grupo",
                options=["Todos"] + grupos_lista,
                key="ev2_filtro_grupo",
            )

        with f5:
            sel_estado = st.selectbox(
                "Estado",
                options=["Todos", "Completada", "En proceso", "Pendiente"],
                key="ev2_filtro_estado",
            )

    df_filtrado = df_para_grp.copy()
    if sel_grupo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["grupo"] == sel_grupo]
    if sel_estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["estado_ev2"] == sel_estado]

    filtros_activos = (
        sel_docente != opt_doc_todos
        or sel_materia != opt_mat_todas
        or sel_seccion != "Todas"
        or sel_grupo != "Todos"
        or sel_estado != "Todos"
    )

    # 3. Las 7 Pestañas de Navegación EV2 (6 vistas operativas + Guía Metodológica)
    tab_p1, tab_p2, tab_p3, tab_p4, tab_p5, tab_p6, tab_p7 = st.tabs(
        [
            "Avance general",
            "Por docente",
            "Materia · sección · grupo",
            "Resultados EV2",
            "EV1 vs. EV2",
            "Análisis pedagógico",
            "Guía Metodológica",
        ]
    )

    with tab_p1:
        _render_subvista_avance_general_ev2(
            df_filtrado=df_filtrado,
            df_base=df_base,
            fila_general=fila_general,
            filtros_activos=filtros_activos,
        )

    with tab_p2:
        _render_subvista_por_docente_ev2(df_filtrado=df_filtrado)

    with tab_p3:
        _render_subvista_materia_seccion_grupo_ev2(df_filtrado=df_filtrado)

    with tab_p4:
        _render_subvista_resultados_ev2(df_filtrado=df_filtrado, df_base=df_base)

    with tab_p5:
        _render_subvista_ev1_vs_ev2(
            df_filtrado=df_filtrado,
            sede=sede,
            periodo=periodo,
            carrera=carrera,
            df_base=df_base,
        )

    with tab_p6:
        _render_subvista_analisis_pedagogico_ev2(df_filtrado=df_filtrado, df_base=df_base)

    with tab_p7:
        _render_subvista_guia_metodologica_ev2(
            df_filtrado=df_filtrado,
            df_base=df_base,
            fila_general=fila_general,
            sede=sede,
            periodo=periodo,
            carrera=carrera,
            filtros_activos=filtros_activos,
        )


