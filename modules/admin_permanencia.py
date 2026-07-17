from datetime import date

import streamlit as st

from services.calculations.permanencia import get_periodo_config, listar_periodos
from services.data.permanencia import fechas_configuradas, limpiar_cache_fechas
from utils import db_pia
from utils.system_logging import log_exception


CAMPOS = (
    ("limite_primer_semestre", "Inicio de clases · alumnos de 1º semestre"),
    ("limite_otros_semestres", "Inicio de clases · alumnos antiguos"),
)


def _a_fecha(valor):
    return date.fromisoformat(valor) if isinstance(valor, str) else valor


def _render_periodo(periodo, configurado):
    por_defecto = get_periodo_config(periodo)
    vigente = {campo: _a_fecha((configurado or {}).get(campo) or por_defecto[campo]) for campo, _ in CAMPOS}

    with st.container(border=True):
        st.markdown(f"#### Índice de Permanencia {periodo}")

        if configurado:
            actualizado = configurado.get("actualizado_en")
            momento = actualizado.strftime("%d/%m/%Y %H:%M") if actualizado else "fecha desconocida"
            st.caption(f"Fechas configuradas desde esta pantalla · última modificación: {momento}")
        else:
            st.caption("Usando las fechas por defecto del sistema.")

        with st.form(f"form_fechas_{periodo}"):
            cols = st.columns(2)
            nuevas = {}
            for col, (campo, etiqueta) in zip(cols, CAMPOS):
                with col:
                    nuevas[campo] = st.date_input(
                        etiqueta,
                        value=vigente[campo],
                        format="DD/MM/YYYY",
                        key=f"fecha_{periodo}_{campo}",
                    )
                    defecto = _a_fecha(por_defecto[campo])
                    st.caption(f"Por defecto: {defecto.strftime('%d/%m/%Y')}")

            if st.form_submit_button("Guardar fechas", type="primary", use_container_width=True):
                try:
                    db_pia.set_permanencia_fechas(
                        periodo,
                        nuevas["limite_primer_semestre"],
                        nuevas["limite_otros_semestres"],
                    )
                    db_pia.log_audit_event(
                        "permanencia_fechas_actualizadas",
                        detalle={"periodo": periodo, **{c: str(v) for c, v in nuevas.items()}},
                    )
                    limpiar_cache_fechas()
                    st.session_state.temp_msg_perm = f"Fechas del indicador {periodo} actualizadas."
                    st.rerun()
                except Exception as exc:
                    log_exception("Error al guardar fechas de permanencia", exc)
                    st.error("No se pudieron guardar las fechas. Intente nuevamente.")

        if configurado:
            if st.button(
                "Restaurar valores por defecto",
                icon=":material/restart_alt:",
                key=f"reset_{periodo}",
                help="Vuelve a las fechas definidas en el sistema",
            ):
                try:
                    db_pia.delete_permanencia_fechas(periodo)
                    db_pia.log_audit_event(
                        "permanencia_fechas_restauradas", detalle={"periodo": periodo}
                    )
                    limpiar_cache_fechas()
                    st.session_state.temp_msg_perm = f"El indicador {periodo} volvió a las fechas por defecto."
                    st.rerun()
                except Exception as exc:
                    log_exception("Error al restaurar fechas de permanencia", exc)
                    st.error("No se pudieron restaurar las fechas por defecto.")


def render():
    if st.session_state.get('rol') != 'ADMIN':
        st.error("Acceso Denegado. Solo administradores pueden ver esta pantalla.", icon=":material/lock:")
        return

    if "temp_msg_perm" in st.session_state:
        st.success(st.session_state.temp_msg_perm)
        del st.session_state.temp_msg_perm

    st.subheader("Fechas de Inicio de Clases")
    st.markdown("""
Fecha en la que empiezan las clases de cada periodo. Se cargan dos por periodo porque
los alumnos de 1º semestre no empiezan el mismo día que los alumnos antiguos.

**Estas fechas afectan directamente el cálculo del Índice de Permanencia:**

- Si un alumno pasó a **suspenso** o **trancado** *antes* de la fecha de inicio de clases,
  se considera que nunca llegó a empezar el semestre y **queda fuera del indicador**
  (no cuenta ni en la base ni como no rematriculado).
- Si la baja fue *en la fecha de inicio o después*, el alumno **sí entra en el cálculo**,
  como rematriculado o como no rematriculado según corresponda.

Por eso, cambiar una fecha mueve tanto la cantidad de alumnos de la base como el
**% de permanencia**. El cambio se ve enseguida en *Índice de Permanencia* →
**Visión General** y **Fecha de Corte**, y queda registrado en *Logs y Auditoría*.
    """)
    st.divider()

    configuradas = fechas_configuradas()
    for periodo in listar_periodos():
        _render_periodo(periodo, configuradas.get(periodo))
