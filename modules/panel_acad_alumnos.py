import datetime
import io
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st
import xlsxwriter

import modules.rend_acad_alumno as raa
from services.data.alumnos import load_current_alumnos, load_alumnos_documentos
from utils import db_pia
from utils.ui import (
    COLOR_BUENO,
    COLOR_MALO,
    COLOR_PRIMARIO,
    estilizar_figura,
    formatear_entero,
    render_cabecera_indicador,
    render_tarjetas_kpi,
    render_titulo_seccion,
)


COL_ID_ALUMNO = "usuarios_id"
COL_CATRACA = "numero_catraca"
COL_NOMBRE = "nome_sobrenome"
COL_PERIODO = "ano_periodo_letivo"
COL_SUBPERIODO = "periodo_anual_periodo_letivo"
COL_SEMESTRE = "semestre_alumno"

SEMESTRES = list(range(1, 13))

# Colores de la matriz semestre x periodo, iguales a la hoja "Matriz" del
# consolidado "Alumnos Reales Max 2 Recursantes": cada diagonal (una cohorte
# que avanza un semestre por periodo) tiene el mismo color, en un ciclo de 10.
COLORES_COHORTE = [
    "#FFCC99", "#99FFCC", "#CCB3FF", "#FFD966", "#FF99CC",
    "#FFFF99", "#66CC99", "#99FF99", "#66FFFF", "#99CCFF",
]
COLOR_CABECERA_MATRIZ = "#C6E0B4"
COLOR_COLUMNA_SEMESTRE = "#FCE4D6"
COLOR_TOTAL_MATRIZ = "#BFBFBF"
# 2018.2 es la primera columna de la hoja "Matriz": ancla del ciclo de colores.
RANGO_ANCLA_COLORES = 2018 * 2 + 1


def _rango_periodo(ano, subperiodo):
    return int(ano) * 2 + int(subperiodo) - 1


def _color_cohorte(ano, subperiodo, semestre):
    """Color de la celda (periodo, semestre) según la cohorte (diagonal)."""
    indice = (_rango_periodo(ano, subperiodo) - RANGO_ANCLA_COLORES - semestre + 1) % len(COLORES_COHORTE)
    return COLORES_COHORTE[indice]


def _prepare_alumnos(df):
    required_cols = [COL_ID_ALUMNO, COL_CATRACA, COL_NOMBRE, COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return pd.DataFrame(), missing_cols

    prepared = df[required_cols].copy()
    prepared[COL_PERIODO] = pd.to_numeric(prepared[COL_PERIODO], errors="coerce")
    prepared[COL_SUBPERIODO] = pd.to_numeric(prepared[COL_SUBPERIODO], errors="coerce")
    prepared[COL_SEMESTRE] = pd.to_numeric(prepared[COL_SEMESTRE], errors="coerce")
    prepared = prepared.dropna(subset=[COL_ID_ALUMNO, COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE])
    prepared[COL_PERIODO] = prepared[COL_PERIODO].astype(int)
    prepared[COL_SUBPERIODO] = prepared[COL_SUBPERIODO].astype(int)
    prepared[COL_SEMESTRE] = prepared[COL_SEMESTRE].astype(int)
    prepared = prepared[prepared[COL_SEMESTRE].between(1, 12)].copy()
    prepared["Periodo"] = prepared[COL_PERIODO].astype(str) + "." + prepared[COL_SUBPERIODO].astype(str)
    return prepared, []


def _build_period_summary(df):
    """Alumnos únicos por periodo, en orden cronológico."""
    unique_period = df[[COL_ID_ALUMNO, COL_PERIODO, COL_SUBPERIODO, "Periodo"]].drop_duplicates()
    summary = (
        unique_period.groupby([COL_PERIODO, COL_SUBPERIODO, "Periodo"], as_index=False)[COL_ID_ALUMNO]
        .nunique()
        .rename(columns={COL_ID_ALUMNO: "Alumnos"})
        .sort_values([COL_PERIODO, COL_SUBPERIODO])
    )
    return summary[[COL_PERIODO, COL_SUBPERIODO, "Periodo", "Alumnos"]].reset_index(drop=True)


def _build_matriz(df, period_summary):
    """Matriz semestre (filas) x periodo (columnas) con alumnos únicos, como
    la hoja "Matriz" del consolidado."""
    matriz = (
        df[[COL_ID_ALUMNO, "Periodo", COL_SEMESTRE]].drop_duplicates()
        .pivot_table(index=COL_SEMESTRE, columns="Periodo", values=COL_ID_ALUMNO, aggfunc="nunique", fill_value=0)
        .reindex(index=SEMESTRES, columns=period_summary["Periodo"].tolist(), fill_value=0)
        .astype(int)
    )
    matriz.index.name = "Semestre"
    return matriz


def _build_alumnos_list(df):
    latest = (
        df.sort_values([COL_ID_ALUMNO, COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE])
        .drop_duplicates(subset=[COL_ID_ALUMNO], keep="last")
        .rename(
            columns={
                COL_CATRACA: "Número de Matrícula",
                COL_NOMBRE: "Nombre y Apellido",
                COL_SEMESTRE: "Semestre",
            }
        )
    )
    # usuarios_id se conserva para abrir el perfil del alumno; no se muestra ni se exporta.
    return latest[[COL_ID_ALUMNO, "Número de Matrícula", "Nombre y Apellido", "Periodo", "Semestre"]].sort_values(
        ["Nombre y Apellido", "Número de Matrícula"]
    ).reset_index(drop=True)


@st.dialog("Historial académico del estudiante", width="large")
def _mostrar_rendimiento(id_alumno, df_completo):
    """Ventana con el perfil académico (mismo detalle que Rendimiento Académico > Estudiante)."""
    df_estudiante = df_completo[df_completo[raa.COL_ID_ALUMNO] == id_alumno].copy()
    if df_estudiante.empty:
        st.error("No se encontraron datos para este estudiante.")
        return
    raa.render_alumno_details(df_estudiante, df_completo)


ALUMNOS_POR_PAGINA = 20


def _render_listado(alumnos_list, df_completo):
    """Listado paginado con un botón "Ver historial académico" en cada alumno
    (abre la misma ficha que Rendimiento Académico > Estudiante)."""
    c_busqueda, c_info = st.columns([2, 1], vertical_alignment="bottom")
    busqueda = c_busqueda.text_input(
        "Buscar alumno", placeholder="Nombre o número de matrícula", key="alumnos_busqueda",
    ).strip().lower()
    listado = alumnos_list
    if busqueda:
        listado = alumnos_list[
            alumnos_list["Nombre y Apellido"].astype(str).str.lower().str.contains(busqueda, regex=False)
            | alumnos_list["Número de Matrícula"].astype(str).str.contains(busqueda, regex=False)
        ].reset_index(drop=True)
    c_info.caption(f"{formatear_entero(len(listado))} alumno(s) · último periodo y semestre de cada uno")

    if listado.empty:
        st.info("No se encontraron alumnos con esa búsqueda.")
        return

    # Paginación: vuelve a la página 1 cuando cambia la búsqueda.
    total_paginas = (len(listado) - 1) // ALUMNOS_POR_PAGINA + 1
    if st.session_state.get("alumnos_busqueda_anterior") != busqueda:
        st.session_state["alumnos_busqueda_anterior"] = busqueda
        st.session_state["alumnos_pagina"] = 1
    pagina = min(max(1, st.session_state.get("alumnos_pagina", 1)), total_paginas)
    pagina_df = listado.iloc[(pagina - 1) * ALUMNOS_POR_PAGINA: pagina * ALUMNOS_POR_PAGINA]

    anchos = [1.2, 3.4, 1, 1, 2.2]
    with st.container(border=True, gap=None):  # sin espacio extra entre filas
        cab = st.columns(anchos, vertical_alignment="center")
        for col, titulo in zip(cab, ["**Matrícula**", "**Nombre y apellido**", "**Periodo**", "**Semestre**", ""]):
            col.markdown(titulo)
        for _, fila in pagina_df.iterrows():
            st.markdown('<hr style="margin:6px 0; border:none; border-top:1px solid #eef2f6;">', unsafe_allow_html=True)
            cols = st.columns(anchos, vertical_alignment="center")
            cols[0].write(str(fila["Número de Matrícula"]))
            cols[1].write(str(fila["Nombre y Apellido"]))
            cols[2].write(str(fila["Periodo"]))
            cols[3].write(f"{int(fila['Semestre'])}º")
            if cols[4].button(
                "Ver historial académico", icon=":material/history_edu:", key=f"hist_alumno_{fila[COL_ID_ALUMNO]}",
                width="stretch", help="Abre el rendimiento académico del alumno, semestre por semestre",
            ):
                _mostrar_rendimiento(fila[COL_ID_ALUMNO], df_completo)

    c_ant, c_pag, c_sig = st.columns([1, 2, 1], vertical_alignment="center")
    if c_ant.button("Anterior", icon=":material/chevron_left:", disabled=pagina <= 1, width="stretch",
                    key="alumnos_pag_anterior"):
        st.session_state["alumnos_pagina"] = pagina - 1
        st.rerun()
    desde = (pagina - 1) * ALUMNOS_POR_PAGINA + 1
    hasta = min(pagina * ALUMNOS_POR_PAGINA, len(listado))
    c_pag.markdown(
        f"<div style='text-align:center; color:#64748b; font-size:14px;'>Página {pagina} de {total_paginas} · "
        f"alumnos {formatear_entero(desde)}–{formatear_entero(hasta)} de {formatear_entero(len(listado))}</div>",
        unsafe_allow_html=True,
    )
    if c_sig.button("Siguiente", icon=":material/chevron_right:", disabled=pagina >= total_paginas, width="stretch",
                    key="alumnos_pag_siguiente"):
        st.session_state["alumnos_pagina"] = pagina + 1
        st.rerun()


def _grafico_por_periodo(period_summary):
    datos = period_summary.assign(Etiqueta=period_summary["Alumnos"].map(formatear_entero))
    fig = px.bar(datos, x="Periodo", y="Alumnos", text="Etiqueta")
    fig.update_traces(
        marker_color=COLOR_PRIMARIO,
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>%{text} alumnos<extra></extra>",
    )
    estilizar_figura(fig, titulo_y="Alumnos", altura=360, leyenda=False)
    fig.update_xaxes(type="category")
    return fig


def _matriz_html(matriz, period_summary):
    """Tabla HTML de la matriz con los colores por cohorte del Excel."""
    sub_por_periodo = dict(zip(period_summary["Periodo"], zip(period_summary[COL_PERIODO], period_summary[COL_SUBPERIODO])))
    totales = dict(zip(period_summary["Periodo"], period_summary["Alumnos"]))

    estilo_celda = "padding:6px 10px; text-align:right; border:1px solid #ffffff; white-space:nowrap;"
    cabecera = "".join(
        f'<th style="{estilo_celda} text-align:center; background:{COLOR_CABECERA_MATRIZ};">{escape(p)}</th>'
        for p in matriz.columns
    )
    filas = []
    for semestre, fila in matriz.iterrows():
        celdas = []
        for periodo, valor in fila.items():
            if valor:
                ano, sub = sub_por_periodo[periodo]
                fondo = _color_cohorte(ano, sub, semestre)
                celdas.append(f'<td style="{estilo_celda} background:{fondo}; color:#1e293b;">{formatear_entero(valor)}</td>')
            else:
                celdas.append(f'<td style="{estilo_celda} color:#cbd5e1;">–</td>')
        filas.append(
            f'<tr><th style="{estilo_celda} text-align:center; background:{COLOR_COLUMNA_SEMESTRE};">{semestre}º</th>'
            + "".join(celdas) + "</tr>"
        )
    total = "".join(
        f'<td style="{estilo_celda} background:{COLOR_TOTAL_MATRIZ}; font-weight:700;">{formatear_entero(totales[p])}</td>'
        for p in matriz.columns
    )
    filas.append(
        f'<tr><th style="{estilo_celda} text-align:center; background:{COLOR_TOTAL_MATRIZ};">TOTAL</th>{total}</tr>'
    )
    return (
        '<div style="overflow-x:auto; border:1px solid #e2e8f0; border-radius:10px;">'
        '<table style="border-collapse:collapse; width:100%; font-size:13.5px; font-variant-numeric:tabular-nums;">'
        f'<thead><tr><th style="{estilo_celda} text-align:center; background:{COLOR_CABECERA_MATRIZ};">Semestre</th>'
        f"{cabecera}</tr></thead><tbody>{''.join(filas)}</tbody></table></div>"
    )


@st.cache_data(show_spinner="Generando Excel...")
def _generate_excel_bytes(period_summary, matriz, alumnos_list):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        period_summary[["Periodo", "Alumnos"]].to_excel(writer, index=False, sheet_name="Por Periodo")

        # Hoja "Matriz" con el mismo formato (colores por cohorte) que el consolidado.
        libro = writer.book
        hoja = libro.add_worksheet("Matriz")
        base = {"border": 1, "border_color": "#FFFFFF", "align": "center"}
        f_cab = libro.add_format({**base, "bold": True, "bg_color": COLOR_CABECERA_MATRIZ})
        f_sem = libro.add_format({**base, "bold": True, "bg_color": COLOR_COLUMNA_SEMESTRE})
        f_tot = libro.add_format({**base, "bold": True, "bg_color": COLOR_TOTAL_MATRIZ, "num_format": "#,##0"})
        f_cero = libro.add_format({**base, "font_color": "#BFBFBF"})
        f_color = {c: libro.add_format({**base, "bg_color": c, "num_format": "#,##0"}) for c in COLORES_COHORTE}
        sub_por_periodo = dict(zip(period_summary["Periodo"], zip(period_summary[COL_PERIODO], period_summary[COL_SUBPERIODO])))

        hoja.write(0, 0, "Semestre", f_cab)
        for j, periodo in enumerate(matriz.columns, start=1):
            hoja.write(0, j, periodo, f_cab)
        for i, (semestre, fila) in enumerate(matriz.iterrows(), start=1):
            hoja.write(i, 0, semestre, f_sem)
            for j, (periodo, valor) in enumerate(fila.items(), start=1):
                if valor:
                    hoja.write(i, j, int(valor), f_color[_color_cohorte(*sub_por_periodo[periodo], semestre)])
                else:
                    hoja.write(i, j, 0, f_cero)
        fila_total = len(matriz) + 1
        hoja.write(fila_total, 0, "TOTAL", f_tot)
        for j, valor in enumerate(period_summary["Alumnos"], start=1):
            hoja.write(fila_total, j, int(valor), f_tot)
        hoja.set_column(0, len(matriz.columns), 10)

        alumnos_list.to_excel(writer, index=False, sheet_name="Listado")
    return buffer.getvalue()


@st.cache_data(show_spinner="Generando Excel detallado de alumnos...")
def _generar_excel_listado_alumnos(_alumnos_list, _df_completo, busqueda=""):
    """Genera un archivo Excel altamente estético y optimizado con el listado detallado de alumnos,
    sus asignaturas regulares, secciones y calificaciones (1 a 100 y 1 a 5).

    Cumple con los requisitos de diseño institucional:
    - Encabezado con título del reporte y fecha/hora de generación integrada en subtítulo.
    - Encabezados fijos de tabla con colores institucionales (freeze panes).
    - Filtros automáticos en los encabezados (autofilter).
    - Color cebra en filas alternadas y bordes sutiles.
    - Columnas autoajustables y predimensionadas para alto rendimiento.
    - Campos reales del dataset sin inventar datos: Matrícula, Documento (doc_oficial de SysEduca),
      Nombre Completo, Estado de Matrícula, Periodo, Semestre, Sede, Materia, Sección, Nota 1-100 y Nota 1-5.
    - Filtra exclusivamente materias regulares auténticas cursadas en el último periodo lectivo con materias.
    - Tope estricto de notas de 0 a 100 puntos y de 1 a 5.
    - Parámetros con guión bajo (_alumnos_list, _df_completo) para evitar sobrecarga de hasheo en caché de Streamlit.
    """
    df_raw = _df_completo
    alumnos_sub = _alumnos_list

    # Identificar columna de documento si estuviera disponible en el dataset
    col_doc = None
    for col_candidata in ["doc_oficial", "documento", "numero_documento", "cedula", "rg", "dni", "cpf"]:
        if col_candidata in df_raw.columns:
            col_doc = col_candidata
            break

    # Mapeo oficial de documentos (doc_oficial de SysEduca)
    mapa_docs = load_alumnos_documentos()

    # Identificar el conjunto de alumnos a exportar
    uids = set(alumnos_sub["usuarios_id"].dropna().unique())

    # Filtrar exclusivamente asignaturas regulares válidas
    df_reg = df_raw[
        (df_raw["usuarios_id"].isin(uids))
        & (df_raw["tipo_disciplina"] == "Regular")
        & (df_raw["disciplina"].notna())
        & (df_raw["disciplina"].astype(str).str.strip() != "")
    ].copy()

    # Último periodo lectivo regular efectivamente cursado por cada alumno
    ultimos_periodos = (
        df_reg.sort_values(["usuarios_id", "ano_periodo_letivo", "periodo_anual_periodo_letivo", "semestre_alumno"])
        .groupby("usuarios_id")
        .last()
        .reset_index()[["usuarios_id", "ano_periodo_letivo", "periodo_anual_periodo_letivo"]]
    )

    materias_ultimas = df_reg.merge(
        ultimos_periodos,
        on=["usuarios_id", "ano_periodo_letivo", "periodo_anual_periodo_letivo"],
        how="inner",
    )

    pan_reg = pd.to_numeric(materias_ultimas["periodo_anual_periodo_letivo"], errors="coerce").fillna(0).astype(int)
    ano_reg = pd.to_numeric(materias_ultimas["ano_periodo_letivo"], errors="coerce").fillna(0).astype(int)
    materias_ultimas["Periodo_Reg"] = ano_reg.astype(str) + "." + pan_reg.astype(str)
    sem_reg = pd.to_numeric(materias_ultimas["semestre_alumno"], errors="coerce").fillna(0).astype(int)
    materias_ultimas["Semestre_Reg"] = sem_reg.apply(lambda s: f"{s}º" if s > 0 else "")

    cols_materias = [
        "usuarios_id",
        "Periodo_Reg",
        "Semestre_Reg",
        "filial_periodo_letivo",
        "disciplina",
        "turma",
        "calificacion_final",
        "calificacion_final_1a5",
        "nombre_status_actual",
    ]
    if col_doc and col_doc in materias_ultimas.columns:
        cols_materias.append(col_doc)

    # Cruce estricto para incluir únicamente asignaturas regulares efectivas (sin filas vacías)
    detalle = alumnos_sub.merge(materias_ultimas[cols_materias], on="usuarios_id", how="inner")

    # Vectorización de alto rendimiento
    detalle["Matrícula"] = detalle["Número de Matrícula"].astype(str).str.replace(r"\.0$", "", regex=True)
    detalle["Documento"] = detalle["usuarios_id"].map(lambda uid: mapa_docs.get(int(uid), "") if pd.notna(uid) else "")
    if col_doc and col_doc in detalle.columns:
        detalle["Documento"] = detalle["Documento"].where(detalle["Documento"] != "", detalle[col_doc].fillna("").astype(str))

    detalle["Nombre Completo"] = detalle["Nombre y Apellido"].fillna("").astype(str).str.strip()
    detalle["Estado de Matrícula"] = detalle["nombre_status_actual"].fillna("–").astype(str).str.strip().replace(["nan", ""], "–")
    detalle["Periodo"] = detalle["Periodo_Reg"].fillna(detalle["Periodo"]).astype(str)
    detalle["Semestre"] = detalle["Semestre_Reg"].fillna(detalle["Semestre"].astype(str) + "º").astype(str)
    detalle["Sede"] = detalle["filial_periodo_letivo"].fillna("").astype(str).replace("nan", "")
    detalle["Materia"] = detalle["disciplina"].fillna("–").astype(str).replace("nan", "–")
    detalle["Sección"] = detalle["turma"].fillna("–").astype(str).replace("nan", "–")

    # Notas vectorizadas con tope estricto de 0 a 100
    n100 = pd.to_numeric(detalle["calificacion_final"], errors="coerce").clip(lower=0, upper=100)
    detalle["Nota (1 a 100)"] = n100.apply(lambda v: (int(v) if v.is_integer() else round(v, 1)) if pd.notna(v) else None)

    # Notas 1 a 5 aseguradas en rango 1 a 5
    n5 = pd.to_numeric(detalle["calificacion_final_1a5"], errors="coerce").fillna(0).astype(int)
    detalle["Nota (1 a 5)"] = n5.apply(lambda v: min(5, max(1, v)) if v > 0 else "–")

    cols_finales = [
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
    df_export = detalle[cols_finales]

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    worksheet = workbook.add_worksheet("Listado de Alumnos")

    worksheet.hide_gridlines(False)
    worksheet.set_paper(9)  # Formato A4
    worksheet.set_landscape()

    COLOR_AZUL_INST = "#1B365D"
    COLOR_CEBRA = "#F8FAFC"
    COLOR_BORDE = "#E2E8F0"

    fmt_titulo = workbook.add_format({
        "bold": True,
        "font_size": 15,
        "font_color": COLOR_AZUL_INST,
        "font_name": "Calibri",
        "valign": "vcenter",
    })
    fmt_subtitulo = workbook.add_format({
        "italic": True,
        "font_size": 10,
        "font_color": "#64748B",
        "font_name": "Calibri",
        "valign": "vcenter",
    })
    fmt_cabecera = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#FFFFFF",
        "bg_color": COLOR_AZUL_INST,
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#334E68",
        "font_name": "Calibri",
        "text_wrap": True,
    })

    def crear_formato_celda(bg_color, align="left", bold=False, num_fmt=None):
        opciones = {
            "bg_color": bg_color,
            "border": 1,
            "border_color": COLOR_BORDE,
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "vcenter",
            "align": align,
            "bold": bold,
        }
        if num_fmt:
            opciones["num_format"] = num_fmt
        return workbook.add_format(opciones)

    fmt_datos = {
        "impar_centro": crear_formato_celda("#FFFFFF", align="center"),
        "par_centro": crear_formato_celda(COLOR_CEBRA, align="center"),
        "impar_izq": crear_formato_celda("#FFFFFF", align="left"),
        "par_izq": crear_formato_celda(COLOR_CEBRA, align="left"),
        "impar_der": crear_formato_celda("#FFFFFF", align="right"),
        "par_der": crear_formato_celda(COLOR_CEBRA, align="right"),
    }

    # Encabezado institucional superior con fecha integrada
    worksheet.write(0, 0, "REPORTE DETALLADO - LISTADO DE ALUMNOS", fmt_titulo)
    worksheet.set_row(0, 24)

    ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    subtitulo_con_fecha = f"Portal de Indicadores Académicos · Sistema de Gestión Institucional - Fecha y hora de generación: {ahora}"
    worksheet.write(1, 0, subtitulo_con_fecha, fmt_subtitulo)
    worksheet.set_row(1, 18)
    worksheet.set_row(2, 10)

    fila_inicio_tabla = 3
    worksheet.set_row(fila_inicio_tabla, 26)

    for col_idx, encabezado in enumerate(cols_finales):
        worksheet.write(fila_inicio_tabla, col_idx, encabezado, fmt_cabecera)

    worksheet.freeze_panes(fila_inicio_tabla + 1, 0)

    alineaciones = ["centro", "centro", "izq", "centro", "centro", "centro", "centro", "izq", "centro", "der", "centro"]

    # Escritura ultra-rápida con itertuples (mucho más veloz que iterrows y dict lookups)
    for i, row in enumerate(df_export.itertuples(index=False)):
        fila_idx = fila_inicio_tabla + 1 + i
        prefijo = "par_" if i % 2 == 1 else "impar_"
        worksheet.set_row(fila_idx, 19)

        for col_idx, valor in enumerate(row):
            fmt = fmt_datos[prefijo + alineaciones[col_idx]]
            if valor is None or valor == "" or (isinstance(valor, float) and pd.isna(valor)):
                worksheet.write_blank(fila_idx, col_idx, "", fmt)
            elif isinstance(valor, (int, float)):
                worksheet.write_number(fila_idx, col_idx, valor, fmt)
            else:
                worksheet.write_string(fila_idx, col_idx, str(valor), fmt)

    worksheet.autofilter(fila_inicio_tabla, 0, fila_inicio_tabla + len(df_export), len(cols_finales) - 1)

    # Anchos predimensionados para máximo rendimiento
    anchos_optimos = [14, 18, 36, 18, 12, 12, 14, 38, 12, 16, 14]
    for col_idx, ancho in enumerate(anchos_optimos):
        worksheet.set_column(col_idx, col_idx, ancho)

    workbook.close()
    return buffer.getvalue()


def render():
    render_cabecera_indicador(
        "Alumnos",
        "Cantidad de alumnos (ID únicos) por periodo y por semestre. Cada alumno se cuenta una sola "
        "vez por periodo, en el semestre que cursaba.",
    )

    df_completo = load_current_alumnos()
    if df_completo.empty:
        st.error("Archivo de alumnos no encontrado o vacío.")
        return

    df, missing_cols = _prepare_alumnos(df_completo)
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return

    period_summary = _build_period_summary(df)
    matriz = _build_matriz(df, period_summary)
    alumnos_list = _build_alumnos_list(df)

    ultimo = period_summary.iloc[-1]
    if len(period_summary) > 1:
        anterior = period_summary.iloc[-2]
        variacion = (ultimo["Alumnos"] - anterior["Alumnos"]) / anterior["Alumnos"] * 100 if anterior["Alumnos"] else 0
        kpi_variacion = {
            "etiqueta": "Variación", "valor": f"{variacion:+.1f}%".replace(".", ","),
            "detalle": f"{ultimo['Periodo']} frente a {anterior['Periodo']}",
            "color": COLOR_BUENO if variacion >= 0 else COLOR_MALO,
        }
    else:
        kpi_variacion = {"etiqueta": "Variación", "valor": "–", "detalle": "Se necesita más de un periodo"}
    render_tarjetas_kpi([
        {"etiqueta": "Alumnos distintos", "valor": formatear_entero(df[COL_ID_ALUMNO].nunique()),
         "detalle": "En todo el periodo analizado"},
        {"etiqueta": "Periodos", "valor": len(period_summary),
         "detalle": f"De {period_summary['Periodo'].iloc[0]} a {ultimo['Periodo']}"},
        {"etiqueta": f"Alumnos en {ultimo['Periodo']}", "valor": formatear_entero(ultimo["Alumnos"]),
         "detalle": "Último periodo"},
        kpi_variacion,
    ])

    # Selector de vista guardado en la sesión (st.tabs volvía a la primera pestaña
    # en cada recarga, por ejemplo al abrir el historial de un alumno o cambiar de página).
    vistas = ["Por periodo y semestre", "Listado de alumnos"]
    vista = st.segmented_control(
        "Vista", vistas, default=vistas[0], key="alumnos_vista", label_visibility="collapsed",
    ) or vistas[0]

    if vista == vistas[0]:
        render_titulo_seccion("Alumnos por periodo", "Total de alumnos distintos en cada periodo lectivo.")
        st.plotly_chart(_grafico_por_periodo(period_summary), use_container_width=True, config={"displayModeBar": False})

        render_titulo_seccion(
            "Alumnos por semestre y periodo",
            "Cada color sigue a una misma cohorte: en diagonal se ve cómo un grupo avanza un semestre "
            "por periodo. La fila TOTAL coincide con el gráfico de arriba.",
        )
        st.markdown(_matriz_html(matriz, period_summary), unsafe_allow_html=True)
    else:
        _render_listado(alumnos_list, df_completo)

    st.divider()
    if vista == vistas[0]:
        excel_bytes = _generate_excel_bytes(period_summary, matriz, alumnos_list.drop(columns=[COL_ID_ALUMNO]))
        st.download_button(
            "Descargar datos (Excel: por periodo, matriz y listado)",
            data=excel_bytes,
            file_name="Alumnos_Analizados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            on_click=db_pia.log_export_callback,
            args=("Alumnos", "Excel"),
        )
    else:
        busqueda_actual = st.session_state.get("alumnos_busqueda", "").strip()
        listado_filtrado = alumnos_list
        if busqueda_actual:
            listado_filtrado = alumnos_list[
                alumnos_list["Nombre y Apellido"].astype(str).str.lower().str.contains(busqueda_actual.lower(), regex=False)
                | alumnos_list["Número de Matrícula"].astype(str).str.contains(busqueda_actual, regex=False)
            ].reset_index(drop=True)

        excel_bytes_detallado = _generar_excel_listado_alumnos(listado_filtrado, df_completo, busqueda=busqueda_actual)
        st.download_button(
            "Descargar listado de alumnos (Excel)",
            data=excel_bytes_detallado,
            file_name="Listado_Detallado_Alumnos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            on_click=db_pia.log_export_callback,
            args=("Listado Alumnos Detallado", "Excel"),
        )
