# Reglas del Proyecto (Portal de Indicadores)

Este documento define las reglas fundamentales e inquebrantables de desarrollo para este proyecto:

1. **Idioma (Español)**:
   - Todo el código debe estar comentado en español.
   - Todo lo nuevo que se cree o implemente debe tener sus nombres de variables, funciones, clases, comentarios y explicaciones en español.

2. **Depuración y Limpieza de Código**:
   - No dejar código basura de lado.
   - Depurar código **SI y SOLO SI** no es útil ni se va a usar.

3. **Codificación**:
   - Respetar siempre la codificación **UTF-8** en todos los archivos del proyecto.

4. **Estabilidad y Regresión**:
   - **NUNCA romper lo logrado**: Mantener siempre la estabilidad y funcionamiento de las características ya existentes.

5. **Preservación**:
   - **NUNCA borrar archivos ni bloques de código útiles**.

6. **Protocolo Estricto de Despliegue y Subida a Remoto/Servidor**:
   - Este proceso debe ejecutarse **SI Y SOLO SI** el usuario lo autoriza explícitamente en la conversación.
   - **PROHIBIDO** hacer `git push` a ramas remotas (`origin`) o realizar despliegues/reinicios en el servidor de pruebas (`10.20.8.82`) de manera automática o no autorizada.
   - **Fases del Proceso de Despliegue**:
     1. **Fase 1 (Validación Local)**:
        - Verificar que el repositorio local esté limpio (`git status`).
        - Revisar los commits exactos pendientes en la rama local (`armando_teste`).
        - Validar compilación limpia con `python -m py_compile`.
     2. **Fase 2 (Subida a Rama Personal)**:
        - Ejecutar `git push origin armando_teste`.
        - Confirmar que `origin/armando_teste` esté sincronizada.
     3. **Fase 3 (Integración en Rama Teste)**:
        - Verificar `origin/teste` mediante `git fetch origin teste`.
        - Integrar los commits aprobados en la rama `teste`.
        - Subir a GitHub mediante `git push origin teste`.
     4. **Fase 4 (Despliegue en Servidor 10.20.8.82)**:
        - Conectarse vía SSH a `10.20.8.82` (usuario `biocde`).
        - Ir al directorio `/home/biocde/streamlit/sistema_relatorios_test`.
        - Ejecutar `git pull origin teste`.
        - Reiniciar el servicio: `sudo systemctl restart streamlit_app_test.service`.
        - Validar estado del servicio y respuesta HTTP `200 OK` en `http://10.20.8.82:8502/_stcore/health`.
