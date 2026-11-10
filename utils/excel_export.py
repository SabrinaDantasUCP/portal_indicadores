import datetime
import io
import os
import pandas as pd
import streamlit as st
import xlsxwriter
from utils.data_loader import get_global_data_path
from utils.system_logging import log_exception

# Constantes de diseño institucional (estándar de Listado de Alumnos)
COLOR_AZUL_INST = "#1B365D"
COLOR_CEBRA = "#F8FAFC"
COLOR_BORDE = "#E2E8F0"
COLOR_BORDE_CABECERA = "#334E68"
COLOR_SUBTITULO = "#64748B"


def generar_excel_estilizado(
    datos,
    titulo="REPORTE INSTITUCIONAL",
    subtitulo=None,
    filtros=None,
    nombre_hoja_default="Datos",
    alineaciones_personalizadas=None,
    anchos_personalizados=None,
) -> bytes:
    """Genera un archivo Excel altamente estético con el estándar institucional del Portal de Indicadores:
    - Formato de página A4 horizontal (landscape) con cuadrícula activa.
    - Encabezado con título principal en azul institucional (#1B365D) y subtítulo con fecha/hora y filtros.
    - Cabeceras fijas (freeze panes) con fondo azul marino institucional y texto blanco en negrita.
    - Filtros automáticos activos (autofilter) en los encabezados.
    - Filas alternadas tipo cebra (#FFFFFF y #F8FAFC) con bordes suaves (#E2E8F0).
    - Alineación y formatos numéricos inteligentes según el tipo de columna.
    - Dimensionamiento automático y seguro de columnas para evitar cortes de texto.
    - Soporte tanto para un único DataFrame como para un diccionario de múltiples hojas.
    """
    if isinstance(datos, pd.DataFrame):
        hojas = {nombre_hoja_default: datos}
    elif isinstance(datos, dict):
        hojas = datos
    else:
        raise ValueError("El parámetro 'datos' debe ser un DataFrame de pandas o un diccionario {nombre_hoja: df}.")

    alineaciones_personalizadas = alineaciones_personalizadas or {}
    anchos_personalizados = anchos_personalizados or {}

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})

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
        "font_color": COLOR_SUBTITULO,
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
        "border_color": COLOR_BORDE_CABECERA,
        "font_name": "Calibri",
        "text_wrap": True,
    })

    def _crear_formato(bg, align="left", num_fmt=None):
        opciones = {
            "bg_color": bg,
            "border": 1,
            "border_color": COLOR_BORDE,
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "vcenter",
            "align": align,
        }
        if num_fmt:
            opciones["num_format"] = num_fmt
        return workbook.add_format(opciones)

    # Catálogo de formatos cebra (impar=blanco, par=cebra)
    fmt_catalogo = {}
    for p, bg in [("impar", "#FFFFFF"), ("par", COLOR_CEBRA)]:
        fmt_catalogo[f"{p}_izq"] = _crear_formato(bg, "left")
        fmt_catalogo[f"{p}_centro"] = _crear_formato(bg, "center")
        fmt_catalogo[f"{p}_der"] = _crear_formato(bg, "right")
        fmt_catalogo[f"{p}_entero"] = _crear_formato(bg, "right", num_fmt="#,##0")
        fmt_catalogo[f"{p}_decimal"] = _crear_formato(bg, "right", num_fmt="#,##0.0")
        fmt_catalogo[f"{p}_decimal2"] = _crear_formato(bg, "right", num_fmt="#,##0.00")
        fmt_catalogo[f"{p}_porc"] = _crear_formato(bg, "right", num_fmt="0.0%")
        fmt_catalogo[f"{p}_fecha"] = _crear_formato(bg, "center", num_fmt="dd/mm/yyyy")

    ahora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    filtros_texto = []
    if isinstance(filtros, (list, tuple)):
        for item in filtros:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                filtros_texto.append(f"{item[0]}: {item[1]}")
            elif item:
                filtros_texto.append(str(item))
    elif filtros:
        filtros_texto.append(str(filtros))

    if filtros_texto:
        subtitulo_completo = (
            f"Portal de Indicadores Académicos · Sistema de Gestión Institucional - "
            f"Filtros: {', '.join(filtros_texto)} · Fecha y hora de generación: {ahora}"
        )
    elif subtitulo:
        subtitulo_completo = f"{subtitulo} · Fecha y hora de generación: {ahora}"
    else:
        subtitulo_completo = (
            f"Portal de Indicadores Académicos · Sistema de Gestión Institucional · "
            f"Fecha y hora de generación: {ahora}"
        )

    palabras_centro = {
        "periodo", "semestre", "seccion", "sección", "turma", "matricula", "matrícula",
        "catraca", "documento", "doc", "id", "año", "ano", "fecha", "estado", "status",
        "sede", "filial", "cohorte", "titulado", "aula", "aulas", "tipo", "grupo", "corte",
        "resultado", "nota (1 a 5)"
    }
    caracteres_invalidos = set(r"[]:*?/") | {"\\"}
    textos_centro = {"sin nota", "sin sección", "sin seccion", "–", "n/a", "nan", "nd", "sin datos"}

    for nombre_hoja, df_hoja in hojas.items():
        nombre_limpio = "".join(c for c in str(nombre_hoja) if c not in caracteres_invalidos)[:31] or "Hoja"
        worksheet = workbook.add_worksheet(nombre_limpio)

        worksheet.hide_gridlines(False)
        worksheet.set_paper(9)  # A4
        worksheet.set_landscape()

        # Encabezado institucional superior
        worksheet.write(0, 0, str(titulo), fmt_titulo)
        worksheet.set_row(0, 24)
        worksheet.write(1, 0, subtitulo_completo, fmt_subtitulo)
        worksheet.set_row(1, 18)
        worksheet.set_row(2, 10)

        fila_cabecera = 3
        worksheet.set_row(fila_cabecera, 26)

        columnas = list(df_hoja.columns)
        for col_idx, col_nombre in enumerate(columnas):
            worksheet.write(fila_cabecera, col_idx, str(col_nombre), fmt_cabecera)

        worksheet.freeze_panes(fila_cabecera + 1, 0)

        # Reglas de formato por columna
        config_cols = []
        for col in columnas:
            col_str = str(col).strip()
            col_norm = col_str.lower()
            serie = df_hoja[col]

            if col_str in alineaciones_personalizadas:
                al = alineaciones_personalizadas[col_str]
                config_cols.append((al, None))
                continue

            partes = col_norm.replace("_", " ").split()
            if any(p in palabras_centro for p in partes) or col_norm in palabras_centro:
                config_cols.append(("centro", None))
            elif pd.api.types.is_numeric_dtype(serie):
                if any(k in col_norm for k in ["%", "tasa", "porc", "pct"]):
                    max_val = serie.dropna().max() if not serie.dropna().empty else 0
                    if max_val > 1.0:
                        config_cols.append(("der", "decimal"))
                    else:
                        config_cols.append(("der", "porc"))
                elif pd.api.types.is_integer_dtype(serie):
                    config_cols.append(("der", "entero"))
                else:
                    config_cols.append(("der", "decimal"))
            elif pd.api.types.is_datetime64_any_dtype(serie):
                config_cols.append(("centro", "fecha"))
            else:
                config_cols.append(("izq", None))

        for i, row in enumerate(df_hoja.itertuples(index=False)):
            fila_idx = fila_cabecera + 1 + i
            prefijo = "par" if i % 2 == 1 else "impar"
            worksheet.set_row(fila_idx, 19)

            for col_idx, valor in enumerate(row):
                alineacion_base, tipo_num = config_cols[col_idx]

                if valor is None or (isinstance(valor, float) and pd.isna(valor)) or str(valor).strip() in ("", "None", "nan"):
                    fmt = fmt_catalogo[f"{prefijo}_{alineacion_base}"]
                    worksheet.write_blank(fila_idx, col_idx, "", fmt)
                    continue

                val_str = str(valor).strip()
                if val_str.lower() in textos_centro:
                    fmt = fmt_catalogo[f"{prefijo}_centro"]
                    worksheet.write_string(fila_idx, col_idx, val_str, fmt)
                    continue

                if isinstance(valor, (int, float)):
                    if tipo_num == "entero":
                        fmt = fmt_catalogo[f"{prefijo}_entero"]
                        worksheet.write_number(fila_idx, col_idx, int(valor), fmt)
                    elif tipo_num == "porc":
                        fmt = fmt_catalogo[f"{prefijo}_porc"]
                        worksheet.write_number(fila_idx, col_idx, float(valor), fmt)
                    elif tipo_num == "decimal":
                        fmt = fmt_catalogo[f"{prefijo}_decimal"]
                        worksheet.write_number(fila_idx, col_idx, float(valor), fmt)
                    else:
                        fmt = fmt_catalogo[f"{prefijo}_{alineacion_base}"]
                        worksheet.write_number(fila_idx, col_idx, valor, fmt)
                else:
                    fmt = fmt_catalogo[f"{prefijo}_{alineacion_base}"]
                    worksheet.write_string(fila_idx, col_idx, val_str, fmt)

        if len(df_hoja) > 0:
            worksheet.autofilter(fila_cabecera, 0, fila_cabecera + len(df_hoja), len(columnas) - 1)

        # Ajuste inteligente de anchos de columna
        for col_idx, col in enumerate(columnas):
            col_str = str(col)
            if col_str in anchos_personalizados:
                worksheet.set_column(col_idx, col_idx, anchos_personalizados[col_str])
                continue

            max_len = len(col_str)
            muestra = df_hoja[col].dropna().astype(str).head(150)
            if not muestra.empty:
                max_datos = muestra.map(len).max()
                max_len = max(max_len, max_datos)

            ancho_optimo = min(max(max_len + 3, 12), 48)
            worksheet.set_column(col_idx, col_idx, ancho_optimo)

    workbook.close()
    return buffer.getvalue()


def _obtener_datos_alumnos_por_id(usuarios_ids):
    """Busca Nombre y Apellido, Documento oficial y Número de Matrícula
    (catraca) directo en SysEduca (ucp.usuarios + ucp.numero_catraca) para
    los usuarios_id dados. La planilla de egresados en su formato actual
    (subida desde Alumnos - Configuración ETL) solo trae usuarios_id -- ya
    no trae estos datos como antes, así que se cruzan acá en el momento de
    exportar."""
    from services.etl.alumnos_etl import obtener_conexion

    ids = ",".join(str(int(i)) for i in pd.unique(usuarios_ids) if pd.notna(i))
    columnas = ["usuarios_id", "Nombre y Apellido", "Documento", "Número de Matrícula"]
    if not ids:
        return pd.DataFrame(columns=columnas)

    query = f"""
        SELECT
            u.id AS usuarios_id,
            u.nome_sobrenome AS `Nombre y Apellido`,
            u.doc_oficial AS `Documento`,
            nc.numero_catraca AS `Número de Matrícula`
        FROM ucp.usuarios u
        LEFT JOIN (
            SELECT usuarios_id, MAX(numero_catraca) AS numero_catraca
            FROM ucp.numero_catraca
            WHERE usuarios_id IS NOT NULL
            GROUP BY usuarios_id
        ) nc ON nc.usuarios_id = u.id
        WHERE u.id IN ({ids})
    """
    conn = obtener_conexion()
    try:
        return pd.read_sql(query, conn)
    finally:
        conn.close()


@st.cache_data
def get_egresados_excel_bytes():
    try:
        file_path = get_global_data_path("egressados")
        copy_path = get_global_data_path("egressados_copy")

        # Intentar leer el original, si hay error de permiso (común en OneDrive), intentar con la copia
        try:
            if os.path.exists(file_path):
                df = pd.read_excel(file_path)
            elif os.path.exists(copy_path):
                df = pd.read_excel(copy_path)
            else:
                return None
        except PermissionError:
            if os.path.exists(copy_path):
                df = pd.read_excel(copy_path)
            else:
                return None

        # Cruce con SysEduca por usuarios_id: la planilla ya no trae nombre,
        # documento ni catraca directamente (ver _obtener_datos_alumnos_por_id).
        if "usuarios_id" in df.columns:
            try:
                df_extra = _obtener_datos_alumnos_por_id(df["usuarios_id"])
                if not df_extra.empty:
                    df = df.merge(df_extra, on="usuarios_id", how="left")
            except Exception as exc:
                log_exception("No se pudo cruzar egresados con nombre/documento/catraca (SysEduca)", exc)

        # Mapeo de nombres y orden solicitado:
        # 1. Número de Matrícula, 2. Documento, 3. Nombre y Apellido,
        # 4. Año de Egreso, 5. Periodo de Egreso, 6. Fecha de titulación, 7. Titulado, 8. Detalle (antiguo detalle)
        rename_map = {"detalle": "Detalle"}
        df = df.rename(columns=rename_map)

        cols_finales = [
            "Número de Matrícula", "Documento", "Nombre y Apellido",
            "Año de Egreso", "Periodo de Egreso", "Fecha de titulación",
            "Titulado", "Detalle"
        ]

        # Filtrar solo las que existen y mantener el orden
        cols_to_keep = [c for c in cols_finales if c in df.columns]
        df = df[cols_to_keep]

        # Formatear "Fecha de titulación" para que no muestre la hora si es datetime
        if "Fecha de titulación" in df.columns:
            try:
                df["Fecha de titulación"] = pd.to_datetime(df["Fecha de titulación"]).dt.strftime('%d/%m/%Y')
            except Exception as exc:
                log_exception("No se pudo formatear la fecha de titulación para exportación", exc)

        return generar_excel_estilizado(
            df,
            titulo="REPORTE DETALLADO - EGRESADOS Y TITULACIÓN",
            subtitulo="Portal de Indicadores Académicos · Sistema de Gestión Institucional",
            nombre_hoja_default="Egresados",
        )
    except Exception as exc:
        log_exception("No se pudo generar el Excel de egresados", exc)
        return None
