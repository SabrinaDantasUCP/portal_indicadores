# -*- coding: utf-8 -*-
"""
Script para sincronizar y descargar los conjuntos de datos reales desde el servidor remoto vía SFTP.
Descarga los parquets, csvs y excels necesarios para el funcionamiento del portal y los módulos de encuestas.
"""
import os
import sys
import shutil
import paramiko
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Credenciales de conexión
HOST_SERVIDOR = os.getenv("SSH_HOST", "10.20.8.82")
USUARIO_SERVIDOR = os.getenv("SSH_USER", "biocde")
if "@" in USUARIO_SERVIDOR:
    USUARIO_SERVIDOR = USUARIO_SERVIDOR.split("@")[0]
CLAVE_SERVIDOR = os.getenv("SSH_PASSWORD", "biocde")
PUERTO_SERVIDOR = int(os.getenv("SSH_PORT", "22"))

# Rutas locales
DIR_BASE_LOCAL = Path(__file__).resolve().parent.parent
DIR_DATA_LOCAL = DIR_BASE_LOCAL / "assets" / "data"
DIR_ONEDRIVE = Path(r"C:\Users\arman\OneDrive\Documentos\Mis sistemas\portal_indicadores\assets\data")

# Rutas remotas de origen
RUTAS_REMOTAS = [
    "/home/biocde/streamlit/sistema_relatorios_test/assets/data",
    "/home/biocde/streamlit/sistema_relatorios/assets/data",
]

def obtener_archivos_remotos(sftp, ruta_remota_base):
    """
    Recorre recursivamente un directorio remoto en el servidor SFTP
    y retorna una lista de tuplas (ruta_relativa, tamaño, mtime).
    """
    archivos = []
    
    def recorrer(dir_remoto, rel_acumulada=""):
        try:
            entradas = sftp.listdir_attr(dir_remoto)
        except Exception:
            return

        for entrada in entradas:
            nombre = entrada.filename
            if nombre in (".", "..", "desktop.ini"):
                continue
            
            sub_remoto = f"{dir_remoto}/{nombre}"
            sub_rel = f"{rel_acumulada}/{nombre}" if rel_acumulada else nombre
            
            # Verificar si es directorio
            es_directorio = (entrada.st_mode & 0o170000) == 0o040000
            if es_directorio:
                recorrer(sub_remoto, sub_rel)
            else:
                archivos.append((sub_remoto, sub_rel, entrada.st_size, entrada.st_mtime))

    recorrer(ruta_remota_base)
    return archivos

def main():
    print(f"=== Conectando a {USUARIO_SERVIDOR}@{HOST_SERVIDOR}:{PUERTO_SERVIDOR} vía SSH/SFTP ===")
    cliente_ssh = paramiko.SSHClient()
    cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        cliente_ssh.connect(
            hostname=HOST_SERVIDOR,
            port=PUERTO_SERVIDOR,
            username=USUARIO_SERVIDOR,
            password=CLAVE_SERVIDOR,
            timeout=15,
            look_for_keys=False,
            allow_agent=False,
        )
        print("Conexión SSH exitosa.")
        sftp = cliente_ssh.open_sftp()
        print("Canal SFTP abierto correctamente.")
    except Exception as error:
        print(f"Error al conectar con el servidor: {error}")
        return

    # Buscar archivos disponibles en test y producción
    mapa_archivos = {} # sub_rel -> (ruta_remota, tamano, mtime)

    # 1. Cargar desde sistema_relatorios_test
    archivos_test = obtener_archivos_remotos(sftp, "/home/biocde/streamlit/sistema_relatorios_test/assets/data")
    for r_rem, r_rel, tam, mtime in archivos_test:
        mapa_archivos[r_rel] = (r_rem, tam, mtime)

    # 2. Complementar o actualizar con sistema_relatorios (producción) si es más reciente
    archivos_prod = obtener_archivos_remotos(sftp, "/home/biocde/streamlit/sistema_relatorios/assets/data")
    for r_rem, r_rel, tam, mtime in archivos_prod:
        if r_rel not in mapa_archivos or mtime > mapa_archivos[r_rel][2]:
            mapa_archivos[r_rel] = (r_rem, tam, mtime)

    print(f"\nSe encontraron {len(mapa_archivos)} archivos remotos disponibles para sincronizar.")

    # Filtrar solo archivos necesarios: parquet, xlsx, csv (omitir csvs masivos innecesarios si ya existe parquet, salvo encuestas y requeridos)
    descargas = []
    for r_rel, (r_rem, tam, mtime) in sorted(mapa_archivos.items()):
        # Omitir backups de temp_years de años antiguos o dumps masivos > 100MB si no se necesitan de inmediato
        if r_rel.startswith("temp_years/"):
            continue
        # Omitir backups repetidos de ruas/egresados
        if "backup" in r_rel.lower():
            continue
        # Omitir alumnos_v1.csv (200MB) y alumnos_v2.csv (172MB) porque se usan los .parquet directamente
        if r_rel in ("v1/alumnos_v1.csv", "v2/alumnos_v2.csv", "v1/asistencia_unificada_v1.csv", "v2/asistencia_unificada_v2.csv"):
            continue

        descargas.append((r_rem, r_rel, tam))

    print(f"\n--- Descargando {len(descargas)} archivos seleccionados ---")
    for r_rem, r_rel, tam in descargas:
        destino_local = DIR_DATA_LOCAL / r_rel
        destino_local.parent.mkdir(parents=True, exist_ok=True)
        
        tam_mb = tam / (1024 * 1024)
        print(f"Descargando: {r_rel} ({tam_mb:.2f} MB)...", end=" ", flush=True)

        try:
            sftp.get(r_rem, str(destino_local))
            print("OK")
            
            # Copiar también al espejo OneDrive si existe la ruta
            if DIR_ONEDRIVE.parent.exists():
                destino_onedrive = DIR_ONEDRIVE / r_rel
                destino_onedrive.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destino_local, destino_onedrive)
        except Exception as err_descarga:
            print(f"ERROR: {err_descarga}")

    sftp.close()
    cliente_ssh.close()
    print("\n¡Descarga y sincronización completada con éxito!")

if __name__ == "__main__":
    main()
