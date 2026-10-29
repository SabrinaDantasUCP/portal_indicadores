# -*- coding: utf-8 -*-
"""
tests/test_panel_acad_alumnos_export.py

Pruebas unitarias para la exportación estética del Listado de Alumnos,
filtrado estricto de asignaturas regulares (omisión de extracurriculares y sin disciplina),
tope estricto de notas a 100 puntos en escala 1-100, y no regresión de la exportación por Periodo y Semestre.
"""
import io
import unittest
import pandas as pd
from modules.panel_acad_alumnos import _generate_excel_bytes, _generar_excel_listado_alumnos


class TestExportacionAlumnos(unittest.TestCase):

    def setUp(self):
        # Datos simulados de resumen por periodo y matriz
        self.period_summary = pd.DataFrame({
            "ano_periodo_letivo": [2024, 2024],
            "periodo_anual_periodo_letivo": [1, 2],
            "Periodo": ["2024.1", "2024.2"],
            "Alumnos": [150, 160],
        })
        self.matriz = pd.DataFrame(
            [[10, 12], [20, 22]],
            index=[1, 2],
            columns=["2024.1", "2024.2"]
        )
        self.matriz.index.name = "Semestre"

        # Listado base de alumnos
        self.alumnos_list = pd.DataFrame([
            {
                "usuarios_id": 101,
                "Número de Matrícula": 12345,
                "Nombre y Apellido": "Juan Perez",
                "Periodo": "2024.1",
                "Semestre": 1,
            },
            {
                "usuarios_id": 102,
                "Número de Matrícula": 67890,
                "Nombre y Apellido": "Maria Gomez",
                "Periodo": "2024.1",
                "Semestre": 2,
            },
            {
                "usuarios_id": 103,
                "Número de Matrícula": 99999,
                "Nombre y Apellido": "Pedro SinMaterias",
                "Periodo": "2024.1",
                "Semestre": 1,
            },
        ])

        # DataFrame completo con asignaturas regulares, notas > 100, extracurriculares y sin disciplina
        self.df_completo = pd.DataFrame([
            # Juan Perez: 2 materias regulares, 1 extracurricular, 1 sin disciplina en periodo posterior
            {
                "usuarios_id": 101,
                "ano_periodo_letivo": 2024,
                "periodo_anual_periodo_letivo": 1,
                "semestre_alumno": 1,
                "filial_periodo_letivo": "CDE",
                "disciplina": "Anatomía I",
                "tipo_disciplina": "Regular",
                "turma": "A",
                "calificacion_final": 85.0,
                "calificacion_final_1a5": 4,
                "nombre_status_actual": "Activo",
            },
            {
                "usuarios_id": 101,
                "ano_periodo_letivo": 2024,
                "periodo_anual_periodo_letivo": 1,
                "semestre_alumno": 1,
                "filial_periodo_letivo": "CDE",
                "disciplina": "Biología",
                "tipo_disciplina": "Regular",
                "turma": "B",
                "calificacion_final": 92.0,
                "calificacion_final_1a5": 5,
                "nombre_status_actual": "Activo",
            },
            {
                "usuarios_id": 101,
                "ano_periodo_letivo": 2024,
                "periodo_anual_periodo_letivo": 1,
                "semestre_alumno": 1,
                "filial_periodo_letivo": "CDE",
                "disciplina": "Guaraní con énfasis",
                "tipo_disciplina": "Extracurricular",
                "turma": "A",
                "calificacion_final": 20.0,
                "calificacion_final_1a5": 0,
                "nombre_status_actual": "Activo",
            },
            {
                "usuarios_id": 101,
                "ano_periodo_letivo": 2024,
                "periodo_anual_periodo_letivo": 2,
                "semestre_alumno": 2,
                "filial_periodo_letivo": "CDE",
                "disciplina": None,
                "tipo_disciplina": "Sin Disciplina",
                "turma": None,
                "calificacion_final": 0.0,
                "calificacion_final_1a5": 0,
                "nombre_status_actual": "Activo",
            },
            # Maria Gomez: 1 materia regular con nota acumulada de 115 puntos (debe toparse a 100)
            {
                "usuarios_id": 102,
                "ano_periodo_letivo": 2024,
                "periodo_anual_periodo_letivo": 1,
                "semestre_alumno": 2,
                "filial_periodo_letivo": "CDE III",
                "disciplina": "Histología",
                "tipo_disciplina": "Regular",
                "turma": "A",
                "calificacion_final": 115.0,
                "calificacion_final_1a5": 5,
                "nombre_status_actual": "Trancado",
            },
            # Pedro SinMaterias: solo inscripción sin disciplina
            {
                "usuarios_id": 103,
                "ano_periodo_letivo": 2024,
                "periodo_anual_periodo_letivo": 1,
                "semestre_alumno": 1,
                "filial_periodo_letivo": "CDE",
                "disciplina": None,
                "tipo_disciplina": "Sin Disciplina",
                "turma": None,
                "calificacion_final": 0.0,
                "calificacion_final_1a5": 0,
                "nombre_status_actual": "Trancado",
            },
        ])

    def test_no_regresion_excel_por_periodo(self):
        """Valida que la exportación original de Por periodo y semestre siga funcionando intacta."""
        bytes_excel = _generate_excel_bytes(self.period_summary, self.matriz, self.alumnos_list)
        self.assertIsInstance(bytes_excel, bytes)
        self.assertGreater(len(bytes_excel), 1000)

        # Leer con pandas y verificar las 3 hojas originales
        hojas = pd.ExcelFile(io.BytesIO(bytes_excel)).sheet_names
        self.assertIn("Por Periodo", hojas)
        self.assertIn("Matriz", hojas)
        self.assertIn("Listado", hojas)

    def test_generacion_excel_listado_detallado(self):
        """Valida que el Excel del listado de alumnos tenga las 11 columnas y el formato correcto."""
        bytes_excel = _generar_excel_listado_alumnos(self.alumnos_list, self.df_completo, busqueda=None)
        self.assertIsInstance(bytes_excel, bytes)
        self.assertGreater(len(bytes_excel), 1000)

        # Leer el título y subtítulo en filas 0 y 1
        excel_completo = pd.read_excel(io.BytesIO(bytes_excel), header=None)
        self.assertEqual(excel_completo.iloc[0, 0], "REPORTE DETALLADO - LISTADO DE ALUMNOS")
        self.assertIn("Portal de Indicadores Académicos · Sistema de Gestión Institucional", str(excel_completo.iloc[1, 0]))

        # Leer a partir de la fila 3 (encabezados de la tabla)
        df_leido = pd.read_excel(
            io.BytesIO(bytes_excel),
            skiprows=3,
            dtype={"Matrícula": str, "Periodo": str, "Documento": str, "Estado de Matrícula": str, "Semestre": str, "Sección": str}
        )
        columnas_esperadas = [
            "Matrícula",
            "Documento",
            "Nombre Completo",
            "Estado de Matrícula",
            "Periodo",
            "Semestre",
            "Sede",
            "Materia",
            "Sección",
            "Nota (1 a 100)",
            "Nota (1 a 5)",
        ]
        self.assertEqual(list(df_leido.columns), columnas_esperadas)
        # Solo deben salir 3 filas regulares (2 de Juan y 1 de María). Pedro (sin materias) y materias extracurriculares deben omitirse.
        self.assertEqual(len(df_leido), 3)

        # Verificar contenido de la primera fila (Juan Perez)
        primera_fila = df_leido.iloc[0]
        self.assertEqual(primera_fila["Matrícula"], "12345")
        self.assertEqual(primera_fila["Nombre Completo"], "Juan Perez")
        self.assertEqual(primera_fila["Estado de Matrícula"], "Activo")
        self.assertEqual(primera_fila["Periodo"], "2024.1")
        self.assertEqual(primera_fila["Sede"], "CDE")
        self.assertEqual(primera_fila["Materia"], "Anatomía I")
        self.assertEqual(primera_fila["Sección"], "A")
        self.assertEqual(primera_fila["Nota (1 a 100)"], 85)
        self.assertEqual(primera_fila["Nota (1 a 5)"], 4)

        # Verificar contenido de Maria Gomez: su nota 115 debe haberse topado en 100
        fila_maria = df_leido[df_leido["Nombre Completo"] == "Maria Gomez"].iloc[0]
        self.assertEqual(fila_maria["Materia"], "Histología")
        self.assertEqual(fila_maria["Nota (1 a 100)"], 100)
        self.assertEqual(fila_maria["Nota (1 a 5)"], 5)

        # Verificar que NO existen materias vacías ('–') en la columna Materia
        self.assertFalse((df_leido["Materia"] == "–").any())

    def test_filtro_busqueda_excel(self):
        """Valida que si se filtra por un estudiante, el reporte solo contenga a dicho estudiante."""
        filtro = self.alumnos_list[self.alumnos_list["Nombre y Apellido"] == "Maria Gomez"].reset_index(drop=True)
        bytes_excel = _generar_excel_listado_alumnos(filtro, self.df_completo, busqueda="Maria")
        df_leido = pd.read_excel(
            io.BytesIO(bytes_excel),
            skiprows=3,
            dtype={"Matrícula": str, "Periodo": str, "Documento": str, "Estado de Matrícula": str, "Semestre": str, "Sección": str}
        )

        self.assertEqual(len(df_leido), 1)
        self.assertEqual(df_leido.iloc[0]["Nombre Completo"], "Maria Gomez")
        self.assertEqual(df_leido.iloc[0]["Estado de Matrícula"], "Trancado")
        self.assertEqual(df_leido.iloc[0]["Materia"], "Histología")
        self.assertEqual(df_leido.iloc[0]["Nota (1 a 100)"], 100)
        self.assertEqual(df_leido.iloc[0]["Nota (1 a 5)"], 5)

    def test_cruce_doc_oficial_real(self):
        """Valida que el archivo de documentos oficiales exista y contenga registros."""
        from services.data.alumnos import load_alumnos_documentos
        docs = load_alumnos_documentos()
        self.assertIsInstance(docs, dict)
        self.assertGreater(len(docs), 1000)
        # ID 1 debe tener documento oficial 43525
        self.assertEqual(docs.get(1), "43525")


if __name__ == "__main__":
    unittest.main()
