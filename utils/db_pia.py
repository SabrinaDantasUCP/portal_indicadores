import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import hashlib
import hmac
import json
import secrets
import streamlit as st
from utils.menu_config import PERMISOS_SISTEMA
from utils.system_logging import log_exception

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
        log_exception("Error al conectar a MySQL", e)
        st.error(f"Error al conectar a MySQL: {e}")
        return None

PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 260000
MIN_PASSWORD_LENGTH = 8


def legacy_hash_password(password):
    salt = "pia_salt_2026_"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def hash_password(password):
    salt = secrets.token_hex(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt}${derived_key}"


def verify_password(password, stored_hash):
    if not stored_hash:
        return False, False

    if stored_hash.startswith(f"{PASSWORD_HASH_ALGORITHM}$"):
        try:
            algorithm, iterations, salt, expected_hash = stored_hash.split("$", 3)
            if algorithm != PASSWORD_HASH_ALGORITHM:
                return False, False
            calculated_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
            return hmac.compare_digest(calculated_hash, expected_hash), False
        except (ValueError, TypeError):
            return False, False

    legacy_hash = legacy_hash_password(password)
    return hmac.compare_digest(legacy_hash, stored_hash), True


def is_password_strong(password):
    return bool(password) and len(password.strip()) >= MIN_PASSWORD_LENGTH

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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_audit_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    actor_usuario_id INT,
                    target_usuario_id INT,
                    evento VARCHAR(100) NOT NULL,
                    detalle TEXT,
                    fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (actor_usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL,
                    FOREIGN KEY (target_usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL
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
            log_exception("Error inicializando tablas de base de datos", e)
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
            cursor.execute("""
                SELECT id, nombre, apellido, email, rol, activo, contrasena_hash
                FROM pia_usuarios 
                WHERE email = %s AND activo = TRUE
            """, (email,))
            row = cursor.fetchone()
            if row:
                password_ok, needs_rehash = verify_password(password, row["contrasena_hash"])
                if password_ok:
                    if needs_rehash:
                        cursor.execute(
                            "UPDATE pia_usuarios SET contrasena_hash = %s WHERE id = %s",
                            (hash_password(password), row["id"]),
                        )
                        conn.commit()
                    row.pop("contrasena_hash", None)
                    user_data = row
        except Error as e:
            log_exception("Error de autenticación en base de datos", e)
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
            log_exception("Error al obtener usuario por ID", e)
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
            log_exception("Error al obtener permisos", e)
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
            log_exception("Error al ejecutar dict_fetchall", e)
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
            log_exception("Error al ejecutar consulta", e)
            st.error(f"Error ejecutando consulta: {e}")
            raise e
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    return last_id


def current_actor_id():
    return st.session_state.get("user_id") if hasattr(st, "session_state") else None


def log_audit_event(evento, target_usuario_id=None, detalle=None, actor_usuario_id=None):
    actor_usuario_id = actor_usuario_id if actor_usuario_id is not None else current_actor_id()
    detalle_json = json.dumps(detalle or {}, ensure_ascii=False, default=str)
    try:
        execute_query("""
            INSERT INTO pia_audit_logs (actor_usuario_id, target_usuario_id, evento, detalle)
            VALUES (%s, %s, %s, %s)
        """, (actor_usuario_id, target_usuario_id, evento, detalle_json))
    except Exception as exc:
        log_exception(f"No se pudo registrar evento de auditoría '{evento}'", exc)


def get_audit_logs():
    return dict_fetchall("""
        SELECT
            l.id,
            l.evento,
            l.detalle,
            l.fecha_evento,
            actor.nombre AS actor_nombre,
            actor.apellido AS actor_apellido,
            actor.email AS actor_email,
            target.nombre AS target_nombre,
            target.apellido AS target_apellido,
            target.email AS target_email
        FROM pia_audit_logs l
        LEFT JOIN pia_usuarios actor ON l.actor_usuario_id = actor.id
        LEFT JOIN pia_usuarios target ON l.target_usuario_id = target.id
        ORDER BY l.fecha_evento DESC
    """)

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
        valid_permissions = set(PERMISOS_SISTEMA)
        modulos = [mod for mod in modulos if mod in valid_permissions]
    
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
                log_exception("Error al guardar permisos de usuario", e)
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
