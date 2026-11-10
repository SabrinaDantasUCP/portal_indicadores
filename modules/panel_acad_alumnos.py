import datetime
import io
import os
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st
import xlsxwriter

import modules.rend_acad_alumno as raa
from services.data.alumnos import load_current_alumnos, load_alumnos_documentos
from utils.data_loader import get_current_version, get_data_path
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

    # Deduplicar tempranamente reduce las ~362.000 filas de asignaturas a ~56.000
    # registros únicos de (alumno, periodo, semestre) antes de convertir tipos.
    prepared = df[required_cols].drop_duplicates().copy()
    prepared[COL_PERIODO] = pd.to_numeric(prepared[COL_PERIODO], errors="coerce")
    prepared[COL_SUBPERIODO] = pd.to_numeric(prepared[COL_SUBPERIODO], errors="coerce")
    prepared[COL_SEMESTRE] = pd.to_numeric(prepared[COL_SEMESTRE], errors="coerce")
    prepared = prepared.dropna(subset=[COL_ID_ALUMNO, COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE])
    prepared[COL_PERIODO] = prepared[COL_PERIODO].astype(int)
    prepared[COL_SUBPERIODO] = prepared[COL_SUBPERIODO].astype(int)
    prepared[COL_SEMESTRE] = prepared[COL_SEMESTRE].astype(int)
    prepared = prepared[prepared[COL_SEMESTRE].between(1, 12)].copy()
    prepared["Periodo"] = prepared[COL_PERIODO].astype(str) + "." + prepared[COL_SUBPERIODO].astype(str)
    prepared = (
        prepared.drop_duplicates(
            subset=[COL_ID_ALUMNO, COL_CATRACA, COL_NOMBRE, COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE, "Periodo"]
        )
        .sort_values([COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE])
        .reset_index(drop=True)
    )
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
    cols_base = [COL_ID_ALUMNO, "Número de Matrícula", "Nombre y Apellido", "Periodo", "Semestre", COL_PERIODO, COL_SUBPERIODO]
    return latest[cols_base].sort_values(
        ["Nombre y Apellido", "Número de Matrícula"]
    ).reset_index(drop=True)


def _filtrar_alumnos(df_preparado, periodo="Todos", semestre="Todos", busqueda=""):
    """Filtra los alumnos según el periodo lectivo, semestre y/o término de búsqueda (nombre o matrícula).

    Reglas institucionales de selección:
    - Periodo != 'Todos' y Semestre != 'Todos': alumnos matriculados en ese periodo y semestre específico.
    - Periodo != 'Todos' y Semestre == 'Todos': alumnos matriculados en ese periodo (su último semestre en ese periodo).
    - Periodo == 'Todos' y Semestre != 'Todos': alumnos que cursaron ese semestre (su periodo más reciente en dicho semestre).
    - Periodo == 'Todos' y Semestre == 'Todos': último periodo y semestre registrado de cada alumno en la institución.
    - Búsqueda por texto: filtro insensible a mayúsculas/minúsculas por nombre o matrícula.
    """
    registros = df_preparado

    if periodo != "Todos":
        registros = registros[registros["Periodo"] == str(periodo)]

    if semestre != "Todos":
        try:
            num_sem = int(str(semestre).replace("º", "").strip())
            registros = registros[registros[COL_SEMESTRE] == num_sem]
        except (ValueError, TypeError):
            pass

    alumnos_unicos = (
        registros.sort_values([COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE])
        .drop_duplicates(subset=[COL_ID_ALUMNO], keep="last")
        .rename(
            columns={
                COL_CATRACA: "Número de Matrícula",
                COL_NOMBRE: "Nombre y Apellido",
                COL_SEMESTRE: "Semestre",
            }
        )
    )

    if busqueda:
        b_clean = busqueda.strip().lower()
        alumnos_unicos = alumnos_unicos[
            alumnos_unicos["Nombre y Apellido"].astype(str).str.lower().str.contains(b_clean, regex=False)
            | alumnos_unicos["Número de Matrícula"].astype(str).str.contains(b_clean, regex=False)
        ]

    cols_retorno = [
        COL_ID_ALUMNO,
        "Número de Matrícula",
        "Nombre y Apellido",
        "Periodo",
        "Semestre",
        COL_PERIODO,
        COL_SUBPERIODO,
    ]
    return alumnos_unicos[cols_retorno].sort_values(
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


def _render_listado(df_preparado, df_completo, periodos_disponibles):
    """Listado paginado de alumnos con filtros integrados de búsqueda, periodo y semestre,
    y botón 'Ver historial académico' por estudiante."""
    opciones_periodo = ["Todos"] + list(periodos_disponibles)
    opciones_semestre = ["Todos"] + [f"{s}º" for s in SEMESTRES]

    col_busqueda, col_periodo, col_semestre, col_info = st.columns([2.3, 1.2, 1.0, 1.5], vertical_alignment="bottom")

    busqueda = col_busqueda.text_input(
        "Buscar alumno", placeholder="Nombre o número de matrícula", key="alumnos_busqueda",
    ).strip()

    periodo_sel = col_periodo.selectbox(
        "Periodo", opciones_periodo, key="alumnos_filtro_periodo",
    )

    semestre_sel = col_semestre.selectbox(
        "Semestre", opciones_semestre, key="alumnos_filtro_semestre",
    )

    listado = _filtrar_alumnos(df_preparado, periodo=periodo_sel, semestre=semestre_sel, busqueda=busqueda)

    # Detalle explicativo según filtros activos
    detalles_caption = []
    if periodo_sel != "Todos":
        detalles_caption.append(f"periodo {periodo_sel}")
    if semestre_sel != "Todos":
        detalles_caption.append(f"semestre {semestre_sel}")
    if busqueda:
        detalles_caption.append(f'búsqueda "{busqueda}"')

    if not detalles_caption:
        texto_caption = f"{formatear_entero(len(listado))} alumno(s) · último periodo y semestre de cada uno"
    else:
        texto_caption = f"{formatear_entero(len(listado))} alumno(s) · {' · '.join(detalles_caption)}"

    col_info.caption(texto_caption)

    if listado.empty:
        st.info("No se encontraron alumnos con los filtros seleccionados.")
        return listado

    # Paginación: vuelve a la página 1 cuando cambia cualquiera de los filtros
    total_paginas = max(1, (len(listado) - 1) // ALUMNOS_POR_PAGINA + 1)
    clave_filtros = (busqueda.lower(), str(periodo_sel), str(semestre_sel))
    if st.session_state.get("alumnos_filtros_anteriores") != clave_filtros:
        st.session_state["alumnos_filtros_anteriores"] = clave_filtros
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
                datos_completos = df_completo if df_completo is not None else load_current_alumnos()
                _mostrar_rendimiento(fila[COL_ID_ALUMNO], datos_completos)

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

    return listado


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


@st.cache_resource(max_entries=4, show_spinner=False)
def _obtener_estructuras_base_alumnos(version_activa, mtime_archivo):
    """Precalcula y almacena en caché las estructuras base del módulo de Alumnos
    ligadas a la versión activa y a la fecha de modificación del archivo parquet.
    Evita reprocesar las ~362.000 filas en cada cambio de pestaña, filtro o página.
    """
    df_completo = load_current_alumnos()
    if df_completo.empty:
        return {"vacio": True}

    df_prep, missing_cols = _prepare_alumnos(df_completo)
    if missing_cols:
        return {"vacio": False, "missing_cols": missing_cols}

    period_summary = _build_period_summary(df_prep)
    matriz = _build_matriz(df_prep, period_summary)
    periodos_disponibles = period_summary["Periodo"].tolist()[::-1]
    alumnos_list = _build_alumnos_list(df_prep)
    total_alumnos_unicos = int(df_prep[COL_ID_ALUMNO].nunique())
    html_matriz = _matriz_html(matriz, period_summary)
    fig_periodo = _grafico_por_periodo(period_summary)

    return {
        "vacio": False,
        "missing_cols": [],
        "df_preparado": df_prep,
        "period_summary": period_summary,
        "matriz": matriz,
        "periodos_disponibles": periodos_disponibles,
        "alumnos_list": alumnos_list,
        "total_alumnos_unicos": total_alumnos_unicos,
        "html_matriz": html_matriz,
        "fig_periodo": fig_periodo,
        "total_registros_raw": len(df_completo),
    }


@st.cache_data(show_spinner="Generando Excel...")
def _generate_excel_bytes(_period_summary, _matriz, _alumnos_list, version_tag=""):
    buffer = io.BytesIO()
    opciones_motor = {"strings_to_urls": False, "strings_to_formulas": False}
    with pd.ExcelWriter(buffer, engine="xlsxwriter", engine_kwargs={"options": opciones_motor}) as writer:
        libro = writer.book

        # Formatos institucionales
        fmt_cabecera = libro.add_format({
            "bold": True,
            "font_size": 10,
            "font_color": "#FFFFFF",
            "bg_color": "#1B365D",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#334E68",
            "font_name": "Calibri",
        })
        fmt_cebra_blanco = libro.add_format({
            "bg_color": "#FFFFFF",
            "border": 1,
            "border_color": "#E2E8F0",
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "vcenter",
        })
        fmt_cebra_color = libro.add_format({
            "bg_color": "#F8FAFC",
            "border": 1,
            "border_color": "#E2E8F0",
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "vcenter",
        })
        fmt_centro_blanco = libro.add_format({
            "bg_color": "#FFFFFF",
            "border": 1,
            "border_color": "#E2E8F0",
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "vcenter",
            "align": "center",
        })
        fmt_centro_color = libro.add_format({
            "bg_color": "#F8FAFC",
            "border": 1,
            "border_color": "#E2E8F0",
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "vcenter",
            "align": "center",
        })
        fmt_num_blanco = libro.add_format({
            "bg_color": "#FFFFFF",
            "border": 1,
            "border_color": "#E2E8F0",
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "vcenter",
            "align": "right",
            "num_format": "#,##0",
        })
        fmt_num_color = libro.add_format({
            "bg_color": "#F8FAFC",
            "border": 1,
            "border_color": "#E2E8F0",
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "vcenter",
            "align": "right",
            "num_format": "#,##0",
        })

        # 1. Hoja "Por Periodo" estilizada
        hoja_p = libro.add_worksheet("Por Periodo")
        hoja_p.set_landscape()
        hoja_p.set_default_row(19)
        df_p = _period_summary[["Periodo", "Alumnos"]].copy()
        hoja_p.write(0, 0, "Periodo", fmt_cabecera)
        hoja_p.write(0, 1, "Alumnos", fmt_cabecera)
        hoja_p.set_row(0, 24)
        for r_idx, fila in enumerate(df_p.itertuples(index=False), start=1):
            f_cen = fmt_centro_color if r_idx % 2 == 0 else fmt_centro_blanco
            f_num = fmt_num_color if r_idx % 2 == 0 else fmt_num_blanco
            hoja_p.write(r_idx, 0, str(fila[0]), f_cen)
            hoja_p.write(r_idx, 1, int(fila[1]), f_num)
        hoja_p.set_column(0, 0, 16)
        hoja_p.set_column(1, 1, 16)
        hoja_p.autofilter(0, 0, len(df_p), 1)
        hoja_p.freeze_panes(1, 0)

        # 2. Hoja "Matriz" con formato por cohorte
        hoja = libro.add_worksheet("Matriz")
        base = {"border": 1, "border_color": "#FFFFFF", "align": "center"}
        f_cab = libro.add_format({**base, "bold": True, "bg_color": COLOR_CABECERA_MATRIZ})
        f_sem = libro.add_format({**base, "bold": True, "bg_color": COLOR_COLUMNA_SEMESTRE})
        f_tot = libro.add_format({**base, "bold": True, "bg_color": COLOR_TOTAL_MATRIZ, "num_format": "#,##0"})
        f_cero = libro.add_format({**base, "font_color": "#BFBFBF"})
        f_color = {c: libro.add_format({**base, "bg_color": c, "num_format": "#,##0"}) for c in COLORES_COHORTE}
        sub_por_periodo = dict(zip(_period_summary["Periodo"], zip(_period_summary[COL_PERIODO], _period_summary[COL_SUBPERIODO])))

        hoja.write(0, 0, "Semestre", f_cab)
        for j, periodo in enumerate(_matriz.columns, start=1):
            hoja.write(0, j, periodo, f_cab)
        for i, (semestre, fila) in enumerate(_matriz.iterrows(), start=1):
            hoja.write(i, 0, semestre, f_sem)
            for j, (periodo, valor) in enumerate(fila.items(), start=1):
                if valor:
                    hoja.write(i, j, int(valor), f_color[_color_cohorte(*sub_por_periodo[periodo], semestre)])
                else:
                    hoja.write(i, j, 0, f_cero)
        fila_total = len(_matriz) + 1
        hoja.write(fila_total, 0, "TOTAL", f_tot)
        for j, valor in enumerate(_period_summary["Alumnos"], start=1):
            hoja.write(fila_total, j, int(valor), f_tot)
        hoja.set_column(0, len(_matriz.columns), 10)

        # 3. Hoja "Listado" estilizada (escritura rápida con itertuples)
        cols_export_list = [c for c in ["Número de Matrícula", "Nombre y Apellido", "Periodo", "Semestre"] if c in _alumnos_list.columns]
        df_l = _alumnos_list[cols_export_list].copy()
        hoja_l = libro.add_worksheet("Listado")
        hoja_l.set_landscape()
        hoja_l.set_default_row(19)
        hoja_l.set_row(0, 24)
        es_col_centrada = [c_nom in ("Número de Matrícula", "Periodo", "Semestre") for c_nom in cols_export_list]
        for c_idx, c_nom in enumerate(cols_export_list):
            hoja_l.write(0, c_idx, c_nom, fmt_cabecera)
        for r_idx, fila in enumerate(df_l.itertuples(index=False), start=1):
            f_txt = fmt_cebra_color if r_idx % 2 == 0 else fmt_cebra_blanco
            f_cen = fmt_centro_color if r_idx % 2 == 0 else fmt_centro_blanco
            for c_idx, valor_celda in enumerate(fila):
                val = str(valor_celda) if pd.notna(valor_celda) else ""
                fmt_usar = f_cen if es_col_centrada[c_idx] else f_txt
                hoja_l.write_string(r_idx, c_idx, val, fmt_usar)
        hoja_l.set_column(0, 0, 22)
        hoja_l.set_column(1, 1, 38)
        hoja_l.set_column(2, 2, 14)
        hoja_l.set_column(3, 3, 14)
        hoja_l.autofilter(0, 0, len(df_l), len(cols_export_list) - 1)
        hoja_l.freeze_panes(1, 0)

    return buffer.getvalue()


@st.cache_data(show_spinner="Generando Excel detallado de alumnos...")
def _generar_excel_listado_alumnos(_alumnos_list, _df_completo, busqueda="", periodo="Todos", semestre="Todos", version_dataset=""):
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
    - Incluye materias académicas cursadas (regulares y extracurriculares de preinternado/guaraní hospitalario) en el periodo lectivo seleccionado.
    - Tope estricto de notas de 0 a 100 puntos y de 1 a 5.
    - Parámetros con guión bajo (_alumnos_list, _df_completo) para evitar sobrecarga de hasheo en caché de Streamlit.
    """
    df_raw = _df_completo
    alumnos_sub = _alumnos_list.copy()

    # Identificar columna de documento si estuviera disponible en el dataset
    col_doc = None
    for col_candidata in ["doc_oficial", "documento", "numero_documento", "cedula", "rg", "dni", "cpf"]:
        if col_candidata in df_raw.columns:
            col_doc = col_candidata
            break

    # Mapeo oficial de documentos (doc_oficial de SysEduca)
    mapa_docs = load_alumnos_documentos()

    # Asegurar columnas de periodo en alumnos_sub antes del cruce
    if "ano_periodo_letivo" not in alumnos_sub.columns or "periodo_anual_periodo_letivo" not in alumnos_sub.columns:
        partes_p = alumnos_sub["Periodo"].astype(str).str.split(".", expand=True)
        alumnos_sub["ano_periodo_letivo"] = pd.to_numeric(partes_p[0], errors="coerce").fillna(0).astype(int)
        alumnos_sub["periodo_anual_periodo_letivo"] = pd.to_numeric(partes_p[1], errors="coerce").fillna(0).astype(int)
    else:
        alumnos_sub["ano_periodo_letivo"] = pd.to_numeric(alumnos_sub["ano_periodo_letivo"], errors="coerce").fillna(0).astype(int)
        alumnos_sub["periodo_anual_periodo_letivo"] = pd.to_numeric(alumnos_sub["periodo_anual_periodo_letivo"], errors="coerce").fillna(0).astype(int)

    # Identificar el conjunto de alumnos y periodos objetivo a exportar
    uids = set(alumnos_sub["usuarios_id"].dropna().unique())
    periodos_objetivo = alumnos_sub[["usuarios_id", "ano_periodo_letivo", "periodo_anual_periodo_letivo"]].drop_duplicates()

    # Filtrar primero por los alumnos requeridos antes de copiar o transformar el dataset completo
    df_raw_prep = df_raw[df_raw["usuarios_id"].isin(uids)].copy()
    if not pd.api.types.is_integer_dtype(df_raw_prep["ano_periodo_letivo"]):
        df_raw_prep["ano_periodo_letivo"] = pd.to_numeric(df_raw_prep["ano_periodo_letivo"], errors="coerce").fillna(0).astype(int)
    if not pd.api.types.is_integer_dtype(df_raw_prep["periodo_anual_periodo_letivo"]):
        df_raw_prep["periodo_anual_periodo_letivo"] = pd.to_numeric(df_raw_prep["periodo_anual_periodo_letivo"], errors="coerce").fillna(0).astype(int)

    # Cruzar primero con los periodos objetivo para reducir filas antes de evaluar strings de disciplina
    df_candidatos = df_raw_prep.merge(
        periodos_objetivo,
        on=["usuarios_id", "ano_periodo_letivo", "periodo_anual_periodo_letivo"],
        how="inner",
    )
    disc_str = df_candidatos["disciplina"].fillna("").astype(str).str.strip()
    materias_filtradas = df_candidatos[
        df_candidatos["tipo_disciplina"].isin(["Regular", "Extracurricular"])
        & (disc_str != "")
        & (disc_str.str.lower() != "nan")
    ].copy()

    pan_reg = materias_filtradas["periodo_anual_periodo_letivo"]
    ano_reg = materias_filtradas["ano_periodo_letivo"]
    materias_filtradas["Periodo_Reg"] = ano_reg.astype(str) + "." + pan_reg.astype(str)
    sem_reg = pd.to_numeric(materias_filtradas["semestre_alumno"], errors="coerce").fillna(0).astype(int)
    mapa_sem_str = {s: f"{s}º" for s in range(1, 25)}
    materias_filtradas["Semestre_Reg"] = sem_reg.map(mapa_sem_str).fillna("")

    cols_materias = [
        "usuarios_id",
        "ano_periodo_letivo",
        "periodo_anual_periodo_letivo",
        "Periodo_Reg",
        "Semestre_Reg",
        "filial_periodo_letivo",
        "disciplina",
        "turma",
        "calificacion_final",
        "calificacion_final_1a5",
        "nombre_status_actual",
    ]
    if col_doc and col_doc in materias_filtradas.columns:
        cols_materias.append(col_doc)

    # Cruce: how='left' sobre alumnos_sub para garantizar que todos los alumnos aparezcan en el Excel
    detalle = alumnos_sub.merge(
        materias_filtradas[cols_materias],
        on=["usuarios_id", "ano_periodo_letivo", "periodo_anual_periodo_letivo"],
        how="left",
    )

    # Vectorización de alto rendimiento
    detalle["Matrícula"] = detalle["Número de Matrícula"].astype(str).str.replace(r"\.0$", "", regex=True)
    uids_int = pd.to_numeric(detalle["usuarios_id"], errors="coerce").fillna(-1).astype(int)
    detalle["Documento"] = uids_int.map(mapa_docs).fillna("")
    if col_doc and col_doc in detalle.columns:
        detalle["Documento"] = detalle["Documento"].where(detalle["Documento"] != "", detalle[col_doc].fillna("").astype(str))

    detalle["Nombre Completo"] = detalle["Nombre y Apellido"].fillna("").astype(str).str.strip()

    # Si algún alumno no tuvo materias regulares en ese periodo, recuperar estado y filial solo para los faltantes
    mask_faltante = detalle["nombre_status_actual"].isna() | detalle["filial_periodo_letivo"].isna()
    if mask_faltante.any():
        uids_faltantes = set(detalle.loc[mask_faltante, "usuarios_id"].dropna().unique())
        ultimos_registros = (
            df_raw_prep[df_raw_prep["usuarios_id"].isin(uids_faltantes)]
            .sort_values(["usuarios_id", "ano_periodo_letivo", "periodo_anual_periodo_letivo"])
            .drop_duplicates(subset=["usuarios_id"], keep="last")
            .set_index("usuarios_id")
        )
        if detalle["nombre_status_actual"].isna().any() and "nombre_status_actual" in ultimos_registros.columns:
            mapa_status_general = ultimos_registros["nombre_status_actual"].to_dict()
            detalle["nombre_status_actual"] = detalle["nombre_status_actual"].fillna(detalle["usuarios_id"].map(mapa_status_general))
        if detalle["filial_periodo_letivo"].isna().any() and "filial_periodo_letivo" in ultimos_registros.columns:
            mapa_filial_general = ultimos_registros["filial_periodo_letivo"].to_dict()
            detalle["filial_periodo_letivo"] = detalle["filial_periodo_letivo"].fillna(detalle["usuarios_id"].map(mapa_filial_general))

    detalle["Estado de Matrícula"] = detalle["nombre_status_actual"].fillna("–").astype(str).str.strip().replace(["nan", ""], "–")
    detalle["Periodo"] = detalle["Periodo_Reg"].fillna(detalle["Periodo"]).astype(str)

    sem_str = detalle["Semestre"].fillna("").astype(str)
    sem_formateado = sem_str.where(sem_str.str.endswith("º") | (sem_str == ""), sem_str + "º")
    detalle["Semestre"] = detalle["Semestre_Reg"].where(detalle["Semestre_Reg"].notna() & (detalle["Semestre_Reg"] != ""), sem_formateado).astype(str)

    detalle["Sede"] = detalle["filial_periodo_letivo"].fillna("").astype(str).replace("nan", "")
    detalle["Materia"] = detalle["disciplina"].fillna("–").astype(str).replace("nan", "–")
    detalle["Sección"] = detalle["turma"].fillna("–").astype(str).replace("nan", "–")

    # Notas vectorizadas con tope estricto de 0 a 100
    n100 = pd.to_numeric(detalle["calificacion_final"], errors="coerce").clip(lower=0, upper=100)
    detalle["Nota (1 a 100)"] = [
        (int(v) if v == int(v) else round(float(v), 1)) if pd.notna(v) else None
        for v in n100.to_numpy()
    ]
    detalle["Nota (1 a 100)"] = detalle["Nota (1 a 100)"].astype(object)

    # Notas 1 a 5 aseguradas en rango 1 a 5
    n5 = pd.to_numeric(detalle["calificacion_final_1a5"], errors="coerce").fillna(0).astype(int).clip(upper=5)
    detalle["Nota (1 a 5)"] = n5.map({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}).fillna("–").astype(object)

    # Alumnos con matrícula lanzada pero sin materias registradas en el periodo lectivo
    es_sin_materias = detalle["disciplina"].isna() | (detalle["disciplina"].astype(str).str.strip().isin(["", "nan", "–"]))
    detalle.loc[es_sin_materias, "Materia"] = "Matrícula lanzada / Sin materias"
    detalle.loc[es_sin_materias, "Sección"] = "Sin sección"
    detalle.loc[es_sin_materias, "Nota (1 a 100)"] = "Sin nota"
    detalle.loc[es_sin_materias, "Nota (1 a 5)"] = "Sin nota"

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
    workbook = xlsxwriter.Workbook(
        buffer,
        {"in_memory": True, "strings_to_urls": False, "strings_to_formulas": False},
    )
    worksheet = workbook.add_worksheet("Listado de Alumnos")

    worksheet.hide_gridlines(False)
    worksheet.set_paper(9)  # Formato A4
    worksheet.set_landscape()
    worksheet.set_default_row(19)

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

    # Encabezado institucional superior con filtros y fecha integrados
    worksheet.write(0, 0, "REPORTE DETALLADO - LISTADO DE ALUMNOS", fmt_titulo)
    worksheet.set_row(0, 24)

    ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    filtros_aplicados = []
    if periodo != "Todos":
        filtros_aplicados.append(f"Periodo: {periodo}")
    if semestre != "Todos":
        filtros_aplicados.append(f"Semestre: {semestre}")
    if busqueda:
        filtros_aplicados.append(f'Búsqueda: "{busqueda}"')

    if filtros_aplicados:
        subtitulo_con_fecha = (
            f"Portal de Indicadores Académicos · Sistema de Gestión Institucional - "
            f"Filtros: {', '.join(filtros_aplicados)} · Fecha y hora de generación: {ahora}"
        )
    else:
        subtitulo_con_fecha = (
            f"Portal de Indicadores Académicos · Sistema de Gestión Institucional - "
            f"Fecha y hora de generación: {ahora}"
        )

    worksheet.write(1, 0, subtitulo_con_fecha, fmt_subtitulo)
    worksheet.set_row(1, 18)
    worksheet.set_row(2, 10)

    fila_inicio_tabla = 3
    worksheet.set_row(fila_inicio_tabla, 26)

    for col_idx, encabezado in enumerate(cols_finales):
        worksheet.write(fila_inicio_tabla, col_idx, encabezado, fmt_cabecera)

    worksheet.freeze_panes(fila_inicio_tabla + 1, 0)

    alineaciones = ["centro", "centro", "izq", "centro", "centro", "centro", "centro", "izq", "centro", "der", "centro"]

    # Escritura ultra-rápida con itertuples
    for i, row in enumerate(df_export.itertuples(index=False)):
        fila_idx = fila_inicio_tabla + 1 + i
        prefijo = "par_" if i % 2 == 1 else "impar_"

        for col_idx, valor in enumerate(row):
            # Para notas en formato texto (ej. 'Sin nota'), alinear al centro
            alineacion_celda = "centro" if col_idx == 9 and not isinstance(valor, (int, float)) else alineaciones[col_idx]
            fmt = fmt_datos[prefijo + alineacion_celda]
            if valor is None or valor == "" or (isinstance(valor, float) and pd.isna(valor)):
                worksheet.write_blank(fila_idx, col_idx, "", fmt)
            elif isinstance(valor, (int, float)):
                worksheet.write_number(fila_idx, col_idx, valor, fmt)
            else:
                worksheet.write_string(fila_idx, col_idx, str(valor), fmt)

    worksheet.autofilter(fila_inicio_tabla, 0, fila_inicio_tabla + len(df_export), len(cols_finales) - 1)

    # Anchos predimensionados para máximo rendimiento
    anchos_optimos = [14, 18, 36, 18, 12, 12, 14, 40, 14, 16, 14]
    for col_idx, ancho in enumerate(anchos_optimos):
        worksheet.set_column(col_idx, col_idx, ancho)

    workbook.close()
    return buffer.getvalue()


UMBRAL_EXCEL_INMEDIATO = 250


def _excel_listado_bajo_demanda(
    listado_exportar,
    busqueda_actual,
    periodo_actual,
    semestre_actual,
    version_actual_tag,
    nombre_archivo,
):
    """Gestiona la exportación del Excel detallado del Listado de Alumnos:
    - Cuando el filtro tiene <= 250 alumnos (ej. búsqueda o semestre específico) o ya fue
      preparado para el filtro actual, muestra directamente el botón de descarga inmediata.
    - Cuando el listado abarca miles de alumnos (ej. Periodo='Todos' con ~62.000 filas de
      asignaturas), evita bloquear la navegación y el filtrado de la vista mostrando primero
      'Preparar listado de alumnos (Excel)' y luego 'Descargar listado de alumnos (Excel)'.
    """
    firma = (
        version_actual_tag,
        str(periodo_actual),
        str(semestre_actual),
        busqueda_actual.lower(),
        len(listado_exportar),
    )
    clave_estado = "alumnos_excel_listado_preparado"
    estado = st.session_state.get(clave_estado)

    if len(listado_exportar) <= UMBRAL_EXCEL_INMEDIATO:
        df_completo = load_current_alumnos()
        bytes_excel = _generar_excel_listado_alumnos(
            listado_exportar,
            df_completo,
            busqueda=busqueda_actual,
            periodo=periodo_actual,
            semestre=semestre_actual,
            version_dataset=version_actual_tag,
        )
        st.download_button(
            "Descargar listado de alumnos (Excel)",
            data=bytes_excel,
            file_name=nombre_archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            key="btn_descargar_excel_listado_inmediato",
            on_click=db_pia.log_export_callback,
            args=("Listado Alumnos Detallado", "Excel"),
        )
        return

    if estado and estado[0] == firma and estado[1]:
        st.download_button(
            "Descargar listado de alumnos (Excel)",
            data=estado[1],
            file_name=nombre_archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            width="stretch",
            key="btn_descargar_excel_listado_preparado",
            on_click=db_pia.log_export_callback,
            args=("Listado Alumnos Detallado", "Excel"),
        )
    elif st.button(
        "Preparar listado de alumnos (Excel)",
        icon=":material/table_view:",
        width="stretch",
        key="btn_preparar_excel_listado",
    ):
        df_completo = load_current_alumnos()
        bytes_excel = _generar_excel_listado_alumnos(
            listado_exportar,
            df_completo,
            busqueda=busqueda_actual,
            periodo=periodo_actual,
            semestre=semestre_actual,
            version_dataset=version_actual_tag,
        )
        st.session_state[clave_estado] = (firma, bytes_excel)
        st.rerun()


def render():
    render_cabecera_indicador(
        "Alumnos",
        "Cantidad de alumnos (ID únicos) por periodo y por semestre. Cada alumno se cuenta una sola "
        "vez por periodo, en el semestre que cursaba.",
    )

    version_activa = get_current_version()
    ruta_parquet = get_data_path("alumnos", version_activa)
    mtime_archivo = os.path.getmtime(ruta_parquet) if os.path.exists(ruta_parquet) else 0

    estructuras = _obtener_estructuras_base_alumnos(version_activa, mtime_archivo)
    if estructuras.get("vacio"):
        st.error("Archivo de alumnos no encontrado o vacío.")
        return

    missing_cols = estructuras.get("missing_cols", [])
    if missing_cols:
        st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
        return

    df = estructuras["df_preparado"]
    period_summary = estructuras["period_summary"]
    matriz = estructuras["matriz"]
    periodos_disponibles = estructuras["periodos_disponibles"]
    alumnos_list = estructuras["alumnos_list"]
    total_alumnos_unicos = estructuras["total_alumnos_unicos"]
    html_matriz = estructuras["html_matriz"]
    fig_periodo = estructuras["fig_periodo"]
    total_registros_raw = estructuras["total_registros_raw"]

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
        {"etiqueta": "Alumnos distintos", "valor": formatear_entero(total_alumnos_unicos),
         "detalle": "En todo el periodo analizado"},
        {"etiqueta": "Periodos", "valor": len(period_summary),
         "detalle": f"De {period_summary['Periodo'].iloc[0]} a {ultimo['Periodo']}"},
        {"etiqueta": f"Alumnos en {ultimo['Periodo']}", "valor": formatear_entero(ultimo["Alumnos"]),
         "detalle": "Último periodo"},
        kpi_variacion,
    ])

    # Selector de vista guardado en la sesión
    vistas = ["Por periodo y semestre", "Listado de alumnos"]
    vista = st.segmented_control(
        "Vista", vistas, default=vistas[0], key="alumnos_vista", label_visibility="collapsed",
    ) or vistas[0]

    listado_actual = None
    if vista == vistas[0]:
        render_titulo_seccion("Alumnos por periodo", "Total de alumnos distintos en cada periodo lectivo.")
        st.plotly_chart(fig_periodo, use_container_width=True, config={"displayModeBar": False})

        render_titulo_seccion(
            "Alumnos por semestre y periodo",
            "Cada color sigue a una misma cohorte: en diagonal se ve cómo un grupo avanza un semestre "
            "por periodo. La fila TOTAL coincide con el gráfico de arriba.",
        )
        st.markdown(html_matriz, unsafe_allow_html=True)
    else:
        listado_actual = _render_listado(df, None, periodos_disponibles)

    st.divider()
    if vista == vistas[0]:
        cols_export_list = [c for c in ["Número de Matrícula", "Nombre y Apellido", "Periodo", "Semestre"] if c in alumnos_list.columns]
        tag_vistas = f"{version_activa}_{mtime_archivo}_{total_registros_raw}"
        excel_bytes = _generate_excel_bytes(
            period_summary, matriz, alumnos_list[cols_export_list], version_tag=tag_vistas
        )
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
        periodo_actual = st.session_state.get("alumnos_filtro_periodo", "Todos")
        semestre_actual = st.session_state.get("alumnos_filtro_semestre", "Todos")

        listado_exportar = (
            listado_actual
            if listado_actual is not None
            else _filtrar_alumnos(
                df,
                periodo=periodo_actual,
                semestre=semestre_actual,
                busqueda=busqueda_actual,
            )
        )

        if not listado_exportar.empty:
            version_actual_tag = f"{version_activa}_{mtime_archivo}_{total_registros_raw}_{len(listado_exportar)}"
            partes_nombre = ["Listado_Alumnos"]
            if periodo_actual != "Todos":
                partes_nombre.append(str(periodo_actual))
            if semestre_actual != "Todos":
                partes_nombre.append(f"Sem{str(semestre_actual).replace('º', '')}")
            nombre_archivo = "_".join(partes_nombre) + ".xlsx"

            _excel_listado_bajo_demanda(
                listado_exportar=listado_exportar,
                busqueda_actual=busqueda_actual,
                periodo_actual=periodo_actual,
                semestre_actual=semestre_actual,
                version_actual_tag=version_actual_tag,
                nombre_archivo=nombre_archivo,
            )
