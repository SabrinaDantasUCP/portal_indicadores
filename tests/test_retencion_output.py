# -*- coding: utf-8 -*-
"""
tests/test_retencion_output.py

Pruebas automatizadas de la lógica de retención segura y purga de snapshots.
Verifica que bajo ningún concepto se eliminen archivos si el sistema está pausado
o congelado, respetando el piso mínimo y la lista blanca de snapshots.
"""
import os
import time
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

from services.etl.retencion_output import (
    clasificar_archivo_snapshot,
    aplicar_retencion_output,
)


class TestRetencionOutput(unittest.TestCase):

    def setUp(self):
        # Crear un directorio temporal aislado para simular output/
        self.temp_dir = tempfile.mkdtemp(prefix="test_output_")

    def tearDown(self):
        # Limpiar el directorio temporal
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _crear_archivo_simulado(self, nombre: str, tamano_bytes: int = 1024, dias_antiguedad: int = 0) -> str:
        ruta = os.path.join(self.temp_dir, nombre)
        with open(ruta, "wb") as f:
            f.write(b"0" * tamano_bytes)

        if dias_antiguedad > 0:
            tiempo_antiguo = time.time() - (dias_antiguedad * 86400)
            os.utime(ruta, (tiempo_antiguo, tiempo_antiguo))

        return ruta

    def test_clasificacion_de_archivos(self):
        """Verifica que solo los snapshots con timestamp califiquen y los demás se ignoren."""
        self.assertEqual(
            clasificar_archivo_snapshot("indicadores_encuestas_20261019_125221.csv"),
            "indicadores_encuestas_v1",
        )
        self.assertEqual(
            clasificar_archivo_snapshot("indicadores_encuestas_v2_20261019_125242.csv"),
            "indicadores_encuestas_v2",
        )
        self.assertEqual(
            clasificar_archivo_snapshot("indicadores_encuestas_docente_autoeval_20261019_084734.csv"),
            "indicadores_encuestas_autoeval_docente",
        )
        self.assertEqual(
            clasificar_archivo_snapshot("avance_por_alumno_activos_20261019_084734.csv"),
            "avance_por_alumno_activos",
        )

        # Archivos crudos o del sistema NO deben calificar nunca
        self.assertIsNone(clasificar_archivo_snapshot("respuestas_raw.csv"))
        self.assertIsNone(clasificar_archivo_snapshot("planificacion_raw.csv"))
        self.assertIsNone(clasificar_archivo_snapshot("contacto_raw.csv"))
        self.assertIsNone(clasificar_archivo_snapshot("alumnos_v1.csv"))
        self.assertIsNone(clasificar_archivo_snapshot("indicadores_encuestas_20261019.csv")) # sin hora
        self.assertIsNone(clasificar_archivo_snapshot("indicadores_encuestas_20261019_125221.parquet")) # parquet

    def test_sistema_congelado_o_pausado_no_toca_nada(self):
        """
        Si el sistema está congelado o pausado y tiene solo 2 snapshots viejos (ej. de hace 30 días),
        NO DEBE BORRAR NINGUNO porque se garantiza el piso mínimo.
        """
        arch1 = self._crear_archivo_simulado("indicadores_encuestas_20260901_100000.csv", dias_antiguedad=30)
        arch2 = self._crear_archivo_simulado("indicadores_encuestas_20260902_100000.csv", dias_antiguedad=29)

        # También crear archivos crudos que jamás deben tocarse
        raw1 = self._crear_archivo_simulado("planificacion_raw.csv", dias_antiguedad=30)
        raw2 = self._crear_archivo_simulado("respuestas_raw.csv", dias_antiguedad=30)

        res = aplicar_retencion_output(
            directorio_output=self.temp_dir,
            dias_retencion=7,
            min_versiones=2,
            dry_run=False,
        )

        self.assertEqual(len(res["archivos_eliminados"]), 0)
        self.assertEqual(len(res["archivos_conservados"]), 2)
        self.assertTrue(os.path.exists(arch1))
        self.assertTrue(os.path.exists(arch2))
        self.assertTrue(os.path.exists(raw1))
        self.assertTrue(os.path.exists(raw2))

    def test_purga_activa_con_archivos_antiguos_excedentes(self):
        """
        Si el sistema sigue generando y hay 4 versiones de una serie:
        - 2 versiones recientes (hace 1 y 2 días).
        - 2 versiones antiguas (hace 10 y 15 días).
        Debe borrar las 2 antiguas y conservar las 2 recientes.
        """
        v_antigua1 = self._crear_archivo_simulado("indicadores_encuestas_20261001_100000.csv", dias_antiguedad=15)
        v_antigua2 = self._crear_archivo_simulado("indicadores_encuestas_20261005_100000.csv", dias_antiguedad=10)
        v_reciente1 = self._crear_archivo_simulado("indicadores_encuestas_20261025_100000.csv", dias_antiguedad=2)
        v_reciente2 = self._crear_archivo_simulado("indicadores_encuestas_20261026_100000.csv", dias_antiguedad=1)

        res = aplicar_retencion_output(
            directorio_output=self.temp_dir,
            dias_retencion=7,
            min_versiones=2,
            dry_run=False,
        )

        self.assertEqual(len(res["archivos_eliminados"]), 2)
        self.assertEqual(len(res["archivos_conservados"]), 2)

        # Verificar en disco
        self.assertFalse(os.path.exists(v_antigua1))
        self.assertFalse(os.path.exists(v_antigua2))
        self.assertTrue(os.path.exists(v_reciente1))
        self.assertTrue(os.path.exists(v_reciente2))

    def test_modo_dry_run_no_elimina_archivos(self):
        """En modo dry-run debe simular y reportar pero NO eliminar archivos del disco."""
        v_antigua = self._crear_archivo_simulado("indicadores_encuestas_20261001_100000.csv", dias_antiguedad=15)
        v_reciente1 = self._crear_archivo_simulado("indicadores_encuestas_20261025_100000.csv", dias_antiguedad=2)
        v_reciente2 = self._crear_archivo_simulado("indicadores_encuestas_20261026_100000.csv", dias_antiguedad=1)

        res = aplicar_retencion_output(
            directorio_output=self.temp_dir,
            dias_retencion=7,
            min_versiones=2,
            dry_run=True,
        )

        self.assertEqual(len(res["archivos_eliminados"]), 1)
        self.assertTrue(os.path.exists(v_antigua), "En dry-run el archivo antiguo debe persistir en disco")


if __name__ == "__main__":
    unittest.main()
