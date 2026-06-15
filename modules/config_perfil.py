import streamlit as st
from utils import db_pia
from utils.system_logging import log_exception

def render():
    st.header("🔑 Cambiar Contraseña")
    st.markdown("---")
    
    st.info("Para actualizar tu contraseña de acceso, por favor completa los siguientes campos. Asegúrate de que la nueva clave sea segura.")

    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col1:
        pass # Espaciador
        
    with col2:
        with st.form("form_cambio_clave"):
            old_pass = st.text_input("Contraseña Actual", type="password", help="Ingresa tu clave actual para validar que eres tú.")
            new_pass = st.text_input("Nueva Contraseña", type="password", help="Ingresa tu nueva clave.")
            confirm_pass = st.text_input("Confirmar Nueva Contraseña", type="password", help="Repite tu nueva clave para evitar errores.")
            
            st.markdown("<br>", unsafe_allow_html=True)
            btn_submit = st.form_submit_button("Actualizar y Guardar", type="primary", use_container_width=True)
            
            if btn_submit:
                if not old_pass or not new_pass or not confirm_pass:
                    st.warning("⚠️ Debe completar todos los campos obligatorios.")
                elif new_pass != confirm_pass:
                    st.error("❌ Las nuevas contraseñas no coinciden. Por favor, verifícalas.")
                elif not db_pia.is_password_strong(new_pass):
                    st.error(f"❌ La nueva contraseña es demasiado corta (mínimo {db_pia.MIN_PASSWORD_LENGTH} caracteres).")
                else:
                    # Verificar la contraseña actual contra la base de datos
                    # Usamos st.session_state.user['email'] que está garantizado al estar logueado
                    user_email = st.session_state.user.get('email')
                    user_verify = db_pia.authenticate_user(user_email, old_pass)
                    
                    if not user_verify:
                        st.error("❌ La contraseña actual ingresada es incorrecta.")
                    else:
                        # Proceder al cambio
                        try:
                            db_pia.change_password(st.session_state.user_id, new_pass)
                            db_pia.log_audit_event(
                                "password_changed_by_user",
                                target_usuario_id=st.session_state.user_id,
                            )
                            st.success("✅ ¡Contraseña actualizada exitosamente! Usa tu nueva clave la próxima vez que inicies sesión.")
                            # No hacemos rerun forzoso para que el usuario vea el mensaje de éxito
                        except Exception as e:
                            log_exception("Error al cambiar contraseña desde perfil", e)
                            st.error(f"❌ Ocurrió un error al intentar actualizar la base de datos: {e}")
    
    with col3:
        pass # Espaciador
