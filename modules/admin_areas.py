import streamlit as st
from utils import db_pia
from utils.system_logging import log_exception

@st.dialog("Crear Nueva Área")
def modal_crear_area():
    nueva_area = st.text_input("Nombre del Área", placeholder="Ej: Dirección Académica")
    if st.button("Guardar", type="primary", use_container_width=True):
        if nueva_area.strip():
            try:
                db_pia.add_area(nueva_area.strip())
                st.session_state.temp_msg_area = f"Área '{nueva_area.strip()}' creada exitosamente."
                st.rerun()
            except Exception as e:
                log_exception("Error al crear área", e)
                st.error("El nombre de esta área ya existe en este sistema.")
        else:
            st.warning("El nombre del área es requerido y no puede estar vacío.")

@st.dialog("Editar Información de Área")
def modal_editar_area(a):
    edit_area = st.text_input("Nombre del Área", value=a['nombre'])
    if st.button("Actualizar Cambio", type="primary", use_container_width=True):
        if edit_area.strip():
            try:
                db_pia.update_area(a['id'], edit_area.strip())
                st.session_state.temp_msg_area = "El nombre del Área ha sido actualizado."
                st.rerun()
            except Exception as e:
                log_exception("Error al actualizar área", e)
                st.error("Error al actualizar (posiblemente hay otra área con ese nombre).")
        else:
            st.warning("El nombre del área no puede estar vacío.")

def render():
    if st.session_state.get('rol') != 'ADMIN':
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return

    # Mensajes de éxito efímeros
    if "temp_msg_area" in st.session_state:
        st.success(st.session_state.temp_msg_area)
        del st.session_state.temp_msg_area

    c_head1, c_head2 = st.columns([3, 1])
    with c_head1:
        st.subheader("Gestión de Áreas")
    with c_head2:
        if st.button("Crear Nueva Área", icon=":material/add:", type="primary", use_container_width=True):
            modal_crear_area()

    st.markdown("---")

    areas = db_pia.get_all_areas()
    
    if not areas:
        st.info("Aún no hay áreas registradas en el sistema.")
        return

    flt_area = st.text_input("Buscar Área", placeholder="Escribe para filtrar la lista...")
    if flt_area.strip():
        areas = [a for a in areas if flt_area.strip().lower() in a['nombre'].lower()]

    st.divider()
    # Encabezados
    st.markdown("""
    <div style='background-color: #003366; color: white; padding: 10px; border-radius: 5px; display: flex; width: 100%; margin-bottom: 10px;'>
        <div style='flex: 3; text-align: center; font-weight: bold;'>Nombre</div>
        <div style='flex: 1; text-align: center; font-weight: bold;'>Acciones</div>
    </div>
    """, unsafe_allow_html=True)
    
    for a in areas:
        with st.container():
            colA, colB, colC = st.columns([3, 0.5, 0.5])
            with colA:
                st.markdown(f"<p style='margin-top: 5px; font-weight: bold; text-align: center;'>{a['nombre']}</p>", unsafe_allow_html=True)
            with colB:
                if st.button("Editar", icon=":material/edit:", key=f"eda_{a['id']}", help="Editar Área"):
                    modal_editar_area(a)
            with colC:
                if st.button("Borrar", icon=":material/delete:", key=f"del_{a['id']}", help="Eliminar permanentemente"):
                    try:
                        db_pia.delete_area(a['id'])
                        st.session_state.temp_msg_area = "Área eliminada exitosamente."
                        st.rerun()
                    except Exception as e:
                        log_exception("Error al eliminar área", e)
                        st.error("No se puede eliminar porque esta área está vinculada a un usuario.")
        st.markdown("<hr style='margin: 5px 0px; border-top: 1px solid #f0f0f0;'>", unsafe_allow_html=True)
