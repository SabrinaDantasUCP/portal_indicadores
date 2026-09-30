import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import zlib
from utils import db_pia
from services.data.permanencia import (
    VISTA_FECHA_CORTE,
    VISTA_VISION_GENERAL,
    get_periodo_config_efectivo,
    load_permanencia_lista,
)
from html import escape
from services.calculations.permanencia import (
    BASE_SEMESTRES,
    MOTIVOS_NR,
    PERIODO_DEFAULT,
    PERMANENCIA_INDICATORS,
    RESULTADO_FUERA,
    RESULTADO_NO_REMATRICULADO,
    RESULTADO_REMATRICULADO,
    calculate_permanencia_indicators,
    clasificar_alumnos,
    es_pago,
    es_recursante_anterior,
    get_periodo_config,
    listar_periodos,
)


@st.cache_data(show_spinner=False, max_entries=8, ttl=600)
def excel_bytes(df, sheet_name="Datos"):
    """Arma el Excel una sola vez por combinación de datos.

    st.download_button exige los bytes por adelantado, así que sin cache el
    archivo se generaba en cada rerun aunque nadie lo descargara.
    """
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def render_common_setup():
    st.markdown("""
        <style>
        [data-testid="stElementToolbar"] { display: none; }
        div[data-testid="stDownloadButton"] button {
            min-height: 50px !important;
            font-size: 16px !important;
            border-radius: 8px !important;
        }
        .metric-container {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            font-size: 1.2rem;
            font-weight: bold;
            color: #31333F;
            margin-bottom: 1rem;
        }
        table.custom_table {
            width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 12px;
        }
        table.custom_table th {
            background-color: #4b8cd9; color: white; text-align: center; padding: 5px; border: 1px solid #ddd;
        }
        table.custom_table td {
            text-align: center; padding: 5px; border: 1px solid #ddd;
        }
        .header_explicacion {
            background-color: #66a3ff !important;
        }
        /* Grupos de la pestaña Alumnos: los botones ocupan todo el ancho, iguales */
        div[class*="st-key-vista_"] button { flex: 1 1 0; }
        /* Selector de sección con aspecto de pestañas */
        div[class*="st-key-ip_seccion"] div[role="radiogroup"] {
            gap: 30px; width: 100%; border-bottom: 2px solid #e5e7eb; margin-bottom: 10px;
        }
        div[class*="st-key-ip_seccion"] label[data-baseweb="radio"] {
            padding: 4px 2px 10px 2px; margin: 0 0 -2px 0; border-bottom: 3px solid transparent;
            cursor: pointer;
        }
        div[class*="st-key-ip_seccion"] label[data-baseweb="radio"] > div:first-child { display: none; }
        div[class*="st-key-ip_seccion"] label[data-baseweb="radio"] p {
            font-size: 20px; font-weight: 700; color: #31333F;
        }
        div[class*="st-key-ip_seccion"] label[data-baseweb="radio"]:has(input:checked) {
            border-bottom-color: #1e3a8a;
        }
        div[class*="st-key-ip_seccion"] label[data-baseweb="radio"]:has(input:checked) p { color: #1e3a8a; }
        div[class*="st-key-ip_seccion"] label[data-baseweb="radio"]:hover p { color: #1e3a8a; }
        .ip_sec { border-left: 4px solid #1e3a8a; padding: 2px 0 2px 12px; margin: 4px 0 14px 0; }
        .ip_sec_tit { font-size: 21px; font-weight: 700; color: #1e3a8a; line-height: 1.3; }
        .ip_sec_sub { font-size: 14px; color: #6b7280; margin-top: 2px; }
        table.ip_tabla {
            width: 100%; border-collapse: separate; border-spacing: 0; font-size: 15px;
            border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; margin: 4px 0 6px 0;
        }
        table.ip_tabla th {
            background: #1e3a8a; color: #ffffff; font-weight: 600; text-align: center;
            padding: 11px 12px; border: none;
        }
        table.ip_tabla td {
            text-align: center; vertical-align: middle; padding: 10px 12px; color: #31333F;
            border: none; border-top: 1px solid #eef0f3;
        }
        table.ip_tabla tbody tr:nth-child(even) td { background: #f8fafc; }
        .ip_tabla_ip { font-weight: 700; }
        .ip_tabla_sem { font-size: 12px; color: #6b7280; }
        .ip_pill {
            display: inline-block; min-width: 58px; padding: 3px 12px; border-radius: 999px;
            font-weight: 700; border: 1px solid;
        }
        .ip_ficha {
            border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px 18px; background: #ffffff;
        }
        .ip_ficha_vacia { color: #6b7280; text-align: center; padding: 48px 18px; background: #f8fafc; }
        .ip_ficha_nombre { font-size: 20px; font-weight: 700; color: #1e3a8a; line-height: 1.25; }
        .ip_ficha_meta { font-size: 13px; color: #6b7280; margin: 2px 0 10px 0; }
        .ip_ficha_frase { font-size: 14.5px; color: #31333F; margin: 10px 0 12px 0; }
        .ip_ficha_per { background: #f8fafc; border: 1px solid #eef0f3; border-radius: 8px; padding: 10px 12px; }
        .ip_ficha_per_tit { font-size: 13px; font-weight: 700; color: #1e3a8a; margin-bottom: 4px; }
        .ip_ficha_dato { display: flex; justify-content: space-between; gap: 12px; font-size: 14px; padding: 2px 0; }
        .ip_ficha_dato span { color: #6b7280; }
        .ip_ficha_dato b { color: #31333F; text-align: right; }
        .ip_ficha_flecha { text-align: center; color: #9ca3af; font-size: 16px; line-height: 1.4; }
        .ip_ficha_nota { font-size: 12.5px; color: #6b7280; margin-top: 10px; }
        table.ip_tabla td.ip_td_izq { text-align: left; }
        .ip_aviso {
            background: #fff8dc; border-left: 4px solid #f2c94c; border-radius: 0 8px 8px 0;
            padding: 10px 14px; margin: 4px 0 6px 0; font-size: 15px; color: #5c4a00;
        }
        .ip_titulo { font-size: 30px; font-weight: 800; color: #1e3a8a; line-height: 1.2; }
        .ip_subtitulo { font-size: 15px; color: #6b7280; margin-top: 2px; }
        </style>
    """, unsafe_allow_html=True)

# Nombre de cada vista, para mostrarlo en el título del indicador.
VISTA_LABELS = {
    "actual": "Visión General",
    "corte": "Fecha de Corte",
}

VISTA_POR_SUFIJO = {
    "actual": VISTA_VISION_GENERAL,
    "corte": VISTA_FECHA_CORTE,
}

# Lo que se muestra en la tabla cuando no hay dato.
SIN_DATO = "-"

SECCION_RESUMEN = "Resumen"
SECCION_ALUMNOS = "Alumnos"
SECCION_METODO = "¿Cómo se calcula?"
SECCIONES = [SECCION_RESUMEN, SECCION_ALUMNOS, SECCION_METODO]

# (mínimo aceptable, meta) de cada IP: debajo del mínimo es rojo, entre los dos amarillo.
METAS_IP = {1: (76, 80)}
METAS_IP_DEFAULT = (86, 90)

# estado -> (texto, color del texto/número, fondo, borde)
ESTADOS_META = {
    "ok": ("Alcanzada o superada", "#2e7d32", "#edf7ee", "#a5d6a7"),
    "warn": ("Aceptable / Advertencia", "#8a6100", "#fff8e1", "#ffd54f"),
    "bad": ("No alcanzado", "#c62828", "#fdecea", "#ef9a9a"),
}
# Color del cuadradito de cada estado en el tooltip (los de la tabla de metas).
COLOR_SQ_META = {"ok": "#388e3c", "warn": "#fbc02d", "bad": "#d32f2f"}


def tooltip_indicador(ind, row, p_base, p_dest):
    """Descripción y metas de un IP, para el hover de su barra (HTML de plotly)."""
    minimo, meta = METAS_IP.get(ind["r_nivel"], METAS_IP_DEFAULT)
    rangos = {
        "ok": f"≥ {meta}%",
        "warn": f"{minimo}% - {meta - 1}%",
        "bad": f"&lt; {minimo}%",
    }
    estado = estado_meta(ind["r_nivel"], row["tasa_num"])
    metas = "<br>".join(
        f"<span style='color:{COLOR_SQ_META[e]}'>■</span> {ESTADOS_META[e][0]}: <b>{rangos[e]}</b>"
        for e in ("ok", "warn", "bad")
    )
    return (
        f"<b>IP {ind['r_nivel']}</b> · {ind['sem_origen']}º → {ind['sem_destino']}º semestre<br>"
        f"<b>{row['tasa_num']:.0f}%</b> · {fmt_int(row['Rematrícula'])} de {fmt_int(row['Inicio'])} · "
        f"<span style='color:{COLOR_SQ_META[estado]}'>{ESTADOS_META[estado][0]}</span><br><br>"
        f"Alumnos que inician el {ind['sem_origen']}º semestre en el {p_base}<br>"
        f"y al terminar se rematricularon para el {p_dest}.<br><br>"
        f"<b>Metas</b><br>{metas}"
    )

# Motivo -> color en el gráfico de no rematriculados.
# Tonos de azul (no rojo/amarillo, que en el gráfico de barras significan la meta).
# motivo -> (color de la barra, color del número adentro)
COLORES_MOTIVO = {
    "Trancado": ("#a9c1e6", "#1e3a8a"),
    "Reprobado": ("#4b7bc4", "#ffffff"),
    "Abandono": ("#1e3a8a", "#ffffff"),
}


def fmt_int(n):
    return f"{int(n):,}".replace(",", ".")


def estado_meta(nivel, tasa):
    minimo, meta = METAS_IP.get(nivel, METAS_IP_DEFAULT)
    if tasa >= meta:
        return "ok"
    return "warn" if tasa >= minimo else "bad"


def titulo_seccion(titulo, subtitulo=""):
    sub = f"<div class='ip_sec_sub'>{subtitulo}</div>" if subtitulo else ""
    st.markdown(f"<div class='ip_sec'><div class='ip_sec_tit'>{titulo}</div>{sub}</div>", unsafe_allow_html=True)


def tabla_indicador_html(df_vp, p_base, p_dest):
    """Tabla del indicador: datos centralizados y el % con el color de su meta."""
    filas = []
    for ind, (_, row) in zip(PERMANENCIA_INDICATORS, df_vp.iterrows()):
        _, color, fondo, borde = ESTADOS_META[estado_meta(ind["r_nivel"], row["tasa_num"])]
        filas.append(
            "<tr>"
            f"<td><div class='ip_tabla_ip'>{row['Indicador']}</div>"
            f"<div class='ip_tabla_sem'>{ind['sem_origen']}º → {ind['sem_destino']}º semestre</div></td>"
            f"<td>{fmt_int(row['Inicio'])}</td>"
            f"<td>{fmt_int(row['Rematrícula'])}</td>"
            f"<td><span class='ip_pill' style='color:{color};background:{fondo};border-color:{borde}'>"
            f"{row['% de Permanencia']}</span></td>"
            "</tr>"
        )
    return (
        "<table class='ip_tabla'><thead><tr>"
        f"<th>Indicador</th><th>Inicio {p_base}</th><th>Rematrícula {p_dest}</th><th>% de Permanencia</th>"
        f"</tr></thead><tbody>{''.join(filas)}</tbody></table>"
    )


def render_resumen(df_vp, df_nr, p_base, p_dest, k):
    """Pestaña Resumen: cada IP contra su meta (barras con descripción y metas en
    el hover), por qué no volvieron y la tabla del indicador. Cada parte en su tarjeta."""
    # --- Una barra por IP, con el color de su meta ---
    with st.container(border=True):
        titulo_seccion(
            "Permanencia por indicador",
            f"Porcentaje de alumnos que iniciaron el {p_base} y se rematricularon en el {p_dest}. "
            "Pase el mouse sobre cada barra para ver su descripción y sus metas.",
        )
        render_barras_ip(df_vp, p_base, p_dest, k)

    # --- Por qué no volvieron ---
    with st.container(border=True):
        titulo_seccion(
            "¿Por qué no se rematricularon?",
            "Alumnos de la base que no se rematricularon, por motivo, en cada indicador.",
        )
        render_motivos(df_nr, k)

    # --- Tabla del indicador ---
    with st.container(border=True):
        titulo_seccion(
            "Resumen por indicador",
            f"Alumnos que iniciaron cada semestre en el {p_base} y cuántos se rematricularon en el {p_dest}.",
        )
        st.markdown(tabla_indicador_html(df_vp, p_base, p_dest), unsafe_allow_html=True)


def render_barras_ip(df_vp, p_base, p_dest, k):
    filas = list(zip(PERMANENCIA_INDICATORS, (row for _, row in df_vp.iterrows())))
    fig_ip = go.Figure(go.Bar(
        x=df_vp["Indicador"],
        y=df_vp["tasa_num"],
        marker_color=[COLOR_SQ_META[estado_meta(ind["r_nivel"], row["tasa_num"])] for ind, row in filas],
        text=df_vp["% de Permanencia"],
        textposition="outside",
        textfont=dict(size=22, family="Arial Black", color="#6b7280"),
        hovertext=[tooltip_indicador(ind, row, p_base, p_dest) for ind, row in filas],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    fig_ip.update_layout(
        yaxis_range=[0, 110], height=320, showlegend=False,
        margin=dict(t=10, b=0, l=0, r=0),
        xaxis=dict(tickfont=dict(size=16, family="Arial Black")),
        yaxis=dict(tickfont=dict(size=12)),
        hoverlabel=dict(bgcolor="#1f2937", bordercolor="#1f2937", align="left",
                        font=dict(color="#f9fafb", size=13)),
    )
    st.plotly_chart(fig_ip, use_container_width=True, key=f"ip_barras_{k}")


def render_motivos(df_nr, k):
    if int(df_nr["No rematriculados"].sum()) == 0:
        st.success("Todos los alumnos de la base se rematricularon.")
    else:
        df_mot = df_nr.melt(
            id_vars="Nivel", value_vars=list(MOTIVOS_NR.values()),
            var_name="Motivo", value_name="Alumnos",
        )
        df_mot["Motivo"] = df_mot["Motivo"].map({col: m for m, col in MOTIVOS_NR.items()})
        df_mot["Indicador"] = "IP " + df_mot["Nivel"].astype(str)
        totales = df_mot.groupby("Motivo")["Alumnos"].sum()
        etiqueta = {m: f"{m} ({fmt_int(totales.get(m, 0))})" for m in MOTIVOS_NR}
        df_mot["Motivo_base"] = df_mot["Motivo"]
        df_mot["Motivo"] = df_mot["Motivo"].map(etiqueta)

        fig = px.bar(
            df_mot[df_mot["Alumnos"] > 0], x="Alumnos", y="Indicador", color="Motivo",
            orientation="h", text="Alumnos", custom_data=["Motivo_base"],
            color_discrete_map={etiqueta[m]: c for m, (c, _) in COLORES_MOTIVO.items()},
            category_orders={
                "Indicador": [f"IP {i['r_nivel']}" for i in PERMANENCIA_INDICATORS],
                "Motivo": list(etiqueta.values()),
            },
        )
        texto_por_motivo = {etiqueta[m]: t for m, (_, t) in COLORES_MOTIVO.items()}
        fig.update_traces(textposition="inside", insidetextanchor="middle",
                          marker_line=dict(color="#ffffff", width=1.5),
                          hovertemplate="%{y} · %{customdata[0]}: <b>%{x}</b> alumnos<extra></extra>")
        fig.for_each_trace(lambda t: t.update(textfont=dict(size=14, color=texto_por_motivo[t.name])))
        fig.update_layout(
            barmode="stack", bargap=0.35, height=300, margin=dict(t=10, b=0, l=0, r=0),
            xaxis=dict(title="Alumnos no rematriculados", gridcolor="#eef0f3"),
            yaxis=dict(title=None, tickfont=dict(size=15, family="Arial Black")),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None,
                        font=dict(size=14)),
        )
        st.plotly_chart(fig, use_container_width=True, key=f"motivos_{k}")
        st.caption(
            "Trancado: matrícula trancada · Reprobado: no está trancado y reprobó al menos una materia · "
            "Abandono: ninguno de los anteriores."
        )


def _txt(valor):
    """Valor de una fila para mostrar: vacío/nulo -> '-'."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return SIN_DATO
    texto = str(valor).strip()
    return SIN_DATO if texto.lower() in ("", "nan", "none", "<na>", "nat") else texto


def _sem(valor):
    n = pd.to_numeric(valor, errors="coerce")
    return f"{int(n)}º semestre" if pd.notna(n) and n > 0 else "sin matrícula"


# resultado -> (color del texto, fondo, borde): la misma paleta de las metas.
RESULTADO_ESTILO = {
    RESULTADO_REMATRICULADO: ("#2e7d32", "#edf7ee", "#a5d6a7"),
    RESULTADO_NO_REMATRICULADO: ("#c62828", "#fdecea", "#ef9a9a"),
    RESULTADO_FUERA: ("#4b5563", "#f3f4f6", "#d1d5db"),
}


def _pill(texto, estilo):
    color, fondo, borde = estilo
    return (f"<span class='ip_pill' style='color:{color};background:{fondo};border-color:{borde}'>"
            f"{escape(texto)}</span>")


def _dato(etiqueta, valor):
    return (f"<div class='ip_ficha_dato'><span>{etiqueta}</span>"
            f"<b>{escape(valor)}</b></div>")


def render_ficha_alumno(row, p_base, p_dest, p_ant):
    """Ficha de un alumno: su recorrido y, en una frase, por qué quedó así."""
    resultado = row["Resultado"]
    motivo = row["Motivo"]
    fila = pd.DataFrame([row])

    if resultado == RESULTADO_REMATRICULADO:
        frase = f"Rematriculado en el {p_dest}: {motivo.lower()}."
    elif resultado == RESULTADO_NO_REMATRICULADO:
        sem_prox = pd.to_numeric(row["sem_proximo"], errors="coerce")
        if pd.isna(sem_prox) or sem_prox <= 0:
            causa = f"no tiene matrícula en el {p_dest}"
        elif not es_pago(fila, "estado_pago_proximo").iloc[0]:
            causa = f"la primera cuota del {p_dest} no está pagada ni al día ({_txt(row.get('estado_pago_proximo'))})"
        else:
            causa = f"en el {p_dest} está en {_sem(sem_prox)}"
        frase = f"No rematriculado: {causa}. Motivo: {motivo.lower()}."
    else:
        frase = f"No entra en el cálculo del indicador: {motivo}."

    notas = []
    if es_recursante_anterior(fila).iloc[0]:
        notas.append(f"Ya estaba en el mismo semestre en el {p_ant} (recursante de periodos anteriores).")
    if _txt(row.get("fecha_cambio")) != SIN_DATO:
        notas.append(
            f"Último cambio de matrícula: {_txt(row.get('fecha_cambio'))} por {_txt(row.get('usuario_cambio'))} "
            f"({_txt(row.get('momento_cambio'))}). {_txt(row.get('desc_audit_log'))}"
        )
    notas_html = "".join(f"<div class='ip_ficha_nota'>{escape(n)}</div>" for n in notas)

    # Solo los datos que existen: sin "· - ·" cuando falta alguno.
    antiguedad = _txt(row.get("analise_primer_periodo"))
    antiguedad = {"Veterano": "Antiguo"}.get(antiguedad, antiguedad)
    matricula = _txt(row.get("numero_catraca"))
    partes = [f"Matrícula {matricula}" if matricula != SIN_DATO else SIN_DATO,
              _txt(row.get("tipo_matricula")), antiguedad]
    meta = " · ".join(escape(p) for p in partes if p != SIN_DATO)

    # Para el rematriculado el resultado académico no aporta: ya volvió.
    resultado_academico = "" if resultado == RESULTADO_REMATRICULADO else _dato(
        "Resultado académico", _txt(row.get("status_academico")).capitalize()
    )

    st.markdown(
        "<div class='ip_ficha'>"
        f"<div class='ip_ficha_nombre'>{escape(_txt(row.get('nombre_apellido')))}</div>"
        f"<div class='ip_ficha_meta'>{meta}</div>"
        f"{_pill(resultado, RESULTADO_ESTILO[resultado])}"
        f"<div class='ip_ficha_frase'>{escape(frase)}</div>"
        f"<div class='ip_ficha_per'><div class='ip_ficha_per_tit'>{p_base} · Inicio</div>"
        f"{_dato('Semestre', _sem(row['sem_atual']))}"
        f"{_dato('Primera cuota', _txt(row.get('estado_pago_atual')))}"
        f"{_dato('Estado de matrícula', _txt(row.get('estado_matricula')).capitalize())}"
        f"{resultado_academico}</div>"
        "<div class='ip_ficha_flecha'>↓</div>"
        f"<div class='ip_ficha_per'><div class='ip_ficha_per_tit'>{p_dest} · Rematrícula</div>"
        f"{_dato('Semestre', _sem(row['sem_proximo']))}"
        f"{_dato('Primera cuota', _txt(row.get('estado_pago_proximo')))}</div>"
        f"{notas_html}"
        "</div>",
        unsafe_allow_html=True,
    )


VISTAS_ALUMNOS = {
    RESULTADO_REMATRICULADO: "Rematriculados",
    RESULTADO_NO_REMATRICULADO: "No rematriculados",
    RESULTADO_FUERA: "Fuera de la base",
    "Todos": "Todos",
}


def render_alumnos(df_lista, incluir_convalidados, incluir_recursantes, p_base, p_dest, p_ant, k):
    """Pestaña Alumnos: grupos listos (quién volvió, quién no, quién quedó fuera),
    filtros, la tabla y al lado la ficha del alumno seleccionado."""
    clasif = clasificar_alumnos(df_lista, incluir_convalidados, incluir_recursantes, p_base)
    df = df_lista.assign(
        Resultado=clasif["resultado"],
        Motivo=clasif["motivo"],
        IP=np.where(df_lista["sem_atual"].isin(BASE_SEMESTRES), "IP " + df_lista["sem_atual"].astype(str), SIN_DATO),
    )

    base_cols = {
        "nombre_apellido": "Nombre",
        "numero_catraca": "Matrícula",
        "estado_pago_proximo": f"Cuota {p_dest}",
        "Resultado": "Resultado",
        "Motivo": "Motivo",
    }
    extra_cols = {
        "IP": "IP",
        "sem_atual": f"Semestre {p_base}",
        "sem_proximo": f"Semestre {p_dest}",
        "estado_pago_atual": f"Cuota {p_base}",
        "monto_pagado_atual": f"Monto pagado {p_base}",
        "monto_pagado_proximo": f"Monto pagado {p_dest}",
        "estado_matricula": "Estado de matrícula",
        "status_academico": "Resultado académico",
        "tipo_matricula": "Tipo de matrícula",
        "tipo_alumno": "Tipo de alumno",
        "recursante_primera_vez": "¿Recursa por primera vez?",
        "es_recursante": "¿Recursante de periodos anteriores?",
        "fecha_cambio": "Fecha de cambio",
        "usuario_cambio": "Usuario del cambio",
        "desc_audit_log": "Auditoría",
    }
    extra_cols = {c: e for c, e in extra_cols.items() if c in df.columns}

    # Qué es cada columna: tooltip en la tabla y "?" en "Más columnas".
    descripciones = {
        "nombre_apellido": "Nombre y apellido del alumno.",
        "numero_catraca": "Número de catraca del alumno.",
        "estado_pago_proximo": (
            f"Estado de la primera cuota del {p_dest} (rematrícula): Paga, Negociada - Paga, "
            "Negociada - Pendiente (al día), Negociada - Vencida, Pendiente o Sin Factura."
        ),
        "Resultado": (
            "Rematriculado, No rematriculado o Fuera de la base (el alumno no entra en el cálculo del indicador)."
        ),
        "Motivo": (
            "Rematriculado: si avanzó de semestre o lo recursa. No rematriculado: Trancado, "
            "Reprobado o Abandono. Si quedó fuera de la base: por qué no entra en el cálculo."
        ),
        "IP": f"Indicador del alumno según su semestre en el {p_base} (IP 1 = 1º semestre ... IP 5 = 5º semestre).",
        "sem_atual": f"Semestre en el que estaba el alumno en el {p_base}.",
        "sem_proximo": f"Semestre en el que está matriculado en el {p_dest} ('-' si no tiene matrícula).",
        "estado_pago_atual": f"Estado de la primera cuota del {p_base} (inicio).",
        "monto_pagado_atual": f"Monto de la primera cuota del {p_base}, en Gs. Solo aparece si está efectivamente pagada.",
        "monto_pagado_proximo": f"Monto de la primera cuota del {p_dest}, en Gs. Solo aparece si está efectivamente pagada.",
        "estado_matricula": "Estado actual de la matrícula: Activo, Trancado o Suspenso.",
        "status_academico": (
            f"Aprobado o Reprobado en el {p_base} (reprobado = al menos una materia con nota final menor a 60). "
            "'Sem notas' si no tiene notas cargadas."
        ),
        "tipo_matricula": "Tipo de matrícula del curso: Normal o Convalidado.",
        "tipo_alumno": f"Antiguo o Nuevo, según el registro del alumno en el periodo lectivo {p_base}.",
        "recursante_primera_vez": f"SI: está en el mismo semestre en el {p_base} y en el {p_dest}, por primera vez.",
        "es_recursante": (
            f"SI: ya estaba en el mismo semestre en el {p_ant} y en el {p_base}. "
            "Estos alumnos quedan siempre fuera del análisis."
        ),
        "fecha_cambio": "Fecha del último cambio de estado de la matrícula (trancado o suspenso). Vacío si está activo.",
        "usuario_cambio": "Funcionario que hizo el último cambio de estado de la matrícula.",
        "desc_audit_log": "Descripción registrada en la auditoría del sistema para ese cambio de matrícula.",
    }

    with st.container(border=True):
        titulo_seccion(
            "Alumnos",
            f"Elija un grupo, filtre y seleccione un alumno en la tabla para ver su ficha "
            f"(inicio {p_base} → rematrícula {p_dest}).",
        )

        conteo = df["Resultado"].value_counts()
        etiquetas = {
            v: f"{txt} ({fmt_int(len(df) if v == 'Todos' else conteo.get(v, 0))})"
            for v, txt in VISTAS_ALUMNOS.items()
        }
        vista = st.segmented_control(
            "Grupo", options=list(VISTAS_ALUMNOS), format_func=etiquetas.get,
            default=RESULTADO_REMATRICULADO, key=f"vista_{k}", label_visibility="collapsed",
            width="stretch",
        ) or RESULTADO_REMATRICULADO
        if vista != "Todos":
            df = df[df["Resultado"] == vista]

        c_busca, c_ip, c_motivo, c_mas = st.columns([2.2, 1, 1.6, 0.9], vertical_alignment="bottom")
        with c_busca:
            busca = st.text_input("Buscar", placeholder="Nombre o número de matrícula", key=f"busca_{k}")
        with c_ip:
            ips = sorted(i for i in df["IP"].unique() if i != SIN_DATO)
            sel_ip = st.multiselect("IP", options=ips, placeholder="Todos", key=f"ip_{k}")
        with c_motivo:
            motivos = sorted(m for m in df["Motivo"].dropna().unique() if m)
            sel_motivo = st.multiselect("Motivo", options=motivos, placeholder="Todos", key=f"motivo_{k}")
        with c_mas:
            n_extra = sum(bool(st.session_state.get(f"col_{c}_{k}")) for c in extra_cols)
            with st.popover(f"Más columnas ({n_extra})" if n_extra else "Más columnas", use_container_width=True):
                st.markdown("**Columnas adicionales en la tabla**")
                col_a, col_b = st.columns(2)
                mitad = (len(extra_cols) + 1) // 2
                for i, (c, etiqueta) in enumerate(extra_cols.items()):
                    with (col_a if i < mitad else col_b):
                        st.checkbox(etiqueta, key=f"col_{c}_{k}", help=descripciones.get(c))
                sel_extra = [c for c in extra_cols if st.session_state.get(f"col_{c}_{k}")]

    if busca.strip():
        texto = busca.strip()
        df = df[df["nombre_apellido"].astype(str).str.contains(texto, case=False, na=False, regex=False)
                | df["numero_catraca"].astype(str).str.contains(texto, case=False, na=False, regex=False)]
    if sel_ip:
        df = df[df["IP"].isin(sel_ip)]
    if sel_motivo:
        df = df[df["Motivo"].isin(sel_motivo)]

    # --- Tabla: pocas columnas; el resto se agrega en "Más columnas" ---
    cols = {**base_cols, **{c: extra_cols[c] for c in sel_extra}}
    df_view = df[list(cols)].rename(columns=cols)

    anchos = {"nombre_apellido": "medium", "numero_catraca": "small", "IP": "small", "Motivo": "large"}
    column_config = {
        etiqueta: st.column_config.Column(
            help=descripciones.get(c), width=anchos.get(c), pinned=(c == "nombre_apellido") or None,
        )
        for c, etiqueta in cols.items()
    }

    for c in (f"Semestre {p_base}", f"Semestre {p_dest}"):
        if c in df_view.columns:
            df_view[c] = (pd.to_numeric(df_view[c], errors="coerce").replace(0, np.nan)
                          .astype("Int64").astype(str).replace("<NA>", SIN_DATO))
    for c in ("Estado de matrícula", "Resultado académico"):
        if c in df_view.columns:
            df_view[c] = df_view[c].astype(str).str.capitalize()
    if "Tipo de alumno" in df_view.columns:
        df_view["Tipo de alumno"] = df_view["Tipo de alumno"].replace({"A": "Antiguo", "N": "Nuevo"})
    for c in df_view.columns:
        if pd.api.types.is_object_dtype(df_view[c]):
            df_view[c] = df_view[c].map(_txt)

    montos = [c for c in df_view.columns if c.startswith("Monto pagado")]
    tabla = (
        df_view.style
        .map(lambda v: f"color: {RESULTADO_ESTILO[v][0]}; font-weight: 600" if v in RESULTADO_ESTILO else "",
             subset=["Resultado"])
        .format(lambda v: SIN_DATO if pd.isna(v) else fmt_int(v), subset=montos)
    )

    # La selección se reinicia al cambiar grupo o filtros: si no, la fila marcada
    # pasaría a ser otro alumno.
    filtros = (vista, busca.strip(), tuple(sel_ip), tuple(sel_motivo))
    clave_tabla = f"tabla_alumnos_{k}_{zlib.crc32(repr(filtros).encode())}"

    c_tabla, c_ficha = st.columns([1.75, 1], gap="medium")
    with c_tabla:
        evento = st.dataframe(
            tabla, hide_index=True, width="stretch", height=520,
            on_select="rerun", selection_mode="single-row", key=clave_tabla,
            column_config=column_config,
        )
        c_n, c_dl = st.columns([2, 1], vertical_alignment="center")
        with c_n:
            st.caption(f"{fmt_int(len(df_view))} alumnos en la lista.")
        with c_dl:
            st.download_button(
                "Descargar lista (Excel)",
                data=excel_bytes(df_view, "Alumnos"),
                file_name=f"Permanencia_Alumnos_{p_base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                icon=":material/download:",
                key=f"btn_dl_lista_{k}",
                use_container_width=True,
                on_click=db_pia.log_export_callback, args=("Índice de Permanencia - Lista", "Excel"),
            )

    with c_ficha:
        filas = evento.selection.rows if evento else []
        if filas and filas[0] < len(df):
            render_ficha_alumno(df.iloc[filas[0]], p_base, p_dest, p_ant)
        else:
            st.markdown(
                "<div class='ip_ficha ip_ficha_vacia'>Seleccione un alumno en la tabla "
                "para ver su recorrido y por qué quedó en este grupo.</div>",
                unsafe_allow_html=True,
            )


def render_encabezado(suffix):
    """Título y selector de periodo en una sola línea. El periodo es obligatorio:
    sin selección no se muestra ningún dato."""
    c_tit, c_sel = st.columns([3, 1.1], vertical_alignment="bottom")
    with c_sel:
        periodo = st.selectbox(
            "Periodo",
            options=listar_periodos(),
            index=None,
            placeholder="Elija el periodo",
            key=f"ip_periodo_{suffix}",
            format_func=lambda p: f"{p} → {get_periodo_config(p)['destino']}",
        )

    vista = VISTA_LABELS.get(suffix, suffix)
    if periodo and suffix == "corte":
        corte_cfg = db_pia.get_permanencia_etl_config(periodo)
        if corte_cfg and corte_cfg.get("fecha_corte"):
            vista = f"{vista} ({corte_cfg['fecha_corte'].strftime('%d/%m/%Y')})"

    with c_tit:
        if periodo:
            titulo = f"Índice de Permanencia {periodo}"
            sub = f"{vista} · Inicio {periodo} → Rematrícula {get_periodo_config(periodo)['destino']}"
        else:
            titulo = "Índice de Permanencia"
            sub = f"{vista} · Elija el periodo a la derecha para ver los datos"
        st.markdown(
            f"<div class='ip_titulo'>{titulo}</div><div class='ip_subtitulo'>{sub}</div>",
            unsafe_allow_html=True,
        )
    return periodo


def render_actual():
    render_common_setup()
    periodo = render_encabezado("actual")
    if periodo:
        render_permanence_module("actual", periodo)

def render_corte():
    render_common_setup()
    periodo = render_encabezado("corte")
    if periodo:
        render_permanence_module("corte", periodo)

def render():
    # Por defecto cargamos la versión actual si alguien llama a .render()
    render_actual()


def render_permanence_module(suffix="", periodo=PERIODO_DEFAULT):
    # Las fechas pueden estar configuradas por un admin; si no, son las del código.
    config = get_periodo_config_efectivo(periodo)
    p_base = periodo
    p_dest = config["destino"]
    p_ant = config["anterior"]
    # Las claves de los widgets llevan el periodo para que los filtros se
    # reinicien al cambiar de indicador.
    k = f"{suffix}_{p_base}"

    df_lista = load_permanencia_lista(
        periodo,
        VISTA_POR_SUFIJO[suffix],
        config["limite_primer_semestre"],
        config["limite_otros_semestres"],
    )
    if df_lista.empty:
        st.warning(f"No hay datos de permanencia disponibles para el periodo {periodo}.")
        return

    # === Parámetros del cálculo (valen para todas las pestañas) ===
    st.markdown("<div style='height: 14px'></div>", unsafe_allow_html=True)
    col_conv, col_rec, col_nota = st.columns([1, 1.2, 2.3], vertical_alignment="center")
    with col_conv:
        incluir_convalidados = st.toggle(
            "Incluir convalidados", value=False, key=f"conv_{k}",
            help="Alumnos con matrícula convalidada que ya cursaron al menos un semestre. "
                 "Los convalidados en su primer semestre quedan siempre fuera.",
        )
    with col_rec:
        incluir_recursantes = st.toggle(
            "Incluir recursantes (1ª vez)", value=False, key=f"recurs_{k}",
            help=f"Alumnos que recursan el semestre por primera vez (mismo semestre en {p_base} y {p_dest}). "
                 f"Los que ya venían recursando de periodos anteriores quedan siempre fuera del análisis.",
        )
    with col_nota:
        st.caption("Parámetros del cálculo (desactivados por defecto). Afectan al Resumen y a la lista de Alumnos.")

    # === Pestañas ===
    # No se usa st.tabs: guarda la pestaña solo en el navegador y vuelve a la
    # primera cuando la página se redibuja (ej. al cambiar la vista en Alumnos).
    # Un radio con key la conserva en la sesión (con estilo de pestañas en el CSS)
    # y además solo se calcula la pestaña abierta.
    seccion = st.radio(
        "Sección", SECCIONES, horizontal=True, key=f"ip_seccion_{k}", label_visibility="collapsed",
    )

    if seccion == SECCION_RESUMEN:
        df_vp, df_nr, _ = calculate_permanencia_indicators(
            df_lista,
            incluir_convalidados=incluir_convalidados,
            incluir_recursantes=incluir_recursantes,
            periodo=periodo,
        )
        render_resumen(df_vp, df_nr, p_base, p_dest, k)
    elif seccion == SECCION_ALUMNOS:
        render_alumnos(df_lista, incluir_convalidados, incluir_recursantes, p_base, p_dest, p_ant, k)
    else:
        render_metodologia(config, p_base, p_dest, p_ant)


def render_metodologia(config, p_base, p_dest, p_ant):
    lim_primer_sem = pd.to_datetime(config["limite_primer_semestre"]).strftime("%d/%m/%Y")
    lim_otros_sem = pd.to_datetime(config["limite_otros_semestres"]).strftime("%d/%m/%Y")

    titulo_seccion(
        "Criterios y Metodología de Análisis",
        f"A continuación se detallan las reglas lógicas y comerciales aplicadas para obtener los resultados "
        f"del Índice de Permanencia {p_base}.",
    )

    with st.container(border=True):
        titulo_seccion("1. ¿Qué es la Permanencia?")
        st.markdown(f"""
La permanencia mide cuántos alumnos que estudiaron en el periodo **{p_base}** continuaron en el siguiente periodo **{p_dest}**.

- **Quiénes se consideran (base)**: todos los alumnos que pagaron su primera cuota en {p_base} o que la negociaron y están al día (ver punto 6).
- **Cuándo se considera que un alumno continuó (éxito)**: cuando el alumno
    - pagó su primera cuota en {p_dest} (o la negoció y está al día), y
    - avanzó de semestre o permaneció en el mismo (recursante por primera vez).
""")
        st.markdown(
            "<div class='ip_aviso'><b>Nota:</b> el caso \"permaneció en el mismo semestre\" solo se contabiliza "
            "cuando el filtro de Recursantes (ver punto 4) está activo — si está desactivado, esos alumnos quedan "
            "fuera de la base y no llegan a evaluarse acá.</div>",
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        titulo_seccion("2. Fechas importantes (bajas de matrícula)")
        st.markdown(f"""
Si el alumno tuvo un cambio de estado a **suspenso** o **trancado**:

- **Antes del inicio de clases**: no se tiene en cuenta en el análisis.
    - **{lim_primer_sem}**: alumnos de 1º semestre
    - **{lim_otros_sem}**: alumnos antiguos
- **Después del inicio de clases**: sí se incluye en el análisis (como retenido o no retenido).
""")

    with st.container(border=True):
        titulo_seccion("3. Alumnos que no continuaron")
        st.markdown(f"""
Los alumnos que estaban en {p_base} pero no siguieron en {p_dest} se clasifican así:

- **Trancados**: si el alumno tiene el estado **trancado**, se contabiliza en esta categoría.
- **Reprobados**: si el alumno **no está trancado** y tiene al menos una materia reprobada, se contabiliza aquí.
- **Abandonos**: si el alumno **no está trancado** y **no tiene materias reprobadas**, se contabiliza en esta categoría.
""")

    with st.container(border=True):
        titulo_seccion("4. Filtros del sistema")
        st.markdown(f"""
El sistema permite activar o desactivar ciertos tipos de alumnos:

- **Convalidados**
- **Recursantes**: alumnos que recursan el semestre **por primera vez**, es decir, que están en **el mismo semestre** en {p_base} y en {p_dest} (ej.: 2º semestre en {p_base} y 2º semestre de nuevo en {p_dest}). Si el filtro está activo, entran en la base y cuentan como rematriculados (si pagaron la primera cuota de {p_dest}).

Si estos filtros están apagados, esos alumnos no se incluyen en el análisis, para que el indicador sea más preciso.
""")

    with st.container(border=True):
        titulo_seccion("5. Exclusiones")
        st.markdown(f"""
- Alumnos convalidados en su primer semestre están siendo desconsiderados del cálculo; solo se incluyen aquellos alumnos convalidados que ya han cursado al menos un semestre.
- Alumnos que **ya venían recursando de periodos anteriores** (mismo semestre en {p_ant} y en {p_base}) quedan siempre fuera del análisis, sin importar el filtro de Recursantes. En la pestaña Alumnos aparecen en la vista "Fuera de la base" con el motivo correspondiente.
""")

    with st.container(border=True):
        titulo_seccion(
            "6. Análisis de pagos (primera cuota)",
            f"Para {p_base} (base) y {p_dest} (rematrícula) se analiza la primera cuota del periodo "
            "(cuota 1; si fue cancelada y reemitida, se toma la reemitida).",
        )
        si = _pill("Sí", RESULTADO_ESTILO[RESULTADO_REMATRICULADO])
        no = _pill("No", RESULTADO_ESTILO[RESULTADO_NO_REMATRICULADO])
        pagos = [
            ("Paga", "", si),
            ("Negociada - Paga / Renegociada - Paga", "Todas las cuotas de la negociación están pagadas.", si),
            ("Negociada - Pendiente / Renegociada - Pendiente",
             "La negociación tiene cuotas por vencer, pero ninguna vencida (alumno al día).", si),
            ("Negociada - Vencida / Renegociada - Vencida", "Al menos una cuota de la negociación está vencida.", no),
            ("Pendiente (sin negociar) / Sin Factura", "", no),
        ]
        filas = "".join(
            f"<tr><td class='ip_td_izq'><b>{estado}</b></td><td class='ip_td_izq'>{desc}</td><td>{pill}</td></tr>"
            for estado, desc, pill in pagos
        )
        st.markdown(
            "<table class='ip_tabla'><thead><tr><th>Estado de la primera cuota</th><th>Descripción</th>"
            f"<th>¿Cuenta como pagada?</th></tr></thead><tbody>{filas}</tbody></table>",
            unsafe_allow_html=True,
        )
        st.markdown("""
- Cuando la primera cuota fue negociada, se analizan las cuotas generadas por la **negociación más reciente**. Si alguna de esas cuotas fue negociada de nuevo, se sigue esa nueva negociación (**Renegociada**).
- Una cuota se considera **vencida** si no está pagada y su fecha de vencimiento es anterior a la fecha en que se actualizaron los datos. Por eso, un alumno al día puede pasar a vencido en una actualización posterior.
- En la pestaña Alumnos, la columna de **Monto pagado** solo muestra el valor cuando la cuota está efectivamente pagada; en una negociación al día queda vacía.
""")
