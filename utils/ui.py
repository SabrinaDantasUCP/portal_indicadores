from html import escape

import streamlit as st

from utils import db_pia


def render_egresados_fuente_caption():
    """Leyenda de origen de los datos de titulados/egresados, mostrada al pie
    de los indicadores que cruzan con egressados.xlsx (eficiencia_egreso,
    eficiencia_terminal, eficiencia_titulacion, tasa_retencion,
    eficiencia_rezago, tiempos_medios). La fecha viene de
    pia_egresados_meta.fecha_envio (fecha en que la Secretaría General
    Académica envió la planilla, actualizada en Alumnos - Configuración ETL),
    no de la fecha de hoy ni de cuándo se subió el archivo al sistema."""
    meta = db_pia.get_egresados_meta()
    if meta and meta.get("fecha_envio"):
        fecha = meta["fecha_envio"]
        fecha_str = fecha.strftime("%d/%m/%Y") if hasattr(fecha, "strftime") else str(fecha)
    else:
        fecha_str = "fecha no informada"
    st.markdown(
        f'<p style="color: #4f4f4f; font-size: 0.85rem; margin-bottom: 0;">'
        f'Los datos de titulados y egresados están basados en los datos enviados por la '
        f'Secretaria General Académica el día {fecha_str}.</p>',
        unsafe_allow_html=True,
    )


def render_info_header(title, description=None, accent="#003366", background="#f3f7fb"):
    st.markdown(f"### {escape(str(title))}")
    if description:
        st.caption(str(description))


def render_download_button_styles():
    st.markdown(
        """
        <style>
        [data-testid="stElementToolbar"] { display: none; }
        div[data-testid="stDownloadButton"] button {
            min-height: 50px !important;
            font-size: 16px !important;
            border-radius: 8px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(label, value, accent="#333", background="#f9f9f9", border="#ddd"):
    st.markdown(
        f"""
        <div style="
            background-color: {background};
            border: 1px solid {border};
            border-radius: 8px;
            padding: 18px 16px;
            text-align: center;
            height: 100%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        ">
            <div style="
                font-size: 13px;
                color: #666;
                font-weight: 600;
                text-transform: uppercase;
                margin-bottom: 6px;
            ">
                {escape(str(label))}
            </div>
            <div style="font-size: 28px; color: {accent}; font-weight: 700;">
                {escape(str(value))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_grid(items, columns=None, **card_kwargs):
    if not items:
        return

    columns = columns or len(items)
    cols = st.columns(columns)
    for idx, item in enumerate(items):
        label, value = item
        with cols[idx % columns]:
            render_kpi_card(label, value, **card_kwargs)


def render_section_box(title):
    st.markdown(
        f"""
        <div style="
            border: 1px solid #ddd;
            border-radius: 8px;
            background-color: #f9f9f9;
            padding: 14px 20px;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 18px;
            font-weight: 600;
            color: #444;
        ">
            {escape(str(title))}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_spacer():
    st.markdown("<br>", unsafe_allow_html=True)
