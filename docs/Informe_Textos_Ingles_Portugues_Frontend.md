# Informe de textos en inglés y portugués del frontend

**Portal de Indicadores Académicos**
Fecha del análisis: 26/10/2026
Alcance: `app.py`, 36 módulos de `modules/`, 8 utilidades de `utils/`, 21 `@st.dialog` y 2 `st.popover`.
Estado: **solo análisis**. No se modificó código en esta etapa.

---

## 1. Objetivo y decisiones acordadas

Este documento inventaría todo el texto visible del frontend que está en inglés o portugués, indica dónde aparece (módulo, pantalla, modal) y propone la corrección en español.

Decisiones tomadas con el usuario:

1. **`Trancado` / `trancada` se mantiene tal cual.** Es terminología institucional aceptada; **no debe cambiarse**. Queda documentado en la sección 6.1 para que futuras revisiones no lo "corrijan" por error.
2. **`Turma` significa `Sección`.** Se reemplaza en la interfaz por `Sección`, manteniendo intacta la columna interna `turma`.
3. No se modifican nombres internos de columnas, claves de sesión, valores de base de datos ni lógica de negocio. Las traducciones son de **presentación**.

---

## 2. Metodología

Se extrajeron las cadenas de texto que llegan a la interfaz desde:

- Etiquetas de widgets (`label`), `help=`, `placeholder=`.
- `st.markdown`, `st.caption`, `st.info`, `st.warning`, `st.error`, `st.success`.
- Títulos de pestañas, expanders, `st.metric`, leyendas y anotaciones de gráficos.
- Cuerpos de los 21 modales (`@st.dialog`) y 2 popovers.
- Nombres de archivo de las exportaciones PDF/Excel.

Se excluyeron comentarios, docstrings, nombres de columnas, claves de `session_state`, iconos `:material/*`, CSS, SQL y logs de consola.

> **Alcance de la verificación:** el análisis es **estático sobre el código local**, no una navegación de la instancia desplegada en `10.20.8.82:8502`. Se consideró "visible" todo texto que Streamlit renderiza en pantalla, en un tooltip, en un modal o en un archivo descargado. Los textos que solo aparecen en casos de error, en pantallas de ADMIN, en tooltips o dentro de archivos exportados se detallan en el **Anexo E**.

Además se revisaron los **placeholders por defecto de Streamlit**, que no están escritos en el código pero se renderizan en inglés. Se verificó el comportamiento en la versión instalada (`streamlit 1.50.0`):

- `selectbox.py:355-368`: sin `placeholder`, con opciones disponibles muestra **"Choose an option"**.
- `multiselect.py:321-334`: sin `placeholder`, con opciones disponibles muestra **"Choose options"**.
- Con lista de opciones vacía muestra **"No options to select"**.
- Con `accept_new_options=True` muestra **"Choose or add options"**.
- `st.file_uploader` muestra **"Drag and drop file here"**, **"Browse files"** y **"Limit 200MB per file"** (textos del bundle del frontend, sin parámetro oficial para cambiarlos).

---

## 3. Resumen ejecutivo

| Categoría | Cantidad | Estado |
|---|---|---|
| Textos escritos en el código (inglés/portugués) | 47 ubicaciones en 17 archivos | A corregir |
| `Trancado` / `trancada` | 8 bloques (10 apariciones) | **Aceptado, sin cambio** |
| Placeholders escritos en el código | 37 | Correctos, todos en español |
| Placeholders por defecto de Streamlit | 43 widgets | A corregir |
| `st.file_uploader` | 3 | Texto en inglés no configurable |
| **Total inventariado** | **93 puntos** | |

Prioridad global:

- **Alta:** portugués visible y palabras inglesas en etiquetas principales (`Início`, `Turma`, `Dados_`, `Cadastre`, `LEITURA`, `Email (Login)`, `Dashboard`, `Logs`, `Status`, `pipeline`).
- **Media:** anglicismos técnicos en ayudas y captions (`cron`, `dataset`, `dashboard`).
- **Baja:** abreviaturas aceptadas (`N/A`, `Id`).

---

## 4. Inventario por módulo, pantalla o modal

### 4.1 Login y navegación general

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `app.py:115` | PT | `st.Page(page_home, title="Início", ...)` | `title="Inicio"` (consistencia; no se ve en la barra lateral porque `st.navigation` usa `position="hidden"`) | Baja |
| `app.py:80` | PT | `"O módulo '{module.__name__}' foi carregado, mas não possui a função 'render()'."` | `"El módulo '{module.__name__}' se cargó, pero no tiene la función 'render()'."` (solo si falla la importación de un módulo) | Baja |

> El resto del login (`Correo Electrónico`, `Contraseña`, `Entrar`) y de la barra lateral (`Cuenta`, `Cambiar Contraseña`, `Cerrar`) está en español.

---

### 4.2 Administración → Gestión de Usuarios

Afecta al listado y a los modales **"Crear Nuevo Usuario"**, **"Editar Información de Usuario"** y **"Cambiar Contraseña Manualmente"**.

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `modules/admin_usuarios.py:88` | EN | `"Email (Login) *"` | `"Correo (Usuario) *"` | Alta |
| `modules/admin_usuarios.py:108` | EN | `"...ya exista el Email o Documento en la base de datos."` | `"...ya exista el correo o el documento en la base de datos."` | Alta |
| `modules/admin_usuarios.py:117` | EN | `st.text_input("Email", ...)` | `"Correo electrónico"` | Alta |
| `modules/admin_usuarios.py:203` | EN | Cabecera `Nombre y Email` | `Nombre y Correo` | Alta |
| `modules/admin_usuarios.py:90` y `127` | PT + EN | `st.selectbox("Rol", ["LEITURA", "ADMIN"])` | Mantener los valores y mostrar `Lectura` / `Administrador` con `format_func` | Alta |
| `modules/admin_usuarios.py:216` | PT + EN | `{u['rol']}` muestra `LEITURA` o `ADMIN` | Mapear a `Lectura` / `Administrador` solo al mostrar | Alta |

**Cómo traducir el rol sin tocar la base de datos:**

```python
# El valor interno sigue siendo LEITURA o ADMIN; solo cambia lo que se ve.
ETIQUETAS_ROL = {"LEITURA": "Lectura", "ADMIN": "Administrador"}

f_rol = st.selectbox(
    "Rol",
    ["LEITURA", "ADMIN"],
    format_func=lambda rol: ETIQUETAS_ROL.get(rol, rol),
)
```

En la tabla del listado:

```python
rol_visible = ETIQUETAS_ROL.get(u["rol"], u["rol"])
```

> `LEITURA` es un `ENUM` de la base (`utils/db_pia.py:110`). **No se recomienda cambiarlo en la BD.**

---

### 4.3 Administración → Logs y Auditoría

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `utils/menu_config.py:139` | EN | Menú: `"Logs y Auditoría"` | `"Registros y Auditoría"` | Alta |
| `modules/admin_logs.py:12` | EN | `st.subheader("Logs y Auditoría")` | `"Registros y Auditoría"` | Alta |
| `modules/admin_logs.py:131` | EN | `fillna("sin email")` | `fillna("sin correo")` | Alta |
| `modules/admin_logs.py:135` y `139` | EN | `fillna("N/A")` | `"No disponible"` o `"—"` | Baja |

---

### 4.4 Configuración ETL

#### 4.4.1 Alumnos Activos — `modules/activos_config_etl.py`

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:235` | EN | `(o esperar el cron)` | `(o esperar la actualización automática)` | Media |
| `:442` | EN | `"Actualización automática (cron diario, antes que Alumnos/Asistencias/Encuestas)"` | `"Actualización automática (diaria, antes que Alumnos/Asistencias/Encuestas)"` | Media |
| `:444` | EN | `"...el cron nocturno no ejecuta el ETL..."` | `"...la actualización automática nocturna no ejecuta el ETL..."` | Media |
| `:472` | EN | `"(otra pestaña/sesión, o el cron)"` | `"(otra pestaña/sesión, o la actualización automática)"` | Media |

#### 4.4.2 Alumnos — `modules/alumnos_config_etl.py`

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:238` | EN | `"El cron nocturno (**04:00**) corre automáticamente..."` | `"La actualización automática nocturna (**04:00**) se ejecuta automáticamente..."` | Media |
| `:285` | EN | `"Actualización automática (cron diario 04:00)"` | `"Actualización automática (diaria, 04:00)"` | Media |
| `:287` | EN | `"...siguen visibles en el dashboard."` | `"...siguen visibles en el panel."` | Media |

#### 4.4.3 Asistencias — `modules/asistencias_config_etl.py`

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:291` | EN | `"Actualización automática (cron diario 03:00)"` | `"Actualización automática (diaria, 03:00)"` | Media |
| `:293` | EN | `"...siguen visibles en el dashboard."` | `"...siguen visibles en el panel."` | Media |
| `:320` | EN | `"(otra pestaña/sesión, o el cron nocturno)"` | `"(otra pestaña/sesión, o la actualización automática nocturna)"` | Media |

#### 4.4.4 Encuestas — `modules/encuestas_config_etl.py`

Afecta a los modales **"Nueva Configuración de ETL de Encuesta"** y **"Editar Configuración de ETL de Encuesta"**.

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:84` | EN | `"El pipeline de 'Evaluación de Pares'..."` | `"El flujo de procesamiento de 'Evaluación de Pares'..."` | Alta |
| `:85` | PT | `"...Puede cadastrar la configuración..."` | `"...Puede registrar la configuración..."` | Alta |
| `:89` | PT | `"Cadastre qué tipo de encuesta..."` | `"Registre qué tipo de encuesta..."` | Alta |
| `:99` y `:146` | EN | `"Nombre del dataset (identificador interno)"` | `"Nombre del conjunto de datos (identificador interno)"` | Alta |
| `:125` | EN | `"...o el dataset_name ya está en uso."` | `"...o el nombre del conjunto ya está en uso."` | Alta |
| `:168` | EN | `"...posiblemente el dataset_name ya está en uso..."` | `"...posiblemente el nombre del conjunto ya está en uso..."` | Alta |
| `:196` | EN | `"(cron 3x al día)"` | `"(3 veces al día)"` | Media |
| `:241` | EN | `"Id encuesta: ... · dataset: \`...\`"` | `"ID de encuesta: ... · conjunto: \`...\`"` | Alta |
| `:259` | EN | `"...no se ejecuta en el cron 3x al día... dashboard."` | `"...no se ejecuta 3 veces al día... panel."` | Media |
| `:94` | EN | `"Id de la Encuesta (Academico.Encuesta) *"` | `"ID de la Encuesta (Academico.Encuesta) *"` | Baja |

> `Academico.Encuesta` es el nombre de una tabla de origen. Si se quiere evitar tecnicismos en la UI, puede quedar como `"ID de la Encuesta *"` y mover la referencia a la tabla al `help`.

#### 4.4.5 Índice de Permanencia — `modules/permanencia_config_etl.py`

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:214` y `:256` | EN | `"Actualización automática (cron 03:30)"` | `"Actualización automática (diaria, 03:30)"` | Media |

---

### 4.5 Indicadores

#### 4.5.1 Matrículas — `modules/matriculas.py`

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:77` | PT | `col5.multiselect("Turma", turma_vals)` | `col5.multiselect("Sección", turma_vals, placeholder="Todas")` | Alta |
| `:185` | PT | PDF: `Turma: ...` | `Sección: ...` | Alta |

> La columna interna sigue siendo `turma`; solo cambia la etiqueta visible y el texto del PDF.

#### 4.5.2 Eficiencia Terminal — `modules/eficiencia_terminal.py`

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:300` | PT | `file_name="Dados_ET_Comparativo.xlsx"` | `"Datos_ET_Comparativo.xlsx"` | Alta |
| `:395` | PT | `file_name=f"Dados_ET_{cohorte_sel}.xlsx"` | `f"Datos_ET_{cohorte_sel}.xlsx"` | Alta |

#### 4.5.3 Eficiencia de Titulación — `modules/eficiencia_titulacion.py`

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:248` | EN | `multiselect("Filtrar por Status de Titulación", ...)` | `"Filtrar por Estado de Titulación"` | Alta |

#### 4.5.4 Rendimiento Académico → Estudiante — `modules/rend_acad_alumno.py`

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:766` | PT | `file_name=f"Dados_{catraca_num}_{fecha}.xlsx"` | `f"Datos_{catraca_num}_{fecha}.xlsx"` | Alta |
| `:200` y `:208` | EN | `"N/A"` → se muestra `Sede: N/A` | `"No disponible"` o `"—"` | Baja |

> `Trancado` en este módulo (`:121`) **se mantiene** por decisión del usuario (ver sección 6.1).

#### 4.5.5 Tasa de Retención — `modules/tasa_retencion.py`

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `:112` | EN | Celda de tabla: `"N/A"` | `"No disponible"` o `"—"` | Baja |

---

### 4.6 Encuestas EV1 / EV2

| Ubicación | Idioma | Texto actual | Sugerencia | Prioridad |
|---|---|---|---|---|
| `modules/encuestas_ev1.py:460` | EN | `st.expander("Filtros del Dashboard EV1", ...)` | `"Filtros del Panel EV1"` | Alta |
| `modules/encuestas_ev2.py:2880` | EN | `st.expander("Filtros del Dashboard EV2", ...)` | `"Filtros del Panel EV2"` | Alta |
| `modules/encuestas.py:529` | EN | `"No se encontró la fila \`resultado_general\` en el dataset."` | `"...en el conjunto de datos."` | Alta |

> `NENHUM`, `NENHUMA` y `SEM COMENTARIOS` (`modules/encuestas_ev1.py:2186`) son una lista interna de filtro y **no se muestran** en pantalla. No requieren cambio.

---

### 4.7 Exportaciones (resumen de nombres de archivo)

| Archivo | Origen | Nombre actual | Sugerencia |
|---|---|---|---|
| `modules/eficiencia_terminal.py:300` | PT | `Dados_ET_Comparativo.xlsx` | `Datos_ET_Comparativo.xlsx` |
| `modules/eficiencia_terminal.py:395` | PT | `Dados_ET_{cohorte}.xlsx` | `Datos_ET_{cohorte}.xlsx` |
| `modules/rend_acad_alumno.py:766` | PT | `Dados_{catraca}_{fecha}.xlsx` | `Datos_{catraca}_{fecha}.xlsx` |

El resto de exportaciones ya usa `Datos_`, `Reporte_`, `Listado_` o `Resumen_` en español.

---

## 5. Placeholders

### 5.1 Placeholders escritos en el código: 37, todos correctos

Se revisaron los 37 `placeholder=` del proyecto. **Todos están en español** y no requieren cambio. Ejemplos:

| Módulo | Placeholder |
|---|---|
| `admin_areas.py:7` | `Ej: Dirección Académica` |
| `admin_areas.py:60` | `Escribe para filtrar la lista...` |
| `admin_usuarios.py:193` | `Filtra escribiendo un nombre, apellido o correo...` |
| `eficiencia_egreso.py:295` | `Escriba el nombre del alumno...` |
| `encuestas.py:133` | `Elija una sede...` |
| `indice_permanencia.py:539` | `Nombre o número de matrícula` |
| `panel_acad_resumen.py:69` | `Elija uno o más periodos` |
| `rend_acad_asignatura.py:75` | `Seleccione una Cohorte` |

**Conclusión:** no hay hallazgos de idioma en los placeholders escritos a mano.

---

### 5.2 Placeholders por defecto de Streamlit: `selectbox` con `index=None`

Muestran **"Choose an option"** en inglés.

| Ubicación | Pantalla | Etiqueta del campo | Placeholder sugerido |
|---|---|---|---|
| `modules/eficiencia_egreso.py:235` | Eficiencia de Egreso | Seleccione una Cohorte | `"Seleccione una cohorte"` |
| `modules/eficiencia_rezago.py:206` | Rezago Educativo | Seleccione una Cohorte | `"Seleccione una cohorte"` |
| `modules/eficiencia_terminal.py:304` | Eficiencia Terminal → Detalle por Cohorte | Seleccione una Cohorte (Ciclo Completo) | `"Seleccione una cohorte"` |
| `modules/eficiencia_titulacion.py:205` | Eficiencia de Titulación | Seleccione una Cohorte | `"Seleccione una cohorte"` |
| `modules/tasa_aprobacion_carrera.py:314` | Tasa de Aprobación → Carrera | Seleccione una cohorte | `"Seleccione una cohorte"` |
| `modules/tasa_desercion_generacional.py:160` | Tasa de Deserción Generacional | Seleccione una Cohorte | `"Seleccione una cohorte"` |
| `modules/tasa_retencion.py:254` | Tasa de Retención | Seleccione una Cohorte | `"Seleccione una cohorte"` |
| `modules/tiempos_medios.py:198` | Tiempos Medios de Egreso | Seleccione una Cohorte | `"Seleccione una cohorte"` |

Ejemplo de corrección:

```python
cohorte_sel = st.selectbox(
    "Seleccione una Cohorte",
    opciones_cohorte(df_ee["cohorte"]),
    index=None,
    placeholder="Seleccione una cohorte",
)
```

---

### 5.3 Placeholders por defecto de Streamlit: `multiselect` sin `default`

Muestran **"Choose options"** en inglés. Son 34 widgets.

| Archivo | Campos afectados | Placeholder sugerido |
|---|---|---|
| `modules/matriculas.py:50, 51, 52, 69, 77` | Año, Período Anual, Semestre, Disciplina, Turma | `"Todos"`, `"Todos"`, `"Todos"`, `"Todas"`, `"Todas"` |
| `modules/notas.py:56, 57, 66, 71, 76` | Período, Sub-Período, Asignatura, Profesor, Sección | `"Todos"`, `"Todos"`, `"Todas"`, `"Todos"`, `"Todas"` |
| `modules/panel_acad_asistencias.py:326, 334, 342, 350, 358` | Semestre, Asignatura, Docente, Sección, Tipo de Clase | `"Todos"`, `"Todas"`, `"Todos"`, `"Todas"`, `"Todos"` |
| `modules/panel_acad_resumen.py:88, 94, 100, 106, 196` | Semestre, Asignatura, Docente, Sección, Calificación | `"Todos"`, `"Todas"`, `"Todos"`, `"Todas"`, `"Todas"` |
| `modules/rend_acad_alumno.py:419, 420, 424` | Año, Período, Semestre | `"Todos"`, `"Todos"`, `"Todos"` |
| `modules/rend_acad_asignatura.py:87, 98` | Semestre, Asignatura | `"Todos"`, `"Todas"` |
| `modules/rend_acad_carrera.py:89` | Semestre | `"Todos"` |
| `modules/rend_acad_semestre.py:90` | Semestre | `"Todos"` |
| `modules/eficiencia_egreso.py:267` | Filtrar por Tipo de Egreso (Opcional) | `"Todos"` |
| `modules/eficiencia_titulacion.py:248, 251` | Filtrar por Status de Titulación, Filtrar por Tipo de Egreso | `"Todos"`, `"Todos"` |

Regla de estilo: usar `"Todas"` o `"Todos"` según el sustantivo, igual que ya hace `modules/encuestas.py` (`:935-973`, `:1191-1215`). Si se prefiere una frase más explícita, usar `"Seleccione..."`.

Ejemplo:

```python
turma_sel = col5.multiselect("Sección", turma_vals, placeholder="Todas")
```

---

### 5.4 Casos condicionales y de lista vacía

| Ubicación | Qué muestra | Cuándo | Sugerencia |
|---|---|---|---|
| `modules/panel_acad_asistencias.py:312` | `Choose options` | Cuando hay más de un año seleccionado (`default=None`) | `placeholder="Seleccione un subperiodo"` |
| `modules/rend_acad_asignatura.py:78, 79` | `No options to select` | Mientras no hay cohorte elegida (`options=[], disabled=True`) | `placeholder="Sin opciones"` |
| `modules/rend_acad_carrera.py:82` | `No options to select` | Mismo caso | `placeholder="Sin opciones"` |
| `modules/rend_acad_semestre.py:83` | `No options to select` | Mismo caso | `placeholder="Sin opciones"` |
| `modules/activos_config_etl.py:425` | `Choose or add options` | Solo si la configuración guardada no tiene períodos | `placeholder="Seleccione o agregue periodos"` |
| `modules/alumnos_config_etl.py:269` | `Choose or add options` | Solo si la configuración no tiene años | `placeholder="Seleccione o agregue años"` |
| `modules/asistencias_config_etl.py:261, 275` | `Choose or add options` | Solo si la configuración no tiene años/períodos | `placeholder="Seleccione o agregue valores"` |
| Filtros con opciones dinámicas vacías (`admin_logs.py:54-62`, `admin_usuarios.py:89`) | `No options to select` | Si no hay datos para ese filtro | `placeholder="Sin opciones"` |

---

### 5.5 `st.file_uploader`: texto en inglés del componente

Hay 3 cargadores:

| Ubicación | Etiqueta |
|---|---|
| `modules/activos_config_etl.py:260` | `Archivo de población (.csv, .txt o .xlsx)` |
| `modules/activos_config_etl.py:330` | `Archivo de ids activos (.txt)` |
| `utils/ui_uploads.py:79` | `Nueva planilla (.xlsx)` |

Streamlit muestra en inglés: **"Drag and drop file here"**, **"Browse files"** y **"Limit 200MB per file"**. En 1.50 **no existe un parámetro oficial** para cambiar esos textos.

Opciones, en orden de recomendación:

1. **Aceptarlo como componente del framework.** Es el comportamiento estándar de Streamlit y no afecta la operación.
2. **Ocultarlo con CSS y mostrar una instrucción en español** (frágil, depende de `data-testid`):

```css
/* Oculta el texto inglés del recuadro; la instrucción en español va en un caption aparte. */
[data-testid="stFileUploaderDropzoneInstructions"] { display: none; }
```

   Requiere centralizar el CSS en `utils/ui.py` y agregar un `st.caption("Arrastre el archivo aquí o haga clic en Examinar.")`.
3. **Componente personalizado**, solo si el requisito de idioma es obligatorio.

---

## 6. Términos aceptados (no cambiar)

### 6.1 `Trancado` / `trancada`

Por decisión del usuario, **se mantiene** en toda la interfaz. Es terminología institucional y no se considera error.

Ubicaciones documentadas para evitar futuras "correcciones":

| Ubicación | Uso |
|---|---|
| `modules/indice_permanencia.py:200` | Color del motivo `"Trancado"` |
| `modules/indice_permanencia.py:334` | Leyenda `"Trancado: matrícula trancada..."` |
| `modules/indice_permanencia.py:491` | Glosario de motivos |
| `modules/indice_permanencia.py:500` | Glosario de `estado_matricula` |
| `modules/indice_permanencia.py:512` | Glosario de `fecha_cambio` |
| `modules/indice_permanencia.py:780` | Metodología, bajas de matrícula |
| `modules/indice_permanencia.py:793-795` | Metodología, alumnos que no continuaron |
| `modules/rend_acad_alumno.py:121` | Estilo del estado del alumno |

Origen del dato (no es frontend): `services/etl/activos_criterios_etl.py:109` y `services/etl/permanencia_etl.py:227`.

### 6.2 Términos técnicos aceptados

| Término | Tratamiento |
|---|---|
| `ETL` | Se mantiene |
| `PDF`, `Excel`, `CSV` | Se mantienen |
| `ID` | Se mantiene (se sugiere unificar `Id` → `ID`) |
| `URL`, `MySQL` | Se mantienen |
| `EV1`, `EV2` | Se mantienen |
| `KPI`, `IP` | Se mantienen |
| `N/A` | Se mantiene si se prefiere; alternativa: `No disponible` o `—` |

---

## 7. Fuera del alcance (no es frontend)

- **Logs en portugués de `services/etl/*`**: son `log.info`, `log.warning` y `log.error`, no llamadas `st.*`. No se renderizan en la interfaz. Ejemplos: `"Executando query..."`, `"Nenhum dado encontrado."`, `"Falha na conexão, pulando."` (`services/etl/alumnos_etl.py:484, 497, 512`).
- **Mensajes de progreso de los ETL**: los `on_progress(...)` visibles están en español.
- **Comentarios y docstrings en portugués** en `app.py`, `modules/` y `services/`.
- **Nombres internos**: `turma`, `usuarios_id`, `periodo_egresso_format`, claves de `session_state`, iconos `:material/*`, CSS y SQL.
- **`NENHUM`, `NENHUMA`, `SEM COMENTARIOS`** (`modules/encuestas_ev1.py:2186`): lista de filtro interna, no visible.
- **Barra de herramientas de `st.dataframe`** (`Download as CSV`, `Search`, `Fullscreen`): ya se oculta con `[data-testid="stElementToolbar"]` en `utils/ui.py:147` en las páginas que llaman a `aplicar_estilos_indicador()`. En pantallas que no la llaman (por ejemplo Administración) podría verse; se puede extender el CSS si se desea.

---

## 8. Anexo A: modales y popovers verificados

Los **21 `@st.dialog`** tienen título en español:

- `Confirmar ETL de Alumnos Activos`
- `Crear Nueva Área`, `Editar Información de Área`
- `Crear Nuevo Usuario`, `Editar Información de Usuario`, `Cambiar Contraseña Manualmente`
- `Confirmar ejecución del ETL de Alumnos`
- `Confirmar ejecución del ETL de Asistencias`
- `Perfil Académico del Estudiante` (7 módulos)
- `Nueva Configuración de ETL de Encuesta`, `Editar Configuración de ETL de Encuesta`
- `Historial académico del estudiante`
- `Confirmar ejecución del ETL de Permanencia`
- `Nueva Configuración de Permanencia`, `Editar Configuración de Permanencia`

Los **2 `st.popover`** son `Cuenta` (`app.py:364`) y `Más columnas` (`modules/indice_permanencia.py:548`), ambos en español.

**Conclusión:** no hay hallazgos en los títulos de modales; los textos a corregir están dentro de sus cuerpos (formularios de usuario y configuración ETL).

---

## 9. Anexo B: plan de aplicación sugerido

Orden recomendado, de menor a mayor riesgo. Todos los cambios son de presentación.

### Paso 1 — Cadenas de texto (sin impacto funcional)

1. `app.py:115` → `"Inicio"`.
2. `app.py:80` → mensaje de advertencia en español.
3. `utils/menu_config.py:139` y `modules/admin_logs.py:12` → `"Registros y Auditoría"`.
4. `modules/admin_logs.py:131` → `"sin correo"`; `:135` y `:139` → `"No disponible"`.
5. `modules/admin_usuarios.py:88, 108, 117, 203` → `Correo`.
6. `modules/eficiencia_titulacion.py:248` → `Estado`.
7. `modules/encuestas_ev1.py:460` y `modules/encuestas_ev2.py:2880` → `Panel`.
8. `modules/encuestas.py:529` → `conjunto de datos`.
9. `modules/encuestas_config_etl.py:84, 85, 89, 99, 125, 146, 168, 241` → `flujo`, `registrar/Registre`, `conjunto de datos`.
10. `modules/matriculas.py:77, 185` → `Sección`.
11. `modules/eficiencia_terminal.py:300, 395` y `modules/rend_acad_alumno.py:766` → `Datos_`.
12. `modules/rend_acad_alumno.py:200` y `modules/tasa_retencion.py:112` → `No disponible`.
13. `cron` en los 5 módulos de configuración ETL → `actualización automática` / `diaria`.

### Paso 2 — Roles y estados (mapeo de presentación)

- `modules/admin_usuarios.py:90, 127` → `format_func` con `Lectura` / `Administrador`.
- `modules/admin_usuarios.py:216` → diccionario de etiquetas.

No tocar `utils/db_pia.py` ni el `ENUM`.

### Paso 3 — Placeholders

- 8 `selectbox` con `index=None` → `placeholder="Seleccione una cohorte"`.
- 34 `multiselect` → `placeholder="Todas"` / `"Todos"`.
- Casos condicionales de 5.4.
- Decidir si se acepta el inglés de `st.file_uploader` o se aplica CSS.

### Paso 4 — Verificación

```powershell
# Compilación limpia de los archivos tocados
.venv\Scripts\python.exe -m py_compile app.py modules\admin_usuarios.py modules\matriculas.py modules\encuestas_config_etl.py
```

Búsquedas de control (no deberían quedar resultados en texto visible):

```powershell
Select-String -Path app.py,modules\*.py -Pattern 'Início|Turma|Dados_|Cadastre|cadastrar|dataset_name|Dashboard|Filtros del Dashboard'
Select-String -Path app.py,modules\*.py -Pattern 'LEITURA'   # solo debe quedar en la lógica, nunca en etiquetas
Select-String -Path app.py,modules\*.py -Pattern 'cron'      # solo en comentarios o nombres internos
```

Prueba manual mínima:

1. Login y barra lateral.
2. Administración → Usuarios (crear, editar, listar roles).
3. Administración → Logs y Auditoría.
4. Configuración ETL → Encuestas (modal nuevo y editar).
5. Matrículas (filtro y PDF).
6. Eficiencia Terminal (descarga Excel).
7. Encuestas EV1/EV2 (expander de filtros).
8. Un `selectbox` de cohorte y un `multiselect` de filtros para confirmar que ya no aparece texto en inglés.

---

## 10. Anexo C: criterios de aceptación

- [ ] Ningún texto visible dice `Início`, `Turma`, `Dados_`, `Cadastre`, `cadastrar`, `LEITURA`, `ADMIN` (como etiqueta), `Email`, `Logs`, `Status`, `Dashboard`, `dataset`, `pipeline`.
- [ ] `Trancado` / `trancada` **siguen presentes** (decisión institucional).
- [ ] Los 8 `selectbox` con `index=None` muestran un placeholder en español.
- [ ] Los 34 `multiselect` muestran `Todas`/`Todos` o el texto acordado.
- [ ] Los roles se ven como `Lectura` / `Administrador` y la base sigue guardando `LEITURA` / `ADMIN`.
- [ ] Las exportaciones descargan `Datos_*.xlsx`.
- [ ] `python -m py_compile` pasa sin errores.
- [ ] No se modificó ningún ETL, consulta, esquema ni valor de base de datos.
- [ ] Codificación UTF-8 conservada en todos los archivos.

---

## 11. Anexo D: matriz de riesgo

| Cambio | Riesgo | Mitigación |
|---|---|---|
| Textos de etiquetas, ayudas y captions | Muy bajo | Solo presentación |
| Nombres de archivo de exportación | Muy bajo | No afecta datos ni rutas internas |
| `Turma` → `Sección` | Bajo | La columna `turma` no se renombra |
| `format_func` de roles | Bajo | El valor devuelto sigue siendo `LEITURA`/`ADMIN` |
| `placeholder=` en widgets | Muy bajo | No altera filtros ni estado |
| CSS para `file_uploader` | Medio | Depende de `data-testid`; puede cambiar entre versiones de Streamlit |
| Cambiar `Trancado` en la BD | Alto | **Descartado**: se mantiene el término |

---

## 12. Anexo E: ¿cuándo ve el usuario cada hallazgo?

No todo el inventario aparece en la primera pantalla ni en todas las sesiones. Clasificación por condición de visibilidad:

### E.1 Siempre visible al abrir la pantalla

| Hallazgo | Dónde |
|---|---|
| `Turma` en el filtro | Matrículas |
| `Filtrar por Status de Titulación` | Eficiencia de Titulación |
| `Filtros del Dashboard EV1/EV2` | Encuestas EV1 y EV2 |
| `Cadastre...` y `Nombre del dataset` | Configuración ETL → Encuestas (ADMIN) |
| `Actualización automática (cron ...)` | Configuración ETL → toggles (ADMIN) |
| `Email (Login)`, `Email`, `Nombre y Email` | Administración → Usuarios (ADMIN) |
| `Logs y Auditoría` | Menú y pantalla de Administración (ADMIN) |
| `LEITURA` / `ADMIN` en la tabla de usuarios | Administración → Usuarios (ADMIN) |

### E.2 Solo para usuarios ADMIN

Todo lo de `admin_usuarios.py`, `admin_logs.py` y los módulos `*_config_etl.py`. Un usuario con rol `LEITURA` no los ve.

### E.3 Solo al pasar el mouse (tooltip `help=`)

| Hallazgo | Ubicación |
|---|---|
| `cron` dentro de ayudas | `activos_config_etl.py:444`, `alumnos_config_etl.py:287`, `asistencias_config_etl.py:293`, `encuestas_config_etl.py:259` |
| `dataset` en ayudas | `encuestas_config_etl.py:99, 146` |

### E.4 Solo en archivos descargados

| Hallazgo | Dónde se ve |
|---|---|
| `Turma:` | Texto interno del PDF de Matrículas (`matriculas.py:185`) |
| `Dados_ET_*.xlsx` | Nombre del archivo al descargar el Excel de Eficiencia Terminal |
| `Datos_<catraca>_<fecha>.xlsx` | Nombre del archivo al descargar el Excel del estudiante |

> El nombre del archivo se ve en el navegador al momento de descargar; no aparece dentro de la página.

### E.5 Solo si faltan datos o hay un error

| Hallazgo | Condición |
|---|---|
| `app.py:80` | Un módulo no tiene función `render()` |
| `encuestas.py:529` | No existe la fila `resultado_general` para la selección |
| `admin_logs.py:131, 135, 139` | El log no tiene actor o usuario afectado |
| `rend_acad_alumno.py:200` | El alumno no tiene sede/filial registrada |
| `tasa_retencion.py:112` | No hay dato para la cohorte |
| `activos_config_etl.py:472`, `asistencias_config_etl.py:320` | Hay un ETL en curso (bloqueo) |
| `encuestas_config_etl.py:84-85` | Se elige el tipo `EVALUACION_PARES` |
| `encuestas_config_etl.py:125, 168` | Falla la creación o edición de una configuración |

### E.6 Solo cuando el campo está vacío (placeholders)

Los 8 `selectbox` con `index=None` y los 34 `multiselect` sin `default`. En cuanto el usuario elige un valor, el texto desaparece. Son visibles desde el primer render.

### E.7 Dependen de los datos cargados

| Hallazgo | Condición |
|---|---|
| `Trancado` / `trancada` | Solo si hay alumnos con ese estado (**se mantiene por decisión institucional**) |
| `LEITURA` / `ADMIN` | Solo si hay usuarios listados |
| `sin email` / `N/A` | Solo si el registro no tiene el dato |

### E.8 No visible para el usuario

| Hallazgo | Motivo |
|---|---|
| `app.py:115` `title="Início"` | La navegación de Streamlit está oculta (`position="hidden"`); la barra lateral se dibuja a mano con `"Inicio"` |

---

**Nota final:** este informe no aplica cambios. Cualquier modificación posterior debe ejecutarse con autorización explícita, validarse con `py_compile` y no requiere `git push` ni despliegue hasta que el usuario lo indique.

---

## 13. Anexo F: registro de cambios aplicados (26/10/2026)

Esta sección documenta la ejecución del plan de las secciones 9 y 10. **Solo se modificó presentación** (etiquetas, ayudas, mensajes, nombres de archivo descargable y `placeholder`). No se tocaron consultas, ETL, esquemas, claves de `session_state` ni la lógica de filtros.

### F.1 Textos traducidos

| Archivo | Cambio |
|---|---|
| `app.py` | `title="Início"` → `"Inicio"`; mensaje de módulo sin `render()` en español |
| `utils/menu_config.py` | Menú `Logs y Auditoría` → `Registros y Auditoría` |
| `modules/admin_logs.py` | Subtítulo `Registros y Auditoría`; `sin email` → `sin correo`; `N/A` → `No disponible` |
| `modules/admin_usuarios.py` | Diccionario `ETIQUETAS_ROL`; `Email (Login)` → `Correo (Usuario)`; `Email` → `Correo electrónico`; cabecera `Nombre y Correo`; `format_func` en los dos `selectbox` de rol; tabla de usuarios muestra `Lectura`/`Administrador` |
| `modules/activos_config_etl.py` | `cron` → `actualización automática` en ayudas y avisos de bloqueo |
| `modules/alumnos_config_etl.py` | `cron nocturno` → `actualización automática nocturna`; `dashboard` → `panel` |
| `modules/asistencias_config_etl.py` | Igual que el anterior, en textos y ayuda del toggle de 03:00 |
| `modules/encuestas_config_etl.py` | `pipeline` → `flujo de procesamiento`; `cadastrar`/`Cadastre` → `registrar`/`Registre`; `dataset`/`dataset_name` → `conjunto de datos`; `Id` → `ID`; `cron 3x al día` → `3 veces al día`; `dashboard` → `panel` |
| `modules/permanencia_config_etl.py` | `cron 03:30` → `actualización automática (diaria 03:30)` en los tres textos |
| `modules/matriculas.py` | `Turma` → `Sección` en el filtro y en el PDF (la columna `turma` se mantiene) |
| `modules/eficiencia_terminal.py` | `Dados_ET_*` → `Datos_ET_*` en los dos Excel |
| `modules/rend_acad_alumno.py` | `Dados_<catraca>.xlsx` → `Datos_...`; `N/A` → `No disponible` |
| `modules/eficiencia_titulacion.py` | `Status de Titulación` → `Estado de Titulación` |
| `modules/encuestas_ev1.py` | `Filtros del Dashboard EV1` → `Panel EV1` (expander y nota HTML) |
| `modules/encuestas_ev2.py` | `Filtros del Dashboard EV2` → `Panel EV2` |
| `modules/encuestas.py` | `dataset` → `conjunto de datos` |
| `modules/tasa_retencion.py` | `N/A` → `No disponible` en la tabla y el PDF |

### F.2 Placeholders agregados (46 widgets)

| Tipo | Cantidad | Texto |
|---|---|---|
| `selectbox` con `index=None` | 8 | `Seleccione una cohorte` |
| `multiselect` de filtros | 33 | `Todos` / `Todas` según el sustantivo |
| `multiselect` de subperiodo | 1 | `Seleccione un subperiodo` |
| `multiselect` ETL con `accept_new_options` | 4 | `Seleccione o agregue años` / `periodos` |

Archivos con placeholders nuevos: `eficiencia_egreso.py`, `eficiencia_rezago.py`, `eficiencia_terminal.py`, `eficiencia_titulacion.py`, `tasa_aprobacion_carrera.py`, `tasa_desercion_generacional.py`, `tasa_retencion.py`, `tiempos_medios.py`, `matriculas.py`, `notas.py`, `panel_acad_asistencias.py`, `panel_acad_resumen.py`, `rend_acad_alumno.py`, `rend_acad_asignatura.py`, `rend_acad_carrera.py`, `rend_acad_semestre.py`, `activos_config_etl.py`, `alumnos_config_etl.py`, `asistencias_config_etl.py`.

### F.3 Sin cambios (por decisión o por alcance)

| Elemento | Motivo |
|---|---|
| `Trancado` / `trancada` | Terminología institucional aceptada |
| Texto del `st.file_uploader` (`Drag and drop file here`, `Browse files`) | Sin parámetro oficial en Streamlit 1.50; requiere CSS frágil o componente propio |
| Toolbar de `st.dataframe` (`Download as CSV`, `Search`) | Se oculta solo en páginas que llaman a `aplicar_estilos_indicador()`; son tooltips al pasar el mouse |
| `LEITURA` / `ADMIN` en la base y en `session_state` | Valor interno; solo se traduce lo que se muestra |
| `logs` en portugués de `services/etl/*` | No se renderizan en la interfaz |
| Columna `turma`, `dataset_name`, `status_academico` | Nombres internos de datos |

### F.4 Validación ejecutada

| Prueba | Resultado |
|---|---|
| `python -m py_compile` de los archivos modificados | OK |
| `compileall` de todo el proyecto (excluyendo `.venv`) | OK |
| Escáner `ast` de `selectbox`/`multiselect` sin `placeholder` | 0 pendientes |
| Arranque de `app.py` con `streamlit.testing.AppTest` | 0 excepciones |
| Codificación de los 29 archivos modificados | UTF-8 sin BOM, sin caracteres de reemplazo |
| `Trancado` / `trancada` | Intactos en `indice_permanencia.py` y `rend_acad_alumno.py` |

> Los cambios quedaron **sin commit, sin `git push` y sin despliegue**. Se aplicarán según el protocolo del `GEMINI.md` cuando el usuario lo autorice.

### F.5 Barra superior de Streamlit

El botón **Deploy** y el menú **⋮** (`Rerun`, `Settings`, `Print`, `Record a screencast`, `Developer options`, `Clear cache`) son cadenas internas del framework: **no existe API ni traducción oficial** para cambiarlas. Se resolvió ocultándolas con configuración, sin CSS ni parches del paquete:

```toml
# .streamlit/config.toml
[client]
toolbarMode = "minimal"
```

Comportamiento verificado en local con Streamlit 1.50.0:

| Modo | Resultado |
|---|---|
| `auto` (anterior) | Deploy + menú completo en inglés |
| `viewer` | Sin Deploy, pero el menú conserva `Rerun`, `Settings`, `Print`, `Record a screencast` y `Developer options` |
| `minimal` (aplicado) | Sin barra superior, sin Deploy y sin menú: la interfaz queda solo en español |

Efecto secundario: también desaparecen `Rerun` y `Clear cache` del menú. No afecta la operación (el navegador con F5 vuelve a ejecutar y las cachés se invalidan por la fecha de modificación de los archivos). Si se necesita el menú de desarrollo en local, se puede levantar la app con `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` sin tocar el archivo.

> Este cambio aplica al servidor recién después de un despliegue autorizado, porque `config.toml` viaja por Git.

### F.6 Ruta propia para el inicio de sesión (`/login`)

Antes el login no era una página de `st.navigation`: se dibujaba dentro de `main()` sobre cualquier ruta y luego se cortaba con `return`. Por eso la barra de direcciones conservaba `/panel_resumen` o `/inicio` mientras se veía el formulario, y no existía `/login`.

Cambios en `app.py`:

| Cambio | Detalle |
|---|---|
| Nueva función `page_login()` | Contiene exactamente el mismo formulario y comportamiento que el bloque anterior (mismo `st.form("login_form")`, misma auditoría, misma cookie de 3 horas) |
| Nuevo `p_login` | `st.Page(page_login, title="Iniciar sesión", url_path="login")`, agregado a `all_pages_list` |
| Guardas en `main()` | Sin sesión y ruta distinta de `login` → `st.switch_page(p_login)`; con sesión en `/login` → `st.switch_page(p_home)` |
| `cookie_manager` | Pasa a nivel de módulo, porque lo usan `page_login()` y la barra lateral |

Pruebas en local (puerto 8599):

| Caso | Resultado |
|---|---|
| `GET /` | Redirige a `/login` y muestra el formulario |
| `GET /panel_resumen` sin sesión | Redirige a `/login` (sin barra lateral) |
| `GET /login` | Muestra el formulario directamente |
| Envío con credenciales inválidas | Queda en `/login` y muestra “Credenciales incorrectas o cuenta inactiva.” |
| Arranque con sesión ADMIN simulada (`AppTest`) | 0 excepciones; la app normal sigue funcionando |

> **Efecto secundario de la prueba:** se registró un evento `login_failed` en la auditoría con el correo ficticio `prueba.invalida@ucp.edu.py`. Es un registro real en la tabla de auditoría y puede eliminarse cuando se autorice.

> **Hallazgo del framework:** en Streamlit 1.50 la primera página de `st.navigation` se publica en `/` y su `url_path` **no** es enrutable. Como `p_home` es la página principal, `/inicio` responde con el aviso inglés del framework: *“Page not found — The page that you have requested does not seem to exist. Running the app's main page.”* Ese texto no es traducible y el efecto ya existía antes de este cambio (se comprobó con una app mínima). Por eso `/login` funciona y `/inicio` no se usa; el botón “Inicio” del menú navega por objeto de página, no por URL.

### F.7 Eliminación de la franja superior y reubicación del botón del menú

La barra superior de Streamlit seguía reservando 60 px de alto aunque estuviera vacía (sin Deploy ni menú). Ese espacio se veía como una franja en blanco sobre el menú y el contenido.

Cambios aplicados en el CSS de `app.py` (bloque de estilos de la barra lateral):

| Regla | Efecto |
|---|---|
| `header[data-testid="stHeader"]` con `height: 0`, `min-height: 0` y `padding: 0` | La franja superior deja de ocupar espacio |
| `[data-testid="stSidebarHeader"]` con `height: 0` y `padding: 0`; `stLogoSpacer` oculto | El logo sube hasta el borde superior del menú |
| `[data-testid="stSidebarCollapseButton"]` en `position: absolute`, `top: 6px`, `right: 4px` | El botón « para ocultar el menú queda dentro de la barra lateral, arriba a la derecha, a la altura del logo |
| `[data-testid="stExpandSidebarButton"]` en `position: fixed`, `top: 8px`, `left: 8px` | Con el menú oculto, el botón » para volver a abrirlo queda arriba a la izquierda |
| `[aria-expanded="false"] ~ div [data-testid="stMain"] .block-container` con `padding-top: 3.2rem` | Al ocultar el menú se deja aire para que el botón no tape el primer elemento |

Verificación visual en un servidor local (puerto 8598, sesión ADMIN simulada, copia temporal eliminada después):

| Caso | Resultado |
|---|---|
| Menú visible | Sin franja superior; el logo arranca arriba y el botón « aparece arriba a la derecha del menú |
| Menú oculto | El contenido ocupa todo el ancho y el botón » aparece arriba a la izquierda, sin superponerse |
| Navegación y cierre de sesión | Sin cambios: solo se modificó la presentación |

> El botón de ocultar del propio Streamlit solo se muestra al pasar el mouse por la barra lateral; esa visibilidad es del framework y no se alteró.
