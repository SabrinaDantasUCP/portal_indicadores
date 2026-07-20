import io
import os

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
    listar_periodos_encuestas,
    listar_tipos_encuesta,
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
        .enc_header_sub { font-size: 17px; opacity: .92; margin-top: 6px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def select_encuesta():
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            periodo = st.selectbox(
                "Seleccione la encuesta que desea visualizar",
                options=listar_periodos_encuestas(),
                index=None,
                placeholder="Elija una encuesta para ver los datos...",
                key="encuestas_periodo",
                format_func=lambda p: f"Encuesta {p}",
            )
        with c2:
            tipos_opts = listar_tipos_encuesta(periodo) if periodo else []
            tipo = st.selectbox(
                "Seleccione el tipo de análisis",
                options=tipos_opts,
                index=None,
                placeholder="Elija un tipo de análisis...",
                key="encuestas_tipo",
                disabled=not periodo,
            )
    if not periodo:
        st.info("Seleccione la **encuesta** que desea visualizar para continuar.")
    elif not tipo:
        st.info("Seleccione el **tipo de análisis** que desea visualizar para continuar.")
    return periodo, tipo


def render():
    render_common_setup()
    periodo, tipo = select_encuesta()
    if not periodo or not tipo:
        return

    fila_general = load_encuestas_general(periodo, tipo)
    df_detalle = load_encuestas_detalle(periodo, tipo)

    if fila_general is None and df_detalle.empty:
        st.warning(f"No hay datos disponibles para la Encuesta {periodo} — {tipo}.")
        return

    st.markdown(
        f"""
        <div class="enc_header">
            <div class="enc_header_title">Encuesta {periodo}</div>
            <div class="enc_header_sub">{tipo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_general, tab_detalle = st.tabs(["Visión General", "Detalle por Materia / Sección / Grupo"])

    with tab_general:
        render_vision_general(fila_general)

    with tab_detalle:
        render_detalle(df_detalle, periodo, tipo)


def render_vision_general(fila_general):
    if fila_general is None:
        st.warning("No se encontró la fila de avance general en el archivo de la encuesta.")
        return

    st.markdown("#### Avance de Alumnos")
    st.caption("Alumnos únicos que debían responder al menos una encuesta, y cuántos ya respondieron al menos una.")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_kpi_card(
            "Alumnos que debían responder",
            _fmt_num(fila_general["alumnos_unicos_esperados"]),
            accent="#1e3a8a", background="#e8f0fe", border="#a9c6f5",
        )
    with c2:
        render_kpi_card(
            "Alumnos que respondieron",
            _fmt_num(fila_general["alumnos_unicos_que_respondieron_al_menos_una"]),
            accent="#385623", background="#e2efd9", border="#a9d08e",
        )
    with c3:
        render_kpi_card(
            "% de Avance",
            _fmt_pct(fila_general["porcentaje_avance_alumnos"]),
            accent="#8a4b1e", background="#fdeee0", border="#f0b98a",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Alumnos: respondieron vs. pendientes**")
    esperados = float(fila_general["alumnos_unicos_esperados"] or 0)
    respondieron = float(fila_general["alumnos_unicos_que_respondieron_al_menos_una"] or 0)
    pendientes = max(esperados - respondieron, 0)
    pct_avance = (respondieron / esperados * 100) if esperados else 0
    df_pie = pd.DataFrame({"Estado": ["Respondieron", "Pendientes"], "Valor": [respondieron, pendientes]})
    fig = px.pie(
        df_pie, names="Estado", values="Valor", hole=0.6, color="Estado",
        color_discrete_map={"Respondieron": "#388e3c", "Pendientes": "#d32f2f"},
    )
    fig.update_traces(
        textinfo="percent",
        textposition="outside",
        texttemplate="%{percent}",
        textfont=dict(size=25, color="#222222"),
        marker=dict(line=dict(color="#ffffff", width=2)),
        # Encoge el círculo dentro del área de la figura (coordenadas relativas,
        # no píxeles) para reservar siempre espacio a las etiquetas externas,
        # sin importar el ancho real del contenedor en Streamlit.
        domain=dict(x=[0.22, 0.78], y=[0.08, 0.92]),
    )
    fig.update_layout(
    legend=dict(
        font=dict(size=25)
    )
    )
    st.plotly_chart(fig, use_container_width=True, key="enc_pie_alumnos")


# (clave de la pestaña, columnas a agrupar -acumulativas-, etiquetas de esas
# columnas, si debe usarse el detalle crudo sin deduplicar). Cada nivel suma
# la columna anterior: Sección incluye Materia, Grupo incluye Materia+Sección,
# Docente incluye Materia+Sección+Grupo. Sólo "Docente" necesita los datos
# crudos: cada fila ya es única por grupo+docente. Los demás deben usar la
# base deduplicada (ver comentario en render_detalle) para no contar dos
# veces a los mismos alumnos cuando un grupo tiene más de un docente.
TABLAS_AVANCE = [
    ("Materia", ["materia"], ["Materia"], False),
    ("Sección", ["materia", "seccion"], ["Materia", "Sección"], False),
    ("Grupo", ["materia", "seccion", "grupo"], ["Materia", "Sección", "Grupo"], False),
    ("Docente", ["materia", "seccion", "grupo", "docente"], ["Materia", "Sección", "Grupo", "Docente"], True),
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
    return df_res.sort_values("% de Avance", ascending=False).reset_index(drop=True)


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


def render_detalle(df_detalle, periodo, tipo):
    if df_detalle.empty:
        st.warning("No hay detalle por materia/sección/grupo disponible para esta encuesta.")
        return

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            materias_opts = sorted(df_detalle["materia"].dropna().unique())
            flt_materia = st.multiselect(
                "Materia", options=materias_opts, placeholder="Todas",
                key="enc_flt_materia", on_change=_limpiar_seccion_grupo_docente,
            )

        df_scope_seccion = df_detalle[df_detalle["materia"].isin(flt_materia)] if flt_materia else df_detalle
        with c2:
            secciones_opts = sorted(df_scope_seccion["seccion"].dropna().unique())
            flt_seccion = st.multiselect(
                "Sección", options=secciones_opts, placeholder="Todas",
                key="enc_flt_seccion", on_change=_limpiar_grupo_docente,
            )

        df_scope_grupo = df_scope_seccion[df_scope_seccion["seccion"].isin(flt_seccion)] if flt_seccion else df_scope_seccion
        with c3:
            grupos_opts = sorted(df_scope_grupo["grupo"].dropna().unique())
            flt_grupo = st.multiselect(
                "Grupo", options=grupos_opts, placeholder="Todos",
                key="enc_flt_grupo", on_change=_limpiar_docente,
            )

        df_scope_docente = df_scope_grupo[df_scope_grupo["grupo"].isin(flt_grupo)] if flt_grupo else df_scope_grupo
        with c4:
            docentes_opts = sorted(df_scope_docente["docente"].dropna().unique())
            flt_docente = st.multiselect(
                "Docente", options=docentes_opts, placeholder="Todos", key="enc_flt_docente",
            )

    df_filt = df_scope_docente[df_scope_docente["docente"].isin(flt_docente)] if flt_docente else df_scope_docente

    if df_filt.empty:
        st.info("Ningún registro coincide con los filtros seleccionados.")
        return

    # Un mismo grupo (materia+sección+grupo) puede repetirse una vez por cada
    # docente que lo dicta, con el mismo conteo de alumnos (cada docente tiene
    # su propia encuesta con ese grupo). Para no duplicar alumnos al agregar
    # por materia/sección/grupo, nos quedamos con un valor por combinación
    # antes de sumar. Para "Docente" se usan los datos crudos (df_filt): cada
    # fila ya es única por grupo+docente.
    df_grupos = (
        df_filt.groupby(["materia", "seccion", "grupo"], as_index=False)
        .agg(
            alumnos_esperados=("alumnos_esperados", "max"),
            alumnos_que_respondieron=("alumnos_que_respondieron", "max"),
        )
    )

    tablas_resumen = {}
    for key, cols, labels, usar_crudo in TABLAS_AVANCE:
        base = df_filt if usar_crudo else df_grupos
        tablas_resumen[key] = _tabla_avance(base, cols, labels)

    st.markdown("#### Avance por Materia / Sección / Grupo / Docente")
    tab_materia, tab_seccion, tab_grupo, tab_docente = st.tabs(["Por Materia", "Por Sección", "Por Grupo", "Por Docente"])
    with tab_materia:
        _mostrar_tabla_avance(tablas_resumen["Materia"], key="enc_tabla_materia")
    with tab_seccion:
        _mostrar_tabla_avance(tablas_resumen["Sección"], key="enc_tabla_seccion")
    with tab_grupo:
        _mostrar_tabla_avance(tablas_resumen["Grupo"], key="enc_tabla_grupo")
    with tab_docente:
        _mostrar_tabla_avance(tablas_resumen["Docente"], key="enc_tabla_docente")

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
            [(f"Avance por {key}", tablas_resumen[key], labels) for key, _, labels, _ in TABLAS_AVANCE],
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
