import streamlit as st
import pandas as pd
from utils import db_pia

def render():
    if st.session_state.get('rol') != 'ADMIN':
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return

    st.subheader("Registro de Descargas (Logs)")
    st.markdown("Visualiza el historial completo de las exportaciones de datos y reportes realizadas por los usuarios.")

    logs_data = db_pia.get_export_logs()

    if not logs_data:
        st.info("Aún no hay registros de descargas.")
        return

    df = pd.DataFrame(logs_data)
    
    # Formatear la fecha
    df['fecha_descarga'] = pd.to_datetime(df['fecha_descarga'])
    
    # Crear la columna de Usuario completo
    df['Usuario'] = df['nombre'] + " " + df['apellido'] + " (" + df['email'] + ")"
    
    st.markdown("---")
    st.markdown("### Filtros")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        date_range = st.date_input(
            "Rango de Fechas", 
            value=(df['fecha_descarga'].min().date(), df['fecha_descarga'].max().date()),
            format="DD/MM/YYYY"
        )
    with col2:
        usuarios_unicos = ["Todos"] + sorted(df['Usuario'].unique().tolist())
        usr_sel = st.selectbox("Usuario", usuarios_unicos)
    with col3:
        # Algunos usuarios pueden no tener área, manejamos None
        df['area'] = df['area'].fillna("Sin Área")
        areas_unicas = ["Todas"] + sorted(df['area'].unique().tolist())
        area_sel = st.selectbox("Área", areas_unicas)
    with col4:
        formatos_unicos = ["Ambos", "PDF", "Excel"]
        fmt_sel = st.selectbox("Formato", formatos_unicos)

    # Aplicar Filtros
    df_filtered = df.copy()
    
    # Filtro de fecha
    if len(date_range) == 2:
        start_date, end_date = date_range
        # Convertir a datetime para poder comparar con la columna timestamp
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        df_filtered = df_filtered[(df_filtered['fecha_descarga'] >= start_dt) & (df_filtered['fecha_descarga'] <= end_dt)]
        
    # Filtro de usuario
    if usr_sel != "Todos":
        df_filtered = df_filtered[df_filtered['Usuario'] == usr_sel]
        
    # Filtro de área
    if area_sel != "Todas":
        df_filtered = df_filtered[df_filtered['area'] == area_sel]
        
    # Filtro de formato
    if fmt_sel != "Ambos":
        df_filtered = df_filtered[df_filtered['formato'] == fmt_sel]

    st.markdown("---")
    st.markdown(f"**Total de registros encontrados:** {len(df_filtered)}")
    
    if df_filtered.empty:
        st.warning("No hay descargas que coincidan con los filtros seleccionados.")
    else:
        # Preparar tabla para visualización final
        df_display = df_filtered[['fecha_descarga', 'Usuario', 'area', 'indicador', 'formato']].copy()
        df_display.columns = ['Fecha y Hora', 'Usuario', 'Área', 'Indicador', 'Formato']
        df_display['Fecha y Hora'] = df_display['Fecha y Hora'].dt.strftime('%d/%m/%Y %H:%M:%S')
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True
        )
