# Limpieza de disco en el servidor 10.20.8.82

**Fecha:** 27/10/2026
**Entornos intervenidos:** Producción (`/home/biocde/streamlit/sistema_relatorios`) y Pruebas (`/home/biocde/streamlit/sistema_relatorios_test`)
**Alcance:** análisis de necesidad de los datos que ocupan disco y eliminación de lo prescindible, sin tocar datos, ETL, consultas ni esquemas.

---

## 1. Situación inicial

| Indicador | Antes |
|---|---|
| Disco raíz | 86 GB, **80 GB usados, 1,7 GB libres (98 %)** |
| `sistema_relatorios` (producción) | 3,6 GB |
| `sistema_relatorios_test` (pruebas) | 4,3 GB |
| `output/` en cada entorno | ~2,8 GB |

El servidor ya había rechazado una corrida del ETL por falta de espacio
(`ERROR: ALUMNO_DOCENTE ... [Errno 28] No space left on device`).

---

## 2. Análisis de necesidad

### 2.1 Snapshots `output/indicadores_encuestas*.csv` — **PRESCINDIBLES**

Cada corrida del ETL escribe tres archivos con marca de tiempo:

| Serie | Archivos en producción | Tamaño unitario |
|---|---|---|
| `indicadores_encuestas_AAAAMMDD_HHMMSS.csv` | 63 | ~65,7 MB |
| `indicadores_encuestas_v2_AAAAMMDD_HHMMSS.csv` | 16 | ~61,8 MB |
| `indicadores_encuestas_docente_autoeval_AAAAMMDD_HHMMSS.csv` | 64 | ~0,26 MB |

Verificación de uso en el código:

- Se **escriben** en `services/etl/encuestas_etl.py` (líneas 1840 y 1938) mediante `df.to_csv(...)`.
- **No se leen en ningún punto**: no hay `read_csv` ni referencia a esos nombres fuera de la escritura (la única mención es un comentario en `modules/etl_resumen.py`).
- El portal consume los datos vigentes desde `assets/data/encuestas/` (`*.csv` + `*.parquet`), que el ETL regenera en cada corrida a partir de la base de datos.
- Conclusión: son **copias históricas de auditoría**, no insumos ni respaldo único. La información es reconstruible desde la base y desde los `*_raw.csv`.

### 2.2 `.venv` local de Pruebas — **PRESCINDIBLE**

- Ocupaba 752 MB y databa del 17/07/2026.
- Los dos servicios systemd y todos los scripts de cron usan el **venv compartido** `/home/biocde/streamlit/.venv/bin/python`.
- Se verificó por `grep` que `sistema_relatorios_test/scripts/*.sh` apuntan explícitamente a `VENV_PYTHON="/home/biocde/streamlit/.venv/bin/python3"`.

### 2.3 `__pycache__` — **PRESCINDIBLE**

Carpetas de bytecode Python (3 MB). Se regeneran solas; el ETL además corre con `PYTHONDONTWRITEBYTECODE=1`.

### 2.4 Datos conservados por ser necesarios

| Elemento | Motivo |
|---|---|
| `output/*_raw.csv` (`respuestas_raw.csv` 88 MB, `respuestas_abiertas_raw.csv` 31 MB, `planificacion_raw.csv` 9,1 MB, `contacto_raw.csv`, `encuesta_raw.csv`, `estructura_encuesta_raw.csv`, `escala_encuesta_raw.csv`, `respuestas_docente_raw_5.csv`, `encuesta_docente_raw_5.csv`) | Insumos del ETL (`offline_*_csv` en `encuesta_runner.py`); se usan durante la generación de indicadores. |
| `assets/data/**` (v1, v2, encuestas, global, temp_years) | Datos vivos que consume el portal. |
| `logs/` | Trazabilidad del ETL y del portal; rotación ya configurada. |
| `asistencias20261` (5,0 GB), `biblioteca` (4,1 GB), `seguimiento_egresados`, `helpdesk_correo*` | Sistemas y procesos ajenos al portal de indicadores (corren por cron propio). No se tocaron. |

---

## 3. Acciones ejecutadas

| Acción | Producción | Pruebas | Total |
|---|---|---|---|
| Snapshots históricos eliminados (se conservaron los **2 más recientes de cada serie**) | 137 archivos · 2,5 GB | 131 archivos · 2,4 GB | **268 archivos · 4,9 GB** |
| `.venv` local sin uso | — | 752 MB | **752 MB** |
| `__pycache__` | 8 carpetas | 8 carpetas | 3 MB |

El detalle exacto de cada archivo eliminado quedó registrado en
`docs/Limpieza_Disco_20261027.txt`.

---

## 4. Estado final verificado

| Indicador | Antes | Después |
|---|---|---|
| Disco raíz | 1,7 GB libres (98 %) | **7,2 GB libres (92 %)** |
| `output/` producción | 2,9 GB | **374 MB** |
| `output/` pruebas | 2,8 GB | **374 MB** |
| `streamlit/` completo | 8,6 GB | **3,1 GB** |

- `streamlit_app.service` (8501): `active` · health **HTTP 200**
- `streamlit_app_test.service` (8502): `active` · health **HTTP 200**
- Datos vivos en `assets/data/encuestas/` intactos (v1, v2 y autoevaluación docente con sus `.csv` y `.parquet`).
- Repositorio del servidor sin cambios: no se modificó código, ETL, consultas ni esquemas.

---

## 5. Hallazgos y pendientes

1. **Crecimiento recurrente:** cada corrida completa del ETL genera ~128 MB de snapshots
   (65,7 + 61,8 + 0,26 MB) y corre 3 veces al día en cada entorno ⇒ **~766 MB/día**.
   Con 7,2 GB libres, el disco se volvería a llenar en **~9 días**.
   *Por decisión del usuario no se automatiza la retención por ahora:* conviene repetir
   esta limpieza manualmente cada 1–2 semanas.
2. **ETL de producción del 27/10 (06:00):** la etapa `ALUMNO_DOCENTE` falló por disco lleno;
   los datos v1/v2 quedaron con fecha 26/10 18:01. La corrida programada de las 12:00
   debería normalizarlos ahora que hay espacio. No se forzó una ejecución manual.
3. **ETL de pruebas del 27/10 (04:00):** falló por timeout de VPN/SQL Server
   (`Login timeout expired`), no por disco. Es un problema de conectividad previo.
4. **Otros candidatos disponibles (no eliminados):** `/home/biocde/.cache/ms-playwright`
   (656 MB) y `/var/log` (~250 MB tras el vaciado del journal a 192 MB).
