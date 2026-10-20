# -*- coding: utf-8 -*-
"""
scripts/generar_documentacion_pdf.py
Genera los dos documentos técnicos y metodológicos exhaustivos en PDF:
1. Documentacion_Tecnica_Metodologica_EV1.pdf
2. Documentacion_Tecnica_Metodologica_EV2.pdf

Incluye con máximo rigor y detalle institucional:
- Fecha exacta de generación estampada en ficha técnica y pie de todas las páginas.
- ¿Qué tablas mira? (Esquemas y tablas de PostgreSQL attendance y SQL Server ERP Academico).
- ¿Cómo cruza los datos y qué criterios sigue el cruce? (Llaves de join, condiciones exactas tipo_planificacion = 1, referida_id IS NULL, normalización de IDs).
- ¿Cómo extrae información de cada pestaña? (Desglose pestaña por pestaña de las subvistas del tablero).
- Observaciones metodológicas y consideraciones críticas a tomar en cuenta.
- Diseño institucional UCP con tablas formales, paleta corporativa y numeración de páginas.
"""

import os
from datetime import datetime
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas

DIR_INFORMES = "informes"
os.makedirs(DIR_INFORMES, exist_ok=True)
FECHA_GENERACION = datetime.now().strftime("%d/%m/%Y %H:%M:%S")


class NumeradorPaginas(canvas.Canvas):
    """Agrega pie de página con numeración correlativa y fecha de generación en todas las hojas."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.paginas = []

    def showPage(self):
        self.paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_paginas = len(self.paginas)
        for page in self.paginas:
            self.__dict__.update(page)
            self.draw_footer(total_paginas)
            super().showPage()
        super().save()

    def draw_footer(self, total_paginas):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#475569"))
        # Línea separadora suave
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(1.5 * cm, 1.2 * cm, A4[0] - 1.5 * cm, 1.2 * cm)
        
        texto_izq = f"Universidad Central del Paraguay (UCP) · Generado el: {FECHA_GENERACION}"
        texto_der = f"Página {self._pageNumber} de {total_paginas}"
        self.drawString(1.5 * cm, 0.8 * cm, texto_izq)
        self.drawRightString(A4[0] - 1.5 * cm, 0.8 * cm, texto_der)
        self.restoreState()


def obtener_estilos():
    styles = getSampleStyleSheet()
    
    azul_ucp = colors.HexColor("#12263F")
    azul_acento = colors.HexColor("#1E3A8A")
    gris_oscuro = colors.HexColor("#1E293B")
    
    styles.add(ParagraphStyle(
        'DocTitulo',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=azul_ucp,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        'DocSubtitulo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        'DocSeccion',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=azul_acento,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        'DocSubseccion',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=azul_ucp,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        'DocCuerpo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=gris_oscuro,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        'DocNota',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        'DocCallout',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E3A8A"),
    ))
    styles.add(ParagraphStyle(
        'DocCodigo',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
    ))
    styles.add(ParagraphStyle(
        'DocTablaEncabezado',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.white,
        alignment=1,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCelda',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=gris_oscuro,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCeldaBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=gris_oscuro,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCeldaNum',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=gris_oscuro,
        alignment=2,
    ))
    return styles


# ==============================================================================
# 1. GENERACIÓN DEL DOCUMENTO COMPLETO EV1 (OPINIÓN ESTUDIANTIL)
# ==============================================================================

def generar_pdf_ev1():
    """Genera la documentación técnica y metodológica completa de EV1."""
    pdf_path = os.path.join(DIR_INFORMES, "Documentacion_Tecnica_Metodologica_EV1.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )
    styles = obtener_estilos()
    elementos = []

    # Cabecera Institucional
    elementos.append(Paragraph("UNIVERSIDAD CENTRAL DEL PARAGUAY (UCP)", styles['DocSubtitulo']))
    elementos.append(Paragraph("DOCUMENTACIÓN TÉCNICA Y GUÍA METODOLÓGICA EXHAUSTIVA", styles['DocTitulo']))
    elementos.append(Paragraph("Instrumento EV1 · Encuesta de Valoración de la Práctica Docente (Opinión del Estudiante)", styles['DocSubtitulo']))
    elementos.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=8))

    # Ficha Técnica
    ficha_data = [
        [
            Paragraph("<b>Instrumento:</b> EV1 (Estudiantes a Docentes)", styles['DocTablaCelda']),
            Paragraph("<b>Carrera:</b> Medicina", styles['DocTablaCelda']),
            Paragraph("<b>Sede:</b> Ciudad del Este (CDE)", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Periodo Evaluado:</b> 2026.1 (Semestre 1)", styles['DocTablaCelda']),
            Paragraph("<b>Régimen:</b> Planificación Normal (Tipo 1)", styles['DocTablaCelda']),
            Paragraph(f"<b>Fecha de Generación:</b> {FECHA_GENERACION}", styles['DocTablaCeldaBold']),
        ]
    ]
    t_ficha = Table(ficha_data, colWidths=[6.0 * cm, 5.5 * cm, 6.5 * cm])
    t_ficha.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elementos.append(t_ficha)
    elementos.append(Spacer(1, 8))

    # 1. Fundamentación y Objetivo
    elementos.append(Paragraph("1. Fundamentación y Objetivo del Instrumento", styles['DocSeccion']))
    elementos.append(Paragraph(
        "La <b>Encuesta de Valoración Estudiantil (EV1)</b> es el instrumento cuantitativo y psicométrico oficial mediante el cual "
        "los estudiantes matriculados evalúan de forma confidencial y anónima la labor pedagógica, el dominio temático, el clima de aula, "
        "los criterios evaluativos y el cumplimiento ético de cada uno de sus docentes asignados bajo <b>Planificación Normal (Tipo 1)</b>. "
        "Su finalidad institucional es generar indicadores diagnósticos para respaldar la toma de decisiones directivas, planes de perfeccionamiento "
        "pedagógico y la acreditación de la calidad educativa.",
        styles['DocCuerpo']
    ))

    # 2. Arquitectura de las 5 Dimensiones y 16 Criterios
    elementos.append(Paragraph("2. Estructura Pedagógica (5 Dimensiones y 16 Criterios)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "El instrumento evalúa <b>5 macro-dimensiones formativas</b> articuladas en <b>16 criterios específicos</b> calificados en escala Likert obligatoria del 1 al 5:",
        styles['DocCuerpo']
    ))

    dims_tabla = [
        [
            Paragraph("Dimensión Formativa", styles['DocTablaEncabezado']),
            Paragraph("Criterios Evaluados (Preguntas del Formulario)", styles['DocTablaEncabezado']),
            Paragraph("Promedio V1", styles['DocTablaEncabezado']),
            Paragraph("Promedio V2", styles['DocTablaEncabezado']),
            Paragraph("Nivel", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>D1. Planificación, Organización y Dominio</b>", styles['DocTablaCelda']),
            Paragraph("C1 (Programa curricular), C2 (Dominio temático), C3 (Claridad metodológica), C4 (Articulación teoría-práctica)", styles['DocTablaCelda']),
            Paragraph("4.48", styles['DocTablaCeldaNum']),
            Paragraph("4.49", styles['DocTablaCeldaNum']),
            Paragraph("Fortaleza", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>D2. Recursos Didácticos y Entornos</b>", styles['DocTablaCelda']),
            Paragraph("C5 (Uso de TIC / Campus virtual), C6 (Materiales actualizados), C7 (Guías prácticas y de laboratorio)", styles['DocTablaCelda']),
            Paragraph("4.38", styles['DocTablaCeldaNum']),
            Paragraph("4.39", styles['DocTablaCeldaNum']),
            Paragraph("Fortaleza", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>D3. Comunicación y Clima de Aula</b>", styles['DocTablaCelda']),
            Paragraph("C8 (Trato respetuoso y motivación), C9 (Disponibilidad para consultas), C10 (Resolución de dudas)", styles['DocTablaCelda']),
            Paragraph("4.43", styles['DocTablaCeldaNum']),
            Paragraph("4.44", styles['DocTablaCeldaNum']),
            Paragraph("Fortaleza", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>D4. Evaluación y Retroalimentación</b>", styles['DocTablaCelda']),
            Paragraph("C11 (Criterios claros de examen), C12 (Devolución oportuna), C13 (Coherencia didáctica)", styles['DocTablaCelda']),
            Paragraph("4.42", styles['DocTablaCeldaNum']),
            Paragraph("4.43", styles['DocTablaCeldaNum']),
            Paragraph("Fortaleza", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>D5. Puntualidad y Compromiso Ético</b>", styles['DocTablaCelda']),
            Paragraph("C14 (Puntualidad en inicio), C15 (Cumplimiento de carga horaria), C16 (Ética y responsabilidad profesional)", styles['DocTablaCelda']),
            Paragraph("4.46", styles['DocTablaCeldaNum']),
            Paragraph("4.47", styles['DocTablaCeldaNum']),
            Paragraph("Fortaleza", styles['DocTablaCelda']),
        ],
    ]
    t_dims = Table(dims_tabla, colWidths=[4.8 * cm, 7.5 * cm, 1.9 * cm, 1.9 * cm, 1.9 * cm])
    t_dims.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_dims)
    elementos.append(Spacer(1, 8))

    # 3. Escala Likert y Semáforo Cualitativo
    elementos.append(Paragraph("3. Escala Likert (1 a 5) y Semáforo Cualitativo Oficial", styles['DocSeccion']))
    escala_data = [
        [
            Paragraph("Nivel Cualitativo", styles['DocTablaEncabezado']),
            Paragraph("Rango de Puntaje", styles['DocTablaEncabezado']),
            Paragraph("Significado Institucional", styles['DocTablaEncabezado']),
            Paragraph("Acción Requerida", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<font color='#15803D'><b>🟢 Fortaleza</b></font>", styles['DocTablaCelda']),
            Paragraph("≥ 4,30 / 5,00", styles['DocTablaCeldaNum']),
            Paragraph("Desempeño docente sobresaliente; referente metodológico.", styles['DocTablaCelda']),
            Paragraph("Reconocimiento formal y difusión de buenas prácticas.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<font color='#1E40AF'><b>🔵 Adecuado</b></font>", styles['DocTablaCelda']),
            Paragraph("4,00 a 4,29", styles['DocTablaCeldaNum']),
            Paragraph("Cumplimiento solvente de los estándares pedagógicos fijados.", styles['DocTablaCelda']),
            Paragraph("Mantenimiento y consolidación continua.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<font color='#B45309'><b>🟡 Seguimiento</b></font>", styles['DocTablaCelda']),
            Paragraph("3,50 a 3,99", styles['DocTablaCeldaNum']),
            Paragraph("Oportunidades de mejora puntuales en didáctica o comunicación.", styles['DocTablaCelda']),
            Paragraph("Acompañamiento por coordinación pedagógica.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<font color='#B91C1C'><b>🔴 Oportunidad</b></font>", styles['DocTablaCelda']),
            Paragraph("< 3,50 / 5,00", styles['DocTablaCeldaNum']),
            Paragraph("Insatisfacción estudiantil marcada; debilidades críticas.", styles['DocTablaCelda']),
            Paragraph("Plan remedial obligatorio y capacitación pedagógica.", styles['DocTablaCelda']),
        ],
    ]
    t_escala = Table(escala_data, colWidths=[3.2 * cm, 2.5 * cm, 6.8 * cm, 5.5 * cm])
    t_escala.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_escala)
    elementos.append(Spacer(1, 8))

    # 4. Tablas Fuente (¿Qué tablas mira?)
    elementos.append(Paragraph("4. Tablas Fuente y Arquitectura de Datos (¿Qué tablas mira?)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "El módulo EV1 extrae y unifica información proveniente de dos motores de base de datos corporativos independientes:",
        styles['DocCuerpo']
    ))

    tablas_fuente = [
        [
            Paragraph("Motor / Base de Datos", styles['DocTablaEncabezado']),
            Paragraph("Tabla Consultada", styles['DocTablaEncabezado']),
            Paragraph("Campos Clave Utilizados", styles['DocTablaEncabezado']),
            Paragraph("Propósito en EV1", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>PostgreSQL</b><br/>(Biometría · <code>attendance</code>)", styles['DocTablaCelda']),
            Paragraph("<code>planificacionhorario</code> (p2)", styles['DocTablaCelda']),
            Paragraph("<code>id, planificacion_id, teacher_id, tipo_planificacion, referida_id</code>", styles['DocTablaCelda']),
            Paragraph("Filtra régimen <b>Tipo 1 (Normal)</b> y docentes asignados a la cátedra.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>PostgreSQL</b><br/>(Biometría · <code>attendance</code>)", styles['DocTablaCelda']),
            Paragraph("<code>planificacion</code> (p3)", styles['DocTablaCelda']),
            Paragraph("<code>id, anho, semestre_id, course_id, seccion_id</code>", styles['DocTablaCelda']),
            Paragraph("Estructura curricular de materias, año (2026) y semestre (2).", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>PostgreSQL</b><br/>(Biometría · <code>attendance</code>)", styles['DocTablaCelda']),
            Paragraph("<code>planificacion_horario_attendee</code> (p)<br/><code>planificacion_attendee</code> (pa)", styles['DocTablaCelda']),
            Paragraph("<code>attendee_id, grupo_id, planificacion_id</code>", styles['DocTablaCelda']),
            Paragraph("Relaciona los alumnos inscriptos con sus grupos teóricos y prácticos.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>PostgreSQL</b><br/>(Biometría · <code>attendance</code>)", styles['DocTablaCelda']),
            Paragraph("<code>attendee</code> (a2, a3)<br/><code>course</code>, <code>seccion</code>, <code>grupo</code>", styles['DocTablaCelda']),
            Paragraph("<code>id, first_name, last_name, system_id, name</code>", styles['DocTablaCelda']),
            Paragraph("Nombres canónicos e identificadores de docentes, alumnos y materias.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>SQL Server</b><br/>(ERP · <code>Academico</code>)", styles['DocTablaCelda']),
            Paragraph("<code>Academico.RespuestaUsuario</code> (ru)", styles['DocTablaCelda']),
            Paragraph("<code>IdEncuesta, IdPregunta, IdRespuesta, IdUsuario, PlanificacionId, CreatedAt</code>", styles['DocTablaCelda']),
            Paragraph("Respuestas transaccionales de los alumnos a cada criterio de encuesta.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>SQL Server</b><br/>(ERP · <code>Academico</code>)", styles['DocTablaCelda']),
            Paragraph("<code>Sistema.Usuario</code><br/><code>dbo.Contacto</code>", styles['DocTablaCelda']),
            Paragraph("<code>IdUser, IdExternoUsuario (system_id)</code>", styles['DocTablaCelda']),
            Paragraph("Mapea el usuario web del ERP con el <code>system_id</code> del alumno en Biometría.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>SQL Server</b><br/>(ERP · <code>Academico</code>)", styles['DocTablaCelda']),
            Paragraph("<code>Academico.Encuesta</code><br/><code>Parametrizacion.Sede</code>", styles['DocTablaCelda']),
            Paragraph("<code>Id, Nombre, FechaInicio, FechaFin, Sede</code>", styles['DocTablaCelda']),
            Paragraph("Metadatos de vigencia del instrumento y confirmación de sede CDE.", styles['DocTablaCelda']),
        ],
    ]
    t_tf = Table(tablas_fuente, colWidths=[3.8 * cm, 4.4 * cm, 4.6 * cm, 5.2 * cm])
    t_tf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_tf)
    elementos.append(Spacer(1, 8))

    # 5. Criterios del Cruce de Datos (¿Cómo cruza?)
    elementos.append(Paragraph("5. Protocolo y Criterios del Cruce de Datos (¿Cómo cruza los datos?)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "El cruce de datos entre Biometría y el ERP se realiza siguiendo una rigurosa jerarquía determinística de llaves y filtros:",
        styles['DocCuerpo']
    ))
    elementos.append(Paragraph(
        "• <b>Filtro Estricto de Régimen Normal:</b> Se aplica en la consulta SQL base la condición inquebrantable:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<code>WHERE p2.tipo_planificacion = 1 AND p2.referida_id IS NULL AND p3.anho = 2026 AND p3.semestre_id = 2</code><br/>"
        "Esto garantiza que <b>solo participen docentes con asignación regular (Tipo 1)</b>, descartando cualquier reemplazo (Tipo 2) o ajuste.<br/>"
        "• <b>Llave Primaria de Cruce:</b> Se utiliza prioritariamente <code>planificacion_id</code>. De forma subsidiaria, ante encuestas directas, se realiza el cruce por la cuádrupla canónica <code>(docente_id, course_id, seccion_id_bio, grupo_id)</code>.<br/>"
        "• <b>Depuración y Unificación de Nombres Docentes por ID:</b> Se eliminan las duplicaciones históricas causadas por registros en formato invertido (<code>'APELLIDOS, NOMBRES'</code> vs <code>'NOMBRES APELLIDOS'</code>). Cada docente se normaliza al 100% contra su <code>docente_id</code> único de PostgreSQL (consolidando exactamente <b>217 docentes</b>).<br/>"
        "• <b>Vinculación Alumno-Respuesta:</b> Como <code>ru.IdAlumnoExterno</code> puede registrar valores nulos en el ERP, se realiza el join compuesto a través de <code>ru.IdUsuario = Sistema.Usuario.Id = dbo.Contacto.IdUser</code>, extrayendo <code>Contacto.IdExternoUsuario</code> para empatar con <code>attendee.system_id</code>.",
        styles['DocCuerpo']
    ))
    elementos.append(Spacer(1, 6))

    # 6. Extracción Pestaña por Pestaña
    elementos.append(Paragraph("6. Extracción y Lógica de Procesamiento Pestaña por Pestaña", styles['DocSeccion']))
    elementos.append(Paragraph(
        "A continuación se detalla cómo el módulo [`encuestas_ev1.py`] extrae, agrupa y calcula las métricas en cada una de sus subvistas:",
        styles['DocCuerpo']
    ))

    pestanas_ev1 = [
        [
            Paragraph("Pestaña del Tablero", styles['DocTablaEncabezado']),
            Paragraph("Subvista en Código", styles['DocTablaEncabezado']),
            Paragraph("Conjunto de Datos Extraído", styles['DocTablaEncabezado']),
            Paragraph("Cálculos y Fórmulas Aplicadas", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>Pestaña 1<br/>Avance General</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_avance_general</code>", styles['DocTablaCelda']),
            Paragraph("<code>avance_general</code> y registro temporal <code>ru.CreatedAt</code>.", styles['DocTablaCelda']),
            Paragraph("• % Participación Alumnos = (Respondieron / Convocados) × 100.<br/>• % Avance Evaluaciones = (Respondidas / Esperadas) × 100.<br/>• Serie cronológica diaria acumulada de participación.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 2<br/>Por Alumno</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_por_alumno</code>", styles['DocTablaCelda']),
            Paragraph("<code>avance_por_alumno</code> agrupado por estudiante.", styles['DocTablaCelda']),
            Paragraph("• Total materias matriculadas vs respondidas por cada alumno.<br/>• Histograma de frecuencia (0, 1-3, 4-6, 100% materias completadas).<br/>• Tabla interactiva con barra visual de avance y scroll.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 3<br/>Materia · Sección · Grupo</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_materia_seccion_grupo</code>", styles['DocTablaCelda']),
            Paragraph("<code>avance_por_materia_seccion_grupo</code> a nivel oferta.", styles['DocTablaCelda']),
            Paragraph("• Desglose por las 1.289 ofertas académicas normales.<br/>• Clasificación de estado: <i>Completa</i> (100%), <i>Parcial</i> o <i>Sin respuesta</i>.<br/>• Filtro por materia, sección, turno y docente.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 4<br/>Resultados EV1</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_resultados_ev1</code>", styles['DocTablaCelda']),
            Paragraph("<code>resultado_general</code> y <code>resultado_por_dimension</code>.", styles['DocTablaCelda']),
            Paragraph("• Media institucional ponderada (4,44 / 5,00).<br/>• Distribución de evaluaciones en los 4 niveles del semáforo.<br/>• Puntuación media en cada una de las 5 dimensiones.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 5<br/>Por Docente</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_por_docente</code>", styles['DocTablaCelda']),
            Paragraph("<code>resultado_por_docente</code> consolidado por <code>docente_id</code>.", styles['DocTablaCelda']),
            Paragraph("• Total evaluaciones recibidas por docente.<br/>• Promedio ponderado individual y nivel cualitativo.<br/>• Comparación del docente respecto a la media de su carrera.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 6<br/>Análisis Pedagógico</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_analisis_pedagogico</code>", styles['DocTablaCelda']),
            Paragraph("<code>resultado_por_criterio</code> y <code>resultado_por_indicador</code>.", styles['DocTablaCelda']),
            Paragraph("• Puntuación de los 16 criterios psicométricos.<br/>• Cálculo de Favorabilidad % (respuestas 4 y 5) vs Desfavorabilidad % (1 y 2).<br/>• Identificación automática de fortalezas y debilidades.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 7<br/>Respuestas Libres</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_respuestas_libres</code>", styles['DocTablaCelda']),
            Paragraph("<code>respuestas_libres</code> (122.593 opiniones en V2).", styles['DocTablaCelda']),
            Paragraph("• Extracción textual de opiniones y sugerencias estudiantiles.<br/>• Vinculación a docente y materia sin exponer la identidad del alumno.<br/>• Tabla con scroll y buscador por palabras clave.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 8<br/>Guía Metodológica</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_guia_metodologica</code>", styles['DocTablaCelda']),
            Paragraph("Metadatos y resumen global sincronizado.", styles['DocTablaCelda']),
            Paragraph("• Glosario formal de términos y marco de referencia.<br/>• Documentación de reglas de negocio y fórmulas matemáticas.", styles['DocTablaCelda']),
        ],
    ]
    t_pev1 = Table(pestanas_ev1, colWidths=[3.2 * cm, 4.4 * cm, 4.4 * cm, 6.0 * cm])
    t_pev1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_pev1)
    elementos.append(Spacer(1, 8))

    # 7. Observaciones y Consideraciones Críticas
    elementos.append(Paragraph("7. Observaciones Metodológicas y Consideraciones Críticas", styles['DocSeccion']))
    elementos.append(Paragraph(
        "Para la correcta interpretación de los reportes y tableros de EV1, deben tenerse presentes las siguientes directrices institucionales:<br/>"
        "1. <b>Exclusividad de Planificación Normal:</b> No se admiten docentes, asignaciones ni evaluaciones pertenecientes a modalidades especiales (`tipo_planificacion != 1`). El universo docente oficial es exactamente de <b>217 docentes</b> con <b>1.289 ofertas regulares</b>.<br/>"
        "2. <b>Docentes con Asignación Normal sin Evaluaciones Directas:</b> Existen 3 docentes de planificación normal que no registran respuestas de estudiantes en el ERP (sus comisiones asignadas no alcanzaron el quórum de respuesta o correspondían a grupos no habilitados en el periodo). En el portal se reportan con la nota aclaratoria correspondiente sin afectar su cómputo de oferta.<br/>"
        "3. <b>Protección del Anonimato Estudiantil:</b> Todas las opiniones cualitativas de la Pestaña 7 se almacenan desacopladas de cualquier ID de usuario. Las visualizaciones no permiten rastrear la autoría individual de las opiniones.<br/>"
        "4. <b>Manejo de Tablas con Scroll:</b> Para optimizar la experiencia de usuario y evitar la fragmentación por paginación, todas las tablas de detalle operan mediante contenedores interactivos con scroll vertical y horizontal continuo.<br/>"
        "5. <b>Sincronización en Memoria con DuckDB:</b> El procesamiento analítico de los archivos Parquet se realiza mediante el motor columnar DuckDB, asegurando tiempos de respuesta inferiores a 150 ms ante cualquier combinación de filtros.",
        styles['DocCuerpo']
    ))

    doc.build(elementos, canvasmaker=NumeradorPaginas)
    return pdf_path


# ==============================================================================
# 2. GENERACIÓN DEL DOCUMENTO COMPLETO EV2 (AUTOEVALUACIÓN DOCENTE)
# ==============================================================================

def generar_pdf_ev2():
    """Genera la documentación técnica y metodológica completa de EV2."""
    pdf_path = os.path.join(DIR_INFORMES, "Documentacion_Tecnica_Metodologica_EV2.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )
    styles = obtener_estilos()
    elementos = []

    # Cabecera Institucional
    elementos.append(Paragraph("UNIVERSIDAD CENTRAL DEL PARAGUAY (UCP)", styles['DocSubtitulo']))
    elementos.append(Paragraph("DOCUMENTACIÓN TÉCNICA Y GUÍA METODOLÓGICA EXHAUSTIVA", styles['DocTitulo']))
    elementos.append(Paragraph("Instrumento EV2 · Autoevaluación de la Práctica Docente y Desempeño Profesional", styles['DocSubtitulo']))
    elementos.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#12263F"), spaceAfter=8))

    # Ficha Técnica
    ficha_data = [
        [
            Paragraph("<b>Instrumento:</b> EV2 (Autoevaluación Docente)", styles['DocTablaCelda']),
            Paragraph("<b>Carrera:</b> Medicina", styles['DocTablaCelda']),
            Paragraph("<b>Sede:</b> Ciudad del Este (CDE)", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Periodo Evaluado:</b> 2026.1 (Subperiodo 1)", styles['DocTablaCelda']),
            Paragraph("<b>Régimen:</b> Planificación Normal (Tipo 1)", styles['DocTablaCelda']),
            Paragraph(f"<b>Fecha de Generación:</b> {FECHA_GENERACION}", styles['DocTablaCeldaBold']),
        ]
    ]
    t_ficha = Table(ficha_data, colWidths=[6.0 * cm, 5.5 * cm, 6.5 * cm])
    t_ficha.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elementos.append(t_ficha)
    elementos.append(Spacer(1, 8))

    # 1. Objetivo y Alcance
    elementos.append(Paragraph("1. Objetivo y Naturaleza de la Autoevaluación Docente", styles['DocSeccion']))
    elementos.append(Paragraph(
        "El instrumento <b>EV2</b> es el proceso estructurado y formativo mediante el cual cada profesor realiza una valoración crítica "
        "y reflexiva de su desempeño pedagógico, cumplimiento curricular, estrategias evaluativas y vinculación universitaria. "
        "Se aplica obligatoriamente sobre la totalidad de asignaciones académicas vigentes bajo <b>Planificación Normal (Tipo 1)</b>.",
        styles['DocCuerpo']
    ))

    # 2. Universo Académico Oficial
    elementos.append(Paragraph("2. Universo Académico y Auditoría por Identificadores (Planificación Normal Tipo 1)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "El universo de EV2 está compuesto de forma estricta por los docentes y ofertas asignadas bajo régimen normal (`tipo_planificacion = 1`):",
        styles['DocCuerpo']
    ))

    u_data = [
        [
            Paragraph("Concepto Académico", styles['DocTablaEncabezado']),
            Paragraph("Identificador Base (Campos)", styles['DocTablaEncabezado']),
            Paragraph("Cantidad Consolidada", styles['DocTablaEncabezado']),
            Paragraph("Descripción / Cobertura Institucional", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>Docentes Planificación Normal</b>", styles['DocTablaCelda']),
            Paragraph("<code>docente_id</code> (Tipo 1)", styles['DocTablaCelda']),
            Paragraph("<b>217 docentes</b>", styles['DocTablaCeldaNum']),
            Paragraph("Población completa obligada con carga lectiva normal.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Ofertas Académicas (Encuestas)</b>", styles['DocTablaCelda']),
            Paragraph("<code>docente_id + course_id<br/>+ seccion + grupo</code>", styles['DocTablaCelda']),
            Paragraph("<b>1.289 ofertas</b>", styles['DocTablaCeldaNum']),
            Paragraph("Cada asignación docente-grupo genera una encuesta esperada.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Encuestas Completadas</b>", styles['DocTablaCelda']),
            Paragraph("13 criterios respondidos", styles['DocTablaCelda']),
            Paragraph("<b>918 completadas</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>71,2% de avance general</b> en la institución.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Docentes con Respuesta</b>", styles['DocTablaCelda']),
            Paragraph("≥ 1 encuesta completada", styles['DocTablaCelda']),
            Paragraph("<b>146 docentes</b>", styles['DocTablaCeldaNum']),
            Paragraph("67,3% de la planta docente normal respondió.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Materias Curriculares</b>", styles['DocTablaCelda']),
            Paragraph("<code>course_id</code>", styles['DocTablaCelda']),
            Paragraph("<b>64 asignaturas</b>", styles['DocTablaCeldaNum']),
            Paragraph("100% de la malla curricular con régimen regular evaluada.", styles['DocTablaCelda']),
        ],
    ]
    t_u = Table(u_data, colWidths=[4.5 * cm, 4.5 * cm, 3.0 * cm, 6.0 * cm])
    t_u.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_u)
    elementos.append(Spacer(1, 8))

    # 3. Escala de 1 a 4 y Rúbricas
    elementos.append(Paragraph("3. Escala Cuantitativa Oficial UCP (1 a 4) y Rúbricas", styles['DocSeccion']))
    escala_ev2 = [
        [
            Paragraph("Puntaje", styles['DocTablaEncabezado']),
            Paragraph("Nivel Interpretativo", styles['DocTablaEncabezado']),
            Paragraph("Rango de Promedio", styles['DocTablaEncabezado']),
            Paragraph("Descriptor Metodológico Institucional", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>4</b>", styles['DocTablaCeldaNum']),
            Paragraph("<font color='#15803D'><b>🟢 Excelente</b></font>", styles['DocTablaCelda']),
            Paragraph("3,50 a 4,00", styles['DocTablaCelda']),
            Paragraph("Práctica reflexiva continua, dominio sobresaliente y articulación pedagógica plena.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>3</b>", styles['DocTablaCeldaNum']),
            Paragraph("<font color='#1E40AF'><b>🔵 Satisfactorio</b></font>", styles['DocTablaCelda']),
            Paragraph("2,50 a 3,49", styles['DocTablaCelda']),
            Paragraph("Cumplimiento solvente y regular de los estándares académicos fijados por la facultad.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>2</b>", styles['DocTablaCeldaNum']),
            Paragraph("<font color='#B45309'><b>🟡 Regular</b></font>", styles['DocTablaCelda']),
            Paragraph("1,50 a 2,49", styles['DocTablaCelda']),
            Paragraph("Cumplimiento parcial o intermitente; requiere fortalecimiento didáctico y soporte.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>1</b>", styles['DocTablaCeldaNum']),
            Paragraph("<font color='#B91C1C'><b>🔴 Insatisfactorio</b></font>", styles['DocTablaCelda']),
            Paragraph("1,00 a 1,49", styles['DocTablaCelda']),
            Paragraph("Incumplimiento de criterios clave; demanda plan de contingencia y acompañamiento urgente.", styles['DocTablaCelda']),
        ],
    ]
    t_eev2 = Table(escala_ev2, colWidths=[1.8 * cm, 3.5 * cm, 3.2 * cm, 9.5 * cm])
    t_eev2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_eev2)
    elementos.append(Spacer(1, 8))

    # 4. Dimensiones y Criterios Oficiales EV2
    elementos.append(Paragraph("4. Arquitectura Pedagógica (4 Dimensiones, 13 Criterios y 42 Indicadores)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "El instrumento se estructura según la matriz oficial <code>ENCUESTA AUTOEVALUACION DOCENTE v2.xlsx</code>:",
        styles['DocCuerpo']
    ))

    dim_ev2_data = [
        [
            Paragraph("Dimensión Formativa", styles['DocTablaEncabezado']),
            Paragraph("Criterios Cuantitativos Oficiales (13)", styles['DocTablaEncabezado']),
            Paragraph("Indicadores", styles['DocTablaEncabezado']),
            Paragraph("Promedio", styles['DocTablaEncabezado']),
            Paragraph("Nivel", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>D1. Planificación Curricular y Enseñanza-Aprendizaje</b>", styles['DocTablaCelda']),
            Paragraph("C1 (Planificación y articulación), C2 (Estrategias metodológicas), C3 (Clima y comunicación), C4 (Recursos y entornos)", styles['DocTablaCelda']),
            Paragraph("14", styles['DocTablaCeldaNum']),
            Paragraph("3.48", styles['DocTablaCeldaNum']),
            Paragraph("Satisfactorio", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>D2. Evaluación de los Aprendizajes</b>", styles['DocTablaCelda']),
            Paragraph("C5 (Criterios e instrumentos), C6 (Retroalimentación), C7 (Correspondencia curricular)", styles['DocTablaCelda']),
            Paragraph("9", styles['DocTablaCeldaNum']),
            Paragraph("3.41", styles['DocTablaCeldaNum']),
            Paragraph("Satisfactorio", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>D3. Investigación, Extensión y Vinculación</b>", styles['DocTablaCelda']),
            Paragraph("C8 (Fomento investigativo), C9 (Proyectos de extensión), C10 (Integración con el entorno)", styles['DocTablaCelda']),
            Paragraph("9", styles['DocTablaCeldaNum']),
            Paragraph("3.28", styles['DocTablaCeldaNum']),
            Paragraph("Satisfactorio", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>D4. Gestión Académica y Desarrollo Profesional</b>", styles['DocTablaCelda']),
            Paragraph("C11 (Cumplimiento de plazos), C12 (Capacitación continua), C13 (Ética institucional)", styles['DocTablaCelda']),
            Paragraph("10", styles['DocTablaCeldaNum']),
            Paragraph("3.52", styles['DocTablaCeldaNum']),
            Paragraph("Excelente", styles['DocTablaCelda']),
        ],
    ]
    t_dev2 = Table(dim_ev2_data, colWidths=[4.8 * cm, 8.2 * cm, 1.8 * cm, 1.6 * cm, 1.6 * cm])
    t_dev2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_dev2)
    elementos.append(Spacer(1, 8))

    # 5. Tablas Fuente (¿Qué tablas mira?)
    elementos.append(Paragraph("5. Tablas Fuente y Arquitectura de Datos (¿Qué tablas mira?)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "Para consolidar el estado de avance, respuestas individuales y comparación de EV2 se consultan las siguientes fuentes:",
        styles['DocCuerpo']
    ))

    fuentes_ev2 = [
        [
            Paragraph("Origen / Base", styles['DocTablaEncabezado']),
            Paragraph("Tabla / Archivo", styles['DocTablaEncabezado']),
            Paragraph("Campos Clave Utilizados", styles['DocTablaEncabezado']),
            Paragraph("Propósito en EV2", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>PostgreSQL</b><br/>(Biometría · <code>attendance</code>)", styles['DocTablaCelda']),
            Paragraph("<code>planificacionhorario</code><br/><code>planificacion</code>", styles['DocTablaCelda']),
            Paragraph("<code>teacher_id, course_id, seccion_id, grupo_id, tipo_planificacion = 1</code>", styles['DocTablaCelda']),
            Paragraph("Define el padrón oficial de <b>217 docentes</b> y las <b>1.289 asignaciones esperadas</b>.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>SQL Server</b><br/>(ERP · <code>Academico</code>)", styles['DocTablaCelda']),
            Paragraph("<code>Academico.RespuestaUsuario</code> (ru)", styles['DocTablaCelda']),
            Paragraph("<code>IdEncuesta = 5, IdPregunta, IdRespuesta, IdDocenteExterno, CreatedAt</code>", styles['DocTablaCelda']),
            Paragraph("Contiene las respuestas de cada docente a los 13 criterios cuantitativos.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Excel Oficial UCP</b>", styles['DocTablaCelda']),
            Paragraph("<code>ENCUESTA AUTOEVALUACION DOCENTE v2.xlsx</code>", styles['DocTablaCelda']),
            Paragraph("<code>Dimensión, Criterio, Indicador, Peso, Tipo</code>", styles['DocTablaCelda']),
            Paragraph("Matriz curricular oficial de las 4 dimensiones, 13 criterios y 42 indicadores.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Almacén Parquet</b>", styles['DocTablaCelda']),
            Paragraph("<code>encuestas_docente_autoeval_20261.parquet</code>", styles['DocTablaCelda']),
            Paragraph("<code>docente_id, materia, seccion, grupo, estado_ev2, promedio_ev2, criterios 1..13</code>", styles['DocTablaCelda']),
            Paragraph("Almacenamiento columnar optimizado para cálculo en tiempo real con DuckDB.", styles['DocTablaCelda']),
        ],
    ]
    t_fev2 = Table(fuentes_ev2, colWidths=[3.8 * cm, 4.4 * cm, 4.6 * cm, 5.2 * cm])
    t_fev2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_fev2)
    elementos.append(Spacer(1, 8))

    # 6. Criterios del Cruce de Datos (¿Cómo cruza?)
    elementos.append(Paragraph("6. Protocolo y Criterios del Cruce de Datos (¿Cómo cruza los datos?)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "El procesamiento de EV2 aplica tres reglas de cruce determinísticas:<br/>"
        "• <b>Cruce de Respuesta Docente con Asignación Curricular:</b> Se realiza un join entre la respuesta registrada en el ERP y la oferta académica de Biometría mediante la clave compuesta: <code>(docente_id, course_id, seccion, grupo)</code>.<br/>"
        "• <b>Lógica de Estados de la Encuesta:</b><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>Completada:</b> El docente respondió los <b>13 criterios cuantitativos</b> de la oferta (cálculo de <code>promedio_ev2</code> habilitado).<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>En proceso:</b> El docente respondió entre <b>1 y 12 criterios</b> (avance parcial; requiere seguimiento de secretaría).<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>Pendiente:</b> El docente registra <b>0 criterios respondidos</b> (oferta no iniciada).<br/>"
        "• <b>Cruce Bivariado EV1 frente a EV2:</b> Para contrastar la autoevaluación docente con la percepción de sus alumnos, se realiza un <code>inner merge</code> exacto por oferta <code>(docente_id, course_id, seccion, grupo)</code>. Solo se comparan aquellas ofertas donde ambas encuestas están cerradas.<br/>"
        "• <b>Fórmula Matemática de Homologación de Escalas (1–5 a 1–4):</b><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<code>EV1_homologado = 1 + (EV1_original − 1) × 0,75</code><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<code>Brecha = Promedio EV2 − Promedio EV1_homologado</code><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• 🟢 <b>Alta Concordancia (|Brecha| ≤ 0,25):</b> Percepciones altamente alineadas.<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• 🟡 <b>Brecha Moderada (0,26 a 0,50):</b> Discrepancia tolerable pero sujeta a retroalimentación pedagógica.<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• 🔴 <b>Brecha Amplia (|Brecha| > 0,50):</b> Diferencia significativa que amerita revisión de la coordinación académica.",
        styles['DocCuerpo']
    ))
    elementos.append(Spacer(1, 6))

    # 7. Extracción Pestaña por Pestaña
    elementos.append(Paragraph("7. Extracción y Lógica de Procesamiento Pestaña por Pestaña", styles['DocSeccion']))
    elementos.append(Paragraph(
        "A continuación se describe qué datos extrae y cómo calcula cada una de las subvistas del módulo [`encuestas_ev2.py`]:",
        styles['DocCuerpo']
    ))

    pestanas_ev2 = [
        [
            Paragraph("Pestaña del Tablero", styles['DocTablaEncabezado']),
            Paragraph("Subvista en Código", styles['DocTablaEncabezado']),
            Paragraph("Datos Extraídos y Transformación", styles['DocTablaEncabezado']),
            Paragraph("Cálculos y Visualizaciones", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>Pestaña 1<br/>Avance General</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_avance_general_ev2</code>", styles['DocTablaCelda']),
            Paragraph("Padrón total de 1.289 ofertas filtradas por sede y periodo.", styles['DocTablaCelda']),
            Paragraph("• Encuestas completadas (918), en proceso (7) y pendientes (364).<br/>• Avance general = (918 / 1.289) × 100 = <b>71,2%</b>.<br/>• Velocímetro semicircular y tarjetas métricas.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 2<br/>Por Docente</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_por_docente_ev2</code>", styles['DocTablaCelda']),
            Paragraph("Agrupación por <code>docente_id</code> sobre las ofertas asignadas.", styles['DocTablaCelda']),
            Paragraph("• Total ofertas esperadas vs completadas por cada docente.<br/>• Clasificación: <i>Total</i> (100%), <i>Parcial</i>, <i>Proceso inicial</i>, <i>Sin respuesta</i>.<br/>• Tabla interactiva con filtro de estado y barra de avance.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 3<br/>Materia · Sección · Grupo</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_materia_seccion_grupo_ev2</code>", styles['DocTablaCelda']),
            Paragraph("Matriz de las 64 materias curriculares y sus secciones/grupos.", styles['DocTablaCelda']),
            Paragraph("• Cobertura curricular de la autoevaluación.<br/>• Estado individual por oferta académica.<br/>• Filtro multifactorial y tabla con scroll continuo.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 4<br/>Resultados EV2</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_resultados_ev2</code>", styles['DocTablaCelda']),
            Paragraph("Ofertas completadas con cálculo de <code>promedio_ev2</code>.", styles['DocTablaCelda']),
            Paragraph("• Promedio global docente (3,42 / 4,00).<br/>• Distribución en 4 niveles (Excelente, Satisfactorio, Regular, Insatisfactorio).<br/>• Medias comparativas por materia y departamento.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 5<br/>Comparación EV1 vs. EV2</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_ev1_vs_ev2</code>", styles['DocTablaCelda']),
            Paragraph("Inner join de ofertas cerradas en EV1 y EV2.", styles['DocTablaCelda']),
            Paragraph("• Aplicación de fórmula de homologación de escala (1-5 a 1-4).<br/>• Cálculo de brecha individual por docente y materia.<br/>• Gráfico de dispersión bivariado y tabla con scroll clasificada por concordancia.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 6<br/>Análisis Pedagógico EV2</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_analisis_pedagogico_ev2</code>", styles['DocTablaCelda']),
            Paragraph("Puntuaciones en los 13 criterios y 42 indicadores.", styles['DocTablaCelda']),
            Paragraph("• Puntuación media en las 4 dimensiones curriculares.<br/>• Gráfico radar de competencias pedagógicas.<br/>• Detección automática de fortalezas y áreas de mejora.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Pestaña 7<br/>Guía Metodológica EV2</b>", styles['DocTablaCelda']),
            Paragraph("<code>_render_subvista_guia_metodologica_ev2</code>", styles['DocTablaCelda']),
            Paragraph("Cálculos analíticos sincronizados en tiempo real.", styles['DocTablaCelda']),
            Paragraph("• Tarjetas KPI autoajustables según filtros activos.<br/>• Documentación paso a paso de fórmulas y reglas institucionales.", styles['DocTablaCelda']),
        ],
    ]
    t_pev2 = Table(pestanas_ev2, colWidths=[3.2 * cm, 4.4 * cm, 4.4 * cm, 6.0 * cm])
    t_pev2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_pev2)
    elementos.append(Spacer(1, 8))

    # 8. Observaciones y Consideraciones Críticas
    elementos.append(Paragraph("8. Observaciones Metodológicas y Consideraciones Críticas", styles['DocSeccion']))
    elementos.append(Paragraph(
        "Para la gestión analítica y directiva de los resultados de EV2, deben observarse los siguientes lineamientos:<br/>"
        "1. <b>Validez Estricta del Cierre de Encuesta:</b> Únicamente las encuestas con los <b>13 criterios cuantitativos completados</b> se consideran válidas para el cálculo de promedios de desempeño y cruce comparativo con EV1. Las encuestas en estado 'En proceso' computan en el avance operacional pero se aíslan de las métricas pedagógicas para preservar la confiabilidad psicométrica.<br/>"
        "2. <b>Docentes con Cumplimiento Parcial o Sin Respuesta:</b> Los 71 docentes que no han alcanzado el 100% de cumplimiento se encuentran plenamente identificados en la Pestaña 2 para las gestiones de acompañamiento académico y recordatorio institucional.<br/>"
        "3. <b>Lectura Ética de la Brecha EV1 vs EV2:</b> Una brecha amplia (|Brecha| > 0,50) no constituye una sanción administrativa, sino una señal de alerta metodológica que orienta el diálogo formativo entre la dirección de carrera y el docente.<br/>"
        "4. <b>Mapeo sin Fragmentación (Tablas con Scroll):</b> Todas las listas docentes y de ofertas se presentan con contenedores de scroll completo para evitar omisiones de visualización.<br/>"
        "5. <b>Actualización Sincronizada:</b> Cualquier nuevo lote de encuestas completadas se incorpora de forma inmediata al regenerar los archivos Parquet sin necesidad de reconfigurar la estructura del portal.",
        styles['DocCuerpo']
    ))

    doc.build(elementos, canvasmaker=NumeradorPaginas)
    return pdf_path


if __name__ == "__main__":
    p1 = generar_pdf_ev1()
    p2 = generar_pdf_ev2()
    print("PDF EV1 generado:", p1, f"({os.path.getsize(p1):,} bytes)")
    print("PDF EV2 generado:", p2, f"({os.path.getsize(p2):,} bytes)")
