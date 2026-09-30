# -*- coding: utf-8 -*-
"""
Script para conectar vía SSH/SFTP al servidor y descargar los conjuntos de datos reales.
"""
import os
import sys
import paramiko
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Obtener credenciales desde .env o usar los valores configurados
host_servidor = os.getenv("SSH_HOST", "10.20.8.82")
usuario_servidor = os.getenv("SSH_USER", "biocde")
if "@" in usuario_servidor:
    usuario_servidor = usuario_servidor.split("@")[0]
clave_servidor = os.getenv("SSH_PASSWORD", "biocde")
puerto_servidor = int(os.getenv("SSH_PORT", "22"))

def main():
    print(f"--- Conectando a {usuario_servidor}@{host_servidor}:{puerto_servidor} ---")
    cliente_ssh = paramiko.SSHClient()
    cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        cliente_ssh.connect(
            hostname=host_servidor,
            port=puerto_servidor,
            username=usuario_servidor,
            password=clave_servidor,
            timeout=10,
            look_for_keys=False,
            allow_agent=False
        )
        print("¡Conexión SSH establecida exitosamente!")
    except Exception as error_conexion:
        print(f"Error al conectar por SSH: {error_conexion}")
        return

    # Ejecutar comandos de exploración en el servidor
    rutas_a_explorar = [
        "/home/biocde/streamlit/sistema_relatorios/assets/data",
        "/home/biocde/streamlit/sistema_relatorios_test/assets/data",
    ]

    for ruta in rutas_a_explorar:
        print(f"\n================ Explorando: {ruta} ================")
        comando = f"find {ruta} -type f -exec ls -lh {{}} +"
        stdin, stdout, stderr = cliente_ssh.exec_command(comando)
        salida = stdout.read().decode("utf-8", errors="replace")
        errores = stderr.read().decode("utf-8", errors="replace")
        if salida:
            print(salida)
        if errores:
            print(f"Avisos/Errores: {errores}")

    # Cerrar conexión
    cliente_ssh.close()
    print("\nExploración finalizada.")

if __name__ == "__main__":
    main()
