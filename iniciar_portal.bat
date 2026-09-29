@echo off
chcp 65001 > nul
title Portal de Indicadores - UCP

:: Cambiar al directorio donde reside este archivo .bat
cd /d "%~dp0"

echo ========================================================
echo       Iniciando Portal de Indicadores Academicos
echo ========================================================
echo.

:: Verificar si existe el entorno virtual local
if exist ".venv\Scripts\streamlit.exe" (
    echo [OK] Entorno virtual detectado (.venv).
    echo [INFO] Iniciando servidor Streamlit en el puerto 8501...
    echo [INFO] Para detener el servidor, presione Ctrl + C en esta ventana.
    echo.
    ".venv\Scripts\streamlit.exe" run app.py --server.port=8501
) else (
    echo [AVISO] No se encontro .venv local. Intentando con Python global...
    streamlit run app.py --server.port=8501
)

pause
