import streamlit as st
import pandas as pd
from utils import db_pia
from utils.ui import render_info_header
from utils.system_logging import log_exception
from utils.menu_config import (
    INDICADORES_VERSION,
    INDICE_PERMANENCIA,
    INDICE_PERMANENCIA_PERMISSION,
    VERSION_GROUPS,
    permission_key,
    version_permission_key,
)


def render_permission_inputs(prefix, current_perms=None):
    current_perms = set(current_perms or [])
    selected_perms = []

    render_info_header(
        "Permisos de Acceso",
        "Configure qué versiones e indicadores puede visualizar este usuario.",
    )
    for version in VERSION_GROUPS:
        version_permission = version_permission_key(version)
        has_all_version = version_permission in current_perms
        has_any_indicator = any(
            permission_key(version, indicator) in current_perms
            for indicator in INDICADORES_VERSION
        )

        with st.container(border=True):
            st.markdown(f"**{version}**")
            col_ver, col_todos = st.columns(2)
            with col_ver:
                can_view_version = st.checkbox(
                    "Habilitar versión",
                    value=has_all_version or has_any_indicator,
                    key=f"{prefix}_{version}_can_view",
                )
            with col_todos:
                can_view_all = st.checkbox(
                    "Todos los indicadores",
                    value=has_all_version,
                    disabled=not can_view_version,
                    key=f"{prefix}_{version}_all",
                )

            if not can_view_version:
                st.caption("Versión no visible para este usuario.")
                continue

            if can_view_all:
                selected_perms.append(version_permission)
                st.caption("El usuario verá todos los indicadores de esta versión.")
                continue

            st.caption("Seleccione los indicadores visibles")
            indicator_cols = st.columns(2)
            for idx, indicator in enumerate(INDICADORES_VERSION):
                indicator_name = indicator["name"]
                default_value = (
                    permission_key(version, indicator) in current_perms
                )
                with indicator_cols[idx % 2]:
                    if st.checkbox(
                        indicator_name,
                        value=default_value,
                        key=f"{prefix}_{version}_{indicator_name}",
                    ):
                        selected_perms.append(permission_key(version, indicator))

    with st.container(border=True):
        if st.checkbox(
            INDICE_PERMANENCIA,
            value=INDICE_PERMANENCIA_PERMISSION in current_perms,
            key=f"{prefix}_{INDICE_PERMANENCIA}",
        ):
            selected_perms.append(INDICE_PERMANENCIA_PERMISSION)

    return selected_perms

@st.dialog("Crear Nuevo Usuario")
def modal_crear_usuario(areas_disp):
    f_nom = st.text_input("Nombre *")
    f_ape = st.text_input("Apellido *")
    f_doc = st.text_input("Documento *")
    f_eml = st.text_input("Email (Login) *")
    f_area = st.selectbox("Área *", options=areas_disp, format_func=lambda x: x['nombre']) if areas_disp else None
    f_rol = st.selectbox("Rol", ["LEITURA", "ADMIN"])
    f_mods = render_permission_inputs("crear_perms") if f_rol == "LEITURA" else []
    
    if st.button("Registrar Usuario", type="primary", use_container_width=True):
        if f_nom and f_ape and f_doc and f_eml and f_area:
            try:
                uid, plain_pw = db_pia.add_user(f_nom, f_ape, f_doc, f_eml, f_area['id'], f_rol)
                if f_rol == 'LEITURA':
                    db_pia.set_user_permissions(uid, f_mods)
                db_pia.log_audit_event(
                    "user_created",
                    target_usuario_id=uid,
                    detalle={"email": f_eml, "rol": f_rol, "permisos": f_mods},
                )
                st.session_state.temp_message = f"Usuario '{f_nom}' creado exitosamente. Contraseña inicial: {plain_pw}"
                st.rerun()
            except Exception as e:
                log_exception("Error al crear usuario desde administración", e)
                st.error("Error al registrar: Probablemente ya exista el Email o Documento en la base de datos.")
        else:
            st.warning("Debe completar todos los campos obligatorios (*).")

@st.dialog("Editar Información de Usuario")
def modal_editar_usuario(us_sel, areas_d, curr_perms):
    e_nom = st.text_input("Nombre", value=us_sel['nombre'])
    e_ape = st.text_input("Apellido", value=us_sel['apellido'])
    e_doc = st.text_input("Documento", value=us_sel['documento'])
    e_eml = st.text_input("Email", value=us_sel['email'])
    
    idx_area = 0
    if areas_d and us_sel.get('area'):
        for i, a in enumerate(areas_d):
            if a['nombre'] == us_sel['area']:
                idx_area = i
                break
                
    e_area = st.selectbox("Área", options=areas_d, format_func=lambda x: x['nombre'], index=idx_area) if areas_d else None
    e_rol = st.selectbox("Rol", ["LEITURA", "ADMIN"], index=0 if us_sel['rol'] == 'LEITURA' else 1)
    e_mods = render_permission_inputs(f"editar_perms_{us_sel['id']}", curr_perms) if e_rol == "LEITURA" else []
    
    if st.button("Guardar Cambios", type="primary", use_container_width=True):
        area_id_val = e_area['id'] if e_area else None
        old_permissions = sorted(curr_perms)
        new_permissions = sorted(e_mods if e_rol == "LEITURA" else [])
        db_pia.update_user(us_sel['id'], e_nom, e_ape, e_doc, e_eml, area_id_val, e_rol, bool(us_sel['activo']))
        if e_rol == 'LEITURA':
            db_pia.set_user_permissions(us_sel['id'], e_mods)
        else:
            db_pia.set_user_permissions(us_sel['id'], [])
        if old_permissions != new_permissions:
            db_pia.log_audit_event(
                "permissions_updated",
                target_usuario_id=us_sel["id"],
                detalle={"old": old_permissions, "new": new_permissions},
            )
        db_pia.log_audit_event(
            "user_updated",
            target_usuario_id=us_sel["id"],
            detalle={
                "email": e_eml,
                "rol": e_rol,
                "activo": bool(us_sel["activo"]),
                "permisos": new_permissions,
            },
        )
        st.session_state.temp_message = "Módulo de permisos y usuario actualizado correctamente."
        st.rerun()

@st.dialog("Cambiar Contraseña Manualmente")
def modal_cambiar_pass(us_sel):
    st.info(f"Generando nueva clave para: **{us_sel['nombre']} {us_sel['apellido']}**")
    new_pw = st.text_input("Nueva Contraseña Obligatoria", type="password")
    if st.button("Actualizar y Sobreescribir", type="primary", use_container_width=True):
        if db_pia.is_password_strong(new_pw):
            db_pia.change_password(us_sel['id'], new_pw.strip())
            db_pia.log_audit_event("password_reset_by_admin", target_usuario_id=us_sel["id"])
            st.session_state.temp_message = "La contraseña del usuario fue sobreescrita manualmente."
            st.rerun()
        else:
            st.error(f"La contraseña debe tener al menos {db_pia.MIN_PASSWORD_LENGTH} caracteres.")

def render():
    if st.session_state.get('rol') != 'ADMIN':
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return

    if "temp_message" in st.session_state:
        st.success(st.session_state.temp_message)
        del st.session_state.temp_message

    c_head1, c_head2 = st.columns([3, 1])
    with c_head1:
        st.subheader("Gestión de Usuarios")
    with c_head2:
        if st.button("Crear Nuevo Usuario", icon=":material/add:", type="primary", use_container_width=True):
            modal_crear_usuario(db_pia.get_all_areas())

    usuarios = db_pia.get_all_users()

    if not usuarios:
        st.info("No hay usuarios registrados.")
        return

    flt_usr = st.text_input("Buscar Usuario", placeholder="Filtra escribiendo un nombre, apellido o correo...")
    if flt_usr.strip():
        q = flt_usr.strip().lower()
        usuarios = [u for u in usuarios if q in u['nombre'].lower() or q in u['apellido'].lower() or q in u['email'].lower()]

    st.markdown("---")
    
    # Encabezados
    st.markdown("""
    <div style='background-color: #003366; color: white; padding: 10px; border-radius: 5px; display: flex; width: 100%; margin-bottom: 10px;'>
        <div style='flex: 1.5; text-align: center; font-weight: bold;'>Nombre y Email</div>
        <div style='flex: 1; text-align: center; font-weight: bold;'>Rol</div>
        <div style='flex: 1; text-align: center; font-weight: bold;'>Estado</div>
        <div style='flex: 1.2; text-align: center; font-weight: bold;'>Acciones</div>
    </div>
    """, unsafe_allow_html=True)

    for u in usuarios:
        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1, 1, 0.4, 0.4, 0.4])
            with c1:
                st.markdown(f"<div style='text-align: center; padding-top: 5px;'><b>{u['nombre']} {u['apellido']}</b><br><span style='color: gray; font-size: 0.8em;'>{u['email']}</span></div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div style='text-align: center; padding-top: 15px;'>{u['rol']}</div>", unsafe_allow_html=True)
            with c3:
                lbl_est = "Activo" if u['activo'] else "Inactivo"
                st.markdown(f"<div style='text-align: center; padding-top: 15px;'>{lbl_est}</div>", unsafe_allow_html=True)
            with c4:
                if st.button("Editar", icon=":material/edit:", key=f"ed_{u['id']}", help="Editar Usuario"):
                    curr_perms = db_pia.get_user_permissions(u['id'])
                    modal_editar_usuario(u, db_pia.get_all_areas(), curr_perms)
            with c5:
                if st.button("Clave", icon=":material/key:", key=f"pw_{u['id']}", help="Restablecer Contraseña"):
                    modal_cambiar_pass(u)
            with c6:
                ico_btn = ":material/block:" if u['activo'] else ":material/check_circle:"
                btn_txt = "Desactivar" if u['activo'] else "Activar"
                hlp_t = "Desactivar Acceso" if u['activo'] else "Reactivar Acceso"
                if st.button(btn_txt, icon=ico_btn, key=f"tg_{u['id']}", help=hlp_t):
                    areas_d = db_pia.get_all_areas()
                    aid = None
                    if areas_d and u.get('area'):
                        for a in areas_d:
                            if a['nombre'] == u['area']: aid = a['id']
                    new_active = not bool(u['activo'])
                    db_pia.update_user(u['id'], u['nombre'], u['apellido'], u['documento'], u['email'], aid, u['rol'], new_active)
                    db_pia.log_audit_event(
                        "user_status_changed",
                        target_usuario_id=u["id"],
                        detalle={"activo": new_active},
                    )
                    st.rerun()
        st.markdown("<hr style='margin: 5px 0px; border-top: 1px solid #f0f0f0;'>", unsafe_allow_html=True)
