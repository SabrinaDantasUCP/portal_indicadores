import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import hashlib
import streamlit as st

# Cargar variables de entorno
load_dotenv()

def get_connection():
    """Establece y devuelve una conexión a la base de datos MySQL usando el .env"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST_PIA", "localhost"),
            port=os.getenv("MYSQL_PORT_PIA", "3306"),
            user=os.getenv("MYSQL_USER_PIA", "root"),
            password=os.getenv("MYSQL_PASSWORD_PIA", ""),
            database=os.getenv("MYSQL_DB_PIA", "sistema_relatorios")
        )
        if connection.is_connected():
            return connection
    except Error as e:
        st.error(f"Error al conectar a MySQL: {e}")
        return None

def hash_password(password):
    """Genera un hash SHA-256 de forma asaltada para la contraseña"""
    # Usar un salt simple estático o dinámico. Para robustez media:
    salt = "pia_salt_2026_"
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()

@st.cache_resource
def init_db():
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # Tabla de Áreas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_areas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(255) NOT NULL UNIQUE
                )
            """)
            
            # Tabla de Usuarios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(255) NOT NULL,
                    apellido VARCHAR(255) NOT NULL,
                    documento VARCHAR(255) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    contrasena_hash VARCHAR(255) NOT NULL,
                    area_id INT,
                    rol ENUM('ADMIN', 'LEITURA') NOT NULL DEFAULT 'LEITURA',
                    activo BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (area_id) REFERENCES pia_areas(id) ON DELETE SET NULL
                )
            """)
            
            # Tabla de Permisos (Por categoría principal)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_permisos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NOT NULL,
                    modulo VARCHAR(255) NOT NULL,
                    FOREIGN KEY (usuario_id) REFERENCES pia_usuarios(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_user_mod (usuario_id, modulo)
                )
            """)
            
            # Tabla de Logs de Descargas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_log_descargas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT,
                    indicador VARCHAR(255) NOT NULL,
                    formato VARCHAR(50) NOT NULL,
                    fecha_descarga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL
                )
            """)
            
            # Crear un administrador por defecto si no existe ninguno
            cursor.execute("SELECT COUNT(*) FROM pia_usuarios")
            if cursor.fetchone()[0] == 0:
                p_hash = hash_password("admin")
                cursor.execute("""
                    INSERT INTO pia_usuarios (nombre, apellido, documento, email, contrasena_hash, rol, activo)
                    VALUES ('Admin', 'Sistema', '0000000', 'admin@admin.com', %s, 'ADMIN', TRUE)
                """, (p_hash,))
                
            conn.commit()
        except Error as e:
            st.error(f"Error inicializando las tablas de DB: {e}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

# ---------------- Funciones CRUD y Autenticación ---------------- #

def authenticate_user(email, password):
    conn = get_connection()
    user_data = None
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            p_hash = hash_password(password)
            cursor.execute("""
                SELECT id, nombre, apellido, email, rol, activo 
                FROM pia_usuarios 
                WHERE email = %s AND contrasena_hash = %s AND activo = TRUE
            """, (email, p_hash))
            user_data = cursor.fetchone()
        except Error as e:
            st.error(f"Error de autenticación: {e}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    return user_data

def get_user_by_id(user_id):
    conn = get_connection()
    user_data = None
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, nombre, apellido, email, rol, activo 
                FROM pia_usuarios 
                WHERE id = %s AND activo = TRUE
            """, (user_id,))
            user_data = cursor.fetchone()
        except Error as e:
            st.error(f"Error al obtener usuario por ID: {e}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    return user_data

def get_user_permissions(usuario_id):
    conn = get_connection()
    permisos = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT modulo FROM pia_permisos WHERE usuario_id = %s", (usuario_id,))
            permisos = [row[0] for row in cursor.fetchall()]
        except Error as e:
            st.error(f"Error al obtener permisos: {e}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    return permisos

def dict_fetchall(query, params=None):
    conn = get_connection()
    result = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            result = cursor.fetchall()
        except Error as e:
            st.error(f"Error de query: {e}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    return result

def execute_query(query, params=None, commit=True):
    conn = get_connection()
    last_id = None
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            if commit:
                conn.commit()
                last_id = cursor.lastrowid
        except Error as e:
            st.error(f"Error ejecutando consulta: {e}")
            raise e
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    return last_id

# MÉTODOS CRUD RÁPIDOS PARA ADMIN

def get_all_areas():
    return dict_fetchall("SELECT id, nombre FROM pia_areas ORDER BY nombre")

def add_area(nombre):
    execute_query("INSERT INTO pia_areas (nombre) VALUES (%s)", (nombre,))

def delete_area(id_area):
    execute_query("DELETE FROM pia_areas WHERE id = %s", (id_area,))

def update_area(id_area, nombre):
    execute_query("UPDATE pia_areas SET nombre=%s WHERE id=%s", (nombre, id_area))

def get_all_users():
    return dict_fetchall("""
        SELECT u.id, u.nombre, u.apellido, u.documento, u.email, u.rol, u.activo, a.nombre as area
        FROM pia_usuarios u
        LEFT JOIN pia_areas a ON u.area_id = a.id
        ORDER BY u.nombre
    """)

def add_user(nombre, apellido, documento, email, area_id, rol):
    # Generar contrasena autogenerada: nombre (primera palabra minúscula) @ documento
    primer_nombre = nombre.split()[0].lower()
    pw_plain = f"{primer_nombre}@{documento}"
    hashed = hash_password(pw_plain)
    
    uid = execute_query("""
        INSERT INTO pia_usuarios (nombre, apellido, documento, email, contrasena_hash, area_id, rol)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (nombre, apellido, documento, email, hashed, area_id, rol))
    
    return uid, pw_plain

def update_user(user_id, nombre, apellido, documento, email, area_id, rol, activo):
    execute_query("""
        UPDATE pia_usuarios 
        SET nombre=%s, apellido=%s, documento=%s, email=%s, area_id=%s, rol=%s, activo=%s
        WHERE id=%s
    """, (nombre, apellido, documento, email, area_id, rol, activo, user_id))

def set_user_permissions(user_id, modulos):
    query_del = "DELETE FROM pia_permisos WHERE usuario_id = %s"
    execute_query(query_del, (user_id,))
    
    if modulos:
        # Re-insertar bloque
        conn = get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                data = [(user_id, mod) for mod in modulos]
                cursor.executemany("INSERT INTO pia_permisos (usuario_id, modulo) VALUES (%s, %s)", data)
                conn.commit()
            except Error as e:
                st.error(f"Error seteando permisos: {e}")
            finally:
                if conn and conn.is_connected():
                    cursor.close()
                    conn.close()

def change_password(user_id, new_password):
    hashed = hash_password(new_password)
    execute_query("UPDATE pia_usuarios SET contrasena_hash=%s WHERE id=%s", (hashed, user_id))

# ---------------- Funciones de Log de Descargas ---------------- #

def log_export(usuario_id, indicador, formato):
    execute_query("""
        INSERT INTO pia_log_descargas (usuario_id, indicador, formato)
        VALUES (%s, %s, %s)
    """, (usuario_id, indicador, formato))

def get_export_logs():
    return dict_fetchall("""
        SELECT l.id, l.indicador, l.formato, l.fecha_descarga, 
               u.nombre, u.apellido, u.email, a.nombre as area
        FROM pia_log_descargas l
        LEFT JOIN pia_usuarios u ON l.usuario_id = u.id
        LEFT JOIN pia_areas a ON u.area_id = a.id
        ORDER BY l.fecha_descarga DESC
    """)

def log_export_callback(indicador, formato):
    if "user_id" in st.session_state and st.session_state.user_id:
        log_export(st.session_state.user_id, indicador, formato)
