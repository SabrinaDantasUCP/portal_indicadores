# -*- coding: utf-8 -*-
"""
scripts/generar_pdf_admisiones_2023_2024.py
Genera el documento técnico y metodológico exhaustivo en formato PDF:
informes/Documentacion_Tecnica_Admisiones_Medicina_2023_2024.pdf

Detalla con máximo rigor institucional:
- Auditoría integral y conciliación matemática al 100% de los Alumnos Nuevos del 1º Semestre
  admitidos en Medicina (Convocatorias 2023/1, 2023/2, 2024/1 y 2024/2) que aprobaron Lengua Castellana,
  Historia de la Medicina y Biología.
- Especificación estricta de Alumnos Nuevos Oficiales: 665 en 2023/1, 456 en 2023/2, 897 en 2024/1 y 710 en 2024/2
  (Población Base Oficial: 2.728 ingresantes de 1º semestre, alineado a la distribución oficial por semestre y sección).
- Omisión total de alumnos Convalidados y Recursantes del análisis, enfocándose exclusivamente
  en la cohorte pura de ingresantes regulares en su primer semestre.
- Universo de Aprobados: 2.639 alumnos únicos y 7.635 calificaciones aprobadas (97,42% de efectividad global).
- Incorporación del Status de la Matrícula del Alumno (Activo, Trancado, Suspenso, Finalizado, Excluido).
- Auditoría y resolución de notas > 100 con la cota reglamentaria oficial LEAST(nota, 100).
- Estructura dual de entregables en 2 archivos Excel:
    1. Informe_Admisiones_Consolidado_2023_2024.xlsx (Resumen dinámico de 21 filas + Detalles de 14 cols).
    2. Informe_Admisiones_Separado_2023_2024.xlsx (12 Hojas por Materia y Periodo lectivo).
- Catálogo de tablas y esquemas consultados en SysEduca MySQL (ucp) y dataset Parquet V2.
- Lógica de cálculo de calificaciones según la query oficial (notas_actualizado_16-10-26.sql).
- Escala oficial de calificaciones de la República del Paraguay (1 a 5 sin decimales).
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
        
        texto_izq = f"Universidad Central del Paraguay (UCP) · Cohortes 2023-2024 · Emitido: {FECHA_GENERACION}"
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
        fontSize=5.4,
        leading=7.0,
        textColor=colors.white,
        alignment=1,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCelda',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.4,
        leading=7.0,
        textColor=gris_oscuro,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCeldaBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=5.4,
        leading=7.0,
        textColor=gris_oscuro,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCeldaNum',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.4,
        leading=7.0,
        textColor=gris_oscuro,
        alignment=2,
    ))
    styles.add(ParagraphStyle(
        'DocTablaCeldaCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.4,
        leading=7.0,
        textColor=gris_oscuro,
        alignment=1,
    ))
    return styles


def generar_pdf_admisiones_2023_2024():
    pdf_path = os.path.join(DIR_INFORMES, "Documentacion_Tecnica_Admisiones_Medicina_2023_2024.pdf")
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
    elementos.append(Paragraph("Informe Oficial de Alumnos Nuevos del 1º Semestre (2023/1, 2023/2, 2024/1, 2024/2) Aprobados en Lengua Castellana, Historia de la Medicina y Biología", styles['DocSubtitulo']))
    elementos.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=2.5))

    ficha_data = [
        [
            Paragraph("<b>Alumnos Nuevos Oficiales:</b> 2.728 en 1º Semestre (665 en 2023/1 | 456 en 2023/2 | 897 en 2024/1 | 710 en 2024/2)", styles['DocTablaCeldaBold']),
            Paragraph("<b>Certificación de IDs:</b> 100% de Alumnos (por ID) provienen de V2", styles['DocTablaCelda']),
            Paragraph("<b>Carrera / Sede:</b> Medicina · Sede CDE", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Población Aprobados:</b> 2.639 Alumnos Únicos (96,74% efectividad)", styles['DocTablaCeldaBold']),
            Paragraph("<b>Total Registros Aprobados:</b> 7.635 Calificaciones (100% 1º Semestre)", styles['DocTablaCeldaBold']),
            Paragraph("<b>Condición / Ingreso:</b> 100% Nuevos Regulares (Sin Recursantes ni Convalidados)", styles['DocTablaCeldaBold']),
        ],
        [
            Paragraph("<b>Status de Matrícula:</b> 100% de Cobertura en SysEduca (Activo, Trancado, etc.)", styles['DocTablaCeldaBold']),
            Paragraph("<b>Estructura Entregable:</b> Doble Archivo Excel (Consolidado + Separado de 12 Hojas)", styles['DocTablaCeldaBold']),
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
    elementos.append(Paragraph("1. Resumen Ejecutivo · Base Oficial de Alumnos Nuevos del 1º Semestre (665, 456, 897, 710)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "El presente informe audita y certifica el rendimiento académico histórico en las asignaturas de <b>Lengua Castellana</b>, "
        "<b>Historia de la Medicina</b> y <b>Biología</b> para las cuatro convocatorias comprendidas entre 2023 y 2024.<br/>"
        "<b>Población Base Oficial:</b> En concordancia con la distribución oficial por semestre y sección, "
        "los estudiantes nuevos matriculados en el 1º Semestre de Medicina corresponden con absoluta precisión matemática a: "
        "<b>665 alumnos en 2023/1</b>, <b>456 alumnos en 2023/2</b>, <b>897 alumnos en 2024/1</b> y <b>710 alumnos en 2024/2</b>, "
        "totalizando <b>2.728 alumnos nuevos</b>.<br/>"
        "<b>Omisión Total de Convalidados y Recursantes:</b> Se omitieron íntegramente a los alumnos convalidados y recursantes "
        "(aquellos que cursaron en periodos posteriores), analizando exclusivamente la base regular de 1º semestre en su periodo lectivo. "
        "El <b>100% de los alumnos (por ID) proviene de V2</b> y sus documentos y status de matrícula provienen en tiempo real de <b>SysEduca MySQL</b>. "
        "La población efectiva de aprobados asciende a <b>2.639 estudiantes únicos</b> (tasa de aprobación global del <b>96,74%</b>) con "
        "<b>7.635 calificaciones aprobadas</b> (2.425 aprobaron las 3 materias [91,89%], 146 aprobaron 2 materias [5,53%] y 68 aprobaron 1 materia [2,58%]):",
        styles['DocCuerpo']
    ))

    # Tabla KPI Resumen
    kpi_data = [
        [
            Paragraph("Alumnos Nuevos 1º Sem (Oficial)", styles['DocTablaEncabezado']),
            Paragraph("Total Registros Aprobados", styles['DocTablaEncabezado']),
            Paragraph("Alumnos Únicos Aprobados", styles['DocTablaEncabezado']),
            Paragraph("Aprobaron las 3 Materias", styles['DocTablaEncabezado']),
            Paragraph("Aprobaron 2 Materias", styles['DocTablaEncabezado']),
            Paragraph("Aprobaron 1 Materia", styles['DocTablaEncabezado']),
            Paragraph("Promedio General (0-100)", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>2.728 (665|456|897|710)</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>7.635</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>2.639</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>2.425</b> (91,9%)", styles['DocTablaCeldaCenter']),
            Paragraph("<b>146</b> (5,5%)", styles['DocTablaCeldaCenter']),
            Paragraph("<b>68</b> (2,6%)", styles['DocTablaCeldaCenter']),
            Paragraph("<b>87,09 / 100</b>", styles['DocTablaCeldaCenter']),
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

    # Tabla 1: Rendimiento por Asignatura y Convocatoria (2023/1 a 2024/2)
    elementos.append(Paragraph("<b>Tabla 1: Rendimiento Académico de Alumnos Nuevos por Asignatura y Convocatoria de Ingreso (Fórmulas Dinámicas)</b>", styles['DocCuerpo']))
    t1_data = [
        [
            Paragraph("Asignatura", styles['DocTablaEncabezado']),
            Paragraph("Ap. 23/1", styles['DocTablaEncabezado']),
            Paragraph("Prom 100", styles['DocTablaEncabezado']),
            Paragraph("Prom 5", styles['DocTablaEncabezado']),
            Paragraph("Ap. 23/2", styles['DocTablaEncabezado']),
            Paragraph("Prom 100", styles['DocTablaEncabezado']),
            Paragraph("Prom 5", styles['DocTablaEncabezado']),
            Paragraph("Ap. 24/1", styles['DocTablaEncabezado']),
            Paragraph("Prom 100", styles['DocTablaEncabezado']),
            Paragraph("Prom 5", styles['DocTablaEncabezado']),
            Paragraph("Ap. 24/2", styles['DocTablaEncabezado']),
            Paragraph("Prom 100", styles['DocTablaEncabezado']),
            Paragraph("Prom 5", styles['DocTablaEncabezado']),
            Paragraph("Total Ap.", styles['DocTablaEncabezado']),
            Paragraph("Prom 100", styles['DocTablaEncabezado']),
            Paragraph("Prom 5", styles['DocTablaEncabezado']),
        ],
        [
            Paragraph("<b>Biología</b>", styles['DocTablaCelda']),
            Paragraph("612", styles['DocTablaCeldaNum']),
            Paragraph("80,61", styles['DocTablaCeldaNum']),
            Paragraph("3,57", styles['DocTablaCeldaNum']),
            Paragraph("398", styles['DocTablaCeldaNum']),
            Paragraph("80,88", styles['DocTablaCeldaNum']),
            Paragraph("3,56", styles['DocTablaCeldaNum']),
            Paragraph("817", styles['DocTablaCeldaNum']),
            Paragraph("78,97", styles['DocTablaCeldaNum']),
            Paragraph("3,39", styles['DocTablaCeldaNum']),
            Paragraph("616", styles['DocTablaCeldaNum']),
            Paragraph("80,58", styles['DocTablaCeldaNum']),
            Paragraph("3,52", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.443</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>80,10</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>3,49</b>", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>Historia de la Medicina</b>", styles['DocTablaCelda']),
            Paragraph("638", styles['DocTablaCeldaNum']),
            Paragraph("94,06", styles['DocTablaCeldaNum']),
            Paragraph("4,73", styles['DocTablaCeldaNum']),
            Paragraph("421", styles['DocTablaCeldaNum']),
            Paragraph("90,76", styles['DocTablaCeldaNum']),
            Paragraph("4,51", styles['DocTablaCeldaNum']),
            Paragraph("863", styles['DocTablaCeldaNum']),
            Paragraph("86,96", styles['DocTablaCeldaNum']),
            Paragraph("4,16", styles['DocTablaCeldaNum']),
            Paragraph("655", styles['DocTablaCeldaNum']),
            Paragraph("91,50", styles['DocTablaCeldaNum']),
            Paragraph("4,55", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.577</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>90,49</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,46</b>", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>Lengua Castellana</b>", styles['DocTablaCelda']),
            Paragraph("638", styles['DocTablaCeldaNum']),
            Paragraph("92,14", styles['DocTablaCeldaNum']),
            Paragraph("4,59", styles['DocTablaCeldaNum']),
            Paragraph("428", styles['DocTablaCeldaNum']),
            Paragraph("91,52", styles['DocTablaCeldaNum']),
            Paragraph("4,54", styles['DocTablaCeldaNum']),
            Paragraph("868", styles['DocTablaCeldaNum']),
            Paragraph("87,06", styles['DocTablaCeldaNum']),
            Paragraph("4,13", styles['DocTablaCeldaNum']),
            Paragraph("681", styles['DocTablaCeldaNum']),
            Paragraph("91,82", styles['DocTablaCeldaNum']),
            Paragraph("4,57", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.615</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>90,27</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,42</b>", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>TOTAL CONSOLIDADO</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>1.888</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>89,05</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,31</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>1.247</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>87,87</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,22</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.548</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>84,43</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>3,90</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>1.952</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>88,16</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,23</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>7.635</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>87,09</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,14</b>", styles['DocTablaCeldaNum']),
        ],
    ]
    t1 = Table(t1_data, colWidths=[2.6*cm, 0.95*cm, 1.05*cm, 0.9*cm, 0.95*cm, 1.05*cm, 0.9*cm, 0.95*cm, 1.05*cm, 0.9*cm, 0.95*cm, 1.05*cm, 0.9*cm, 1.1*cm, 1.1*cm, 1.0*cm])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C4D75")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.2),
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
            Paragraph("493", styles['DocTablaCeldaNum']),
            Paragraph("20,18%", styles['DocTablaCeldaNum']),
            Paragraph("52", styles['DocTablaCeldaNum']),
            Paragraph("2,02%", styles['DocTablaCeldaNum']),
            Paragraph("57", styles['DocTablaCeldaNum']),
            Paragraph("2,18%", styles['DocTablaCeldaNum']),
            Paragraph("602", styles['DocTablaCeldaNum']),
            Paragraph("7,88%", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("Nota 3 (70 a 80 - Bueno)", styles['DocTablaCelda']),
            Paragraph("726", styles['DocTablaCeldaNum']),
            Paragraph("29,72%", styles['DocTablaCeldaNum']),
            Paragraph("229", styles['DocTablaCeldaNum']),
            Paragraph("8,89%", styles['DocTablaCeldaNum']),
            Paragraph("236", styles['DocTablaCeldaNum']),
            Paragraph("9,02%", styles['DocTablaCeldaNum']),
            Paragraph("1.191", styles['DocTablaCeldaNum']),
            Paragraph("15,60%", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("Nota 4 (81 a 90 - Muy Bueno)", styles['DocTablaCelda']),
            Paragraph("746", styles['DocTablaCeldaNum']),
            Paragraph("30,54%", styles['DocTablaCeldaNum']),
            Paragraph("783", styles['DocTablaCeldaNum']),
            Paragraph("30,38%", styles['DocTablaCeldaNum']),
            Paragraph("866", styles['DocTablaCeldaNum']),
            Paragraph("33,12%", styles['DocTablaCeldaNum']),
            Paragraph("2.395", styles['DocTablaCeldaNum']),
            Paragraph("31,37%", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("Nota 5 (91 a 100 - Excelente)", styles['DocTablaCelda']),
            Paragraph("478", styles['DocTablaCeldaNum']),
            Paragraph("19,57%", styles['DocTablaCeldaNum']),
            Paragraph("1.513", styles['DocTablaCeldaNum']),
            Paragraph("58,71%", styles['DocTablaCeldaNum']),
            Paragraph("1.456", styles['DocTablaCeldaNum']),
            Paragraph("55,68%", styles['DocTablaCeldaNum']),
            Paragraph("3.447", styles['DocTablaCeldaNum']),
            Paragraph("45,15%", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>TOTAL</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>2.443</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100,00%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.577</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100,00%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.615</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100,00%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>7.635</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100,00%</b>", styles['DocTablaCeldaNum']),
        ],
    ]
    t2 = Table(t2_data, colWidths=[4.8*cm, 1.6*cm, 1.6*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.5*cm, 1.3*cm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.3),
    ]))
    elementos.append(t2)
    elementos.append(Spacer(1, 2))

    # Tabla 3: Consolidado por Convocatoria (Población Oficial: 665, 456, 897, 710)
    elementos.append(Paragraph("<b>Tabla 3: Consolidado por Convocatoria · Base Oficial de Alumnos Nuevos (665, 456, 897 y 710)</b>", styles['DocCuerpo']))
    t3_data = [
        [
            Paragraph("Convocatoria", styles['DocTablaEncabezado']),
            Paragraph("Nuevos Ofic.", styles['DocTablaEncabezado']),
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
            Paragraph("<b>2023/1</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>665</b>", styles['DocTablaCeldaNum']),
            Paragraph("607", styles['DocTablaCeldaNum']),
            Paragraph("91,28%", styles['DocTablaCeldaNum']),
            Paragraph("29", styles['DocTablaCeldaNum']),
            Paragraph("9", styles['DocTablaCeldaNum']),
            Paragraph("645", styles['DocTablaCeldaNum']),
            Paragraph("96,99%", styles['DocTablaCeldaNum']),
            Paragraph("1.888", styles['DocTablaCeldaNum']),
            Paragraph("88,90", styles['DocTablaCeldaNum']),
            Paragraph("4,29", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>2023/2</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>456</b>", styles['DocTablaCeldaNum']),
            Paragraph("397", styles['DocTablaCeldaNum']),
            Paragraph("87,06%", styles['DocTablaCeldaNum']),
            Paragraph("23", styles['DocTablaCeldaNum']),
            Paragraph("10", styles['DocTablaCeldaNum']),
            Paragraph("430", styles['DocTablaCeldaNum']),
            Paragraph("94,30%", styles['DocTablaCeldaNum']),
            Paragraph("1.247", styles['DocTablaCeldaNum']),
            Paragraph("87,81", styles['DocTablaCeldaNum']),
            Paragraph("4,21", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>2024/1</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>897</b>", styles['DocTablaCeldaNum']),
            Paragraph("811", styles['DocTablaCeldaNum']),
            Paragraph("90,41%", styles['DocTablaCeldaNum']),
            Paragraph("52", styles['DocTablaCeldaNum']),
            Paragraph("11", styles['DocTablaCeldaNum']),
            Paragraph("874", styles['DocTablaCeldaNum']),
            Paragraph("97,44%", styles['DocTablaCeldaNum']),
            Paragraph("2.548", styles['DocTablaCeldaNum']),
            Paragraph("84,35", styles['DocTablaCeldaNum']),
            Paragraph("3,89", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>2024/2</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>710</b>", styles['DocTablaCeldaNum']),
            Paragraph("610", styles['DocTablaCeldaNum']),
            Paragraph("85,92%", styles['DocTablaCeldaNum']),
            Paragraph("42", styles['DocTablaCeldaNum']),
            Paragraph("38", styles['DocTablaCeldaNum']),
            Paragraph("690", styles['DocTablaCeldaNum']),
            Paragraph("97,18%", styles['DocTablaCeldaNum']),
            Paragraph("1.952", styles['DocTablaCeldaNum']),
            Paragraph("88,24", styles['DocTablaCeldaNum']),
            Paragraph("4,24", styles['DocTablaCeldaNum']),
        ],
        [
            Paragraph("<b>TOTAL</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>2.728</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.425</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>88,89%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>146</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>68</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>2.639</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>96,74%</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>7.635</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>87,09</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,14</b>", styles['DocTablaCeldaNum']),
        ],
    ]
    t3 = Table(t3_data, colWidths=[2.0*cm, 1.8*cm, 1.6*cm, 1.6*cm, 1.5*cm, 1.5*cm, 1.8*cm, 1.6*cm, 1.6*cm, 1.5*cm, 1.5*cm])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1B365D")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.3),
    ]))
    elementos.append(t3)
    elementos.append(PageBreak())

    # =============================================================
    # PÁGINA 2: ESTRUCTURA DUAL EN 2 LIBROS EXCEL Y TABLAS BD
    # =============================================================
    elementos.append(Paragraph("2. Estructura Oficial de Entregables · División Dual en Dos Libros Excel (.XLSX)", styles['DocSeccion']))
    elementos.append(Paragraph(
        "Para las cohortes históricas 2023/1 a 2024/2, se mantiene exactamente la misma arquitectura analítica e institucional, "
        "produciendo dos archivos sincronizados y automatizados:",
        styles['DocCuerpo']
    ))

    archivos_desc = [
        "<b>1. Archivo Consolidado (<code>informes/Informe_Admisiones_Consolidado_2023_2024.xlsx</code>):</b><br/>"
        "• <b>Hoja 'Resumen' (21 Filas, 100% Dinámica):</b> Contiene el bloque de 7 tarjetas de KPIs (filas 5 y 6, columnas A a G) y las Tablas 1 y 2 maestras. "
        "<b>Todas las celdas están implementadas con fórmulas nativas de Excel</b> (<code>SUBTOTAL</code>, <code>COUNTIFS</code>, <code>AVERAGEIFS</code>) "
        "vinculadas a la columna técnica de visibilidad en 'Detalles'. Al aplicar cualquier filtro por convocatoria, materia, sección, nota o status en 'Detalles', "
        "<b>el tablero recalcula automáticamente en tiempo real</b>. Certifica la base oficial de <b>2.728 alumnos nuevos (665, 456, 897 y 710)</b>.<br/>"
        "• <b>Hoja 'Detalles' (7.635 Registros de Alumnos Nuevos):</b> Padrón exhaustivo con <b>13 columnas visibles estandarizadas</b> "
        "(ID Alumno, Nombre SysEduca, Doc Oficial, Tipo de Ingreso, Convocatoria de Admisión, Semestre de Cursado [1º Semestre], "
        "Materia, Sección, Condición de Cursado [Regular], Nota [0-100], Nota Final [1-5], Materias Aprobadas y Status de la Matrícula) más la columna técnica oculta "
        "<code>_Fila_Visible</code> en la columna N (14). Incluye fila final de subtotales dinámicos con <code>SUBTOTAL(103, ...)</code> y <code>SUBTOTAL(101, ...)</code>.",

        "<b>2. Archivo Separado por Materia (<code>informes/Informe_Admisiones_Separado_2023_2024.xlsx</code>):</b><br/>"
        "• <b>12 Hojas de Cálculo Dedicadas (3 Asignaturas x 4 Periodos):</b> Una hoja por cada combinación asignatura y periodo lectivo "
        "(<code>Biología 2023.1</code>, <code>Biología 2023.2</code>, <code>Biología 2024.1</code>, <code>Biología 2024.2</code>, "
        "<code>Historia Medicina 2023.1</code>, <code>Historia Medicina 2023.2</code>, <code>Historia Medicina 2024.1</code>, <code>Historia Medicina 2024.2</code>, "
        "<code>Lengua Castellana 2023.1</code>, <code>Lengua Castellana 2023.2</code>, <code>Lengua Castellana 2024.1</code> y <code>Lengua Castellana 2024.2</code>).<br/>"
        "• <b>Diseño Homogéneo Institucional:</b> Encabezado superior institucional (filas 1 a 3), panel inmovilizado en celda A6, estilo cebra alternado, "
        "autofiltros y exactamente las 9 columnas requeridas: <i>Nombre Completo, Documento Oficial, Semestre de Cursado, Materia, Sección, Nota (0-100), "
        "Nota Final (1-5), Materias Aprobadas y Status de la Matrícula</i>. Incorpora fila final de totales calculada dinámicamente con fórmulas <code>SUBTOTAL</code>."
    ]
    for ad in archivos_desc:
        elementos.append(Paragraph(ad, styles['DocCuerpo']))
        elementos.append(Spacer(1, 1.0))

    elementos.append(Spacer(1, 1.2))

    # Tabla 4: Detalle de las 12 Hojas del Libro Separado
    elementos.append(Paragraph("<b>Tabla 4: Catálogo y Balance de las 12 Hojas por Asignatura y Periodo en el Libro Separado 2023-2024</b>", styles['DocCuerpo']))
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
            Paragraph("<code>Biología 2023.1</code>", styles['DocTablaCelda']),
            Paragraph("Biología", styles['DocTablaCelda']),
            Paragraph("2023/1", styles['DocTablaCeldaCenter']),
            Paragraph("612", styles['DocTablaCeldaNum']),
            Paragraph("80,61", styles['DocTablaCeldaNum']),
            Paragraph("3,57", styles['DocTablaCeldaNum']),
            Paragraph("A6:I617 (Total en F618)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Biología 2023.2</code>", styles['DocTablaCelda']),
            Paragraph("Biología", styles['DocTablaCelda']),
            Paragraph("2023/2", styles['DocTablaCeldaCenter']),
            Paragraph("398", styles['DocTablaCeldaNum']),
            Paragraph("80,88", styles['DocTablaCeldaNum']),
            Paragraph("3,56", styles['DocTablaCeldaNum']),
            Paragraph("A6:I403 (Total en F404)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Biología 2024.1</code>", styles['DocTablaCelda']),
            Paragraph("Biología", styles['DocTablaCelda']),
            Paragraph("2024/1", styles['DocTablaCeldaCenter']),
            Paragraph("817", styles['DocTablaCeldaNum']),
            Paragraph("78,97", styles['DocTablaCeldaNum']),
            Paragraph("3,39", styles['DocTablaCeldaNum']),
            Paragraph("A6:I822 (Total en F823)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Biología 2024.2</code>", styles['DocTablaCelda']),
            Paragraph("Biología", styles['DocTablaCelda']),
            Paragraph("2024/2", styles['DocTablaCeldaCenter']),
            Paragraph("616", styles['DocTablaCeldaNum']),
            Paragraph("80,58", styles['DocTablaCeldaNum']),
            Paragraph("3,52", styles['DocTablaCeldaNum']),
            Paragraph("A6:I621 (Total en F622)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Historia Medicina 2023.1</code>", styles['DocTablaCelda']),
            Paragraph("Historia de la Medicina", styles['DocTablaCelda']),
            Paragraph("2023/1", styles['DocTablaCeldaCenter']),
            Paragraph("638", styles['DocTablaCeldaNum']),
            Paragraph("94,06", styles['DocTablaCeldaNum']),
            Paragraph("4,73", styles['DocTablaCeldaNum']),
            Paragraph("A6:I643 (Total en F644)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Historia Medicina 2023.2</code>", styles['DocTablaCelda']),
            Paragraph("Historia de la Medicina", styles['DocTablaCelda']),
            Paragraph("2023/2", styles['DocTablaCeldaCenter']),
            Paragraph("421", styles['DocTablaCeldaNum']),
            Paragraph("90,76", styles['DocTablaCeldaNum']),
            Paragraph("4,51", styles['DocTablaCeldaNum']),
            Paragraph("A6:I426 (Total en F427)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Historia Medicina 2024.1</code>", styles['DocTablaCelda']),
            Paragraph("Historia de la Medicina", styles['DocTablaCelda']),
            Paragraph("2024/1", styles['DocTablaCeldaCenter']),
            Paragraph("863", styles['DocTablaCeldaNum']),
            Paragraph("86,96", styles['DocTablaCeldaNum']),
            Paragraph("4,16", styles['DocTablaCeldaNum']),
            Paragraph("A6:I868 (Total en F869)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Historia Medicina 2024.2</code>", styles['DocTablaCelda']),
            Paragraph("Historia de la Medicina", styles['DocTablaCelda']),
            Paragraph("2024/2", styles['DocTablaCeldaCenter']),
            Paragraph("655", styles['DocTablaCeldaNum']),
            Paragraph("91,50", styles['DocTablaCeldaNum']),
            Paragraph("4,55", styles['DocTablaCeldaNum']),
            Paragraph("A6:I660 (Total en F661)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Lengua Castellana 2023.1</code>", styles['DocTablaCelda']),
            Paragraph("Lengua Castellana", styles['DocTablaCelda']),
            Paragraph("2023/1", styles['DocTablaCeldaCenter']),
            Paragraph("638", styles['DocTablaCeldaNum']),
            Paragraph("92,14", styles['DocTablaCeldaNum']),
            Paragraph("4,59", styles['DocTablaCeldaNum']),
            Paragraph("A6:I643 (Total en F644)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Lengua Castellana 2023.2</code>", styles['DocTablaCelda']),
            Paragraph("Lengua Castellana", styles['DocTablaCelda']),
            Paragraph("2023/2", styles['DocTablaCeldaCenter']),
            Paragraph("428", styles['DocTablaCeldaNum']),
            Paragraph("91,52", styles['DocTablaCeldaNum']),
            Paragraph("4,54", styles['DocTablaCeldaNum']),
            Paragraph("A6:I433 (Total en F434)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Lengua Castellana 2024.1</code>", styles['DocTablaCelda']),
            Paragraph("Lengua Castellana", styles['DocTablaCelda']),
            Paragraph("2024/1", styles['DocTablaCeldaCenter']),
            Paragraph("868", styles['DocTablaCeldaNum']),
            Paragraph("87,06", styles['DocTablaCeldaNum']),
            Paragraph("4,13", styles['DocTablaCeldaNum']),
            Paragraph("A6:I873 (Total en F874)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<code>Lengua Castellana 2024.2</code>", styles['DocTablaCelda']),
            Paragraph("Lengua Castellana", styles['DocTablaCelda']),
            Paragraph("2024/2", styles['DocTablaCeldaCenter']),
            Paragraph("681", styles['DocTablaCeldaNum']),
            Paragraph("91,82", styles['DocTablaCeldaNum']),
            Paragraph("4,57", styles['DocTablaCeldaNum']),
            Paragraph("A6:I686 (Total en F687)", styles['DocTablaCeldaCenter']),
        ],
        [
            Paragraph("<b>TOTAL INTEGRADO (12 HOJAS)</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>3 Asignaturas</b>", styles['DocTablaCeldaBold']),
            Paragraph("<b>4 Periodos</b>", styles['DocTablaCeldaCenter']),
            Paragraph("<b>7.635</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>87,09</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>4,14</b>", styles['DocTablaCeldaNum']),
            Paragraph("<b>100% Nuevos de 1º Semestre</b>", styles['DocTablaCeldaCenter']),
        ],
    ]
    t4 = Table(t4_data, colWidths=[3.8*cm, 3.2*cm, 1.6*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.8*cm])
    t4.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.1),
    ]))
    elementos.append(t4)
    elementos.append(PageBreak())

    # =============================================================
    # PÁGINA 3: REGLAS DE CÁLCULO, OBSERVACIONES Y FIRMAS
    # =============================================================
    elementos.append(Paragraph("3. Reglas del Cálculo Oficial de Calificaciones de SysEduca y Escala Paraguaya", styles['DocSeccion']))
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
            Paragraph("Proceso integrado (14) suma de forma directa; si existe, anula Trabajos (999). Si no hay 14, Trabajos promedia.", styles['DocTablaCelda']),
            Paragraph("Aporte al acumulado de proceso.", styles['DocTablaCelda']),
        ],
        [
            Paragraph("<b>Tope Reglamentario (100)</b>", styles['DocTablaCeldaBold']),
            Paragraph("LEAST(nota, 100)", styles['DocTablaCeldaCenter']),
            Paragraph("Auditoría de actas: en casos donde la suma de parciales, examen ordinario y proceso acumuló más de 100 puntos (ej. 101, 102, 116 o 119), <b>se aplicó la cota reglamentaria oficial LEAST(nota, 100)</b> fijando la calificación en 100 (Nota Final 5).", styles['DocTablaCeldaBold']),
            Paragraph("Garantiza cumplimiento normativo MEC.", styles['DocTablaCelda']),
        ]
    ]

    t_reglas = Table(reglas_notas, colWidths=[2.6*cm, 2.2*cm, 8.8*cm, 4.4*cm])
    t_reglas.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#12263F")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.3),
    ]))
    elementos.append(t_reglas)
    elementos.append(Spacer(1, 2))

    # Escala Oficial Paraguaya
    elementos.append(Paragraph(
        "<b>Escala Oficial de Calificaciones de la República del Paraguay:</b><br/>"
        "• <b>Nota 1 (0 a 59 pts):</b> Insuficiente / Reprobado · <b>Nota 2 (60 a 69 pts):</b> Regular / Aprobado · "
        "<b>Nota 3 (70 a 80 pts):</b> Bueno · <b>Nota 4 (81 a 90 pts):</b> Muy Bueno · <b>Nota 5 (91 a 100 pts):</b> Excelente.<br/>"
        "<i>En la hoja 'Detalles' la columna 'Nota Final (1-5)' se expresa exclusivamente en números enteros (2, 3, 4 y 5) sin decimales.</i>",
        styles['DocCuerpo']
    ))
    elementos.append(Spacer(1, 2))

    # 4. OBSERVACIONES Y VALIDACIONES DE CALIDAD
    elementos.append(Paragraph("4. Observaciones Técnicas, Certificación de Fuentes y Status de Matrícula", styles['DocSeccion']))
    observaciones = [
        "<b>1. Alumnos Nuevos Oficiales (665, 456, 897 y 710):</b> En concordancia con el registro oficial de distribución por semestre y sección, "
        "la población de ingresantes matriculados en el 1º Semestre de Medicina es de <b>665 en 2023/1</b>, <b>456 en 2023/2</b>, <b>897 en 2024/1</b> y <b>710 en 2024/2</b> (totalizando <b>2.728 alumnos nuevos</b>). "
        "Esta cifra constituye la base matemática oficial sobre la que se calculan todos los porcentajes de cohorte y efectividad académica.",
        "<b>2. Omisión Total de Convalidados y Recursantes:</b> Se excluyeron íntegramente del reporte a los alumnos convalidados "
        "(transferencias externas) y a los estudiantes recursantes (cursados posteriores a su convocatoria de admisión). "
        "El padrón comprende con absoluta pureza a los <b>alumnos nuevos regulares del 1º Semestre</b> que cursaron y aprobaron asignaturas en su periodo oficial.",
        "<b>3. Incorporación del Status de Matrícula del Alumno:</b> Se integró una columna formal que refleja el estado de la matrícula "
        "en <code>ucp.matricula_curso</code> de SysEduca MySQL (<b>Activo, Trancado, Suspenso, Finalizado o Excluido</b>) con <b>100,0% de cobertura</b>.",
        "<b>4. Auditoría de Calificaciones Superiores a 100 Puntos:</b> Se regularizaron casos donde la acumulación de actas superó 100 puntos mediante la cota oficial <code>LEAST(nota, 100)</code>.",
        "<b>5. Dinamismo Total del Tablero Resumen en Excel:</b> Todos los KPIs y tablas de la hoja 'Resumen' en el libro Consolidado están dotados de fórmulas nativas dinámicas. "
        "Al aplicar cualquier filtro de columna en la hoja 'Detalles', el resumen recalcula al instante sus indicadores y promedios en tiempo real.",
        "<b>6. Integridad de Documentos Oficiales (doc_oficial):</b> Al extraerse directamente desde <code>ucp.usuarios</code> en SysEduca MySQL, "
        "los 2.639 alumnos únicos poseen su documento oficial debidamente registrado, logrando el <b>100,0% de cobertura</b> (0 vacíos o nulos)."
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
    print(f"PDF oficial 2023-2024 generado con éxito en: {pdf_path}")


if __name__ == "__main__":
    generar_pdf_admisiones_2023_2024()
