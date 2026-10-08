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
    """Fila de tarjetas (etiqueta, valor) con el estilo común de los indicadores."""
    if not items:
        return
    aplicar_estilos_indicador()
    acento = card_kwargs.get("accent", COLOR_PRIMARIO)
    if acento == "#333":
        acento = COLOR_PRIMARIO
    render_tarjetas_kpi([{"etiqueta": label, "valor": value, "color": acento} for label, value in items], columnas=columns)


def render_section_box(title):
    """Título de bloque (ej. un semestre) con el estilo común de los indicadores."""
    st.markdown(
        f"""
        <div style="
            border-left: 4px solid {COLOR_PRIMARIO};
            background-color: #f5f8fc;
            border-radius: 6px;
            padding: 10px 16px;
            margin-top: 22px;
            margin-bottom: 10px;
            font-size: 17px;
            font-weight: 700;
            color: {COLOR_TEXTO};
        ">
            {escape(str(title))}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_spacer():
    st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# DISEÑO COMÚN DE LOS INDICADORES (v1/v2)
# ─────────────────────────────────────────────
# Componentes visuales compartidos por las páginas de indicadores, para que
# todas tengan la misma cabecera, tarjetas, títulos de sección y estilo de
# gráficos. No se inyecta nada global en app.py: cada página llama a
# aplicar_estilos_indicador(), así otras pantallas (ej. Encuestas) no cambian.

COLOR_PRIMARIO = "#004080"
COLOR_TEXTO = "#1e293b"
COLOR_TEXTO_SUAVE = "#64748b"
COLOR_BORDE = "#e2e8f0"
# Paleta para series categóricas (cohortes, grupos, etc.), en orden de uso.
PALETA_CATEGORICA = ["#004080", "#2a9d8f", "#e9a23b", "#c0392b", "#7b5ea7", "#3a86c8", "#8a9a5b", "#d35d90"]
# Colores semánticos: bueno / atención / malo / neutro.
COLOR_BUENO = "#2a9d8f"
COLOR_ATENCION = "#e9a23b"
COLOR_MALO = "#c0392b"
COLOR_NEUTRO = "#94a3b8"



def aplicar_estilos_indicador():
    """CSS común de las páginas de indicadores (tarjetas, cabecera, botones
    de descarga, tablas). Idempotente: se puede llamar en cada render."""
    st.markdown(
        f"""
        <style>
        [data-testid="stElementToolbar"] {{ display: none; }}
        div[data-testid="stDownloadButton"] button {{
            min-height: 46px !important; border-radius: 10px !important; font-weight: 600 !important;
        }}
        .ind-cabecera {{ margin: 0 0 18px 0; }}
        .ind-titulo {{ font-size: 26px; font-weight: 700; color: {COLOR_TEXTO}; line-height: 1.25; margin: 0; }}
        .ind-descripcion {{ font-size: 14.5px; color: {COLOR_TEXTO_SUAVE}; margin: 6px 0 0 0; max-width: 900px; }}
        .ind-kpi {{
            margin-bottom: 14px;
            background: #ffffff; border: 1px solid {COLOR_BORDE}; border-left: 4px solid var(--acento);
            border-radius: 10px; padding: 14px 16px; height: 100%;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }}
        .ind-kpi-etiqueta {{ font-size: 13px; font-weight: 600; color: {COLOR_TEXTO_SUAVE};
            line-height: 1.3; word-break: normal; overflow-wrap: normal; hyphens: auto; }}
        .ind-kpi-valor {{ font-size: clamp(20px, 2vw, 28px); font-weight: 700; color: {COLOR_TEXTO}; line-height: 1.2;
            margin-top: 4px; white-space: nowrap; }}
        .ind-kpi-detalle {{ font-size: 12.5px; color: {COLOR_TEXTO_SUAVE}; margin-top: 2px; }}
        .ind-seccion {{ margin: 22px 0 6px 0; }}
        .ind-seccion-titulo {{ font-size: 18px; font-weight: 700; color: {COLOR_TEXTO}; }}
        .ind-seccion-texto {{ font-size: 13.5px; color: {COLOR_TEXTO_SUAVE}; margin-top: 2px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_cabecera_indicador(titulo, descripcion=None):
    """Cabecera estándar: título y una frase de qué mide el indicador."""
    aplicar_estilos_indicador()
    texto = f'<div class="ind-descripcion">{descripcion}</div>' if descripcion else ""
    st.markdown(
        f'<div class="ind-cabecera"><div class="ind-titulo">{escape(str(titulo))}</div>{texto}</div>',
        unsafe_allow_html=True,
    )


def selector_vista(opciones, clave):
    """Reemplazo de st.tabs que recuerda la vista elegida: st.tabs volvía a la
    primera pestaña en cada recarga (al hacer clic en "Ver perfil", cambiar de
    página, preparar un PDF, etc.). Devuelve la opción elegida."""
    return st.segmented_control(
        "Vista", opciones, default=opciones[0], key=clave, label_visibility="collapsed",
    ) or opciones[0]


def opciones_cohorte(valores):
    """Cohortes para un selector: sin vacíos ni cohortes sin definir
    ("None - None") y de la más reciente a la más antigua."""
    validas = {str(v).strip() for v in valores if v is not None and v == v}
    return sorted((c for c in validas if c and "None" not in c and c.lower() != "nan"), reverse=True)


def render_tarjetas_kpi(items, columnas=None):
    """Fila de tarjetas. items: lista de dicts con etiqueta, valor y
    opcionalmente detalle (texto chico) y color (acento del borde)."""
    if not items:
        return
    columnas = columnas or len(items)
    cols = st.columns(columnas)
    for idx, item in enumerate(items):
        acento = item.get("color", COLOR_PRIMARIO)
        detalle = item.get("detalle")
        detalle_html = f'<div class="ind-kpi-detalle">{escape(str(detalle))}</div>' if detalle else ""
        with cols[idx % columnas]:
            st.markdown(
                f'<div class="ind-kpi" style="--acento:{acento};">'
                f'<div class="ind-kpi-etiqueta">{escape(str(item["etiqueta"]))}</div>'
                f'<div class="ind-kpi-valor">{escape(str(item["valor"]))}</div>{detalle_html}</div>',
                unsafe_allow_html=True,
            )


def render_titulo_seccion(titulo, texto=None):
    """Título de sección con una línea opcional de ayuda para leer lo que sigue."""
    ayuda = f'<div class="ind-seccion-texto">{texto}</div>' if texto else ""
    st.markdown(
        f'<div class="ind-seccion"><div class="ind-seccion-titulo">{escape(str(titulo))}</div>{ayuda}</div>',
        unsafe_allow_html=True,
    )


def estilizar_figura(fig, titulo_x=None, titulo_y=None, porcentaje=False, altura=None, leyenda=True):
    """Aplica el estilo común a una figura de Plotly: fondo blanco, grilla
    suave, tipografía, leyenda horizontal arriba y sin barra de colores
    continua (los colores de las barras se definen en cada página)."""
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Source Sans Pro, sans-serif", size=13, color=COLOR_TEXTO),
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(bgcolor="white", font_size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""),
        showlegend=leyenda,
        coloraxis_showscale=False,
        bargap=0.25,
        separators=",.",  # decimal "," y miles "."
    )
    if altura:
        fig.update_layout(height=altura)
    fig.update_xaxes(showgrid=False, linecolor=COLOR_BORDE, title_text=titulo_x)
    fig.update_yaxes(gridcolor="#eef2f6", zeroline=False, title_text=titulo_y, tickformat=",~f")
    if porcentaje:
        fig.update_yaxes(ticksuffix="%")
    return fig


def formatear_entero(valor):
    """1234567 -> '1.234.567' (separador de miles local)."""
    return f"{int(valor):,}".replace(",", ".")


def formatear_porcentaje(valor, decimales=1):
    """12.345 -> '12,3%'."""
    return f"{valor:,.{decimales}f}%".replace(",", "X").replace(".", ",").replace("X", ".")
