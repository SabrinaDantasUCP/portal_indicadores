import io
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

import modules.rend_acad_alumno as raa
from services.data.alumnos import load_current_alumnos
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

    tab_resumen, tab_listado = st.tabs(["Por periodo y semestre", "Listado de alumnos"])

    with tab_resumen:
        render_titulo_seccion("Alumnos por periodo", "Total de alumnos distintos en cada periodo lectivo.")
        st.plotly_chart(_grafico_por_periodo(period_summary), use_container_width=True, config={"displayModeBar": False})

        render_titulo_seccion(
            "Alumnos por semestre y periodo",
            "Cada color sigue a una misma cohorte: en diagonal se ve cómo un grupo avanza un semestre "
            "por periodo. La fila TOTAL coincide con el gráfico de arriba.",
        )
        st.markdown(_matriz_html(matriz, period_summary), unsafe_allow_html=True)

    with tab_listado:
        _render_listado(alumnos_list, df_completo)

    st.divider()
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
