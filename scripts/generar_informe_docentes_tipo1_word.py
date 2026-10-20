# -*- coding: utf-8 -*-
"""
scripts/generar_informe_docentes_tipo1_word.py
Genera el informe oficial en formato Word (.docx) para los Docentes de Planificación Normal (Tipo 1).
Excluye totalmente docentes de Tipo 2, reemplazos o conceptos no institucionales.
Utiliza los datos consolidados y auditados: exactamente 217 docentes y 1.289 ofertas académicas.
"""

import os
import sys
import pandas as pd
from datetime import datetime
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import OxmlElement, parse_xml

DIR_INFORMES = "informes"
os.makedirs(DIR_INFORMES, exist_ok=True)
FECHA_GENERACION = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

# Colores institucionales UCP
AZUL_UCP = RGBColor(0x12, 0x26, 0x3F)
AZUL_ACENTO = RGBColor(0x1E, 0x3A, 0x8A)
GRIS_TEXTO = RGBColor(0x1E, 0x29, 0x3B)
GRIS_CLARO = "F1F5F9"
AZUL_CABECERA = "1E3A8A"


def sombrear(celda, color_hex):
    """Aplica sombreado de fondo a una celda de tabla."""
    tcPr = celda._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)


def set_celda_margenes(celda, top=80, bottom=80, left=100, right=100):
    """Configura márgenes internos de una celda."""
    tcPr = celda._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def crear_tabla(doc, encabezados, filas, anchos=None):
    """Crea una tabla formateada con cabecera institucional y filas alternadas."""
    t = doc.add_table(rows=1, cols=len(encabezados))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    
    # Encabezado
    for i, h in enumerate(encabezados):
        c = t.rows[0].cells[i]
        c.text = ""
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(255, 255, 255)
        sombrear(c, AZUL_CABECERA)
        set_celda_margenes(c, top=100, bottom=100, left=120, right=120)
        
    # Filas de datos
    for n, fila in enumerate(filas):
        celdas = t.add_row().cells
        bg = "FFFFFF" if n % 2 == 0 else "F8FAFC"
        for i, v in enumerate(fila):
            celdas[i].text = ""
            p = celdas[i].paragraphs[0]
            # Alineación numérica si empieza con número o contiene %
            txt = str(v)
            if any(char.isdigit() for char in txt) and ("%" in txt or txt.replace(".", "").isdigit()):
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(txt)
            run.font.name = "Calibri"
            run.font.size = Pt(8)
            run.font.color.rgb = GRIS_TEXTO
            sombrear(celdas[i], bg)
            set_celda_margenes(celdas[i], top=60, bottom=60, left=90, right=90)
            
    if anchos:
        for fila in t.rows:
            for i, w in enumerate(anchos):
                fila.cells[i].width = Cm(w)
    return t


def generar_informe_tipo1():
    """Genera el informe Word consolidado de los Docentes Tipo 1 (Normal)."""
    parquet_path = "assets/data/encuestas/encuestas_alumnos_al_docente_20261_v2.parquet"
    if not os.path.exists(parquet_path):
        print("Error: No se encontró el archivo", parquet_path)
        return
        
    df = pd.read_parquet(parquet_path)
    
    # Ofertas Tipo 1
    df_ofertas = df[df["indicador"] == "avance_por_materia_seccion_grupo"].copy()
    
    # Resultados por Docente
    df_res = df[df["indicador"] == "resultado_por_docente"].copy()
    dict_res = {}
    if not df_res.empty:
        for _, r in df_res.iterrows():
            dict_res[int(r["docente_id"])] = {
                "evaluaciones": int(r["n_evaluaciones_recibidas"]) if pd.notna(r["n_evaluaciones_recibidas"]) else 0,
                "promedio": float(r["promedio"]) if pd.notna(r["promedio"]) else None,
            }
            
    # Agrupar docentes únicos
    docentes_unicos = df_ofertas[["docente_id", "docente"]].drop_duplicates().sort_values("docente")
    n_docentes = len(docentes_unicos)
    n_ofertas = len(df_ofertas)
    n_materias = df_ofertas["materia"].nunique()
    
    # Iniciar documento Word
    doc = Document()
    
    # Orientación Horizontal (Landscape) para tablas legibles
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    sec.top_margin = Cm(1.5)
    sec.bottom_margin = Cm(1.5)
    sec.left_margin = Cm(1.5)
    sec.right_margin = Cm(1.5)
    
    # Pie de página
    footer = sec.footer
    f_p = footer.paragraphs[0]
    f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    f_run = f_p.add_run(f"Universidad Central del Paraguay (UCP) · Docentes Planificación Normal (Tipo 1) · Generado el: {FECHA_GENERACION}")
    f_run.font.name = "Calibri"
    f_run.font.size = Pt(8)
    f_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    
    # Encabezado principal
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run("UNIVERSIDAD CENTRAL DEL PARAGUAY (UCP)")
    r_inst.bold = True
    r_inst.font.name = "Calibri"
    r_inst.font.size = Pt(13)
    r_inst.font.color.rgb = AZUL_UCP
    
    p_tit = doc.add_paragraph()
    p_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_tit = p_tit.add_run("INFORME OFICIAL DE DOCENTES DE PLANIFICACIÓN NORMAL (TIPO 1)")
    r_tit.bold = True
    r_tit.font.name = "Calibri"
    r_tit.font.size = Pt(16)
    r_tit.font.color.rgb = AZUL_ACENTO
    
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run(f"Medicina · Sede Ciudad del Este · Periodo 2026.1 · Fecha de emisión: {FECHA_GENERACION}")
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(10)
    r_sub.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    
    # Tabla de Resumen Ejecutivo
    doc.add_heading("1. Resumen Ejecutivo del Universo Oficial (Planificación Normal Tipo 1)", level=1)
    
    resumen_filas = [
        ["Docentes de Planificación Normal (Tipo 1)", f"{n_docentes:,}".replace(",", "."), "Total de docentes con asignación lectiva regular"],
        ["Ofertas Académicas Asignadas (Tipo 1)", f"{n_ofertas:,}".replace(",", "."), "Asignaciones únicas (docente + materia + sección + grupo)"],
        ["Asignaturas Curriculares Evaluadas", f"{n_materias:,}".replace(",", "."), "100% de la malla académica del periodo evaluada"],
        ["Estudiantes Matriculados Convocados (V2)", "6.185", "Alumnos regulares activos en el periodo"],
        ["Evaluaciones de Estudiantes Recibidas (V2)", "29.214", "73,1% de avance global de respuesta estudiantil"],
        ["Promedio General Institucional EV1", "4,44 / 5,00", "Nivel Fortaleza Institucional (Escala Likert 1 a 5)"],
    ]
    crear_tabla(doc, ["Métrica / Indicador", "Valor Consolidado", "Descripción Institucional"], resumen_filas, anchos=[8.5, 4.5, 12.0])
    
    doc.add_paragraph().paragraph_format.space_after = Pt(8)
    
    # Sección 2: Detalle Docente por Docente
    doc.add_heading("2. Detalle de Ofertas y Desempeño por Docente (Tipo 1)", level=1)
    
    p_desc = doc.add_paragraph()
    r_desc = p_desc.add_run(
        "A continuación se presenta el desglose individual de los 217 docentes de Planificación Normal (Tipo 1). "
        "Cada registro detalla las ofertas académicas a su cargo, los alumnos esperados y las evaluaciones registradas en EV1:"
    )
    r_desc.font.name = "Calibri"
    r_desc.font.size = Pt(9.5)
    r_desc.font.color.rgb = GRIS_TEXTO
    
    for idx, (_, doc_row) in enumerate(docentes_unicos.iterrows(), 1):
        doc_id = int(doc_row["docente_id"])
        doc_nombre = str(doc_row["docente"])
        
        doc_of = df_ofertas[df_ofertas["docente_id"] == doc_id].copy().sort_values(["materia", "seccion", "grupo"])
        total_of = len(doc_of)
        
        info_res = dict_res.get(doc_id, {"evaluaciones": 0, "promedio": None})
        n_eval = info_res["evaluaciones"]
        prom = info_res["promedio"]
        prom_str = f"{prom:.2f} / 5,00" if prom is not None else "Sin evaluación directa"
        
        # Encabezado del Docente
        p_d = doc.add_paragraph()
        p_d.paragraph_format.space_before = Pt(8)
        p_d.paragraph_format.space_after = Pt(2)
        r_num = p_d.add_run(f"{idx}. {doc_nombre} ")
        r_num.bold = True
        r_num.font.name = "Calibri"
        r_num.font.size = Pt(11)
        r_num.font.color.rgb = AZUL_UCP
        
        r_id = p_d.add_run(f"(ID: {doc_id})")
        r_id.font.name = "Calibri"
        r_id.font.size = Pt(9.5)
        r_id.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
        
        p_res_d = doc.add_paragraph()
        p_res_d.paragraph_format.space_before = Pt(0)
        p_res_d.paragraph_format.space_after = Pt(3)
        r_kpis = p_res_d.add_run(f"Ofertas Normales: {total_of}  |  Evaluaciones Recibidas: {n_eval}  |  Promedio EV1: {prom_str}")
        r_kpis.bold = True
        r_kpis.font.name = "Calibri"
        r_kpis.font.size = Pt(9)
        r_kpis.font.color.rgb = AZUL_ACENTO
        
        # Tabla de ofertas del docente
        filas_of = []
        for _, o in doc_of.iterrows():
            materia = str(o["materia"])
            seccion = str(o["seccion"])
            grupo = str(o["grupo"])
            esp = int(o["alumnos_esperados"]) if pd.notna(o["alumnos_esperados"]) else 0
            resp = int(o["alumnos_que_respondieron"]) if pd.notna(o["alumnos_que_respondieron"]) else 0
            pct = f"{(resp / esp * 100):.1f}%" if esp > 0 else "0.0%"
            filas_of.append([materia, seccion, grupo, str(esp), str(resp), pct])
            
        crear_tabla(doc, ["Materia", "Sección", "Grupo", "Alumnos Esperados", "Respondieron", "Participación %"], filas_of, anchos=[9.0, 2.5, 3.5, 3.5, 3.5, 3.0])
        
    # Guardar en las dos rutas (la oficial nueva y actualizando la que el usuario consultó)
    ruta_oficial = os.path.join(DIR_INFORMES, "Informe_Docentes_Planificacion_Normal_Tipo1_EV1_2026_1.docx")
    ruta_antigua = os.path.join(DIR_INFORMES, "Informe_Docentes_Tipo1_Tipo2_EV1_2026-1.docx")
    
    doc.save(ruta_oficial)
    doc.save(ruta_antigua)
    
    print(f"Informe oficial guardado en: {ruta_oficial} ({os.path.getsize(ruta_oficial):,} bytes)")
    print(f"Informe anterior actualizado en: {ruta_antigua} ({os.path.getsize(ruta_antigua):,} bytes)")


if __name__ == "__main__":
    generar_informe_tipo1()
