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
    get_encuesta_nombre,
    get_encuesta_vigencia,
    listar_carreras_encuesta,
    listar_periodos_encuestas,
    listar_sedes_encuestas,
    listar_tipos_encuesta,
    load_encuestas_alumnos,
    load_encuestas_detalle,
    load_encuestas_general,
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


def render():
    render_common_setup()
    sede, periodo, carrera, tipo = select_encuesta()
    if not sede or not periodo or not carrera or not tipo:
        return

    fila_general = load_encuestas_general(sede, periodo, carrera, tipo)
    df_detalle = load_encuestas_detalle(sede, periodo, carrera, tipo)
    df_alumnos = load_encuestas_alumnos(sede, periodo, carrera, tipo)

    if fila_general is None and df_detalle.empty:
        st.warning(f"No hay datos disponibles para la Encuesta {periodo} — {tipo}.")
        return

    nombre = get_encuesta_nombre(sede, periodo, carrera, tipo)
    vigencia = get_encuesta_vigencia(sede, periodo, carrera, tipo)
    st.markdown(
        f"""
        <div class="enc_header">
            <div class="enc_header_title">{nombre}</div>
            <div class="enc_header_vigencia">({vigencia})</div>
            <div class="enc_header_sub">{sede} · {carrera}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_general, tab_detalle = st.tabs(["Visión General", "Detalle por Materia / Sección / Grupo"])

    with tab_general:
        render_vision_general(fila_general)

    with tab_detalle:
        render_detalle(df_detalle, df_alumnos, periodo, tipo)


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


def _bloque_avance(titulo, cantidad, pct, esperados, key_prefix, accent, background, border):
    with st.container(border=True):
        st.markdown(f"**{titulo}**")
        c1, c2 = st.columns(2)
        with c1:
            render_kpi_card("Alumnos", _fmt_num(cantidad), accent=accent, background=background, border=border)
        with c2:
            render_kpi_card("% de Avance", _fmt_pct(pct), accent=accent, background=background, border=border)

        if _valor_valido(cantidad) and _valor_valido(esperados) and float(esperados) > 0:
            _pie_avance(float(cantidad), float(esperados), key=f"{key_prefix}_pie")
        else:
            _pie_placeholder()


def render_vision_general(fila_general):
    if fila_general is None:
        st.warning("No se encontró la fila de avance general en el archivo de la encuesta.")
        return

    esperados = fila_general["alumnos_unicos_esperados"]

    st.markdown("#### Avance de Alumnos")
    _render_total_esperados("Alumnos que debían responder", _fmt_num(esperados))

    b1, b2 = st.columns(2)
    with b1:
        _bloque_avance(
            "1. Respondieron todas sus encuestas",
            fila_general.get("alumnos_unicos_que_respondieron_todas"),
            fila_general.get("porcentaje_avance_alumnos_todas"),
            esperados,
            key_prefix="enc_todas",
            accent="#385623", background="#e2efd9", border="#a9d08e",
        )
    with b2:
        _bloque_avance(
            "2. Respondieron al menos una encuesta",
            fila_general["alumnos_unicos_que_respondieron_al_menos_una"],
            fila_general["porcentaje_avance_alumnos"],
            esperados,
            key_prefix="enc_al_menos_una",
            accent="#1e3a8a", background="#e8f0fe", border="#a9c6f5",
        )


# (clave de la pestaña, columnas a agrupar -acumulativas-, etiquetas de esas
# columnas, modo de cálculo). Cada nivel suma la columna anterior: Sección
# incluye Materia, Grupo incluye Materia+Sección, Docente incluye
# Materia+Sección+Grupo.
# - "distinct": cuenta alumnos únicos (por system_id) sobre el detalle a nivel
#   de alumno (avance_por_alumno), evitando contar dos veces a un mismo
#   alumno cuando aparece en más de un grupo/docente de la misma materia.
# - "crudo": usa el detalle por materia/sección/grupo/docente tal cual viene
#   (ese grano no tiene distinct de alumno por docente disponible).
TABLAS_AVANCE = [
    ("Materia", ["materia"], ["Materia"], "distinct"),
    ("Sección", ["materia", "seccion"], ["Materia", "Sección"], "distinct"),
    ("Grupo", ["materia", "seccion", "grupo"], ["Materia", "Sección", "Grupo"], "distinct"),
    ("Docente", ["materia", "seccion", "grupo", "docente"], ["Materia", "Sección", "Grupo", "Docente"], "crudo"),
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


def _tabla_avance_distinct(df_alumnos, cols, labels):
    """Igual que _tabla_avance, pero contando alumnos únicos (system_id) sobre
    el detalle a nivel de alumno en vez de sumar conteos ya agregados por
    docente. Necesario porque un mismo alumno puede aparecer en más de un
    grupo/docente dentro de la misma materia/sección."""
    esperados = df_alumnos.groupby(cols)["system_id"].nunique().rename("Alumnos Esperados")
    respondieron = (
        df_alumnos[df_alumnos["respondio"] == True]
        .groupby(cols)["system_id"]
        .nunique()
        .rename("Alumnos que Respondieron")
    )
    df_res = pd.concat([esperados, respondieron], axis=1)
    df_res["Alumnos que Respondieron"] = df_res["Alumnos que Respondieron"].fillna(0).astype(int)
    df_res["% de Avance"] = (
        (df_res["Alumnos que Respondieron"] / df_res["Alumnos Esperados"] * 100).round(2).fillna(0)
    )
    df_res = df_res.reset_index().rename(columns=dict(zip(cols, labels)))
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


def _tabla_pdf(titulo, df, styles, story, col_labels):
    story.append(Paragraph(f"<b>{titulo}</b>", styles["Heading3"]))
    story.append(Spacer(1, 6))
    data_rows = [list(col_labels) + ["Alumnos Esperados", "Alumnos que Respondieron", "% de Avance"]]
    for _, r in df.iterrows():
        data_rows.append(
            [str(r[c]) for c in col_labels]
            + [
                _fmt_num(r["Alumnos Esperados"]),
                _fmt_num(r["Alumnos que Respondieron"]),
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


def generar_pdf_reporte(periodo, tipo, filtros_txt, tablas):
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
        _tabla_pdf(titulo, df, styles, story, col_labels)

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

    # Algunos orígenes (p. ej. v2) no traen el detalle por docente: en ese
    # caso no hay filtro ni pestaña "Docente", y todo se calcula a partir del
    # detalle por alumno.
    tiene_docente = not df_detalle.empty and "docente" in df_detalle.columns

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
            df_det_scope = df_detalle
            if flt_materia:
                df_det_scope = df_det_scope[df_det_scope["materia"].isin(flt_materia)]
            if flt_seccion:
                df_det_scope = df_det_scope[df_det_scope["seccion"].isin(flt_seccion)]
            if flt_grupo:
                df_det_scope = df_det_scope[df_det_scope["grupo"].isin(flt_grupo)]
            with cols[3]:
                docentes_opts = sorted(df_det_scope["docente"].dropna().unique())
                flt_docente = st.multiselect(
                    "Docente", options=docentes_opts, placeholder="Todos", key="enc_flt_docente",
                )

    # Detalle a nivel de alumno filtrado por materia/sección/grupo.
    df_alumnos_filt = df_alumnos
    if not df_alumnos_filt.empty:
        if flt_materia:
            df_alumnos_filt = df_alumnos_filt[df_alumnos_filt["materia"].isin(flt_materia)]
        if flt_seccion:
            df_alumnos_filt = df_alumnos_filt[df_alumnos_filt["seccion"].isin(flt_seccion)]
        if flt_grupo:
            df_alumnos_filt = df_alumnos_filt[df_alumnos_filt["grupo"].isin(flt_grupo)]

    # Detalle por docente filtrado por materia/sección/grupo/docente (sólo
    # existe cuando tiene_docente).
    df_filt = df_detalle
    if tiene_docente:
        if flt_materia:
            df_filt = df_filt[df_filt["materia"].isin(flt_materia)]
        if flt_seccion:
            df_filt = df_filt[df_filt["seccion"].isin(flt_seccion)]
        if flt_grupo:
            df_filt = df_filt[df_filt["grupo"].isin(flt_grupo)]
        if flt_docente:
            df_filt = df_filt[df_filt["docente"].isin(flt_docente)]
            # El filtro de docente también acota el detalle por alumno, a las
            # combinaciones materia/sección/grupo que dicta ese/esos docente(s).
            if not df_alumnos_filt.empty:
                combos = df_filt[["materia", "seccion", "grupo"]].drop_duplicates()
                df_alumnos_filt = df_alumnos_filt.merge(combos, on=["materia", "seccion", "grupo"], how="inner")

    if df_alumnos_filt.empty and df_filt.empty:
        st.info("Ningún registro coincide con los filtros seleccionados.")
        return

    # Fallback para encuestas antiguas sin detalle a nivel de alumno: un mismo
    # grupo (materia+sección+grupo) puede repetirse una vez por cada docente
    # que lo dicta, con el mismo conteo de alumnos. Para no duplicarlos al
    # agregar por materia/sección/grupo, nos quedamos con un valor por
    # combinación antes de sumar.
    df_grupos_fallback = (
        df_filt.groupby(["materia", "seccion", "grupo"], as_index=False)
        .agg(
            alumnos_esperados=("alumnos_esperados", "max"),
            alumnos_que_respondieron=("alumnos_que_respondieron", "max"),
        )
        if tiene_docente and not df_filt.empty
        else pd.DataFrame(columns=["materia", "seccion", "grupo", "alumnos_esperados", "alumnos_que_respondieron"])
    )

    # Resumen según los filtros aplicados arriba (materia/sección/grupo/docente).
    # "Total de Alumnos" y "Alumnos que Respondieron" son distinct de alumno
    # (system_id); "Encuestas Respondidas" es la cantidad de encuestas
    # individuales completadas (un alumno puede responder a más de un
    # docente, por eso puede ser mayor que "Alumnos que Respondieron"). Sin
    # detalle por docente, cada fila del detalle por alumno ya representa una
    # encuesta esperada (una por materia/sección/grupo).
    if not df_alumnos_filt.empty:
        total_alumnos = int(df_alumnos_filt["system_id"].nunique())
        alumnos_respondieron = int(df_alumnos_filt.loc[df_alumnos_filt["respondio"] == True, "system_id"].nunique())
    else:
        total_alumnos = int(df_grupos_fallback["alumnos_esperados"].sum())
        alumnos_respondieron = int(df_grupos_fallback["alumnos_que_respondieron"].sum())

    if tiene_docente:
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
            if not df_alumnos_filt.empty:
                tablas_resumen[key] = _tabla_avance_distinct(df_alumnos_filt, cols, labels)
            else:
                tablas_resumen[key] = _tabla_avance(df_grupos_fallback, cols, labels)
        elif tiene_docente:
            tablas_resumen[key] = _tabla_avance(df_filt, cols, labels)

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
