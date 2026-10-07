# Portal de Indicadores

Aplicación Streamlit que centraliza los indicadores académicos de la
universidad (ANEAES v1/v2, permanencia, eficiencia terminal, matrículas,
notas, asistencias, encuestas, autoevaluación docente, etc.), consumiendo
datos desde MySQL, PostgreSQL y SQL Server (ERP), con exportación a Excel y
un módulo de administración (usuarios, áreas, logs, configuración del ETL de
encuestas).

## Arquitectura

```
app.py                     # punto de entrada Streamlit, layout y menú
modules/                   # una página/vista por módulo (renderiza UI)
services/
  calculations/            # reglas de negocio / cálculo de cada indicador
  data/                    # acceso a datos (queries, DuckDB, datasets)
  etl/                     # ETL de encuestas (runner, VPN, extracción SQL Server)
utils/                     # conexión a BD, configuración de menú, logging, exportación
scripts/                   # ETL por CLI, conversión CSV→Parquet, control de VPN, cron
assets/                    # logos e datasets estáticos/generados (assets/data/)
```

- **Datos**: MySQL (académico, permanencia), PostgreSQL (`pia_*`, config del
  ETL de encuestas), SQL Server local (histórico) y SQL Server del ERP vía
  VPN PPTP (encuestas).
- **Indicadores v1/v2**: dos versiones de la metodología ANEAES conviven en
  el mismo menú (`utils/menu_config.py`, `VERSION_GROUPS`); los módulos
  filtran por versión y por alumnos activos.
- **Encuestas**: `modules/encuestas.py` (visualización) +
  `modules/encuestas_config_etl.py` (admin: configurar y disparar el ETL) +
  `services/etl/` (extracción real desde el ERP) + `scripts/run_etl_cron.py`
  (job que corre por cron, ver más abajo).

## Configuración (`.env`)

No versionado (`.gitignore`). Variables principales:

- `MYSQL_*_BICDE` / `MYSQL_*_PIA` / `MYSQL_*_SYS` — conexiones MySQL.
- `PG_*` — PostgreSQL (config y resultados del ETL de encuestas).
- `SQLSRV_*` — SQL Server local.
- `SQLSRV_ERP_*` — SQL Server del ERP, accesible solo a través de la VPN.
- `VPN_SERVER`, `VPN_USER`, `VPN_PASSWORD` — credenciales de la VPN PPTP
  hacia el ERP, usadas por `scripts/vpn_ctl.sh`.

Si falta cualquiera de estas claves, el ETL de encuestas falla con un
mensaje explícito indicando qué falta (no se cuelga ni pide una contraseña
interactiva).

## Test vs. Producción

El proyecto vive en **dos carpetas independientes** en el mismo servidor,
cada una con su propio checkout de git, su propio `.env` y su propio
servicio systemd. No hay symlinks ni carpetas compartidas entre ambas.

| | Test | Producción |
|---|---|---|
| Carpeta | `/home/biocde/streamlit/sistema_relatorios_test/` | `/home/biocde/streamlit/sistema_relatorios/` |
| Branch git | `teste` (sigue a `origin/main`) | `main` |
| Servicio systemd | `streamlit_app_test.service` | `streamlit_app.service` |
| Puerto | `8502` | `8501` (default) |
| Cron ETL encuestas | `0 4,11,17 * * *` | `0 6,12,18 * * *` |

Los horarios de cron están escalonados a propósito para que test y
producción nunca abran la VPN PPTP hacia el ERP al mismo tiempo (y para no
coincidir con el cron `0 5 * * *` de `migracion-syseduca-erp`, que usa su
propia VPN independiente).

El flujo de trabajo es: se desarrolla y se prueba en `sistema_relatorios_test`
(branch `teste`), se sube a GitHub, y solo después se actualiza
`sistema_relatorios` (producción) desde el mismo remoto.

### VPN PPTP hacia el ERP

`scripts/vpn_ctl.sh connect|disconnect` es el único punto que conecta o
corta la VPN PPTP. Se invoca de dos formas:

1. Como root, desde `scripts/run_etl_cron.sh` (cron).
2. Vía `sudo -n` desde el proceso Streamlit (usuario normal), cuando el
   admin usa el botón "Ejecutar ahora" en `modules/encuestas_config_etl.py`.

Para el caso 2 hace falta una regla en `/etc/sudoers.d/` que autorice,
**sin contraseña**, exactamente ese script con exactamente esos dos
argumentos — ver `scripts/encuestas_vpn.sudoers.example`. Esa regla incluye
las rutas de **ambos** entornos (test y producción), porque los dos pueden
necesitar conectar la VPN.

Instalación/actualización de la regla (requiere sudo interactivo, una sola
vez por servidor o cada vez que cambien las rutas del proyecto):

```bash
sudo cp scripts/encuestas_vpn.sudoers.example /etc/sudoers.d/encuestas_vpn
sudo chmod 440 /etc/sudoers.d/encuestas_vpn
sudo visudo -c
```

## Actualizar población de alumnos activos

La Versión 2 de Alumnos, Asistencias y Encuestas (Alumno→Docente) se filtra
por una **población oficial de alumnos activos** que se cierra **fuera del
portal**. El portal no recalcula criterios, notas, recortes ni cohortes:
solo consume la lista (`services/etl/activos_ids.py`,
`services/etl/activos_criterios_runner.py`, pantalla admin "Alumnos
Activos").

1. **Generar la población (fuera del portal).** Correr
   `etl_unico_activos_2018_2_2026_1.py` y después
   `consolidar_max2_recursantes.py`, que producen el consolidado "Alumnos
   Reales Max 2 Recursantes" (hojas `Alumnos`, `Matriz`, `Excluidos`).
   Responsable / dónde se corre: _completar (equipo de BI, carpeta
   `analisis_general/...` del OneDrive)_.
2. **Exportar.** Guardar la hoja `Alumnos` como CSV (separador `;`, `,` o
   tab; UTF-8 o Latin-1) o usar el `.xlsx` directo (se lee la hoja
   `Alumnos`). Columnas: `Año, Periodo, Catraca, ID Usuario, Nombre,
   Doc. Oficial, Semestre, Sección, Motivo`.
3. **Subir al portal.** Pantalla admin **Alumnos Activos** → sección
   "Población de alumnos activos (CSV)": subir el archivo, conferir en la
   vista previa los totales por periodo (filas, alumnos únicos, filas sin
   sección) y hacer clic en **Guardar población**. Se graba en
   `assets/data/global/alumnos_activos_poblacion.csv`.
4. **ETL de activos.** **Ejecutar ahora** en la misma pantalla (o esperar el
   cron `scripts/run_activos_criterios_etl_cron.sh`, que corre antes que los
   demás). Filtra la población por los "Periodos a incluir" y regenera
   `usuarios_activos_ids.txt` y `usuarios_activos_periodos.csv`. Los avisos
   (periodos del CSV ignorados / periodos configurados sin alumnos) quedan
   en "Última ejecución".
5. **Regenerar la v2.** Correr los ETL de **Alumnos**, **Asistencias** y
   **Encuestas** (pantallas de admin de cada uno o sus crons).
6. **Validar.**

   ```bash
   python scripts/validar_poblacion_activos.py "ruta/al/consolidado.xlsx"
   ```

   Compara contra el consolidado: totales por periodo, IDs repetidos, cupo
   de 95 por sección (sem. 1-10 desde 2021.1), hoja `Matriz`, hoja
   `Excluidos`, pares alumno-periodo y `alumnos_v2` (lista los alumnos de la
   población sin `periodo_letivo` en la base del portal). Solo lectura. Con
   `--poblacion-archivo <archivo>` valida un archivo antes de subirlo; con
   `--periodos 2018.2-2026.1` evita consultar la configuración en la base
   "pia". Prueba unitaria rápida (no toca `assets/data`):
   `python scripts/test_poblacion_activos.py`.

**Deploy de cambios en este flujo** (mismo protocolo de `GEMINI.md`):

1. Desarrollar en la branch personal (`sabrina-dev`), con `origin/teste` ya
   integrado, y validar localmente (`python -m py_compile`,
   `python scripts/test_poblacion_activos.py`).
2. `git push origin sabrina-dev` e integrar los commits aprobados en `teste`
   (`git push origin teste`).
3. En el servidor de test (`/home/biocde/streamlit/sistema_relatorios_test`):
   `git pull origin teste`, `sudo systemctl restart streamlit_app_test.service`
   y verificar `http://10.20.8.82:8502/_stcore/health` (200 OK).
4. En test, hacer los pasos 1-6 de arriba con la población real y confirmar
   `validar_poblacion_activos.py` sin FALLA.
5. Solo con la validación OK, promover a producción siguiendo
   [Actualizar el servidor](#actualizar-el-servidor).

**No hacer deploy en producción antes de validar en test.** La población
(`assets/data/` no está versionado) se sube por separado en cada entorno
desde la pantalla de admin.

## Actualizar el servidor

Pasos para llevar un cambio de `sistema_relatorios_test` a producción:

```bash
# 1. En el checkout de test: subir los cambios a GitHub
cd /home/biocde/streamlit/sistema_relatorios_test
git push origin teste:main

# 2. En el checkout de producción: traer los cambios
cd /home/biocde/streamlit/sistema_relatorios
git pull
```

### 1. Test

**1.1 Verificar el estado del servicio (Test)**

```bash
sudo systemctl status streamlit_app_test.service
```

**1.2 Reiniciar el servicio (Test)**

Una vez subidos los archivos, se debe reiniciar el servicio para que el
Portal de Indicadores cargue los datos actualizados.

```bash
sudo systemctl restart streamlit_app_test.service
```

### 2. Producción

**2.1 Verificar el estado del servicio (Producción)**

Se verifica el estado del servicio de producción antes de reiniciarlo, para
confirmar que todo esté en orden.

```bash
sudo systemctl status streamlit_app.service
```

**2.2 Reiniciar el servicio (Producción)**

Finalmente, se reinicia el servicio de producción para que los cambios sean
visibles para todos los usuarios finales.

```bash
sudo systemctl restart streamlit_app.service
```

> Si el cambio agrega variables nuevas al `.env` (por ejemplo, credenciales
> de una integración nueva) o modifica la regla de sudoers de la VPN, esos
> dos archivos **no se actualizan solos con `git pull`** — hay que
> replicarlos manualmente en producción (el `.env` no está versionado por
> seguridad, y la regla sudoers vive fuera del repo, en `/etc/sudoers.d/`).
