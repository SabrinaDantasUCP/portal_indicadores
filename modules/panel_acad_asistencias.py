import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from utils import db_pia
import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------
# CONSTANTES DE COLUMNAS
# ---------------------------------------------------------------------
COL_PERIODO = "anho"
COL_SUBPERIODO = "periodo_anual"
COL_SEMESTRE_DISCIPLINA = "semestre_asignatura"
COL_DISCIPLINA = "asignatura"
COL_SECCION = "seccion"
COL_DOCENTE = "docente"
COL_MATRICULADOS = "matriculados"
COL_PRESENTES = "presentes"
COL_AUSENTES = "ausentes"
COL_PORC_PRESENCIA = "porc_presencia"
COL_TIPO_CLASE = "tipo_clase"
COL_FECHA = "fecha"
COL_MES = "mes_nombre" # Nueva columna auxiliar

# ---------------------------------------------------------------------
# Carga de Datos
# ---------------------------------------------------------------------
@st.cache_data
def load_data():
    file_path = "assets/data/asistencia_unificada.csv"
    if not os.path.exists(file_path):
        return None
    
    try:
        # Leer CSV
        df = pd.read_csv(file_path, low_memory=False)
        
        # Limpiar nombres de columnas
        df.columns = df.columns.str.strip()
        
        # Convertir columnas clave a numérico/string para filtrado consistente
        df[COL_PERIODO] = pd.to_numeric(df[COL_PERIODO], errors='coerce').fillna(0).astype(int)
        df[COL_SUBPERIODO] = pd.to_numeric(df[COL_SUBPERIODO], errors='coerce').fillna(0).astype(int)
        df[COL_SEMESTRE_DISCIPLINA] = pd.to_numeric(df[COL_SEMESTRE_DISCIPLINA], errors='coerce').fillna(0).astype(int)
        
        # Procesar Fechas
        # Intentar varios formatos si es necesario, o asumir DD/MM/YYYY
        df[COL_FECHA] = pd.to_datetime(df[COL_FECHA], dayfirst=True, errors='coerce')
        
        # Extraer Nombre del Mes
        # Mapeo manual para asegurar español
        meses_map = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        df[COL_MES] = df[COL_FECHA].dt.month.map(meses_map)
        # Orden para gráficas
        df['mes_num'] = df[COL_FECHA].dt.month

        return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        return pd.DataFrame()

# -------------------------------------------------------------------------
# 📄 PDF FUNCTIONS
# -------------------------------------------------------------------------
def agregar_encabezado_y_pie(canvas, doc):
    canvas.saveState()
    width, height = landscape(A4)

    # --- Logo ---
    logo_path = None
    possible_paths = ["assets/logo-ucp-icon.png", "assets/logo-ucp.png", "logo-ucp-icon.png"]
    for candidate in possible_paths:
        if os.path.exists(candidate):
            logo_path = candidate
            break
    
    if logo_path:
        try:
            canvas.drawImage(logo_path, x=2 * cm, y=height - 2.5 * cm, width=2*cm, height=2*cm, preserveAspectRatio=True, mask='auto')
        except: pass

    # --- Cabeçalho ---
    canvas.setFont("Helvetica-Bold", 14)
    canvas.setFillColor(colors.HexColor("#004080"))
    canvas.drawString(5 * cm, height - 1.5 * cm, "Universidad Central del Paraguay")
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.black)
    canvas.drawString(5 * cm, height - 2.1 * cm, "Facultad de Ciencias de la Salud — Carrera de Medicina")
    
    canvas.setStrokeColor(colors.HexColor("#004080"))
    canvas.setLineWidth(1)
    canvas.line(2 * cm, height - 3.0 * cm, width - 2 * cm, height - 3.0 * cm)

    # --- Rodapé ---
    canvas.setFont("Helvetica-Oblique", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(width - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()

@st.cache_data(show_spinner="Cargando datos para exportación...")
def gerar_pdf_asistencia(df_dados, titulo, col_widths=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1 * cm, rightMargin=1 * cm, topMargin=4 * cm, bottomMargin=2 * cm
    )

    story = []
    styles = getSampleStyleSheet()
    
    # Create center style
    style_center = ParagraphStyle(
        name='NormalCenter',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=8,
        leading=9
    )

    story.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
    story.append(Spacer(1, 10))

    # Convert headers and data to list of lists
    headers = df_dados.columns.tolist()
    
    # Prepare data with Paragraph for text wrapping
    data = [headers]
    for _, row in df_dados.iterrows():
        row_list = []
        for item in row:
            if isinstance(item, str) and len(item) > 15: # Arbitrary threshold for wrapping
                    row_list.append(Paragraph(item, style_center))
            else:
                    # For non-wrapped text, the TableStyle aligns it, but if it is short text we can still use Paragraph or str()
                    # Using str() is fine as TableStyle ALIGN=CENTER handles it strings, 
                    # BUT consistency is better if we use Paragraph for all? No, str is faster.
                    # TableStyle ALIGN works for str.
                    row_list.append(str(item))
        data.append(row_list)
    
    # Determine column widths
    final_col_widths = None
    if col_widths:
        # Check if length matches
            if len(col_widths) == len(headers):
                final_col_widths = col_widths
    
    if not final_col_widths:
        width, height = landscape(A4)
        avail_width = width - 2*cm
        col_width = avail_width / len(headers)
        final_col_widths = [col_width] * len(headers)

    tabla = Table(data, repeatRows=1, colWidths=final_col_widths)
    
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004080')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')]),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    story.append(tabla)
    story.append(Spacer(1, 14))
    
    try:
        doc.build(story, onFirstPage=agregar_encabezado_y_pie, onLaterPages=agregar_encabezado_y_pie)
    except Exception as e:
        return None 

    return buffer.getvalue()

@st.cache_data(show_spinner="Generando Excel...")
def generate_excel_bytes(df, sheet_name='Sheet1'):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()




def render():
    # Increase st.dataframe styler limit
    pd.set_option("styler.render.max_elements", 2000000) 

    st.subheader("Panel de Asistencia")


    df = load_data()

    if df is None:
        st.error("Archivo 'assets/data/asistencia_syseduca.csv' no encontrado.")
        return

    if df.empty:
        st.warning("El archivo de datos está vacío.")
        return

    # ---------------------------------------------------------------------
    # Filtros
    # ---------------------------------------------------------------------    
    # Contenedor para filtros
    with st.container():
        c1, c2 = st.columns(2)
        c3, c4, c5 = st.columns(3)
        c6, c7 = st.columns(2)

        # 1. Filtro: Año (Obligatorio)
        anhos_disponibles = sorted(df[COL_PERIODO].unique(), reverse=True)
        anho_sel = c1.multiselect("Periodo (Año) *", anhos_disponibles)

        # Filtrado progresivo para Periodo
        df_temp = df.copy()
        if anho_sel:
            df_temp = df_temp[df_temp[COL_PERIODO].isin(anho_sel)]

        # 2. Filtro: Periodo (Obligatorio)
        periodos_disponibles = sorted(df_temp[COL_SUBPERIODO].unique())
        periodo_sel = c2.multiselect("Subperiodo (Semestre) *", periodos_disponibles)

        # CHECK DE OBLIGATORIEDAD
        if not anho_sel or not periodo_sel:
            st.info("Seleccione **Periodo (Año)** y **Subperiodo (Semestre)** para continuar.")
            return

        # Filtrado progresivo para Semestre
        if periodo_sel:
            df_temp = df_temp[df_temp[COL_SUBPERIODO].isin(periodo_sel)]

        # 3. Filtro: Semestre de la Asignatura
        semestres_disponibles = sorted(df_temp[COL_SEMESTRE_DISCIPLINA].unique())
        semestre_sel = c3.multiselect("Semestre de la Asignatura", semestres_disponibles, format_func=lambda x: f"{x}º Semestre")

        # Filtrado progresivo para Asignatura
        if semestre_sel:
            df_temp = df_temp[df_temp[COL_SEMESTRE_DISCIPLINA].isin(semestre_sel)]

        # 4. Filtro: Asignatura
        asignaturas_disponibles = sorted(df_temp[COL_DISCIPLINA].astype(str).unique())
        asignatura_sel = c4.multiselect("Asignatura", asignaturas_disponibles)

        # Filtrado progresivo para Docente
        if asignatura_sel:
            df_temp = df_temp[df_temp[COL_DISCIPLINA].isin(asignatura_sel)]

        # 5. Filtro: Docente
        docentes_disponibles = sorted(df_temp[COL_DOCENTE].astype(str).unique())
        docente_sel = c5.multiselect("Docente", docentes_disponibles)

        # Filtrado progresivo para Sección
        if docente_sel:
            df_temp = df_temp[df_temp[COL_DOCENTE].isin(docente_sel)]

        # 6. Filtro: Sección
        secciones_disponibles = sorted(df_temp[COL_SECCION].astype(str).unique())
        seccion_sel = c6.multiselect("Sección", secciones_disponibles)

        # Filtrado progresivo para Tipo de Clase
        if seccion_sel:
            df_temp = df_temp[df_temp[COL_SECCION].isin(seccion_sel)]

        # 7. Filtro: Tipo de Clase
        tipos_clase_disponibles = sorted(df_temp[COL_TIPO_CLASE].astype(str).unique())
        tipo_clase_sel = c7.multiselect("Tipo de Clase", tipos_clase_disponibles)

    # ---------------------------------------------------------------------
    # Aplicar Filtros al Dataframe Principal
    # ---------------------------------------------------------------------
    df_filtered = df.copy()

    # Filtros Obligatorios ya chequeados arriba en la UI, pero aplicamos aqui
    df_filtered = df_filtered[df_filtered[COL_PERIODO].isin(anho_sel)]
    df_filtered = df_filtered[df_filtered[COL_SUBPERIODO].isin(periodo_sel)]

    if semestre_sel:
        df_filtered = df_filtered[df_filtered[COL_SEMESTRE_DISCIPLINA].isin(semestre_sel)]

    if asignatura_sel:
        df_filtered = df_filtered[df_filtered[COL_DISCIPLINA].isin(asignatura_sel)]

    if docente_sel:
        df_filtered = df_filtered[df_filtered[COL_DOCENTE].isin(docente_sel)]

    if seccion_sel:
        df_filtered = df_filtered[df_filtered[COL_SECCION].isin(seccion_sel)]

    if tipo_clase_sel:
        df_filtered = df_filtered[df_filtered[COL_TIPO_CLASE].isin(tipo_clase_sel)]

    # ---------------------------------------------------------------------
    # Exualización de Resultados
    # ---------------------------------------------------------------------
    if df_filtered.empty:
        st.info("No se encontraron registros con los filtros seleccionados.")
        return

    st.divider()

    # Métricas Resumen Globales (Siempre visibles o dentro de Tabs?) 
    # Generalmente metricas globales quedan bien fuera
    total_registros = len(df_filtered)
    # Promedio ponderado o simple? Aqui es promedio de la columna porcentaje
    promedio_presencia = df_filtered[COL_PORC_PRESENCIA].mean()    

    m1, m2 = st.columns(2)
    m1.metric("Total de Registros de Clase", total_registros)
    m2.metric("Promedio General de Presencia", f"{promedio_presencia:.2f}%")

    # ---------------------------------------------------------------------
    # TABS
    # ---------------------------------------------------------------------
    tab1, tab2 = st.tabs(["Resumen", "Detalle"])

    # --- TAB 1: RESUMEN ---
    with tab1:
        st.markdown("#### Evolución de Asistencia")
        
        # Agrupar por Mes (y mes_num para ordenar)
        # Sumar Matriculados y Presentes para el gráfico agrupado
        df_agrupado = df_filtered.groupby([COL_MES, 'mes_num'])[[COL_MATRICULADOS, COL_PRESENTES]].sum().reset_index()
        df_agrupado = df_agrupado.sort_values('mes_num') # Enero a izquierda
        
        # Renombrar columnas para que se vea bonito en el gráfico
        df_agrupado = df_agrupado.rename(columns={
            COL_MATRICULADOS: "Matriculados",
            COL_PRESENTES: "Presentes"
        })

        # Melt para tener una columna 'Tipo' (Matriculados vs Presentes) para el color y agrupación
        # id_vars: Mes, mes_num. value_vars: Matriculados, Presentes
        df_melt = df_agrupado.melt(id_vars=[COL_MES, 'mes_num'], value_vars=["Matriculados", "Presentes"], var_name='Tipo', value_name='Cantidad')
        
        # Mapeo de colores amigable
        color_map = {
            "Matriculados": '#1f77b4', # Azul
            "Presentes": '#2ca02c'     # Verde
        }

        fig = px.bar(
            df_melt,
            x=COL_MES,
            y='Cantidad',
            color='Tipo',
            barmode='group',
            text_auto=True,
            color_discrete_map=color_map,
            labels={COL_MES: "Mes", "Cantidad": "Cantidad de Alumnos", "Tipo": "Indicador"}
        )
        
        fig.update_layout(
            xaxis_title="Mes",
            yaxis_title="Cantidad de Alumnos",
            legend_title="Indicador",
            uniformtext_minsize=8, 
            uniformtext_mode='hide',
            separators=",." # Decimal=, Miles=. (Estilo Latam/Euro)
        )
        
        # Formato eje Y sin K (1k -> 1.000)
        fig.update_yaxes(tickformat=",d") 
        fig.update_traces(
            texttemplate='%{y:,d}', # Formato del texto en las barras
            textposition='auto'
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # Download Buttons Tab 1 (Resumen)
        st.divider()
        c_pdf, c_xls = st.columns(2, gap="medium")
        
        # Prepare Table for PDF (Resumen)
        # Using df_melt or df_agrupado? 
        # The chart uses melted data, but table is usually the grouped summary.
        # Let's show the grouped summary: Mes, Matriculados, Presentes
        df_export_resumen = df_agrupado.copy()
        # Rename col_mes if needed (it is already 'mes_nombre' or rename it)
        # It has 'mes_nombre', 'mes_num', 'Matriculados', 'Presentes'
        # Drop mes_num for visual
        df_export_resumen = df_export_resumen.drop(columns=['mes_num'], errors='ignore')
        
        # PDF - No Chart
        pdf_bytes = gerar_pdf_asistencia(df_export_resumen, "Evolución de Asistencia", col_widths=None)
        if pdf_bytes:
             with c_pdf:
                 st.download_button("Descargar Reporte (PDF)", data=pdf_bytes, file_name=f"Resumen_Asistencia.pdf", mime="application/pdf", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Asistencia - Resumen", "PDF"))
        else:
             with c_pdf:
                st.warning("No se pudo generar el PDF.")

        # Excel - Cached
        excel_bytes = generate_excel_bytes(df_export_resumen, sheet_name='Resumen')
        
        with c_xls:
            st.download_button("Descargar Datos (Excel)", data=excel_bytes, file_name=f"Resumen_Asistencia.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", on_click=db_pia.log_export_callback, args=("Asistencia - Resumen", "Excel"))


    # --- TAB 2: DETALLE ---
    with tab2:
        st.markdown("#### Detalle de Registros")
        
        # Seleccionar columnas relevantes para mostrar
        cols_to_show = [
            COL_FECHA, COL_PERIODO, COL_SUBPERIODO, COL_SEMESTRE_DISCIPLINA, 
            COL_DISCIPLINA, COL_SECCION, COL_DOCENTE, 
            COL_MATRICULADOS, COL_PRESENTES, COL_AUSENTES, COL_PORC_PRESENCIA, COL_TIPO_CLASE
        ]
        
        # Verificar que las columnas existan antes de seleccionarlas
        cols_final = [c for c in cols_to_show if c in df_filtered.columns]
        
        df_display = df_filtered[cols_final].sort_values(by=[COL_FECHA, COL_DISCIPLINA])
        
        # Renombrar columnas para visualización
        rename_map = {
            COL_FECHA: "Fecha",
            COL_PERIODO: "Año",
            COL_SUBPERIODO: "Periodo",
            COL_SEMESTRE_DISCIPLINA: "Semestre Asignatura",
            COL_DISCIPLINA: "Asignatura",
            COL_SECCION: "Sección",
            COL_DOCENTE: "Docente",
            COL_MATRICULADOS: "Matriculados",
            COL_PRESENTES: "Presentes",
            COL_AUSENTES: "Ausentes",
            COL_PORC_PRESENCIA: "% Presencia",
            COL_TIPO_CLASE: "Tipo de Clase"
        }
        df_display = df_display.rename(columns=rename_map)
        
        # Reemplazar NaN e Inf con 0 explícitamente para visualización
        df_display = df_display.fillna(0)
        
        # Formateo para visualización
        st.dataframe(
            df_display.style.format({
                "% Presencia": "{:.2f}%",
                "Año": "{:.0f}",
                "Periodo": "{:.0f}",
                "Semestre Asignatura": "{:.0f}",
                "Matriculados": "{:.0f}",
                "Presentes": "{:.0f}",
                "Ausentes": "{:.0f}",
                "Fecha": lambda t: t.strftime("%d/%m/%Y") if pd.notnull(t) and t != 0 else "" 
            }, na_rep="0"),
            width="stretch",
            hide_index=True

        )

        # Download Buttons Tab 2 (Detalle)
        st.divider()
        c_pdf2, c_xls2 = st.columns(2, gap="medium")

        # PDF Definition for Detalle
        # Columns in df_display: "Fecha", "Año", "Periodo", "Semestre Asignatura", ...
        # Need to select concise columns for PDF to fit width
        # Let's select key columns
        cols_pdf_detalle = ["Fecha", "Asignatura", "Sección", "Docente", "Matriculados", "Presentes", "% Presencia"]
        df_pdf_detalle = df_display[cols_pdf_detalle].copy()
        
        # Format Date for PDF
        df_pdf_detalle["Fecha"] = df_pdf_detalle["Fecha"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else "")
        df_pdf_detalle["% Presencia"] = df_pdf_detalle["% Presencia"].apply(lambda x: f"{x:.2f}%")

        # Custom widths
        # A4 Landscape width ~27.7cm
        col_widths_detalle = [
            2.0 * cm, # Fecha
            4.0 * cm, # Asignatura
            4.0 * cm, # Sección
            6.0 * cm, # Docente
            2.0 * cm, # Matriculados
            2.0 * cm, # Presentes
            2.0 * cm  # % Presencia
        ]

        pdf_bytes_2 = gerar_pdf_asistencia(df_pdf_detalle, "Detalle de Asistencia", col_widths=col_widths_detalle)
        
        if pdf_bytes_2:
            with c_pdf2:
                st.download_button("Descargar Reporte (PDF)", data=pdf_bytes_2, file_name=f"Detalle_Asistencia.pdf", mime="application/pdf", icon=":material/download:", width="stretch", key="btn_pdf_asist_2", on_click=db_pia.log_export_callback, args=("Asistencia - Detalle", "PDF"))
        else:
            with c_pdf2:
                st.warning("No se pudo generar el PDF.")

        # Excel - Cached
        excel_bytes_2 = generate_excel_bytes(df_display, sheet_name='Detalle')

        with c_xls2:
            st.download_button("Descargar Datos (Excel)", data=excel_bytes_2, file_name=f"Detalle_Asistencia.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:", width="stretch", key="btn_xls_asist_2", on_click=db_pia.log_export_callback, args=("Asistencia - Detalle", "Excel"))

