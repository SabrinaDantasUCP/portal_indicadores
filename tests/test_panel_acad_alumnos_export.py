# -*- coding: utf-8 -*-
"""
tests/test_panel_acad_alumnos_export.py

Pruebas unitarias para la exportación estética del Listado de Alumnos
y no regresión de la exportación por Periodo y Semestre.
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
        ])

        # DataFrame completo con asignaturas y calificaciones reales
        self.df_completo = pd.DataFrame([
            {
                "usuarios_id": 101,
                "ano_periodo_letivo": 2024,
                "periodo_anual_periodo_letivo": 1,
                "filial_periodo_letivo": "CDE",
                "disciplina": "Anatomía I",
                "turma": "A",
                "calificacion_final": 85.0,
                "calificacion_final_1a5": 4,
                "nombre_status_actual": "Activo",
            },
            {
                "usuarios_id": 101,
                "ano_periodo_letivo": 2024,
                "periodo_anual_periodo_letivo": 1,
                "filial_periodo_letivo": "CDE",
                "disciplina": "Biología",
                "turma": "B",
                "calificacion_final": 92.0,
                "calificacion_final_1a5": 5,
                "nombre_status_actual": "Activo",
            },
            {
                "usuarios_id": 102,
                "ano_periodo_letivo": 2024,
                "periodo_anual_periodo_letivo": 1,
                "filial_periodo_letivo": "CDE III",
                "disciplina": "Histología",
                "turma": "A",
                "calificacion_final": 55.0,
                "calificacion_final_1a5": 1,
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
        """Valida que el Excel del listado de alumnos tenga las 10 columnas y el formato correcto."""
        bytes_excel = _generar_excel_listado_alumnos(self.alumnos_list, self.df_completo, busqueda=None)
        self.assertIsInstance(bytes_excel, bytes)
        self.assertGreater(len(bytes_excel), 1000)

        # Leer a partir de la fila 6 (encabezados de la tabla)
        df_leido = pd.read_excel(io.BytesIO(bytes_excel), skiprows=6, dtype={"Periodo": str, "Documento": str, "Estado de Matrícula": str, "Semestre": str, "Sección": str})
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
        self.assertEqual(len(df_leido), 3)

        # Verificar contenido de la primera fila
        primera_fila = df_leido.iloc[0]
        self.assertEqual(primera_fila["Matrícula"], 12345)
        self.assertEqual(primera_fila["Nombre Completo"], "Juan Perez")
        self.assertEqual(primera_fila["Estado de Matrícula"], "Activo")
        self.assertEqual(primera_fila["Periodo"], "2024.1")
        self.assertEqual(primera_fila["Sede"], "CDE")
        self.assertEqual(primera_fila["Materia"], "Anatomía I")
        self.assertEqual(primera_fila["Sección"], "A")
        self.assertEqual(primera_fila["Nota (1 a 100)"], 85)
        self.assertEqual(primera_fila["Nota (1 a 5)"], 4)

    def test_filtro_busqueda_excel(self):
        """Valida que si se filtra por un estudiante, el reporte solo contenga a dicho estudiante."""
        filtro = self.alumnos_list[self.alumnos_list["Nombre y Apellido"] == "Maria Gomez"].reset_index(drop=True)
        bytes_excel = _generar_excel_listado_alumnos(filtro, self.df_completo, busqueda="Maria")
        df_leido = pd.read_excel(io.BytesIO(bytes_excel), skiprows=6, dtype={"Periodo": str, "Documento": str, "Estado de Matrícula": str, "Semestre": str, "Sección": str})

        self.assertEqual(len(df_leido), 1)
        self.assertEqual(df_leido.iloc[0]["Nombre Completo"], "Maria Gomez")
        self.assertEqual(df_leido.iloc[0]["Estado de Matrícula"], "Trancado")
        self.assertEqual(df_leido.iloc[0]["Materia"], "Histología")
        self.assertEqual(df_leido.iloc[0]["Nota (1 a 100)"], 55)
        self.assertEqual(df_leido.iloc[0]["Nota (1 a 5)"], 1)


if __name__ == "__main__":
    unittest.main()
