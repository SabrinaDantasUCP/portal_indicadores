import io
import os
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from utils import db_pia
from utils.system_logging import log_exception
from utils.ui import render_kpi_card
from services.data.encuestas import (
    TIPO_AUTOEVALUACION_DOCENTE,
    get_encuesta_nombre,
    listar_carreras_encuesta,
    listar_periodos_encuestas,
    listar_sedes_encuestas,
    listar_tipos_encuesta,
    load_autoeval_docente_detalle,
    load_autoeval_docente_general,
    load_encuestas_alumnos,
    load_encuestas_detalle,
    load_encuestas_general,
    load_encuestas_metadata,
)


@st.cache_data(show_spinner=False, max_entries=8, ttl=600)
def excel_bytes_reporte(tablas: dict):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for nombre, df in tablas.items():
            df.to_excel(writer, index=False, sheet_name=nombre[:31])
    return buffer.getvalue()


def _fmt_num(value):
    try:
        return f"{int(round(float(value))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "-"


def _fmt_pct(value):
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "-"


def render_common_setup():
    st.markdown(
        """
        <style>
        [data-testid="stElementToolbar"] { display: none; }
        div[data-testid="stDownloadButton"] button {
            min-height: 50px !important;
            font-size: 16px !important;
            border-radius: 8px !important;
        }
        .enc_header {
            background: linear-gradient(90deg, #1e3a8a 0%, #4b8cd9 100%);
            color: white;
            padding: 18px 26px;
            border-radius: 10px;
            margin: 10px 0 25px 0;
            box-shadow: 0 2px 5px rgba(0,0,0,.15);
        }
        .enc_header_title { font-size: 32px; font-weight: 800; line-height: 1.2; margin: 0; }
        .enc_header_vigencia { font-size: 17px; opacity: .92; margin-top: 6px; }
        .enc_header_sub { font-size: 14px; opacity: .8; margin-top: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _limpiar_periodo_carrera_tipo():
    st.session_state["encuestas_periodo"] = None
    st.session_state["encuestas_carrera"] = None
    st.session_state["encuestas_tipo"] = None


def _limpiar_carrera_tipo():
    st.session_state["encuestas_carrera"] = None
    st.session_state["encuestas_tipo"] = None


def _limpiar_tipo():
    st.session_state["encuestas_tipo"] = None


def select_encuesta():
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            sede = st.selectbox(
                "Sede",
                options=listar_sedes_encuestas(),
                index=None,
                placeholder="Elija una sede...",
                key="encuestas_sede",
                on_change=_limpiar_periodo_carrera_tipo,
            )
        with c2:
            periodos_opts = listar_periodos_encuestas(sede) if sede else []
            periodo = st.selectbox(
                "Periodo",
                options=periodos_opts,
                index=None,
                placeholder="Elija un periodo...",
                key="encuestas_periodo",
                disabled=not sede,
                on_change=_limpiar_carrera_tipo,
            )

        c3, c4 = st.columns(2)
        with c3:
            carreras_opts = listar_carreras_encuesta(sede, periodo) if sede and periodo else []
            carrera = st.selectbox(
                "Carrera",
                options=carreras_opts,
                index=None,
                placeholder="Elija una carrera...",
                key="encuestas_carrera",
                disabled=not (sede and periodo),
                on_change=_limpiar_tipo,
            )
        with c4:
            tipos_opts = (
                listar_tipos_encuesta(sede, periodo, carrera) if sede and periodo and carrera else []
            )
            tipo = st.selectbox(
                "Encuesta",
                options=[t for t, _ in tipos_opts],
                index=None,
                placeholder="Elija una encuesta...",
                key="encuestas_tipo",
                disabled=not (sede and periodo and carrera),
                format_func=lambda t: dict(tipos_opts).get(t, t),
            )

    if not sede:
        st.info("Seleccione la **sede** que desea visualizar para continuar.")
    elif not periodo:
        st.info("Seleccione el **periodo** que desea visualizar para continuar.")
    elif not carrera:
        st.info("Seleccione la **carrera** que desea visualizar para continuar.")
    elif not tipo:
        st.info("Seleccione la **encuesta** que desea visualizar para continuar.")
    return sede, periodo, carrera, tipo


def _render_encabezado_encuesta(nombre, vigencia, semestres_habilitados, sede, carrera):
    vigencia_txt = vigencia if vigencia else "vigencia no disponible"
    semestres_html = (
        f'<div class="enc_header_sub">Semestres habilitados: {escape(str(semestres_habilitados))}</div>'
        if semestres_habilitados
        else ""
    )
    st.markdown(
        f"""
        <div class="enc_header">
            <div class="enc_header_title">{escape(str(nombre))}</div>
            <div class="enc_header_vigencia">({escape(str(vigencia_txt))})</div>
            <div class="enc_header_sub">{escape(sede)} · {escape(carrera)}</div>
            {semestres_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render():
    render_common_setup()
    sede, periodo, carrera, tipo = select_encuesta()
    if not sede or not periodo or not carrera or not tipo:
        return

    if tipo == TIPO_AUTOEVALUACION_DOCENTE:
        render_autoeval_docente(sede, periodo, carrera, tipo)
        return

    fila_general = load_encuestas_general(sede, periodo, carrera, tipo)
    df_detalle = load_encuestas_detalle(sede, periodo, carrera, tipo)
    df_alumnos = load_encuestas_alumnos(sede, periodo, carrera, tipo)

    if fila_general is None and df_detalle.empty:
        st.warning(f"No hay datos disponibles para la Encuesta {periodo} — {tipo}.")
        return

    nombre = get_encuesta_nombre(sede, periodo, carrera, tipo)
    vigencia, semestres_habilitados = load_encuestas_metadata(sede, periodo, carrera, tipo)
    _render_encabezado_encuesta(nombre, vigencia, semestres_habilitados, sede, carrera)

    tab_general, tab_detalle = st.tabs(["Visión General", "Detalle por Materia / Sección / Grupo"])

    with tab_general:
        render_vision_general(fila_general)

    with tab_detalle:
        render_detalle(df_detalle, df_alumnos, periodo, tipo)


def render_autoeval_docente(sede, periodo, carrera, tipo):
    fila_general = load_autoeval_docente_general(sede, periodo, carrera, tipo)
    df_detalle_docente = load_autoeval_docente_detalle(sede, periodo, carrera, tipo)

    if fila_general is None and df_detalle_docente.empty:
        st.warning(f"No hay datos disponibles para la Encuesta {periodo} — {tipo}.")
        return

    nombre = get_encuesta_nombre(sede, periodo, carrera, tipo)
    vigencia, semestres_habilitados = load_encuestas_metadata(sede, periodo, carrera, tipo)
    _render_encabezado_encuesta(nombre, vigencia, semestres_habilitados, sede, carrera)

    tab_general, tab_detalle = st.tabs(["Visión General", "Detalle por Materia / Sección / Grupo / Docente"])

    with tab_general:
        render_vision_general(
            fila_general,
            entidad="Docentes",
            columnas={
                "esperados": "docentes_unicos_esperados",
                "respondieron_todas": "docentes_unicos_que_respondieron_todas",
                "pct_todas": "porcentaje_avance_docentes_todas",
                "respondieron_al_menos_una": "docentes_unicos_que_respondieron_al_menos_una",
                "pct_al_menos_una": "porcentaje_avance_docentes",
            },
        )

    with tab_detalle:
        render_detalle_autoeval_docente(df_detalle_docente, periodo, tipo)


def _valor_valido(valor):
    try:
        return valor is not None and not pd.isna(valor)
    except TypeError:
        return valor is not None


_PIE_HEIGHT = 380


def _pie_avance(respondieron, esperados, key):
    pendientes = max(esperados - respondieron, 0)
    df_pie = pd.DataFrame({"Estado": ["Respondieron", "Pendientes"], "Valor": [respondieron, pendientes]})
    fig = px.pie(
        df_pie, names="Estado", values="Valor", hole=0.6, color="Estado",
        color_discrete_map={"Respondieron": "#388e3c", "Pendientes": "#d32f2f"},
    )
    fig.update_traces(
        textinfo="percent",
        textposition="outside",
        texttemplate="%{percent}",
        textfont=dict(size=18, color="#222222"),
        marker=dict(line=dict(color="#ffffff", width=2)),
        # Encoge el círculo dentro del área de la figura (coordenadas relativas,
        # no píxeles) para reservar siempre espacio a las etiquetas externas,
        # sin importar el ancho real del contenedor en Streamlit.
        domain=dict(x=[0.18, 0.82], y=[0.1, 0.95]),
    )
    fig.update_layout(
        height=_PIE_HEIGHT,
        legend=dict(font=dict(size=14), orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        margin=dict(t=10, b=10, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


def _pie_placeholder():
    st.markdown(
        f"""
        <div style="
            height: {_PIE_HEIGHT}px;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            border: 2px dashed #cccccc;
            border-radius: 12px;
            color: #999999;
            font-size: 14px;
            margin-top: 8px;
        ">
            Gráfico disponible cuando<br>este dato esté cargado
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_total_esperados(label, value):
    st.markdown(
        f"""
        <div style="
            width: 100%;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 18px 24px;
            margin-bottom: 10px;
            box-sizing: border-box;
        ">
            <div style="font-size: 13px; text-transform: uppercase; letter-spacing: .03em; color: #888888; font-weight: 600;">
                {escape(label)}
            </div>
            <div style="font-size: 32px; font-weight: 800; color: #666666; line-height: 1.2;">{escape(str(value))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _bloque_avance(titulo, cantidad, pct, esperados, key_prefix, accent, background, border, entidad="Alumnos"):
    with st.container(border=True):
        st.markdown(f"**{titulo}**")
        c1, c2 = st.columns(2)
        with c1:
            render_kpi_card(entidad, _fmt_num(cantidad), accent=accent, background=background, border=border)
        with c2:
            render_kpi_card("% de Avance", _fmt_pct(pct), accent=accent, background=background, border=border)

        if _valor_valido(cantidad) and _valor_valido(esperados) and float(esperados) > 0:
            _pie_avance(float(cantidad), float(esperados), key=f"{key_prefix}_pie")
        else:
            _pie_placeholder()


# Mapeo por defecto de columnas de la fila general (avance_general), para
# la encuesta de alumnos a docentes. render_vision_general recibe otro mapeo
# para orígenes con otra entidad (p. ej. autoevaluación docente, donde la
# entidad es "Docentes" en vez de "Alumnos" y las columnas del CSV llevan
# el prefijo "docentes_").
_COLUMNAS_VISION_GENERAL_ALUMNOS = {
    "esperados": "alumnos_unicos_esperados",
    "respondieron_todas": "alumnos_unicos_que_respondieron_todas",
    "pct_todas": "porcentaje_avance_alumnos_todas",
    "respondieron_al_menos_una": "alumnos_unicos_que_respondieron_al_menos_una",
    "pct_al_menos_una": "porcentaje_avance_alumnos",
}


def render_vision_general(fila_general, entidad="Alumnos", columnas=None):
    columnas = columnas or _COLUMNAS_VISION_GENERAL_ALUMNOS

    if fila_general is None:
        st.warning("No se encontró la fila de avance general en el archivo de la encuesta.")
        return

    esperados = fila_general.get(columnas["esperados"])

    st.markdown(f"#### Avance de {entidad}")
    _render_total_esperados(f"{entidad} que debían responder", _fmt_num(esperados))

    b1, b2 = st.columns(2)
    with b1:
        _bloque_avance(
            "1. Respondieron todas sus encuestas",
            fila_general.get(columnas["respondieron_todas"]),
            fila_general.get(columnas["pct_todas"]),
            esperados,
            key_prefix="enc_todas",
            accent="#385623", background="#e2efd9", border="#a9d08e",
            entidad=entidad,
        )
    with b2:
        _bloque_avance(
            "2. Respondieron al menos una encuesta",
            fila_general.get(columnas["respondieron_al_menos_una"]),
            fila_general.get(columnas["pct_al_menos_una"]),
            esperados,
            key_prefix="enc_al_menos_una",
            accent="#1e3a8a", background="#e8f0fe", border="#a9c6f5",
            entidad=entidad,
        )


# (clave de la pestaña, columnas a agrupar -acumulativas-, etiquetas de esas
# columnas, modo de cálculo). Cada nivel suma la columna anterior: Sección
# incluye Materia, Grupo incluye Materia+Sección, Docente incluye
# Materia+Sección+Grupo.
# - "distinct": cuenta alumnos únicos (por system_id) sobre el detalle a nivel
#   de alumno (avance_por_alumno), evitando contar dos veces a un mismo
#   alumno cuando aparece en más de un grupo/docente de la misma materia.
# - "docente": según el origen (ver tiene_docente_detalle/tiene_docente_alumno
#   en render_detalle), se resuelve con el detalle por materia/sección/grupo/
#   docente pre-agregado cuando existe (p. ej. v1), o por distinct de alumno
#   sobre la columna "docente" del detalle por alumno cuando sólo está ahí
#   (p. ej. v2, que no trae ese indicador agregado).
TABLAS_AVANCE = [
    ("Materia", ["materia"], ["Materia"], "distinct"),
    ("Sección", ["materia", "seccion"], ["Materia", "Sección"], "distinct"),
    ("Grupo", ["materia", "seccion", "grupo"], ["Materia", "Sección", "Grupo"], "distinct"),
    ("Docente", ["materia", "seccion", "grupo", "docente"], ["Materia", "Sección", "Grupo", "Docente"], "docente"),
]


def _tabla_avance(base, cols, labels):
    df_res = (
        base.groupby(cols, as_index=False)
        .agg(
            alumnos_esperados=("alumnos_esperados", "sum"),
            alumnos_que_respondieron=("alumnos_que_respondieron", "sum"),
        )
    )
    df_res["% de Avance"] = (
        (df_res["alumnos_que_respondieron"] / df_res["alumnos_esperados"] * 100).round(2).fillna(0)
    )
    rename_map = dict(zip(cols, labels))
    rename_map.update({
        "alumnos_esperados": "Alumnos Esperados",
        "alumnos_que_respondieron": "Alumnos que Respondieron",
    })
    df_res = df_res.rename(columns=rename_map)
    return df_res.sort_values(labels).reset_index(drop=True)


def _tabla_avance_distinct(df, cols, labels, id_col="system_id", entidad="Alumnos"):
    """Igual que _tabla_avance, pero contando valores únicos de id_col
    (p. ej. system_id de alumno o docente_id) sobre el detalle recibido en
    vez de sumar conteos ya agregados. Necesario porque un mismo id puede
    aparecer en más de un grupo/docente dentro de la misma materia/sección."""
    col_esperados = f"{entidad} Esperados"
    col_respondieron = f"{entidad} que Respondieron"
    esperados = df.groupby(cols)[id_col].nunique().rename(col_esperados)
    respondieron = (
        df[df["respondio"] == True]
        .groupby(cols)[id_col]
        .nunique()
        .rename(col_respondieron)
    )
    df_res = pd.concat([esperados, respondieron], axis=1)
    df_res[col_respondieron] = df_res[col_respondieron].fillna(0).astype(int)
    df_res["% de Avance"] = (
        (df_res[col_respondieron] / df_res[col_esperados] * 100).round(2).fillna(0)
    )
    df_res = df_res.reset_index().rename(columns=dict(zip(cols, labels)))
    return df_res.sort_values(labels).reset_index(drop=True)


def _tabla_avance_combinada(df_alumnos, df_crudo_faltante, cols, labels):
    """Combina _tabla_avance_distinct (grupos con detalle por alumno) con
    _tabla_avance sobre los grupos que no tienen ese detalle (df_crudo_faltante,
    ya deduplicado por materia/sección/grupo). Sin esto, los grupos sin
    detalle por alumno desaparecerían de la tabla en vez de mostrarse con el
    conteo crudo disponible."""
    partes = []
    if not df_alumnos.empty:
        partes.append(_tabla_avance_distinct(df_alumnos, cols, labels))
    if not df_crudo_faltante.empty:
        partes.append(_tabla_avance(df_crudo_faltante, cols, labels))
    if not partes:
        return pd.DataFrame(columns=labels + ["Alumnos Esperados", "Alumnos que Respondieron", "% de Avance"])
    df_res = pd.concat(partes, ignore_index=True)
    df_res = df_res.groupby(labels, as_index=False)[["Alumnos Esperados", "Alumnos que Respondieron"]].sum()
    df_res["% de Avance"] = (
        (df_res["Alumnos que Respondieron"] / df_res["Alumnos Esperados"] * 100).round(2).fillna(0)
    )
    return df_res.sort_values(labels).reset_index(drop=True)


def _mostrar_tabla_avance(df_res, key):
    st.caption(f"{len(df_res)} registro(s) según los filtros de búsqueda aplicados arriba.")
    st.dataframe(
        df_res,
        hide_index=True,
        width="stretch",
        height=min(38 * (len(df_res) + 1) + 3, 480),
        column_config={
            "% de Avance": st.column_config.ProgressColumn(
                "% de Avance", min_value=0, max_value=100, format="%.1f%%"
            ),
        },
        key=key,
    )


def _agregar_encabezado_y_pie(canvas, doc):
    canvas.saveState()
    width, height = landscape(A4)
    logo_path = None
    for p in ["assets/logo-ucp-icon.png", "assets/logo-ucp.png", "logo-ucp-icon.png"]:
        if os.path.exists(p):
            logo_path = p
            break
    if logo_path:
        try:
            canvas.drawImage(logo_path, x=2 * cm, y=height - 2.5 * cm, width=2 * cm, height=2 * cm, preserveAspectRatio=True, mask="auto")
        except Exception as exc:
            log_exception("Error silencioso tratado en encuestas.py", exc)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.setFillColor(colors.HexColor("#1e3a8a"))
    canvas.drawString(5 * cm, height - 1.5 * cm, "Universidad Central del Paraguay")
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.black)
    canvas.drawString(5 * cm, height - 2.1 * cm, "Reporte de Avance de Encuestas")
    canvas.setStrokeColor(colors.HexColor("#1e3a8a"))
    canvas.setLineWidth(1)
    canvas.line(2 * cm, height - 3.0 * cm, width - 2 * cm, height - 3.0 * cm)
    canvas.setFont("Helvetica-Oblique", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(width - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _tabla_pdf(titulo, df, styles, story, col_labels, entidad="Alumnos"):
    col_esperados = f"{entidad} Esperados"
    col_respondieron = f"{entidad} que Respondieron"
    story.append(Paragraph(f"<b>{titulo}</b>", styles["Heading3"]))
    story.append(Spacer(1, 6))
    data_rows = [list(col_labels) + [col_esperados, col_respondieron, "% de Avance"]]
    for _, r in df.iterrows():
        data_rows.append(
            [str(r[c]) for c in col_labels]
            + [
                _fmt_num(r[col_esperados]),
                _fmt_num(r[col_respondieron]),
                f"{r['% de Avance']:.1f}%",
            ]
        )
    metric_widths = [4 * cm, 5 * cm, 3.5 * cm]
    label_width = (25.5 * cm - sum(metric_widths)) / len(col_labels)
    col_widths = [label_width] * len(col_labels) + metric_widths
    t = Table(data_rows, repeatRows=1, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (len(col_labels), 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fc")]),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))


def generar_pdf_reporte(periodo, tipo, filtros_txt, tablas, entidad="Alumnos"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=4 * cm, bottomMargin=2 * cm,
    )
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph(f"<b>Reporte de Encuesta {periodo} — {tipo}</b>", styles["Title"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Filtros aplicados:</b> {filtros_txt}", styles["Normal"]))
    story.append(Spacer(1, 18))

    for titulo, df, col_labels in tablas:
        _tabla_pdf(titulo, df, styles, story, col_labels, entidad=entidad)

    doc.build(story, onFirstPage=_agregar_encabezado_y_pie, onLaterPages=_agregar_encabezado_y_pie)
    return buffer.getvalue()


def _limpiar_seccion_grupo_docente():
    st.session_state["enc_flt_seccion"] = []
    st.session_state["enc_flt_grupo"] = []
    st.session_state["enc_flt_docente"] = []


def _limpiar_grupo_docente():
    st.session_state["enc_flt_grupo"] = []
    st.session_state["enc_flt_docente"] = []


def _limpiar_docente():
    st.session_state["enc_flt_docente"] = []


def render_detalle(df_detalle, df_alumnos, periodo, tipo):
    if df_detalle.empty and df_alumnos.empty:
        st.warning("No hay detalle disponible para esta encuesta.")
        return

    # El docente puede venir pre-agregado (indicador
    # avance_por_materia_seccion_grupo, p. ej. v1) y/o como columna del
    # detalle a nivel de alumno (p. ej. v2, que no trae ese indicador
    # agregado). Se usa el/los que estén disponibles; cuando ambos existen se
    # prioriza el pre-agregado para la tabla "Docente" (comportamiento
    # histórico), pero el filtro por docente ya se aplica directo sobre el
    # detalle por alumno si tiene esa columna.
    tiene_docente_detalle = not df_detalle.empty and "docente" in df_detalle.columns
    tiene_docente_alumno = not df_alumnos.empty and "docente" in df_alumnos.columns
    tiene_docente = tiene_docente_detalle or tiene_docente_alumno

    # Fuente de opciones para Materia/Sección/Grupo: el detalle a nivel de
    # alumno, disponible en todos los formatos de origen. Si no existiera
    # (orígenes muy antiguos), se usa el detalle por docente como respaldo.
    base = df_alumnos if not df_alumnos.empty else df_detalle

    with st.container(border=True):
        cols = st.columns(4 if tiene_docente else 3)

        with cols[0]:
            materias_opts = sorted(base["materia"].dropna().unique())
            flt_materia = st.multiselect(
                "Materia", options=materias_opts, placeholder="Todas",
                key="enc_flt_materia", on_change=_limpiar_seccion_grupo_docente,
            )

        base_seccion = base[base["materia"].isin(flt_materia)] if flt_materia else base
        with cols[1]:
            secciones_opts = sorted(base_seccion["seccion"].dropna().unique())
            flt_seccion = st.multiselect(
                "Sección", options=secciones_opts, placeholder="Todas",
                key="enc_flt_seccion", on_change=_limpiar_grupo_docente,
            )

        base_grupo = base_seccion[base_seccion["seccion"].isin(flt_seccion)] if flt_seccion else base_seccion
        with cols[2]:
            grupos_opts = sorted(base_grupo["grupo"].dropna().unique())
            flt_grupo = st.multiselect(
                "Grupo", options=grupos_opts, placeholder="Todos",
                key="enc_flt_grupo", on_change=_limpiar_docente,
            )

        flt_docente = []
        if tiene_docente:
            base_docente = base_grupo[base_grupo["grupo"].isin(flt_grupo)] if flt_grupo else base_grupo
            if "docente" in base_docente.columns:
                docente_scope = base_docente
            else:
                # Respaldo para orígenes donde el docente sólo está en el
                # detalle pre-agregado, no en el detalle por alumno.
                docente_scope = df_detalle
                if flt_materia:
                    docente_scope = docente_scope[docente_scope["materia"].isin(flt_materia)]
                if flt_seccion:
                    docente_scope = docente_scope[docente_scope["seccion"].isin(flt_seccion)]
                if flt_grupo:
                    docente_scope = docente_scope[docente_scope["grupo"].isin(flt_grupo)]
            with cols[3]:
                docentes_opts = sorted(docente_scope["docente"].dropna().unique())
                flt_docente = st.multiselect(
                    "Docente", options=docentes_opts, placeholder="Todos", key="enc_flt_docente",
                )

    # Detalle a nivel de alumno filtrado por materia/sección/grupo/docente.
    df_alumnos_filt = df_alumnos
    if not df_alumnos_filt.empty:
        if flt_materia:
            df_alumnos_filt = df_alumnos_filt[df_alumnos_filt["materia"].isin(flt_materia)]
        if flt_seccion:
            df_alumnos_filt = df_alumnos_filt[df_alumnos_filt["seccion"].isin(flt_seccion)]
        if flt_grupo:
            df_alumnos_filt = df_alumnos_filt[df_alumnos_filt["grupo"].isin(flt_grupo)]
        if flt_docente and tiene_docente_alumno:
            df_alumnos_filt = df_alumnos_filt[df_alumnos_filt["docente"].isin(flt_docente)]

    # Detalle por docente pre-agregado, filtrado por materia/sección/grupo/
    # docente (sólo existe cuando tiene_docente_detalle).
    df_filt = df_detalle
    if tiene_docente_detalle:
        if flt_materia:
            df_filt = df_filt[df_filt["materia"].isin(flt_materia)]
        if flt_seccion:
            df_filt = df_filt[df_filt["seccion"].isin(flt_seccion)]
        if flt_grupo:
            df_filt = df_filt[df_filt["grupo"].isin(flt_grupo)]
        if flt_docente:
            df_filt = df_filt[df_filt["docente"].isin(flt_docente)]
            # El filtro de docente también acota el detalle por alumno, a las
            # combinaciones materia/sección/grupo que dicta ese/esos
            # docente(s). Sólo hace falta este cruce cuando el detalle por
            # alumno no tiene su propia columna "docente" para filtrar
            # directo (arriba) — si la tiene, el cruce por combos sería menos
            # preciso en materias con más de un docente por grupo.
            if not tiene_docente_alumno and not df_alumnos_filt.empty:
                combos = df_filt[["materia", "seccion", "grupo"]].drop_duplicates()
                df_alumnos_filt = df_alumnos_filt.merge(combos, on=["materia", "seccion", "grupo"], how="inner")

    if df_alumnos_filt.empty and df_filt.empty:
        st.info("Ningún registro coincide con los filtros seleccionados.")
        return

    # El detalle por docente puede incluir combinaciones materia/sección/grupo
    # que NO tienen ninguna fila en el detalle por alumno (hueco del origen de
    # datos: hay grupos con encuesta configurada pero sin exportar el detalle
    # por alumno). Si esas combinaciones no se incluyen aparte, desaparecen
    # por completo de las tablas y de los totales. Acá se separan del resto
    # para agregarlas con el conteo crudo (no distinct) que sí existe para
    # ellas, y así no perder ningún grupo.
    combos_con_alumno = (
        df_alumnos_filt[["materia", "seccion", "grupo"]].drop_duplicates()
        if not df_alumnos_filt.empty
        else pd.DataFrame(columns=["materia", "seccion", "grupo"])
    )
    if tiene_docente_detalle and not df_filt.empty:
        if not combos_con_alumno.empty:
            _merged = df_filt.merge(
                combos_con_alumno, on=["materia", "seccion", "grupo"], how="left", indicator=True
            )
            df_filt_sin_alumno = _merged[_merged["_merge"] == "left_only"].drop(columns="_merge")
        else:
            df_filt_sin_alumno = df_filt
        df_grupos_faltantes = (
            df_filt_sin_alumno.groupby(["materia", "seccion", "grupo"], as_index=False)
            .agg(
                alumnos_esperados=("alumnos_esperados", "max"),
                alumnos_que_respondieron=("alumnos_que_respondieron", "max"),
            )
            if not df_filt_sin_alumno.empty
            else pd.DataFrame(columns=["materia", "seccion", "grupo", "alumnos_esperados", "alumnos_que_respondieron"])
        )
    else:
        df_grupos_faltantes = pd.DataFrame(columns=["materia", "seccion", "grupo", "alumnos_esperados", "alumnos_que_respondieron"])

    # Resumen según los filtros aplicados arriba (materia/sección/grupo/docente).
    # "Total de Alumnos" y "Alumnos que Respondieron" son distinct de alumno
    # (system_id), coherente con Visión General. No se le suma el conteo
    # crudo de los grupos sin detalle por alumno (df_grupos_faltantes): ese
    # conteo no es distinct (un alumno con varias materias se contaría una
    # vez por grupo), así que sumarlo aquí infla el total. Sólo se usa como
    # respaldo si no hay NINGÚN detalle por alumno para el filtro aplicado.
    # "Encuestas Respondidas" es la cantidad de encuestas individuales
    # completadas (un alumno puede responder a más de un docente, por eso
    # puede ser mayor que "Alumnos que Respondieron"). Sin detalle por
    # docente, cada fila del detalle por alumno ya representa una encuesta
    # esperada (una por materia/sección/grupo).
    if not df_alumnos_filt.empty:
        total_alumnos = int(df_alumnos_filt["system_id"].nunique())
        alumnos_respondieron = int(df_alumnos_filt.loc[df_alumnos_filt["respondio"] == True, "system_id"].nunique())
    else:
        total_alumnos = int(df_grupos_faltantes["alumnos_esperados"].sum()) if not df_grupos_faltantes.empty else 0
        alumnos_respondieron = int(df_grupos_faltantes["alumnos_que_respondieron"].sum()) if not df_grupos_faltantes.empty else 0

    if tiene_docente_detalle:
        encuestas_respondidas = int(df_filt["alumnos_que_respondieron"].sum())
    else:
        encuestas_respondidas = int((df_alumnos_filt["respondio"] == True).sum())

    st.markdown("##### Resumen según los filtros aplicados")
    k1, k2, k3 = st.columns(3)
    with k1:
        render_kpi_card(
            "Total de Alumnos", _fmt_num(total_alumnos),
            accent="#1e3a8a", background="#e8f0fe", border="#a9c6f5",
        )
    with k2:
        render_kpi_card(
            "Encuestas Respondidas", _fmt_num(encuestas_respondidas),
            accent="#385623", background="#e2efd9", border="#a9d08e",
        )
    with k3:
        render_kpi_card(
            "Alumnos que Respondieron", _fmt_num(alumnos_respondieron),
            accent="#7c4a03", background="#fdf1de", border="#e8c07d",
        )
    st.divider()

    tablas_resumen = {}
    for key, cols, labels, modo in TABLAS_AVANCE:
        if modo == "distinct":
            tablas_resumen[key] = _tabla_avance_combinada(df_alumnos_filt, df_grupos_faltantes, cols, labels)
        elif modo == "docente":
            if tiene_docente_detalle:
                tablas_resumen[key] = _tabla_avance(df_filt, cols, labels)
            elif tiene_docente_alumno:
                tablas_resumen[key] = _tabla_avance_distinct(df_alumnos_filt, cols, labels)

    st.markdown("#### Avance por Materia / Sección / Grupo" + (" / Docente" if tiene_docente else ""))
    tab_keys = ["Materia", "Sección", "Grupo"] + (["Docente"] if tiene_docente else [])
    tab_key_slugs = {"Materia": "materia", "Sección": "seccion", "Grupo": "grupo", "Docente": "docente"}
    tabs = st.tabs([f"Por {key}" for key in tab_keys])
    for tab, key in zip(tabs, tab_keys):
        with tab:
            _mostrar_tabla_avance(tablas_resumen[key], key=f"enc_tabla_{tab_key_slugs[key]}")

    st.divider()

    filtros_activos = []
    if flt_materia:
        filtros_activos.append(f"Materia: {', '.join(flt_materia)}")
    if flt_seccion:
        filtros_activos.append(f"Sección: {', '.join(flt_seccion)}")
    if flt_grupo:
        filtros_activos.append(f"Grupo: {', '.join(flt_grupo)}")
    if flt_docente:
        filtros_activos.append(f"Docente: {', '.join(flt_docente)}")
    filtros_txt = " | ".join(filtros_activos) if filtros_activos else "Ninguno (todos los datos)"

    tipo_archivo = tipo.replace(" ", "_")
    c_dl1, c_dl2 = st.columns(2)
    with c_dl1:
        st.download_button(
            "Descargar Reporte Completo (Excel)",
            data=excel_bytes_reporte(tablas_resumen),
            file_name=f"Encuesta_{periodo}_{tipo_archivo}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            key="enc_dl_excel",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Encuesta - Detalle", "Excel"),
        )
    with c_dl2:
        pdf_data = generar_pdf_reporte(
            periodo, tipo, filtros_txt,
            [(f"Avance por {key}", tablas_resumen[key], labels) for key, _, labels, _ in TABLAS_AVANCE if key in tablas_resumen],
        )
        st.download_button(
            "Descargar Reporte Completo (PDF)",
            data=pdf_data,
            file_name=f"Encuesta_{periodo}_{tipo_archivo}.pdf",
            mime="application/pdf",
            icon=":material/download:",
            key="enc_dl_pdf",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Encuesta - Detalle", "PDF"),
        )


# (clave de la pestaña, columnas a agrupar -acumulativas-, etiquetas de esas
# columnas). Autoevaluación docente: cada docente ya autoevalúa cada
# materia/sección/grupo que dicta, así que a diferencia de TABLAS_AVANCE acá
# no hace falta distinguir un origen "crudo" pre-agregado ni combinar con
# huecos de datos: el detalle (avance_por_docente) ya tiene, en una sola
# fila por docente x materia/sección/grupo, todo lo necesario para contar
# distinct de docente_id en cualquier nivel de la jerarquía.
TABLAS_AVANCE_DOCENTE = [
    ("Materia", ["materia"], ["Materia"]),
    ("Sección", ["materia", "seccion"], ["Materia", "Sección"]),
    ("Grupo", ["materia", "seccion", "grupo"], ["Materia", "Sección", "Grupo"]),
    ("Docente", ["materia", "seccion", "grupo", "docente"], ["Materia", "Sección", "Grupo", "Docente"]),
]


def _limpiar_seccion_grupo_docente_autoeval():
    st.session_state["enc_autoeval_flt_seccion"] = []
    st.session_state["enc_autoeval_flt_grupo"] = []
    st.session_state["enc_autoeval_flt_docente"] = []


def _limpiar_grupo_docente_autoeval():
    st.session_state["enc_autoeval_flt_grupo"] = []
    st.session_state["enc_autoeval_flt_docente"] = []


def _limpiar_docente_autoeval():
    st.session_state["enc_autoeval_flt_docente"] = []


def render_detalle_autoeval_docente(df_detalle, periodo, tipo):
    if df_detalle.empty:
        st.warning("No hay detalle disponible para esta encuesta.")
        return

    with st.container(border=True):
        cols = st.columns(4)

        with cols[0]:
            materias_opts = sorted(df_detalle["materia"].dropna().unique())
            flt_materia = st.multiselect(
                "Materia", options=materias_opts, placeholder="Todas",
                key="enc_autoeval_flt_materia", on_change=_limpiar_seccion_grupo_docente_autoeval,
            )

        base_seccion = df_detalle[df_detalle["materia"].isin(flt_materia)] if flt_materia else df_detalle
        with cols[1]:
            secciones_opts = sorted(base_seccion["seccion"].dropna().unique())
            flt_seccion = st.multiselect(
                "Sección", options=secciones_opts, placeholder="Todas",
                key="enc_autoeval_flt_seccion", on_change=_limpiar_grupo_docente_autoeval,
            )

        base_grupo = base_seccion[base_seccion["seccion"].isin(flt_seccion)] if flt_seccion else base_seccion
        with cols[2]:
            grupos_opts = sorted(base_grupo["grupo"].dropna().unique())
            flt_grupo = st.multiselect(
                "Grupo", options=grupos_opts, placeholder="Todos",
                key="enc_autoeval_flt_grupo", on_change=_limpiar_docente_autoeval,
            )

        base_docente = base_grupo[base_grupo["grupo"].isin(flt_grupo)] if flt_grupo else base_grupo
        with cols[3]:
            docentes_opts = sorted(base_docente["docente"].dropna().unique())
            flt_docente = st.multiselect(
                "Docente", options=docentes_opts, placeholder="Todos", key="enc_autoeval_flt_docente",
            )

    df_filt = df_detalle
    if flt_materia:
        df_filt = df_filt[df_filt["materia"].isin(flt_materia)]
    if flt_seccion:
        df_filt = df_filt[df_filt["seccion"].isin(flt_seccion)]
    if flt_grupo:
        df_filt = df_filt[df_filt["grupo"].isin(flt_grupo)]
    if flt_docente:
        df_filt = df_filt[df_filt["docente"].isin(flt_docente)]

    if df_filt.empty:
        st.info("Ningún registro coincide con los filtros seleccionados.")
        return

    # "Total de Docentes" y "Docentes que Respondieron" son distinct de
    # docente_id, coherente con Visión General. "Encuestas Respondidas" es la
    # cantidad de autoevaluaciones individuales completadas (un docente
    # responde una por cada materia/sección/grupo que dicta, por eso puede
    # ser mayor que "Docentes que Respondieron").
    total_docentes = int(df_filt["docente_id"].nunique())
    docentes_respondieron = int(df_filt.loc[df_filt["respondio"] == True, "docente_id"].nunique())
    encuestas_respondidas = int((df_filt["respondio"] == True).sum())

    st.markdown("##### Resumen según los filtros aplicados")
    k1, k2, k3 = st.columns(3)
    with k1:
        render_kpi_card(
            "Total de Docentes", _fmt_num(total_docentes),
            accent="#1e3a8a", background="#e8f0fe", border="#a9c6f5",
        )
    with k2:
        render_kpi_card(
            "Encuestas Respondidas", _fmt_num(encuestas_respondidas),
            accent="#385623", background="#e2efd9", border="#a9d08e",
        )
    with k3:
        render_kpi_card(
            "Docentes que Respondieron", _fmt_num(docentes_respondieron),
            accent="#7c4a03", background="#fdf1de", border="#e8c07d",
        )
    st.divider()

    tablas_resumen = {}
    for key, cols_grp, labels in TABLAS_AVANCE_DOCENTE:
        tablas_resumen[key] = _tabla_avance_distinct(df_filt, cols_grp, labels, id_col="docente_id", entidad="Docentes")

    st.markdown("#### Avance por Materia / Sección / Grupo / Docente")
    tab_keys = ["Materia", "Sección", "Grupo", "Docente"]
    tab_key_slugs = {"Materia": "materia", "Sección": "seccion", "Grupo": "grupo", "Docente": "docente"}
    tabs = st.tabs([f"Por {key}" for key in tab_keys])
    for tab, key in zip(tabs, tab_keys):
        with tab:
            _mostrar_tabla_avance(tablas_resumen[key], key=f"enc_autoeval_tabla_{tab_key_slugs[key]}")

    st.divider()

    filtros_activos = []
    if flt_materia:
        filtros_activos.append(f"Materia: {', '.join(flt_materia)}")
    if flt_seccion:
        filtros_activos.append(f"Sección: {', '.join(flt_seccion)}")
    if flt_grupo:
        filtros_activos.append(f"Grupo: {', '.join(flt_grupo)}")
    if flt_docente:
        filtros_activos.append(f"Docente: {', '.join(flt_docente)}")
    filtros_txt = " | ".join(filtros_activos) if filtros_activos else "Ninguno (todos los datos)"

    tipo_archivo = tipo.replace(" ", "_")
    c_dl1, c_dl2 = st.columns(2)
    with c_dl1:
        st.download_button(
            "Descargar Reporte Completo (Excel)",
            data=excel_bytes_reporte(tablas_resumen),
            file_name=f"Encuesta_{periodo}_{tipo_archivo}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            key="enc_autoeval_dl_excel",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Encuesta - Detalle", "Excel"),
        )
    with c_dl2:
        pdf_data = generar_pdf_reporte(
            periodo, tipo, filtros_txt,
            [(f"Avance por {key}", tablas_resumen[key], labels) for key, _, labels in TABLAS_AVANCE_DOCENTE],
            entidad="Docentes",
        )
        st.download_button(
            "Descargar Reporte Completo (PDF)",
            data=pdf_data,
            file_name=f"Encuesta_{periodo}_{tipo_archivo}.pdf",
            mime="application/pdf",
            icon=":material/download:",
            key="enc_autoeval_dl_pdf",
            width="stretch",
            on_click=db_pia.log_export_callback, args=("Encuesta - Detalle", "PDF"),
        )
