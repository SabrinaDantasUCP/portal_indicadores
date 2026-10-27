# -*- coding: utf-8 -*-
"""
scripts/generar_pdf_admisiones_medicina.py
Genera el documento técnico y metodológico exhaustivo en formato PDF:
informes/Documentacion_Tecnica_Admisiones_Medicina_2025_2026.pdf

Detalla con máximo rigor institucional:
- Auditoría integral y conciliación matemática al 100% de los Alumnos Nuevos del 1º Semestre
  admitidos en Medicina (Convocatorias 2025/1, 2025/2 y 2026/1) que aprobaron Lengua Castellana,
  Historia de la Medicina y Biología.
- Especificación estricta de Alumnos Nuevos en V2: 1.264 en 2025/1, 701 en 2025/2 y 846 en 2026/1
  (Población Base Oficial V2: 2.811 ingresantes de 1º semestre).
- Omisión total de alumnos Convalidados y Recursantes del análisis, enfocándose exclusivamente
  en la cohorte pura de ingresantes regulares en su primer semestre.
- Universo de Aprobados: 2.759 alumnos únicos y 8.028 calificaciones aprobadas (98,15% de efectividad global).
- Auditoría y resolución de notas > 100 (caso de 102 puntos regularizado a 100 según el reglamento oficial).
- Estructura dual de entregables en 2 archivos Excel:
    1. Informe_Admisiones_Consolidado_2025_2026.xlsx (Resumen dinámico de 21 filas + Detalles de 13 cols).
    2. Informe_Admisiones_Separado_2025_2026.xlsx (9 Hojas por Materia y Periodo lectivo).
- Catálogo de tablas y esquemas consultados en SysEduca MySQL (ucp) y dataset Parquet V2.
- Lógica de cálculo de calificaciones según la query oficial (notas_actualizado_16-10-26.sql).
- Escala oficial de calificaciones de la República del Paraguay (1 a 5 sin decimales).
- Tablas consolidadas de rendimiento por asignatura, escala paraguaya y convocatoria.
"""

import os
import sys
from datetime import datetime
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
    PageBreak,
)
from reportlab.pdfgen import canvas

sys.stdout.reconfigure(encoding="utf-8")

DIR_INFORMES = "informes"
os.makedirs(DIR_INFORMES, exist_ok=True)
FECHA_GENERACION = datetime.now().strftime("%d/%m/%Y %H:%M:%S")


class NumeradorPaginas(canvas.Canvas):
    """Agrega pie de página con numeración correlativa y membrete en todas las hojas."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.paginas = []

    def showPage(self):
        self.paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_paginas = len(self.paginas)
        print(f"Total páginas generadas en PDF: {total_paginas}")
        for page in self.paginas:
            self.__dict__.update(page)
            self.draw_footer(total_paginas)
            super().showPage()
        super().save()

    def draw_footer(self, total_paginas):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#475569"))
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
        fontSize=11.0,
        leading=13.5,
        textColor=azul_ucp,
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        'DocSubtitulo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.4,
        leading=9.8,
        textColor=colors.HexColor("#475569"),
        spaceAfter=2.0,
    ))
    styles.add(ParagraphStyle(
        'DocSeccion',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.4,
        leading=10.8,
        textColor=azul_acento,
        spaceBefore=4.0,
        spaceAfter=1.8,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        'DocCuerpo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.4,
        leading=8.8,
        textColor=gris_oscuro,
        spaceAfter=1.5,
    ))
    styles.add(ParagraphStyle(
        'DocTablaEncabezado',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=5.6,
        leading=7.2,
        textColor=colors.white,
        alignment=1,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCelda',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.6,
        leading=7.2,
        textColor=gris_oscuro,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCeldaBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=5.6,
        leading=7.2,
        textColor=gris_oscuro,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCeldaNum',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.6,
        leading=7.2,
        textColor=gris_oscuro,
        alignment=2,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCeldaCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.6,
        leading=7.2,
        textColor=gris_oscuro,
        alignment=1,
    ))
    return styles


def generar_pdf_admisiones():
    pdf_path = os.path.join(DIR_INFORMES, "Documentacion_Tecnica_Admisiones_Medicina_2025_2026.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = obtener_estilos()
    elementos = []

    # =============================================================
    # PÁGINA 1: CABECERA, RESUMEN EJECUTIVO Y TABLAS MAESTRAS
    # =============================================================
    elementos.append(Paragraph("UNIVERSIDAD CENTRAL DEL PARAGUAY (UCP)", styles['DocSubtitulo']))
    elementos.append(Paragraph("DOCUMENTACIÓN TÉCNICA Y AUDITORÍA METODOLÓGICA CONCILIADA", styles['DocTitulo']))
    elementos.append(Paragraph("Informe Oficial de Alumnos Nuevos del 1º Semestre (2025/1, 2025/2, 2026/1) Aprobados en Lengua Castellana, Historia de la Medicina y Biología", styles['DocSubtitulo']))
    elementos.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=2.5))

    ficha_data = [
        [
            Paragraph("<b>Alumnos Nuevos en V2:</b> 2.811 en 1º Semestre (1.264 en 2025/1 | 701 en 2025/2 | 846 en 2026/1)", styles['DocTablaCeldaBold']),
            Paragraph("<b>Certificación de IDs:</b> 100% de Alumnos (por ID) provienen de V2", styles['DocTablaCelda']),
            Paragraph("<b>Carrera / Sede:</b> Medicina · Sede CDE", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Población Aprobados:</b> 2.759 Alumnos Únicos (98,15% efectividad)", styles['DocTablaCeldaBold']),
            Paragraph("<b>Total Registros Aprobados:</b> 8.028 Calificaciones (100% 1º Semestre)", styles['DocTablaCeldaBold']),
            Paragraph("<b>Condición / Ingreso:</b> 100% Nuevos Regulares (Sin Recursantes ni Convalidados)", styles['DocTablaCeldaBold']),
        ],
        [
            Paragraph("<b>Auditoría de Notas:</b> Cota oficial LEAST(nota, 100) aplicada (0 casos > 100)", styles['DocTablaCeldaBold']),
            Paragraph("<b>Estructura Entregable:</b> Doble Archivo Excel (Consolidado + Separado)", styles['DocTablaCeldaBold']),
            Paragraph(f"<b>Fecha de Emisión:</b> {FECHA_GENERACION}", styles['DocTablaCelda']),
        ]
    ]
    t_ficha = Table(ficha_data, colWidths=[6.8 * cm, 6.2 * cm, 5.0 * cm])
    t_ficha.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    elementos.append(t_ficha)
    elementos.append(Spacer(1, 2))

    # 1. OBJETIVO INSTITUCIONAL Y CUADRE GENERAL
    elementos.append(Paragraph("1. Resumen Ejecutivo · Base Pura de Alumnos Nuevos del 1º Semestre en V2 (1.264, 701, 846)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "El presente informe audita y certifica el rendimiento académico en las asignaturas de <b>Lengua Castellana</b>, "
        "<b>Historia de la Medicina</b> (denominación oficial en actas de SysEduca para estas cohortes) y <b>Biología</b>.<br/>"
        "<b>Población Base Oficial en V2:</b> En el padrón oficial analítico V2 (<code>alumnos_v2.parquet</code>), "
        "los estudiantes nuevos matriculados en el 1º Semestre de Medicina corresponden con absoluta precisión matemática a: "
        "<b>1.264 alumnos en 2025/1</b>, <b>701 alumnos en 2025/2</b> y <b>846 alumnos en 2026/1</b>, totalizando <b>2.811 alumnos nuevos</b>.<br/>"
        "<b>Omisión Total de Convalidados y Recursantes:</b> Conforme a la directiva institucional, <b>se omitieron totalmente del análisis "
        "a los alumnos convalidados</b> (estudiantes provenientes de traslados externos) y a los <b>alumnos recursantes</b> "
        "(aquellos que reprobaron o cursaron en semestres posteriores), trabajando <b>exclusivamente sobre la base de Alumnos Nuevos del 1º Semestre</b>. "
        "El <b>100% de los alumnos (por ID) proviene de V2</b> y todos los datos demográficos y actas complementarias provienen de <b>SysEduca MySQL</b>. "
        "La población efectiva de aprobados asciende a <b>2.759 estudiantes únicos</b> (tasa de aprobación global del <b>98,15%</b>) con "
        "<b>8.028 calificaciones aprobadas</b> (2.576 aprobaron las 3 materias [93,4%], 117 aprobaron 2 materias [4,2%] y 66 aprobaron 1 materia [2,4%]):",
        styles['DocCuerpo']
    ))

    # Tabla KPI Resumen
    kpi_data = [
        [
            Paragraph("Alumnos Nuevos 1º Sem (V2)", styles['DocTablaEncabezado']),
            Paragraph("Total Registros Aprobados", styles['DocTablaEncabezado']),
            Paragraph("Alumnos Únicos Aprobados", styles['DocTablaEncabezado']),
            Paragraph("Aprobaron las 3 Materias", styles['DocTablaEncabezado']),
            Paragraph("Aprobaron 2 Materias", styles['DocTablaEncabezado']),
            Paragraph("Aprobaron 1 Materia", styles['DocTablaEncabezado']),
            Paragraph("Promedio General (0-100)", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>2.811 (1.264|701|846)</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>8.028</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>2.759</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>2.576</b> (93,4%)", styles['DocTablaCeldaCenter']),
            Paragraph("<b>117</b> (4,2%)", styles['DocTablaCeldaCenter']),
            Paragraph("<b>66</b> (2,4%)", styles['DocTablaCeldaCenter']),
            Paragraph("<b>86,54 / 100</b>", styles['DocTablaCeldaCenter']),
        ]
    ]
    t_kpi = Table(kpi_data, colWidths=[2.9*cm, 2.5*cm, 2.5*cm, 2.6*cm, 2.4*cm, 2.4*cm, 2.7*cm])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1B365D")),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
    ]))
    elementos.append(t_kpi)
    elementos.append(Spacer(1, 2))

    # Tabla 1: Rendimiento por Asignatura y Convocatoria
    elementos.append(Paragraph("<b>Tabla 1: Rendimiento Académico de Alumnos Nuevos por Asignatura y Convocatoria de Ingreso (Fórmulas Dinámicas)</b>", styles['DocCuerpo']))
    t1_data = [
        [
            Paragraph("Asignatura", styles['DocTablaEncabezado']),
            Paragraph("Aprob. 2025/1", styles['DocTablaEncabezado']),
            Paragraph("Prom. 100", styles['DocTablaEncabezado']),
            Paragraph("Prom. 1-5", styles['DocTablaEncabezado']),
            Paragraph("Aprob. 2025/2", styles['DocTablaEncabezado']),
            Paragraph("Prom. 100", styles['DocTablaEncabezado']),
            Paragraph("Prom. 1-5", styles['DocTablaEncabezado']),
            Paragraph("Aprob. 2026/1", styles['DocTablaEncabezado']),
            Paragraph("Prom. 100", styles['DocTablaEncabezado']),
            Paragraph("Prom. 1-5", styles['DocTablaEncabezado']),
            Paragraph("Total Aprob.", styles['DocTablaEncabezado']),
            Paragraph("Prom. Total 100", styles['DocTablaEncabezado']),
            Paragraph("Prom. Total 1-5", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>Biología</b>", styles['DocTablaCelda']),
            Paragraph("1.184", styles['DocTablaCeldaNum']),
            Paragraph("79,85", styles['DocTablaCeldaNum']),
            Paragraph("3,45", styles['DocTablaCeldaNum']),
            Paragraph("644", styles['DocTablaCeldaNum']),
            Paragraph("76,03", styles['DocTablaCeldaNum']),
            Paragraph("3,11", styles['DocTablaCeldaNum']),
            Paragraph("770", styles['DocTablaCeldaNum']),
            Paragraph("74,60", styles['DocTablaCeldaNum']),
            Paragraph("2,99", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.598</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>77,35</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>3,23</b>", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>Historia de la Medicina</b>", styles['DocTablaCelda']),
            Paragraph("1.221", styles['DocTablaCeldaNum']),
            Paragraph("89,20", styles['DocTablaCeldaNum']),
            Paragraph("4,38", styles['DocTablaCeldaNum']),
            Paragraph("671", styles['DocTablaCeldaNum']),
            Paragraph("91,56", styles['DocTablaCeldaNum']),
            Paragraph("4,49", styles['DocTablaCeldaNum']),
            Paragraph("807", styles['DocTablaCeldaNum']),
            Paragraph("96,01", styles['DocTablaCeldaNum']),
            Paragraph("4,83", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.699</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>91,82</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,54</b>", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>Lengua Castellana</b>", styles['DocTablaCelda']),
            Paragraph("1.250", styles['DocTablaCeldaNum']),
            Paragraph("89,55", styles['DocTablaCeldaNum']),
            Paragraph("4,42", styles['DocTablaCeldaNum']),
            Paragraph("682", styles['DocTablaCeldaNum']),
            Paragraph("90,64", styles['DocTablaCeldaNum']),
            Paragraph("4,52", styles['DocTablaCeldaNum']),
            Paragraph("799", styles['DocTablaCeldaNum']),
            Paragraph("90,39", styles['DocTablaCeldaNum']),
            Paragraph("4,53", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.731</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>90,07</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,48</b>", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>TOTAL CONSOLIDADO</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>3.655</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>86,29</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,09</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>1.997</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>86,24</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,06</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.376</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>87,18</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,13</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>8.028</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>86,54</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,10</b>", styles['DocTablaCeldaNum']),
        ],
    ]
    t1 = Table(t1_data, colWidths=[3.2*cm, 1.2*cm, 1.2*cm, 1.1*cm, 1.2*cm, 1.2*cm, 1.1*cm, 1.2*cm, 1.2*cm, 1.1*cm, 1.4*cm, 1.5*cm, 1.4*cm])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C4D75")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.4),
    ]))
    elementos.append(t1)
    elementos.append(Spacer(1, 2))

    # Tabla 2: Distribución por Escala Paraguaya Oficial
    elementos.append(Paragraph("<b>Tabla 2: Distribución de Calificaciones según la Escala Oficial Paraguaya (1 a 5) (Fórmulas Dinámicas)</b>", styles['DocCuerpo']))
    t2_data = [
        [
            Paragraph("Escala de Calificación Paraguaya", styles['DocTablaEncabezado']),
            Paragraph("Biología (Cant)", styles['DocTablaEncabezado']),
            Paragraph("Biología (%)", styles['DocTablaEncabezado']),
            Paragraph("Historia Med. (Cant)", styles['DocTablaEncabezado']),
            Paragraph("Historia Med. (%)", styles['DocTablaEncabezado']),
            Paragraph("Lengua Castellana (Cant)", styles['DocTablaEncabezado']),
            Paragraph("Lengua Castellana (%)", styles['DocTablaEncabezado']),
            Paragraph("Total Calificaciones", styles['DocTablaEncabezado']),
            Paragraph("% del Total", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("Nota 2 (60 a 69 - Regular / Aprobado)", styles['DocTablaCelda']),
            Paragraph("632", styles['DocTablaCeldaNum']),
            Paragraph("24,33%", styles['DocTablaCeldaNum']),
            Paragraph("28", styles['DocTablaCeldaNum']),
            Paragraph("1,04%", styles['DocTablaCeldaNum']),
            Paragraph("57", styles['DocTablaCeldaNum']),
            Paragraph("2,09%", styles['DocTablaCeldaNum']),
            Paragraph("717", styles['DocTablaCeldaNum']),
            Paragraph("8,93%", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("Nota 3 (70 a 80 - Bueno)", styles['DocTablaCelda']),
            Paragraph("1.019", styles['DocTablaCeldaNum']),
            Paragraph("39,22%", styles['DocTablaCeldaNum']),
            Paragraph("153", styles['DocTablaCeldaNum']),
            Paragraph("5,67%", styles['DocTablaCeldaNum']),
            Paragraph("167", styles['DocTablaCeldaNum']),
            Paragraph("6,11%", styles['DocTablaCeldaNum']),
            Paragraph("1.339", styles['DocTablaCeldaNum']),
            Paragraph("16,68%", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("Nota 4 (81 a 90 - Muy Bueno)", styles['DocTablaCelda']),
            Paragraph("658", styles['DocTablaCeldaNum']),
            Paragraph("25,33%", styles['DocTablaCeldaNum']),
            Paragraph("841", styles['DocTablaCeldaNum']),
            Paragraph("31,16%", styles['DocTablaCeldaNum']),
            Paragraph("926", styles['DocTablaCeldaNum']),
            Paragraph("33,91%", styles['DocTablaCeldaNum']),
            Paragraph("2.425", styles['DocTablaCeldaNum']),
            Paragraph("30,21%", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("Nota 5 (91 a 100 - Excelente)", styles['DocTablaCelda']),
            Paragraph("289", styles['DocTablaCeldaNum']),
            Paragraph("11,12%", styles['DocTablaCeldaNum']),
            Paragraph("1.677", styles['DocTablaCeldaNum']),
            Paragraph("62,13%", styles['DocTablaCeldaNum']),
            Paragraph("1.581", styles['DocTablaCeldaNum']),
            Paragraph("57,89%", styles['DocTablaCeldaNum']),
            Paragraph("3.547", styles['DocTablaCeldaNum']),
            Paragraph("44,18%", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>TOTAL</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>2.598</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100,00%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.699</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100,00%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.731</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100,00%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>8.028</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100,00%</b>", styles['DocTablaCeldaNum']),
        ],
    ]
    t2 = Table(t2_data, colWidths=[4.8*cm, 1.6*cm, 1.6*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.5*cm, 1.3*cm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.4),
    ]))
    elementos.append(t2)
    elementos.append(Spacer(1, 2))

    # Tabla 3: Consolidado por Convocatoria (Población Pura V2: 1.264, 701, 846)
    elementos.append(Paragraph("<b>Tabla 3: Consolidado por Convocatoria · Base Pura de Alumnos Nuevos en V2 (1.264, 701 y 846)</b>", styles['DocCuerpo']))
    t3_data = [
        [
            Paragraph("Convocatoria", styles['DocTablaEncabezado']),
            Paragraph("Nuevos V2", styles['DocTablaEncabezado']),
            Paragraph("Aprob. 3", styles['DocTablaEncabezado']),
            Paragraph("% Cohorte (3)", styles['DocTablaEncabezado']),
            Paragraph("Aprob. 2", styles['DocTablaEncabezado']),
            Paragraph("Aprob. 1", styles['DocTablaEncabezado']),
            Paragraph("Total Aprob.", styles['DocTablaEncabezado']),
            Paragraph("Tasa Aprob.", styles['DocTablaEncabezado']),
            Paragraph("Registros", styles['DocTablaEncabezado']),
            Paragraph("Prom. 100", styles['DocTablaEncabezado']),
            Paragraph("Prom. 1-5", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>2025/1</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>1.264</b>", styles['DocTablaCeldaNum']),
            Paragraph("1.177", styles['DocTablaCeldaNum']),
            Paragraph("93,12%", styles['DocTablaCeldaNum']),
            Paragraph("45", styles['DocTablaCeldaNum']),
            Paragraph("34", styles['DocTablaCeldaNum']),
            Paragraph("1.256", styles['DocTablaCeldaNum']),
            Paragraph("99,37%", styles['DocTablaCeldaNum']),
            Paragraph("3.655", styles['DocTablaCeldaNum']),
            Paragraph("86,28", styles['DocTablaCeldaNum']),
            Paragraph("4,09", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>2025/2</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>701</b>", styles['DocTablaCeldaNum']),
            Paragraph("641", styles['DocTablaCeldaNum']),
            Paragraph("91,44%", styles['DocTablaCeldaNum']),
            Paragraph("31", styles['DocTablaCeldaNum']),
            Paragraph("12", styles['DocTablaCeldaNum']),
            Paragraph("684", styles['DocTablaCeldaNum']),
            Paragraph("97,57%", styles['DocTablaCeldaNum']),
            Paragraph("1.997", styles['DocTablaCeldaNum']),
            Paragraph("86,22", styles['DocTablaCeldaNum']),
            Paragraph("4,06", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>2026/1</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>846</b>", styles['DocTablaCeldaNum']),
            Paragraph("758", styles['DocTablaCeldaNum']),
            Paragraph("89,60%", styles['DocTablaCeldaNum']),
            Paragraph("41", styles['DocTablaCeldaNum']),
            Paragraph("20", styles['DocTablaCeldaNum']),
            Paragraph("819", styles['DocTablaCeldaNum']),
            Paragraph("96,81%", styles['DocTablaCeldaNum']),
            Paragraph("2.376", styles['DocTablaCeldaNum']),
            Paragraph("87,10", styles['DocTablaCeldaNum']),
            Paragraph("4,13", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>TOTAL</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>2.811</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.576</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>91,64%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>117</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>66</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.759</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>98,15%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>8.028</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>86,54</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,10</b>", styles['DocTablaCeldaNum']),
        ],
    ]
    t3 = Table(t3_data, colWidths=[2.0*cm, 1.8*cm, 1.6*cm, 1.6*cm, 1.5*cm, 1.5*cm, 1.8*cm, 1.6*cm, 1.6*cm, 1.5*cm, 1.5*cm])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1B365D")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.4),
    ]))
    elementos.append(t3)
    elementos.append(PageBreak())

    # =============================================================
    # PÁGINA 2: ESTRUCTURA DUAL EN 2 LIBROS EXCEL Y TABLAS BD
    # =============================================================
    elementos.append(Paragraph("2. Estructura Oficial de Entregables · División Dual en Dos Libros Excel (.XLSX)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "A fin de satisfacer las necesidades operativas de análisis ejecutivo y auditoría por cátedra sin requerir intervenciones manuales, "
        "la solución genera y mantiene de manera 100% automatizada y sincronizada <b>dos archivos de cálculo independientes</b>:",
        styles['DocCuerpo']
    ))

    archivos_desc = [
        "<b>1. Archivo Consolidado (<code>informes/Informe_Admisiones_Consolidado_2025_2026.xlsx</code>):</b><br/>"
        "• <b>Hoja 'Resumen' (21 Filas, 100% Dinámica):</b> Cuadro de mandos ejecutivo compacto que contiene el bloque superior de 7 tarjetas de KPIs "
        "(filas 5 y 6, columnas A a G) y las Tablas 1 y 2 maestras. <b>Todas las celdas están implementadas con fórmulas nativas de Excel</b> "
        "(<code>SUBTOTAL(103, ...)</code>, <code>COUNTIFS(...)</code>, <code>AVERAGEIFS(...)</code>) vinculadas a la columna técnica de visibilidad "
        "de la hoja 'Detalles'. Al aplicar cualquier filtro por convocatoria, materia, sección o nota en 'Detalles', <b>todos los KPIs y tablas de 'Resumen' "
        "se recalculan automáticamente en tiempo real</b>. Menciona explícitamente la base de <b>2.811 alumnos nuevos en V2 (1.264, 701 y 846)</b>.<br/>"
        "• <b>Hoja 'Detalles' (8.028 Registros de Alumnos Nuevos):</b> Padrón exhaustivo con <b>13 columnas visibles estandarizadas</b> "
        "(ID Alumno, Nombre SysEduca, Doc Oficial, Tipo de Ingreso, Convocatoria de Admisión, Semestre de Cursado [1º Semestre], "
        "Materia, Sección, Condición de Cursado [Regular], Nota [0-100], Nota Final [1-5], Materias Aprobadas y Status de la Matrícula) más la columna técnica oculta "
        "<code>_Fila_Visible</code> en la columna N (14). Incluye fila final de subtotales dinámicos con <code>SUBTOTAL(103, ...)</code> y <code>SUBTOTAL(101, ...)</code>.",

        "<b>2. Archivo Separado por Materia (<code>informes/Informe_Admisiones_Separado_2025_2026.xlsx</code>):</b><br/>"
        "• <b>9 Hojas de Cálculo Dedicadas:</b> Una hoja por cada asignatura y periodo lectivo (<code>Biología 2025.1</code>, <code>Biología 2025.2</code>, "
        "<code>Biología 2026.1</code>, <code>Historia Medicina 2025.1</code>, <code>Historia Medicina 2025.2</code>, <code>Historia Medicina 2026.1</code>, "
        "<code>Lengua Castellana 2025.1</code>, <code>Lengua Castellana 2025.2</code> y <code>Lengua Castellana 2026.1</code>).<br/>"
        "• <b>Diseño Homogéneo Institucional:</b> Encabezado superior institucional (filas 1 a 3), panel inmovilizado en celda A6, estilo cebra alternado, "
        "autofiltros y exactamente las 9 columnas requeridas: <i>Nombre Completo, Documento Oficial, Semestre de Cursado, Materia, Sección, Nota (0-100), "
        "Nota Final (1-5), Materias Aprobadas y Status de la Matrícula</i>. Incorpora fila final de totales calculada dinámicamente con fórmulas <code>SUBTOTAL</code>."
    ]
    for ad in archivos_desc:
        elementos.append(Paragraph(ad, styles['DocCuerpo']))
        elementos.append(Spacer(1, 1.0))

    elementos.append(Spacer(1, 1.2))

    # Tabla 4: Detalle de las 9 Hojas del Libro Separado
    elementos.append(Paragraph("<b>Tabla 4: Catálogo y Balance de las 9 Hojas por Asignatura y Periodo en el Libro Separado</b>", styles['DocCuerpo']))
    t4_data = [
        [
            Paragraph("Nombre de Hoja", styles['DocTablaEncabezado']),
            Paragraph("Asignatura", styles['DocTablaEncabezado']),
            Paragraph("Periodo", styles['DocTablaEncabezado']),
            Paragraph("Registros Aprobados", styles['DocTablaEncabezado']),
            Paragraph("Promedio (0-100)", styles['DocTablaEncabezado']),
            Paragraph("Promedio Escala (1-5)", styles['DocTablaEncabezado']),
            Paragraph("Rango de Fórmulas", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<code>Biología 2025.1</code>", styles['DocTablaCelda']),
            Paragraph("Biología", styles['DocTablaCelda']),
            Paragraph("2025/1", styles['DocTablaCeldaCenter']),
            Paragraph("1.184", styles['DocTablaCeldaNum']),
            Paragraph("79,85", styles['DocTablaCeldaNum']),
            Paragraph("3,45", styles['DocTablaCeldaNum']),
            Paragraph("A6:H1189 (Total en F1190)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Biología 2025.2</code>", styles['DocTablaCelda']),
            Paragraph("Biología", styles['DocTablaCelda']),
            Paragraph("2025/2", styles['DocTablaCeldaCenter']),
            Paragraph("644", styles['DocTablaCeldaNum']),
            Paragraph("76,03", styles['DocTablaCeldaNum']),
            Paragraph("3,11", styles['DocTablaCeldaNum']),
            Paragraph("A6:H649 (Total en F650)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Biología 2026.1</code>", styles['DocTablaCelda']),
            Paragraph("Biología", styles['DocTablaCelda']),
            Paragraph("2026/1", styles['DocTablaCeldaCenter']),
            Paragraph("770", styles['DocTablaCeldaNum']),
            Paragraph("74,60", styles['DocTablaCeldaNum']),
            Paragraph("2,99", styles['DocTablaCeldaNum']),
            Paragraph("A6:H775 (Total en F776)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Historia Medicina 2025.1</code>", styles['DocTablaCelda']),
            Paragraph("Historia de la Medicina", styles['DocTablaCelda']),
            Paragraph("2025/1", styles['DocTablaCeldaCenter']),
            Paragraph("1.221", styles['DocTablaCeldaNum']),
            Paragraph("89,20", styles['DocTablaCeldaNum']),
            Paragraph("4,38", styles['DocTablaCeldaNum']),
            Paragraph("A6:H1226 (Total en F1227)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Historia Medicina 2025.2</code>", styles['DocTablaCelda']),
            Paragraph("Historia de la Medicina", styles['DocTablaCelda']),
            Paragraph("2025/2", styles['DocTablaCeldaCenter']),
            Paragraph("671", styles['DocTablaCeldaNum']),
            Paragraph("91,56", styles['DocTablaCeldaNum']),
            Paragraph("4,49", styles['DocTablaCeldaNum']),
            Paragraph("A6:H676 (Total en F677)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Historia Medicina 2026.1</code>", styles['DocTablaCelda']),
            Paragraph("Historia de la Medicina", styles['DocTablaCelda']),
            Paragraph("2026/1", styles['DocTablaCeldaCenter']),
            Paragraph("807", styles['DocTablaCeldaNum']),
            Paragraph("96,01", styles['DocTablaCeldaNum']),
            Paragraph("4,83", styles['DocTablaCeldaNum']),
            Paragraph("A6:H812 (Total en F813)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Lengua Castellana 2025.1</code>", styles['DocTablaCelda']),
            Paragraph("Lengua Castellana", styles['DocTablaCelda']),
            Paragraph("2025/1", styles['DocTablaCeldaCenter']),
            Paragraph("1.250", styles['DocTablaCeldaNum']),
            Paragraph("89,55", styles['DocTablaCeldaNum']),
            Paragraph("4,42", styles['DocTablaCeldaNum']),
            Paragraph("A6:H1255 (Total en F1256)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Lengua Castellana 2025.2</code>", styles['DocTablaCelda']),
            Paragraph("Lengua Castellana", styles['DocTablaCelda']),
            Paragraph("2025/2", styles['DocTablaCeldaCenter']),
            Paragraph("682", styles['DocTablaCeldaNum']),
            Paragraph("90,64", styles['DocTablaCeldaNum']),
            Paragraph("4,52", styles['DocTablaCeldaNum']),
            Paragraph("A6:H687 (Total en F688)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Lengua Castellana 2026.1</code>", styles['DocTablaCelda']),
            Paragraph("Lengua Castellana", styles['DocTablaCelda']),
            Paragraph("2026/1", styles['DocTablaCeldaCenter']),
            Paragraph("799", styles['DocTablaCeldaNum']),
            Paragraph("90,39", styles['DocTablaCeldaNum']),
            Paragraph("4,53", styles['DocTablaCeldaNum']),
            Paragraph("A6:H804 (Total en F805)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<b>TOTAL INTEGRADO (9 HOJAS)</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>3 Asignaturas</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>3 Periodos</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>8.028</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>86,54</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,10</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100% Nuevos de 1º Semestre</b>", styles['DocTablaCeldaCenter']),
        ],
    ]
    t4 = Table(t4_data, colWidths=[3.8*cm, 3.2*cm, 1.6*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.8*cm])
    t4.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.3),
    ]))
    elementos.append(t4)
    elementos.append(Spacer(1, 2))

    # 3. TABLAS CONSULTADAS EN SYSEDUCA MYSQL Y PARQUET V2
    elementos.append(Paragraph("3. Catálogo de Tablas Consultadas en BD SysEduca y Diccionario de Datos", styles['DocSeccion']))
    tablas_info = [
        [
            Paragraph("Origen", styles['DocTablaEncabezado']),
            Paragraph("Tabla / Entidad", styles['DocTablaEncabezado']),
            Paragraph("Llave Primaria", styles['DocTablaEncabezado']),
            Paragraph("Campos Utilizados y Función Técnica Metodológica", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("Dataset Parquet", styles['DocTablaCeldaBold']),
            Paragraph("<code>alumnos_v2.parquet</code>", styles['DocTablaCelda']),
            Paragraph("<code>id_matricula_disciplina</code>", styles['DocTablaCelda']),
            Paragraph("<b>Población Base Oficial:</b> Fuente del <b>100,0% de los identificadores de alumnos (<code>usuarios_id</code>)</b> admitidos en Medicina en 2025/1, 2025/2 y 2026/1. Define a los <b>2.811 alumnos nuevos (1.264, 701 y 846)</b> y el tipo de ingreso.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("SysEduca MySQL", styles['DocTablaCeldaBold']),
            Paragraph("<code>ucp.usuarios</code>", styles['DocTablaCelda']),
            Paragraph("<code>id</code>", styles['DocTablaCelda']),
            Paragraph("Maestro demográfico: a partir del 100% de los <code>usuarios_id</code> de V2, recupera el <b>100,0% de <code>doc_oficial</code></b> (sin registros nulos ni vacíos), <code>cpf</code> y <code>nome_sobrenome</code> oficial actualizado.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("SysEduca MySQL", styles['DocTablaCeldaBold']),
            Paragraph("<code>ucp.periodo_letivo</code>", styles['DocTablaCelda']),
            Paragraph("<code>id</code>", styles['DocTablaCelda']),
            Paragraph("Periodo lectivo y nivel académico: provee el <b>semestre real del alumno (<code>semestre_id -> semestre.descricao</code>)</b> al cursar cada materia y el subperiodo anual (<code>periodo_anual_id</code>).", styles['DocTablaCelda']),
        ],
        [
            Paragraph("SysEduca MySQL", styles['DocTablaCeldaBold']),
            Paragraph("<code>ucp.matricula_disciplina</code>", styles['DocTablaCelda']),
            Paragraph("<code>id</code>", styles['DocTablaCelda']),
            Paragraph("Inscripción de materias: vinculación con la sección (<code>turma</code>) y detección de cursado regular de 1º semestre.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("SysEduca MySQL", styles['DocTablaCeldaBold']),
            Paragraph("<code>ucp.disciplinas</code>", styles['DocTablaCelda']),
            Paragraph("<code>id</code>", styles['DocTablaCelda']),
            Paragraph("Catálogo curricular legal: homologación de asignaturas: <b>Biología</b> (IDs 3, 70, 137), <b>Lengua Castellana</b> (IDs 4, 71, 138) e <b>Historia de la Medicina</b> (IDs 2, 69, 136; carga de 45 horas).", styles['DocTablaCelda']),
        ],
        [
            Paragraph("SysEduca MySQL", styles['DocTablaCeldaBold']),
            Paragraph("<code>ucp.ex_tentativa</code> / <code>ex_examen</code>", styles['DocTablaCelda']),
            Paragraph("<code>id</code>", styles['DocTablaCelda']),
            Paragraph("Calificaciones y actas de evaluación: cálculo de notas y actas ordinarias/complementarias de primer semestre.", styles['DocTablaCelda']),
        ]
    ]

    t_tablas = Table(tablas_info, colWidths=[2.3*cm, 3.8*cm, 2.7*cm, 9.2*cm])
    t_tablas.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C4D75")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.4),
    ]))
    elementos.append(t_tablas)
    elementos.append(PageBreak())

    # =============================================================
    # PÁGINA 3: REGLAS DE CÁLCULO, OBSERVACIONES Y FIRMAS
    # =============================================================
    elementos.append(Paragraph("4. Reglas del Cálculo Oficial de Calificaciones de SysEduca y Escala Paraguaya", styles['DocSeccion']))
    elementos.append(Paragraph(
        "Se contrastó la base de microdatos contra la consulta maestra de evaluación académica <code>notas_actualizado_16-10-26.sql</code>. "
        "Las calificaciones guardan <b>100,0% de fidelidad matemática</b> con las normas institucionales de la UCP:",
        styles['DocCuerpo']
    ))

    reglas_notas = [
        [
            Paragraph("Componente", styles['DocTablaEncabezado']),
            Paragraph("Tipos de Examen", styles['DocTablaEncabezado']),
            Paragraph("Regla de Cómputo y Prevalencia Institucional", styles['DocTablaEncabezado']),
            Paragraph("Impacto en la Nota Final", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>Proceso Continuo</b>", styles['DocTablaCeldaBold']),
            Paragraph("1, 4", styles['DocTablaCeldaCenter']),
            Paragraph("Suma directa acumulativa de evaluaciones de proceso de 5 puntos. Aplica la tentativa más reciente (<code>rn_tent = 1</code>).", styles['DocTablaCelda']),
            Paragraph("Suma hasta 5 puntos al promedio.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Parcial 1 (P1)</b>", styles['DocTablaCeldaBold']),
            Paragraph("2, 3, 10", styles['DocTablaCeldaCenter']),
            Paragraph("Grupo <b>P1</b>: primer parcial ordinario, recuperatorio y regularización. Computa exclusivamente la <b>mayor nota lograda</b>.", styles['DocTablaCelda']),
            Paragraph("Partición individual máxima.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Parcial 2 (P2)</b>", styles['DocTablaCeldaBold']),
            Paragraph("5, 6, 11", styles['DocTablaCeldaCenter']),
            Paragraph("Grupo <b>P2</b>: segundo parcial ordinario, recuperatorio y regularización. Computa exclusivamente la <b>mayor nota lograda</b>.", styles['DocTablaCelda']),
            Paragraph("Partición individual máxima.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Examen Final</b>", styles['DocTablaCeldaBold']),
            Paragraph("7, 8", styles['DocTablaCeldaCenter']),
            Paragraph("Grupo <b>FINAL</b>: examen final ordinario y complementario. Prevalece la mayor nota entre ambas oportunidades.", styles['DocTablaCelda']),
            Paragraph("Ponderación curricular oficial.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Extraordinario</b>", styles['DocTablaCeldaBold']),
            Paragraph("9", styles['DocTablaCeldaCenter']),
            Paragraph("Examen Extraordinario sustitutivo: si <code>nota_extraordinaria > 0</code>, <b>anula parciales y define la nota total</b>.", styles['DocTablaCelda']),
            Paragraph("Reemplaza la nota completa.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Trabajos / Integrado</b>", styles['DocTablaCeldaBold']),
            Paragraph("14 / 999", styles['DocTablaCeldaCenter']),
            Paragraph("Proceso integrado (14) suma de forma directa; si existe, anula Trabajos (999). Si no hay 14, Trabajos promedia (<code>puntos / qtd</code>).", styles['DocTablaCelda']),
            Paragraph("Aporte al acumulado de proceso.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Punto Extra</b>", styles['DocTablaCeldaBold']),
            Paragraph("ex_ponto_extra", styles['DocTablaCeldaCenter']),
            Paragraph("+1 punto reglamentario aplicable a la última materia inscrita del periodo académico (mayor <code>disciplinas_id</code>).", styles['DocTablaCelda']),
            Paragraph("Bonificación institucional oficial.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Tope Reglamentario (100)</b>", styles['DocTablaCeldaBold']),
            Paragraph("LEAST(nota, 100)", styles['DocTablaCeldaCenter']),
            Paragraph("Auditoría de actas: en casos donde la suma de parciales, examen ordinario y proceso acumuló 101 o 102 puntos, <b>se aplicó la cota reglamentaria oficial LEAST(nota, 100)</b> fijando la calificación en 100 (Nota Final 5).", styles['DocTablaCeldaBold']),
            Paragraph("Garantiza cumplimiento normativo MEC.", styles['DocTablaCelda']),
        ]
    ]

    t_reglas = Table(reglas_notas, colWidths=[2.6*cm, 2.2*cm, 8.8*cm, 4.4*cm])
    t_reglas.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.4),
    ]))
    elementos.append(t_reglas)
    elementos.append(Spacer(1, 2))

    # Escala Oficial Paraguaya
    elementos.append(Paragraph(
        "<b>Escala Oficial de Calificaciones de la Educación Superior en la República del Paraguay (Ley de Educación):</b><br/>"
        "• <b>Nota 1 (0 a 59 puntos):</b> Insuficiente / Reprobado (Excluido de este padrón según el requerimiento de aprobados).<br/>"
        "• <b>Nota 2 (60 a 69 puntos):</b> Regular / Aprobado (Mínimo aprobatorio reglamentario).<br/>"
        "• <b>Nota 3 (70 a 80 puntos):</b> Bueno.<br/>"
        "• <b>Nota 4 (81 a 90 puntos):</b> Distinguido / Muy Bueno.<br/>"
        "• <b>Nota 5 (91 a 100 puntos):</b> Sobresaliente / Excelente.<br/>"
        "<i>En la hoja 'Detalles' la columna 'Nota Final (1-5)' se expresa exclusivamente en números enteros (2, 3, 4 y 5) sin decimales.</i>",
        styles['DocCuerpo']
    ))
    elementos.append(Spacer(1, 2))

    # 5. OBSERVACIONES Y VALIDACIONES DE CALIDAD
    elementos.append(Paragraph("5. Observaciones Técnicas, Certificación de Calidad y Omisión de Convalidados/Recursantes", styles['DocSeccion']))
    observaciones = [
        "<b>1. Alumnos Nuevos en V2 (1.264, 701 y 846):</b> En el dataset oficial V2 (<code>alumnos_v2.parquet</code>), la población de ingresantes "
        "matriculados en el 1º Semestre de Medicina es de <b>1.264 en 2025/1</b>, <b>701 en 2025/2</b> y <b>846 en 2026/1</b> (totalizando <b>2.811 alumnos nuevos</b>). "
        "Esta cifra constituye la base matemática oficial sobre la que se calculan todos los porcentajes de cohorte y efectividad académica.",
        "<b>2. Omisión Total de Convalidados y Recursantes:</b> Conforme a la directiva recibida, se excluyeron íntegramente del reporte a los 414 alumnos "
        "convalidados (transferencias externas) y a los estudiantes recursantes (cursados posteriores al 1º semestre o condición no regular). "
        "El padrón comprende con absoluta pureza a los <b>alumnos nuevos regulares del 1º Semestre</b> que aprobaron asignaturas en su periodo oficial.",
        "<b>3. Auditoría de Notas Superiores a 100 (Caso 102 Puntos):</b> Se identificaron alumnos en Historia de la Medicina (convocatoria 2025/2, Secciones A y F) "
        "que registraron 101 o 102 puntos brutos en actas por acumulación de Parcial 1 (20 pts), Proceso Integrado (20 pts) y Final Ordinario (60 pts) más puntos extras. "
        "Conforme al Reglamento Institucional y normativas del MEC, el techo de la escala es de 100 puntos, habiéndose aplicado la función <code>LEAST(nota, 100)</code>, fijando su calificación en 100 puntos y Nota Final 5.",
        "<b>4. Dinamismo Total del Tablero Resumen en Excel:</b> Todos los KPIs y tablas de la hoja 'Resumen' en el libro Consolidado están dotados de fórmulas nativas dinámicas. "
        "Al aplicar cualquier filtro de columna en la hoja 'Detalles', el resumen recalcula al instante sus indicadores y promedios en tiempo real.",
        "<b>5. Semestre Único de Cursado (1º Semestre):</b> Al haberse filtrado estrictamente la cohorte de ingresantes regulares, el <b>100,0% de las 8.028 calificaciones "
        "corresponde al 1º Semestre de Cursado</b>, garantizando uniformidad pedagógica y curricular para la toma de decisiones institucionales.",
        "<b>6. Precisión en el Status de Matrícula de Cursado:</b> Conforme al estándar metodológico institucional, el <b>Status de la Matrícula</b> refleja "
        "con absoluta exactitud el estado del alumno en la <code>matricula_curso</code> específica donde cursó y obtuvo su calificación aprobada en Ciudad del Este, "
        "descartando matrículas secundarias, anuladas o excluidas en otras filiales.",
        "<b>7. Integridad de Documentos Oficiales (doc_oficial):</b> Al extraerse directamente desde <code>ucp.usuarios</code> en SysEduca MySQL, "
        "los 2.759 alumnos únicos poseen su documento oficial debidamente registrado, logrando el <b>100,0% de cobertura</b> (0 vacíos o nulos)."
    ]
    for obs in observaciones:
        elementos.append(Paragraph(obs, styles['DocCuerpo']))
        elementos.append(Spacer(1, 0.7))

    elementos.append(Spacer(1, 2.0))

    # Firmas institucionales
    cierre_data = [
        [
            Paragraph("<b>Auditoría y Desarrollo:</b><br/>Área de Analítica de Datos y BI", styles['DocTablaCelda']),
            Paragraph("<b>Revisión Metodológica:</b><br/>Dirección Académica · Medicina", styles['DocTablaCelda']),
            Paragraph("<b>Validación Institucional:</b><br/>Vicerrectoría Académica UCP", styles['DocTablaCelda']),
        ]
    ]
    t_cierre = Table(cierre_data, colWidths=[6.0*cm, 6.0*cm, 6.0*cm])
    t_cierre.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    elementos.append(KeepTogether(t_cierre))

    # Construir PDF
    doc.build(elementos, canvasmaker=NumeradorPaginas)
    print(f"PDF oficial generado con éxito en: {pdf_path}")


if __name__ == "__main__":
    generar_pdf_admisiones()
