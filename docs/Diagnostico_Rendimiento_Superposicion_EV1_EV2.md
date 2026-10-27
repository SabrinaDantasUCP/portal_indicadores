# Diagnóstico: rendimiento y superposición visual en EV1 / EV2

**Fecha:** 26/10/2026  
**Alcance:** página «Análisis de Encuestas» (`encuestas_avance`), instrumentos EV1 y EV2.  
**Estado:** diagnóstico con **Fase 1 aplicada** (rendimiento y estilos). La Fase 2 (separación en páginas) se aplicó y luego **se revirtió** a pedido del usuario: la página única con selector de instrumento vuelve a estar como estaba. Sin cambios en datos, ETL, consultas ni esquemas.

---

## 1. Resumen ejecutivo

Se identificaron dos problemas independientes:

1. **Superposición visual:** al cambiar el instrumento (EV1 ↔ EV2) quedan visibles, durante la transición, controles de la encuesta anterior dentro de la nueva. En la captura del usuario se ve el filtro **«Pregunta (Libres)» de EV1** dentro del panel **«Filtros del Panel EV2»**. Se reprodujo el defecto: es un **fantasma del DOM del navegador**, no una duplicación de datos ni de lógica. El árbol que envía el servidor está limpio; el navegador tarda entre **1 y 2 segundos** en retirar los controles sobrantes.

2. **Lentitud:** el costo principal está en **«Respuestas libres» de EV1**, que genera un Excel de **127.654 filas** consumiendo **~33 s** la primera vez y **cada vez que cambia un filtro**. Además, se envían al navegador **23,6 MB** de tabla y se ejecutan **todas las sub-pestañas** en cada interacción, aunque estén ocultas.

---

## 2. Cómo se midió

- Datos reales: **Ciudad del Este / 2026.1 / Medicina**, instrumentos EV1 y EV2.
- Render medido con `streamlit.testing.v1.AppTest` (contexto real de Streamlit 1.50.0).
- DOM inspeccionado en un servidor local con sesión ADMIN simulada (sin tocar la base).
- Se cronometró cada sub-vista por separado y se midió el tamaño Arrow de la tabla.

---

## 3. Superposición visual (confirmada)

### 3.1 Evidencia

Con el flujo real (`modules/encuestas.py` → `render()`), al pasar de EV1 a EV2 se muestreó el DOM cada 200 ms:

| Momento | Filtros en el panel EV2 | Pestañas visibles |
|---|---|---|
| 0,2 s | **6** (incluye «Pregunta (Libres)» de EV1) | **8** (incluye la 8.ª de EV1) |
| 2,2 s | 5 (correcto) | 7 (correcto) |

El árbol del **servidor** ya está correcto en el mismo instante: `AppTest` devuelve para EV2 solo 5 filtros propios y 7 pestañas, sin rastros de EV1. Por lo tanto, **no hay datos ni widgets de EV1 renderizados por error**; es el navegador el que conserva nodos viejos mientras aplica el nuevo árbol.

### 3.2 Causa técnica

Streamlit reutiliza el mismo componente de **pestañas** y de **columnas** porque ocupan la misma posición en la página:

- EV1: `st.expander("Filtros del Panel EV1")` + `st.columns(6)` + `st.tabs([8 pestañas])`.
- EV2: `st.expander("Filtros del Panel EV2")` + `st.columns([2.2, 2.2, 1.1, 1.3, 1.3])` (5 columnas) + `st.tabs([7 pestañas])`.

Al reducirse la cantidad de columnas (6 → 5) y de pestañas (8 → 7), React retira los hijos sobrantes **un instante después** de pintar los nuevos. En ese intervalo se ve el filtro y la pestaña de la encuesta anterior. En equipos lentos o con mucha carga ese intervalo se percibe más.

Referencias:
- `modules/encuestas_ev1.py` líneas 460–481 (expander + 6 columnas + «Pregunta (Libres)»).
- `modules/encuestas_ev2.py` líneas 2880–2925 (expander + 5 columnas).
- `modules/encuestas_ev1.py` líneas 532–543 (8 pestañas).
- `modules/encuestas_ev2.py` líneas 2942–2952 (7 pestañas).

### 3.3 Superposición secundaria detectada

`render_common_setup()` (en `modules/encuestas.py`, líneas 73–107) y `render_ev1_opinion_estudiante()` (en `encuestas_ev1.py`, líneas 349–361) vuelven a definir:

```css
header[data-testid="stHeader"] { height: 2rem !important; }
.block-container { padding-top: 1.5rem !important; }
```

Esto **deshace la eliminación de la franja superior** que ya se había logrado en `app.py` (header a 0). Medido en el navegador: el header vuelve a ocupar **32 px** con `z-index: 999990` y el contenido arranca a **24 px**, por lo que el header se superpone a la parte superior del contenido. No es la causa de la captura, pero es una superposición real y conviene corregirla junto con lo anterior.

---

## 4. Rendimiento

### 4.1 Tiempos medidos (EV1)

| Sub-vista | Primera carga | Carga en caliente |
|---|---:|---:|
| Respuestas libres | **26,87 s** | 1,19 s |
| Por docente | 1,65 s | 1,25 s |
| Avance general | 1,42 s | 0,15 s |
| Análisis pedagógico | 1,23 s | 1,14 s |
| Participación de alumnos | 1,13 s | 0,90 s |
| Respuestas EV1 | 0,65 s | 0,62 s |
| Guía metodológica | 0,11 s | 0,05 s |
| **Total del render** | **36,05 s** | **6,83 s** |

### 4.2 Tiempos medidos (EV2)

| Medición | Tiempo |
|---|---:|
| Primera carga | 2,10 s |
| Carga en caliente | 0,78 s |

EV2 no tiene el problema del Excel; su lentitud percibida proviene sobre todo del cambio de instrumento y de que se ejecutan sus 7 pestañas en cada rerun.

### 4.3 Causas concretas

1. **Excel de respuestas libres (la causa principal).**
   - `load_respuestas_libres` devuelve **127.654 filas**.
   - `_generar_excel_respuestas_libres` (`encuestas_ev1.py`, líneas 1946–2089) escribe **celda por celda** con formato individual (≈766.000 escrituras). Medición aislada: **32,89 s** en frío y **3,6 MB** de archivo.
   - Está decorada con `@st.cache_data`, pero la clave incluye el DataFrame filtrado: **cada cambio de filtro genera un Excel nuevo** y vuelve a costar ~33 s.
   - Se ejecuta aunque el usuario esté en otra pestaña, porque `st.tabs` ejecuta el contenido de todas.

2. **Tabla completa enviada al navegador.**
   - `st.dataframe(df_presentar)` en «Respuestas libres» envía **23,6 MB** (Arrow IPC) de 127.654 filas en cada render. Esto explica la lentitud del navegador y el consumo de memoria, y alarga la transición donde se ve el fantasma.

3. **Todas las pestañas se ejecutan siempre.**
   - EV1 (8 pestañas) y EV2 (7 pestañas) calculan todas sus sub-vistas en cada interacción, incluidas las ocultas. En caliente, EV1 tarda ~6,8 s por rerun.

4. **`importlib.reload` de EV2.**
   - `modules/encuestas.py` líneas 278–281 recarga el módulo de 147 KB en cada render de EV2. Medido: **~0,002 s** (no es el cuello de botella), pero es innecesario y reinicia el estado de módulo y sus cachés. **No es la causa del fantasma** (se probó desactivándolo y el fantasma persistió).

5. **Carga de parquet.**
   - `load_encuestas_detalle` = 0,41 s; `load_respuestas_libres` = 0,78 s. No es el problema principal y ya está cacheada por archivo + fecha de modificación.

---

## 5. Matriz de riesgos de las correcciones propuestas

| # | Corrección | Impacto esperado | Riesgo | Motivo |
|---|---|---|---|---|
| P1 | Quitar `importlib.reload` de EV2 | Bajo (limpieza) | **Bajo** | No altera datos ni UI; evita recargas y reinicios de caché |
| P2 | Optimizar el Excel (escritura por lotes/tabla en lugar de celda por celda) | Muy alto: ~33 s → ~2 s | **Bajo/medio** | El archivo debe conservar el mismo formato; requiere validar el resultado |
| P3 | Generar el Excel solo al pulsar un botón | Muy alto | **Medio** | Cambia la UX (un clic extra); no rompe datos |
| P4 | Paginar también la «Tabla Estructurada» (mostrar solo la página actual; descargas con todo) | Alto: elimina 23,6 MB por render | **Medio** | Cambia lo que se ve en pantalla; las descargas siguen completas |
| P5 | Quitar las reglas globales de `header` y `.block-container` de encuestas | Medio: elimina el solapamiento superior de 32 px | **Bajo** | Cambia levemente el espacio superior de Encuestas, alineándolo con el resto del portal |
| P6 | Igualar la cantidad de pestañas/columnas entre EV1 y EV2 | Medio: elimina el fantasma | **Medio** | Requiere decisión de producto (nueva pestaña o mover «Pregunta (Libres)») |
| P7 | Separar EV1 y EV2 en páginas/rutas distintas | Alto: sin fantasma y solo se renderiza una encuesta | **Medio/alto** | Reestructura la navegación y el selector de instrumento |
| P8 | Sustituir `st.tabs` por un control segmentado que renderice solo la vista activa | Muy alto: menos tiempo y sin fantasma | **Alto** | Cambia la UX de navegación y exige tocar las 8 + 7 sub-vistas |
| P9 | Forzar recarga del navegador al cambiar de instrumento | Elimina el fantasma | **No recomendado** | Una recarga real pierde la sesión (login) |

**No hacer:** cambiar datos, ETL, consultas, esquemas ni keys de widgets. Ninguna de las propuestas anteriores lo requiere.

---

## 6. Plan recomendado (por fases, sin romper nada)

### Fase 1 — Bajo riesgo, alto beneficio
1. Quitar `importlib.reload` de EV2 (P1).
2. Optimizar `_generar_excel_respuestas_libres` manteniendo el mismo formato visual (P2). Validar con un archivo de prueba antes/después.
3. Quitar las reglas duplicadas de `header` y `.block-container` de encuestas (P5). Verificar que el encabezado azul y los filtros queden bien en EV1 y EV2.

### Fase 2 — Resolver la superposición
4. Igualar la estructura (P6): la opción menos invasiva es **mover «Pregunta (Libres)» a la sub-pestaña «Respuestas libres»** (donde pertenece), dejando 5 columnas en EV1 y EV2, y **agregar una 8.ª pestaña real a EV2** (por definir: «Referencias», «Glosario» o similar). Con eso, el navegador no tiene que retirar hijos al cambiar de instrumento.
   - Alternativa más limpia a mediano plazo: separar EV1 y EV2 en rutas distintas (P7).

### Fase 3 — Rendimiento del navegador
5. Paginar la tabla estructurada (P4), manteniendo las descargas con el total.
6. Evaluar caché por filtros en las sub-vistas más costosas («Por docente», «Análisis pedagógico»).

---

## 7. Verificación realizada

- `AppTest` del flujo real: tras cambiar a EV2, el servidor reporta 7 pestañas y los filtros Docente/Materia/Sección/Grupo/Estado (+ Dimensión/Criterio de la guía). **Sin rastros de EV1.**
- Navegador: el fantasma aparece y desaparece solo en 1–2 s; se confirmó que no persiste ni corrompe el estado.
- Copias temporales de prueba eliminadas; servidores locales detenidos.
- **Sin commit, sin push y sin despliegue.**

---

## 8. Conclusión

La superposición **no es un error de datos**: es el resultado de que Streamlit reutiliza pestañas y columnas con distinta cantidad entre EV1 y EV2. La lentitud sí es real y tiene una causa dominante muy clara: el Excel de 127.654 filas que se regenera con cada filtro, sumado al envío de 23,6 MB de tabla al navegador y a la ejecución de todas las pestañas.

Las correcciones de Fase 1 son de bajo riesgo y no tocan lógica ni datos. La superposición se resuelve de forma estable igualando la estructura o separando las encuestas en rutas distintas.

---

## 9. Anexo: cambios aplicados

**Fecha de aplicación:** 26/10/2026. Sin cambios en datos, ETL, consultas ni esquemas. Sin commit, push ni despliegue.

### 9.1 Fase 1 — rendimiento y estilos (vigente)

| Archivo | Cambio | Propósito |
|---|---|---|
| `modules/encuestas_ev1.py` | `_generar_excel_respuestas_libres` ahora crea la hoja con `workbook.add_worksheet`, escribe con `write_row` y aplica formato de **fila** (`set_row`), usando formato de celda solo en `SECCIÓN` y `GRUPO`. | Eliminar ~766.000 escrituras con estilo. Medición con 127.654 filas: **32,9 s → 8,9–12,4 s**. |
| `modules/encuestas.py`, `modules/encuestas_ev1.py` | Se quitaron las reglas `header[data-testid="stHeader"]` y `.block-container` de los bloques `<style>` de encuestas. | El encabezado y el espaciado superior quedan bajo el control único de `app.py`; desaparece la superposición de 32 px sobre el contenido. |

**Validación del Excel:** hoja `Respuestas Libres EV1`, rango `A1:F127657`, título combinado en la fila 1, encabezados azules con texto blanco en la fila 3, cebra por fila, bordes y `wrap_text`, `SECCIÓN`/`GRUPO` centrados, autofiltro `A3:F127657`, panel congelado en `A4`, anchos por columna y altos de fila calculados. Formato equivalente al anterior.

### 9.2 Fase 2 — separación en páginas (REVERTIDA)

La separación de EV1 y EV2 en páginas independientes se aplicó y luego **se revirtió a pedido del usuario**, que prefiere conservar la página única con el selector de **Instrumento** y el menú original. Estado actual:

- `utils/menu_config.py`: el grupo «Instrumentos de Evaluación Docente» vuelve a tener «Análisis de Encuestas» (`/encuestas_avance`) e «Indicadores». Se eliminó `PAGINAS_HEREDADAS`.
- `modules/encuestas.py`: se restauraron `render()`, `_render_cobertura()` y `render_autoeval_docente()` tal como estaban; se eliminaron `render_ev1_pagina()`, `render_ev2_pagina()`, `select_encuesta_contexto()`, `_instrumento_disponible()`, `_recordar_contexto()`, `_restaurar_contexto()`, `_al_cambiar_sede()` y `_al_cambiar_periodo()`.
- `app.py`: el pie de página vuelve a calcular la fecha solo para `encuestas_avance`.
- `select_encuesta()` conserva el formulario 2×2 original: Sede / Periodo y Carrera / Instrumento, sin espacios vacíos.

**Consecuencia asumida:** el «fantasma» visual al cambiar de instrumento (1–2 s) vuelve a aparecer, porque Streamlit reutiliza las pestañas y columnas al pasar de 8/6 (EV1) a 7/5 (EV2). Es un efecto transitorio del DOM, no un error de datos.

### 9.3 Verificación posterior

- `python -m py_compile modules/encuestas.py modules/encuestas_ev1.py utils/menu_config.py app.py` → **OK**.
- Menú lateral: «Análisis de Encuestas» e «Indicadores» bajo «Instrumentos de Evaluación Docente».
- Selector de la página: **Sede, Periodo, Carrera e Instrumento** (grilla 2×2, sin hueco).
- EV1: 4 selectores comunes + 6 filtros del panel, **8 pestañas**; EV2: 4 comunes + 5 filtros, **7 pestañas**. Sin excepciones.
- Encabezado del portal: `header` a **0 px** y contenido a **16 px**; se mantiene la corrección de Fase 1.
- UTF-8 sin BOM en los archivos intervenidos.
