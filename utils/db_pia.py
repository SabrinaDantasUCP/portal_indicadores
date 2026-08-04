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

def get_connection(silent=False):
    """Establece y devuelve una conexión a la base de datos MySQL usando el .env.

    Con silent=True el fallo solo se registra en el log, sin pintar el error en
    pantalla: para lecturas opcionales que tienen un valor por defecto.
    """
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
        if not silent:
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

            # Fechas de inicio de clases por periodo (Índice de Permanencia).
            # Si un periodo no está acá, se usan los valores por defecto del código.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_config_permanencia (
                    periodo VARCHAR(10) PRIMARY KEY,
                    limite_primer_semestre DATE NOT NULL,
                    limite_otros_semestres DATE NOT NULL,
                    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
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

            # Configuración del ETL de encuestas (qué tipo/periodo/carrera se
            # actualiza automáticamente y con qué id de Academico.Encuesta).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_encuesta_etl_config (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tipo_encuesta ENUM('ALUMNO_DOCENTE', 'AUTOEVAL_DOCENTE', 'EVALUACION_PARES') NOT NULL,
                    sede VARCHAR(100) NOT NULL,
                    periodo VARCHAR(20) NOT NULL,
                    carrera VARCHAR(100) NOT NULL,
                    id_encuesta_externa INT NOT NULL,
                    dataset_name VARCHAR(150) NOT NULL UNIQUE,
                    scope_mode ENUM('GLOBAL', 'SEGUE_VERSION') NOT NULL DEFAULT 'GLOBAL',
                    activo BOOLEAN DEFAULT TRUE,
                    creado_por INT,
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (creado_por) REFERENCES pia_usuarios(id) ON DELETE SET NULL,
                    UNIQUE KEY unique_encuesta_config (tipo_encuesta, sede, periodo, carrera)
                )
            """)

            # Historial de ejecuciones del ETL de encuestas (manual o cron).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_encuesta_etl_run (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    config_id INT NOT NULL,
                    disparado_por ENUM('MANUAL', 'CRON') NOT NULL,
                    actor_usuario_id INT,
                    iniciado_en TIMESTAMP NOT NULL,
                    finalizado_en TIMESTAMP NOT NULL,
                    status ENUM('OK', 'ERROR') NOT NULL,
                    filas_generadas INT,
                    mensaje_error TEXT,
                    FOREIGN KEY (config_id) REFERENCES pia_encuesta_etl_config(id) ON DELETE CASCADE,
                    FOREIGN KEY (actor_usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL
                )
            """)

            # Configuración del ETL de alumnos (matriculas/notas -> alumnos_v1/v2).
            # Config única (singleton, id=1): a diferencia de encuestas, no hay
            # combinación sede/periodo/carrera — solo qué años entran en el loop
            # de extracción (cada año es una query MySQL separada, ver
            # services/etl/alumnos_etl.py) y si el cron nocturno (04:00) está
            # activo. "anos" se guarda como CSV de enteros (ej. "2017,2018,...").
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_alumnos_etl_config (
                    id INT PRIMARY KEY DEFAULT 1,
                    anos VARCHAR(500) NOT NULL,
                    activo BOOLEAN DEFAULT TRUE,
                    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)

            # Historial de ejecuciones del ETL de alumnos (manual o cron).
            # status incluye 'CANCELADO' porque el botón "Detener" del admin
            # (modules/alumnos_config_etl.py) puede cortar la ejecución entre
            # años (ver services/etl/alumnos_etl.procesar_anos).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_alumnos_etl_run (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    disparado_por ENUM('MANUAL', 'CRON') NOT NULL,
                    actor_usuario_id INT,
                    iniciado_en TIMESTAMP NOT NULL,
                    finalizado_en TIMESTAMP NOT NULL,
                    status ENUM('OK', 'ERROR', 'CANCELADO') NOT NULL,
                    filas_v1 INT,
                    filas_v2 INT,
                    anos_procesados VARCHAR(500),
                    mensaje_error TEXT,
                    FOREIGN KEY (actor_usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL
                )
            """)
            # Migración defensiva: si la tabla ya existía de antes (creada en
            # una versión sin 'CANCELADO'), agrega el valor al ENUM.
            try:
                cursor.execute("""
                    ALTER TABLE pia_alumnos_etl_run
                    MODIFY status ENUM('OK', 'ERROR', 'CANCELADO') NOT NULL
                """)
            except Error:
                pass

            # Lock (singleton, id=1) para evitar que dos ejecuciones del ETL de
            # alumnos corran al mismo tiempo (ej. el cron de las 04:00 y un
            # "Ejecutar ahora" manual pisándose, o dos pestañas/sesiones del
            # admin). Se adquiere de forma atómica (ver
            # try_acquire_alumnos_etl_lock) y se libera siempre al terminar
            # (OK, ERROR o CANCELADO).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_alumnos_etl_lock (
                    id INT PRIMARY KEY DEFAULT 1,
                    en_ejecucion BOOLEAN NOT NULL DEFAULT FALSE,
                    disparado_por ENUM('MANUAL', 'CRON'),
                    actor_usuario_id INT,
                    iniciado_en TIMESTAMP NULL,
                    FOREIGN KEY (actor_usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL
                )
            """)
            cursor.execute("SELECT COUNT(*) FROM pia_alumnos_etl_lock")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO pia_alumnos_etl_lock (id, en_ejecucion) VALUES (1, FALSE)
                """)

            # Configuración del ETL de asistencias (coord_aula/syseduca +
            # attendance/biometria -> asistencia_unificada_v1/v2). Config
            # única (singleton, id=1): "anos_syseduca" es una lista de años
            # (CSV de enteros) para la fuente vieja (MySQL, antes de 2025.2);
            # "periodos_biometria" es una lista de periodos tipo "2025.2"
            # (CSV de strings) para la fuente nueva (Postgres, desde 2025.2),
            # reutilizando el mismo formato/parseo que encuestas
            # (derivar_parametros_periodo).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_asistencias_etl_config (
                    id INT PRIMARY KEY DEFAULT 1,
                    anos_syseduca VARCHAR(500) NOT NULL,
                    periodos_biometria VARCHAR(500) NOT NULL,
                    activo BOOLEAN DEFAULT TRUE,
                    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("SELECT COUNT(*) FROM pia_asistencias_etl_config")
            if cursor.fetchone()[0] == 0:
                anos_default = ",".join(str(a) for a in range(2021, 2026))
                cursor.execute("""
                    INSERT INTO pia_asistencias_etl_config (id, anos_syseduca, periodos_biometria, activo)
                    VALUES (1, %s, '2025.2', TRUE)
                """, (anos_default,))

            # Historial de ejecuciones del ETL de asistencias (manual o cron).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_asistencias_etl_run (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    disparado_por ENUM('MANUAL', 'CRON') NOT NULL,
                    actor_usuario_id INT,
                    iniciado_en TIMESTAMP NOT NULL,
                    finalizado_en TIMESTAMP NOT NULL,
                    status ENUM('OK', 'ERROR', 'CANCELADO') NOT NULL,
                    filas_v1 INT,
                    filas_v2 INT,
                    anos_syseduca_procesados VARCHAR(500),
                    periodos_biometria_procesados VARCHAR(500),
                    mensaje_error TEXT,
                    FOREIGN KEY (actor_usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL
                )
            """)

            # Lock (singleton, id=1) del ETL de asistencias — mismo patrón que
            # pia_alumnos_etl_lock, tabla separada porque son pipelines
            # independientes (pueden correr uno mientras el otro corre, solo
            # no dos ejecuciones del MISMO pipeline a la vez).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_asistencias_etl_lock (
                    id INT PRIMARY KEY DEFAULT 1,
                    en_ejecucion BOOLEAN NOT NULL DEFAULT FALSE,
                    disparado_por ENUM('MANUAL', 'CRON'),
                    actor_usuario_id INT,
                    iniciado_en TIMESTAMP NULL,
                    FOREIGN KEY (actor_usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL
                )
            """)
            cursor.execute("SELECT COUNT(*) FROM pia_asistencias_etl_lock")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO pia_asistencias_etl_lock (id, en_ejecucion) VALUES (1, FALSE)
                """)

            # Configuración del ETL de Índice de Permanencia. A diferencia de
            # alumnos/asistencias (singleton), acá hay UNA fila por periodo
            # (ej. "2025.2", "2026.1") porque cada periodo tiene su propia
            # fecha_corte y su propio estado de "ya se congeló o no".
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_permanencia_etl_config (
                    periodo VARCHAR(10) PRIMARY KEY,
                    fecha_corte DATE NOT NULL,
                    corte_generado BOOLEAN DEFAULT FALSE,
                    activo BOOLEAN DEFAULT TRUE,
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("SELECT COUNT(*) FROM pia_permanencia_etl_config")
            if cursor.fetchone()[0] == 0:
                # Semilla con los 2 periodos ya existentes en el sistema.
                # 2025.2 ya tenía su snapshot de corte generado (manualmente,
                # antes de este ETL) -- se marca corte_generado=TRUE y
                # activo=FALSE (periodo cerrado, no hace falta recalcular
                # todos los días). 2026.1 es el periodo vigente: activo=TRUE,
                # corte_generado=FALSE (la fecha es un valor de partida --el
                # admin la redefine en la pantalla de Configuración ETL).
                cursor.execute("""
                    INSERT INTO pia_permanencia_etl_config (periodo, fecha_corte, corte_generado, activo)
                    VALUES ('2025.2', '2026-04-05', TRUE, FALSE),
                           ('2026.1', '2026-07-16', FALSE, TRUE)
                """)

            # Historial de ejecuciones del ETL de permanencia (manual o cron).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_permanencia_etl_run (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    periodo VARCHAR(10) NOT NULL,
                    disparado_por ENUM('MANUAL', 'CRON') NOT NULL,
                    actor_usuario_id INT,
                    iniciado_en TIMESTAMP NOT NULL,
                    finalizado_en TIMESTAMP NOT NULL,
                    status ENUM('OK', 'ERROR', 'CANCELADO') NOT NULL,
                    filas INT,
                    corte_generado_en_este_run BOOLEAN DEFAULT FALSE,
                    mensaje_error TEXT,
                    FOREIGN KEY (actor_usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL
                )
            """)

            # Lock (singleton, id=1) del ETL de permanencia -- global entre
            # periodos: solo una ejecución (de cualquier periodo) a la vez.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_permanencia_etl_lock (
                    id INT PRIMARY KEY DEFAULT 1,
                    en_ejecucion BOOLEAN NOT NULL DEFAULT FALSE,
                    disparado_por ENUM('MANUAL', 'CRON'),
                    actor_usuario_id INT,
                    periodo VARCHAR(10),
                    iniciado_en TIMESTAMP NULL,
                    FOREIGN KEY (actor_usuario_id) REFERENCES pia_usuarios(id) ON DELETE SET NULL
                )
            """)
            cursor.execute("SELECT COUNT(*) FROM pia_permanencia_etl_lock")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO pia_permanencia_etl_lock (id, en_ejecucion) VALUES (1, FALSE)
                """)

            # Metadatos del archivo egresados.xlsx (usado por el cruce en
            # generar_alumnos_v1): guarda la fecha en que el área de origen
            # envió/actualizó la planilla, distinta de "cuándo se subió al
            # sistema" (actualizado_en), para poder mostrar en el dashboard
            # cuán vieja es la información de egreso/titulación.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pia_egresados_meta (
                    id INT PRIMARY KEY DEFAULT 1,
                    fecha_envio DATE NOT NULL,
                    filas INT,
                    actualizado_por INT,
                    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (actualizado_por) REFERENCES pia_usuarios(id) ON DELETE SET NULL
                )
            """)

            # Semilla de la config de alumnos (rango histórico por defecto).
            cursor.execute("SELECT COUNT(*) FROM pia_alumnos_etl_config")
            if cursor.fetchone()[0] == 0:
                anos_default = ",".join(str(a) for a in range(2017, 2027))
                cursor.execute("""
                    INSERT INTO pia_alumnos_etl_config (id, anos, activo)
                    VALUES (1, %s, TRUE)
                """, (anos_default,))

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

def dict_fetchall(query, params=None, silent=False):
    conn = get_connection(silent=silent)
    result = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            result = cursor.fetchall()
        except Error as e:
            log_exception("Error al ejecutar dict_fetchall", e)
            if not silent:
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

# ---------------- Fechas del Índice de Permanencia ---------------- #

def get_permanencia_fechas():
    """Devuelve {periodo: {limite_primer_semestre, limite_otros_semestres}} en formato ISO.

    Solo trae los periodos configurados desde la pantalla de administración; el
    resto usa los valores por defecto del código.
    """
    # silent: es una lectura opcional. Si la tabla o la base no responden, el
    # indicador usa las fechas por defecto en vez de mostrarle un error al usuario.
    rows = dict_fetchall("""
        SELECT periodo, limite_primer_semestre, limite_otros_semestres, actualizado_en
        FROM pia_config_permanencia
    """, silent=True)
    return {
        row["periodo"]: {
            "limite_primer_semestre": row["limite_primer_semestre"].isoformat(),
            "limite_otros_semestres": row["limite_otros_semestres"].isoformat(),
            "actualizado_en": row["actualizado_en"],
        }
        for row in rows
    }


def set_permanencia_fechas(periodo, limite_primer_semestre, limite_otros_semestres):
    execute_query("""
        INSERT INTO pia_config_permanencia (periodo, limite_primer_semestre, limite_otros_semestres)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            limite_primer_semestre = VALUES(limite_primer_semestre),
            limite_otros_semestres = VALUES(limite_otros_semestres)
    """, (periodo, limite_primer_semestre, limite_otros_semestres))


def delete_permanencia_fechas(periodo):
    """Borra la configuración del periodo: vuelve a los valores por defecto del código."""
    execute_query("DELETE FROM pia_config_permanencia WHERE periodo = %s", (periodo,))


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


# ---------------- Configuración ETL de Encuestas ---------------- #
# "anho"/"subperiodo"/"semestre_bio" NO se guardan como columnas propias: se
# derivan siempre a partir de "periodo" (ej. "2026.1") vía
# services.etl.encuestas_etl.derivar_parametros_periodo, para que no puedan
# quedar desincronizados de "periodo" por una edición manual.

def get_encuesta_etl_configs():
    return dict_fetchall("""
        SELECT id, tipo_encuesta, sede, periodo, carrera,
               id_encuesta_externa, dataset_name, scope_mode, activo,
               creado_en, actualizado_en
        FROM pia_encuesta_etl_config
        ORDER BY periodo DESC, sede, carrera, tipo_encuesta
    """)


def get_encuesta_etl_config(config_id):
    rows = dict_fetchall("""
        SELECT id, tipo_encuesta, sede, periodo, carrera,
               id_encuesta_externa, dataset_name, scope_mode, activo
        FROM pia_encuesta_etl_config
        WHERE id = %s
    """, (config_id,))
    return rows[0] if rows else None


def get_encuesta_etl_configs_activos():
    return dict_fetchall("""
        SELECT id, tipo_encuesta, sede, periodo, carrera,
               id_encuesta_externa, dataset_name, scope_mode
        FROM pia_encuesta_etl_config
        WHERE activo = TRUE
    """)


def add_encuesta_etl_config(tipo_encuesta, sede, periodo, carrera,
                             id_encuesta_externa, dataset_name, scope_mode, creado_por=None):
    return execute_query("""
        INSERT INTO pia_encuesta_etl_config
            (tipo_encuesta, sede, periodo, carrera,
             id_encuesta_externa, dataset_name, scope_mode, creado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (tipo_encuesta, sede, periodo, carrera,
          id_encuesta_externa, dataset_name, scope_mode, creado_por))


def update_encuesta_etl_config(config_id, sede, periodo, carrera,
                                id_encuesta_externa, dataset_name, scope_mode):
    execute_query("""
        UPDATE pia_encuesta_etl_config
        SET sede=%s, periodo=%s, carrera=%s,
            id_encuesta_externa=%s, dataset_name=%s, scope_mode=%s
        WHERE id=%s
    """, (sede, periodo, carrera, id_encuesta_externa,
          dataset_name, scope_mode, config_id))


def toggle_encuesta_etl_config_activo(config_id, activo):
    execute_query(
        "UPDATE pia_encuesta_etl_config SET activo=%s WHERE id=%s",
        (activo, config_id),
    )


def delete_encuesta_etl_config(config_id):
    execute_query("DELETE FROM pia_encuesta_etl_config WHERE id = %s", (config_id,))


def registrar_encuesta_etl_run(config_id, disparado_por, status, iniciado_en, finalizado_en,
                                filas_generadas=None, mensaje_error=None, actor_usuario_id=None):
    execute_query("""
        INSERT INTO pia_encuesta_etl_run
            (config_id, disparado_por, actor_usuario_id, iniciado_en, finalizado_en,
             status, filas_generadas, mensaje_error)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (config_id, disparado_por, actor_usuario_id, iniciado_en, finalizado_en,
          status, filas_generadas, mensaje_error))


def get_ultimo_run_por_config():
    """Devuelve {config_id: {status, filas_generadas, mensaje_error, iniciado_en,
    finalizado_en, disparado_por}} solo con la ejecución más reciente de cada config."""
    rows = dict_fetchall("""
        SELECT r.config_id, r.disparado_por, r.iniciado_en, r.finalizado_en,
               r.status, r.filas_generadas, r.mensaje_error
        FROM pia_encuesta_etl_run r
        INNER JOIN (
            SELECT config_id, MAX(id) AS max_id
            FROM pia_encuesta_etl_run
            GROUP BY config_id
        ) ultimo ON ultimo.config_id = r.config_id AND ultimo.max_id = r.id
    """)
    return {row["config_id"]: row for row in rows}


# ---------------- Configuración ETL de Alumnos ---------------- #
# Config singleton (id=1, sembrada en init_db): a diferencia de encuestas no
# hay tipo/sede/periodo/carrera, solo la lista de años del loop de extracción
# (ver services/etl/alumnos_etl.py) y si el cron nocturno (04:00) está activo.

def get_alumnos_etl_config():
    rows = dict_fetchall("""
        SELECT id, anos, activo, actualizado_en
        FROM pia_alumnos_etl_config
        WHERE id = 1
    """)
    if not rows:
        return None
    row = rows[0]
    row["anos"] = [int(a) for a in row["anos"].split(",") if a.strip()]
    return row


def update_alumnos_etl_config(anos, activo):
    """anos: lista de enteros (años a incluir en el loop de extracción)."""
    anos_csv = ",".join(str(int(a)) for a in sorted(anos))
    execute_query("""
        UPDATE pia_alumnos_etl_config
        SET anos=%s, activo=%s
        WHERE id=1
    """, (anos_csv, activo))


def registrar_alumnos_etl_run(disparado_por, status, iniciado_en, finalizado_en,
                               anos_procesados=None, filas_v1=None, filas_v2=None,
                               mensaje_error=None, actor_usuario_id=None):
    anos_csv = ",".join(str(int(a)) for a in anos_procesados) if anos_procesados else None
    execute_query("""
        INSERT INTO pia_alumnos_etl_run
            (disparado_por, actor_usuario_id, iniciado_en, finalizado_en,
             status, filas_v1, filas_v2, anos_procesados, mensaje_error)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (disparado_por, actor_usuario_id, iniciado_en, finalizado_en,
          status, filas_v1, filas_v2, anos_csv, mensaje_error))


def get_ultimo_alumnos_etl_run():
    rows = dict_fetchall("""
        SELECT disparado_por, iniciado_en, finalizado_en, status,
               filas_v1, filas_v2, anos_procesados, mensaje_error
        FROM pia_alumnos_etl_run
        ORDER BY id DESC
        LIMIT 1
    """)
    return rows[0] if rows else None


# ---------------- Lock de ejecución del ETL de Alumnos ---------------- #

def try_acquire_alumnos_etl_lock(disparado_por, actor_usuario_id=None):
    """Intenta tomar el lock de forma atómica: el UPDATE solo afecta la fila
    si todavía estaba libre (WHERE en_ejecucion=FALSE), así que dos llamadas
    concurrentes nunca pueden creer ambas que ganaron. Devuelve True si se
    consiguió el lock, False si ya había una ejecución en curso.

    Usa cursor.rowcount directo (no execute_query/dict_fetchall) porque la
    corrección acá depende de saber exactamente cuántas filas afectó ESTE
    UPDATE, no de releer el estado después (que sería ambiguo entre "gané yo"
    y "ganó otra sesión con los mismos disparado_por/actor_usuario_id)."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pia_alumnos_etl_lock
            SET en_ejecucion=TRUE, disparado_por=%s, actor_usuario_id=%s, iniciado_en=NOW()
            WHERE id=1 AND en_ejecucion=FALSE
        """, (disparado_por, actor_usuario_id))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        log_exception("Error al intentar tomar el lock del ETL de alumnos", e)
        return False
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


def release_alumnos_etl_lock():
    execute_query("""
        UPDATE pia_alumnos_etl_lock
        SET en_ejecucion=FALSE
        WHERE id=1
    """)


def get_alumnos_etl_lock_status():
    rows = dict_fetchall("""
        SELECT en_ejecucion, disparado_por, actor_usuario_id, iniciado_en
        FROM pia_alumnos_etl_lock
        WHERE id = 1
    """)
    return rows[0] if rows else None


# ---------------- Configuración ETL de Asistencias ---------------- #

def get_asistencias_etl_config():
    rows = dict_fetchall("""
        SELECT id, anos_syseduca, periodos_biometria, activo, actualizado_en
        FROM pia_asistencias_etl_config
        WHERE id = 1
    """)
    if not rows:
        return None
    row = rows[0]
    row["anos_syseduca"] = [int(a) for a in row["anos_syseduca"].split(",") if a.strip()]
    row["periodos_biometria"] = [p.strip() for p in row["periodos_biometria"].split(",") if p.strip()]
    return row


def update_asistencias_etl_config(anos_syseduca, periodos_biometria, activo):
    anos_csv = ",".join(str(int(a)) for a in sorted(anos_syseduca))
    periodos_csv = ",".join(sorted(periodos_biometria))
    execute_query("""
        UPDATE pia_asistencias_etl_config
        SET anos_syseduca=%s, periodos_biometria=%s, activo=%s
        WHERE id=1
    """, (anos_csv, periodos_csv, activo))


def registrar_asistencias_etl_run(disparado_por, status, iniciado_en, finalizado_en,
                                   anos_syseduca_procesados=None, periodos_biometria_procesados=None,
                                   filas_v1=None, filas_v2=None, mensaje_error=None, actor_usuario_id=None):
    anos_csv = ",".join(str(int(a)) for a in anos_syseduca_procesados) if anos_syseduca_procesados else None
    periodos_csv = ",".join(periodos_biometria_procesados) if periodos_biometria_procesados else None
    execute_query("""
        INSERT INTO pia_asistencias_etl_run
            (disparado_por, actor_usuario_id, iniciado_en, finalizado_en,
             status, filas_v1, filas_v2, anos_syseduca_procesados,
             periodos_biometria_procesados, mensaje_error)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (disparado_por, actor_usuario_id, iniciado_en, finalizado_en,
          status, filas_v1, filas_v2, anos_csv, periodos_csv, mensaje_error))


def get_ultimo_asistencias_etl_run():
    rows = dict_fetchall("""
        SELECT disparado_por, iniciado_en, finalizado_en, status,
               filas_v1, filas_v2, anos_syseduca_procesados,
               periodos_biometria_procesados, mensaje_error
        FROM pia_asistencias_etl_run
        ORDER BY id DESC
        LIMIT 1
    """)
    return rows[0] if rows else None


def try_acquire_asistencias_etl_lock(disparado_por, actor_usuario_id=None):
    """Ver try_acquire_alumnos_etl_lock -- misma lógica atómica, tabla separada."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pia_asistencias_etl_lock
            SET en_ejecucion=TRUE, disparado_por=%s, actor_usuario_id=%s, iniciado_en=NOW()
            WHERE id=1 AND en_ejecucion=FALSE
        """, (disparado_por, actor_usuario_id))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        log_exception("Error al intentar tomar el lock del ETL de asistencias", e)
        return False
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


def release_asistencias_etl_lock():
    execute_query("""
        UPDATE pia_asistencias_etl_lock
        SET en_ejecucion=FALSE
        WHERE id=1
    """)


def get_asistencias_etl_lock_status():
    rows = dict_fetchall("""
        SELECT en_ejecucion, disparado_por, actor_usuario_id, iniciado_en
        FROM pia_asistencias_etl_lock
        WHERE id = 1
    """)
    return rows[0] if rows else None


# ---------------- Configuración ETL de Índice de Permanencia ---------------- #
# A diferencia de alumnos/asistencias (singleton), acá hay una fila por
# periodo (ver init_db) -- pia_permanencia_etl_config.periodo es la PK.

def get_permanencia_etl_configs():
    return dict_fetchall("""
        SELECT periodo, fecha_corte, corte_generado, activo, creado_en, actualizado_en
        FROM pia_permanencia_etl_config
        ORDER BY periodo DESC
    """)


def get_permanencia_etl_config(periodo):
    rows = dict_fetchall("""
        SELECT periodo, fecha_corte, corte_generado, activo, creado_en, actualizado_en
        FROM pia_permanencia_etl_config
        WHERE periodo = %s
    """, (periodo,))
    return rows[0] if rows else None


def add_permanencia_etl_config(periodo, fecha_corte, activo=True):
    execute_query("""
        INSERT INTO pia_permanencia_etl_config (periodo, fecha_corte, corte_generado, activo)
        VALUES (%s, %s, FALSE, %s)
    """, (periodo, fecha_corte, activo))


def update_permanencia_etl_config(periodo, fecha_corte, activo):
    """No toca corte_generado -- eso solo lo cambia marcar_permanencia_corte_generado
    (cuando el ETL efectivamente congela el snapshot) o un reset manual explícito."""
    execute_query("""
        UPDATE pia_permanencia_etl_config
        SET fecha_corte=%s, activo=%s
        WHERE periodo=%s
    """, (fecha_corte, activo, periodo))


def resetear_permanencia_corte_generado(periodo):
    """Vuelve a permitir que el ETL congele el snapshot de corte de este
    periodo (por si se configuró mal la fecha y hay que rehacerlo)."""
    execute_query("""
        UPDATE pia_permanencia_etl_config
        SET corte_generado=FALSE
        WHERE periodo=%s
    """, (periodo,))


def marcar_permanencia_corte_generado(periodo):
    execute_query("""
        UPDATE pia_permanencia_etl_config
        SET corte_generado=TRUE
        WHERE periodo=%s
    """, (periodo,))


def delete_permanencia_etl_config(periodo):
    execute_query("DELETE FROM pia_permanencia_etl_config WHERE periodo = %s", (periodo,))


def registrar_permanencia_etl_run(periodo, disparado_por, status, iniciado_en, finalizado_en,
                                   filas=None, corte_generado_en_este_run=False,
                                   mensaje_error=None, actor_usuario_id=None):
    execute_query("""
        INSERT INTO pia_permanencia_etl_run
            (periodo, disparado_por, actor_usuario_id, iniciado_en, finalizado_en,
             status, filas, corte_generado_en_este_run, mensaje_error)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (periodo, disparado_por, actor_usuario_id, iniciado_en, finalizado_en,
          status, filas, corte_generado_en_este_run, mensaje_error))


def get_ultimo_permanencia_etl_run(periodo):
    rows = dict_fetchall("""
        SELECT disparado_por, iniciado_en, finalizado_en, status, filas,
               corte_generado_en_este_run, mensaje_error
        FROM pia_permanencia_etl_run
        WHERE periodo = %s
        ORDER BY id DESC
        LIMIT 1
    """, (periodo,))
    return rows[0] if rows else None


def try_acquire_permanencia_etl_lock(disparado_por, periodo, actor_usuario_id=None):
    """Ver try_acquire_alumnos_etl_lock -- misma lógica atómica, tabla
    separada, y es GLOBAL entre periodos (solo un periodo a la vez)."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pia_permanencia_etl_lock
            SET en_ejecucion=TRUE, disparado_por=%s, actor_usuario_id=%s, periodo=%s, iniciado_en=NOW()
            WHERE id=1 AND en_ejecucion=FALSE
        """, (disparado_por, actor_usuario_id, periodo))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        log_exception("Error al intentar tomar el lock del ETL de permanencia", e)
        return False
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


def release_permanencia_etl_lock():
    execute_query("""
        UPDATE pia_permanencia_etl_lock
        SET en_ejecucion=FALSE
        WHERE id=1
    """)


def get_permanencia_etl_lock_status():
    rows = dict_fetchall("""
        SELECT en_ejecucion, disparado_por, actor_usuario_id, periodo, iniciado_en
        FROM pia_permanencia_etl_lock
        WHERE id = 1
    """)
    return rows[0] if rows else None


# ---------------- Metadatos de Egresados (egressados.xlsx) ---------------- #

def get_egresados_meta():
    rows = dict_fetchall("""
        SELECT fecha_envio, filas, actualizado_por, actualizado_en
        FROM pia_egresados_meta
        WHERE id = 1
    """)
    return rows[0] if rows else None


def update_egresados_meta(fecha_envio, filas, actor_usuario_id=None):
    execute_query("""
        INSERT INTO pia_egresados_meta (id, fecha_envio, filas, actualizado_por)
        VALUES (1, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            fecha_envio=VALUES(fecha_envio),
            filas=VALUES(filas),
            actualizado_por=VALUES(actualizado_por)
    """, (fecha_envio, filas, actor_usuario_id))
