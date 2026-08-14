"""
services/etl/asistencias_etl.py

Funciones puras de extracción/agregación del ETL de asistencias
(coord_aula/SysEduca + attendance/Biometría -> asistencia_unificada_v1/v2).
Sin código ejecutable a nivel de módulo -- seguro importar desde el admin
module o el cron runner (services/etl/asistencias_runner.py) sin disparar
consultas.

Dos fuentes, según el periodo (confirmado por el usuario):
  - SysEduca (MySQL, MYSQL_HOST_SYS): asistencias ANTES de 2025.2. La tabla
    ucp.coord_aula guarda un blob JSON (`presenca`) por aula/día con el
    estado de cada alumno -- hay que parsearlo fila por fila.
  - Biometría (Postgres, PG_HOST, esquema "attendance"): asistencias DESDE
    2025.2. Cada fila ya es un evento de presencia individual (la query
    filtra asistencia=1 -- Presente -- directamente en SQL).

Ninguna de las dos fuentes necesita VPN (confirmado: ambos hosts son
alcanzables directo, igual que MYSQL_HOST_SYS en el ETL de alumnos).

Para uso manual/notebook, ver scripts/etl_asistencias.py.

Patrón v1/v2 (igual a alumnos): los datos crudos (detalle por alumno) se
extraen UNA sola vez; v1 (todos los alumnos) y v2 (solo activos, según los
ids subidos en la pantalla de admin "Alumnos Activos" -- ver
services/etl/activos_ids.py) se calculan ambos a partir de esa misma
extracción, sin repetir las consultas a las fuentes.
"""

import json
import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from mysql.connector import Error
import mysql.connector
from sqlalchemy import create_engine

from services.etl.alumnos_etl import MAPA_DISCIPLINAS
from services.etl.encuestas_etl import derivar_parametros_periodo
from utils.system_logging import get_logger

load_dotenv()

log = get_logger()


# ─────────────────────────────────────────────
# CONEXIONES
# ─────────────────────────────────────────────

def _obtener_conexion_mysql():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST_SYS"),
        user=os.getenv("MYSQL_USER_SYS"),
        password=os.getenv("MYSQL_PASSWORD_SYS"),
        database=os.getenv("MYSQL_DB_SYS"),
        port=os.getenv("MYSQL_PORT_SYS", "3306"),
        connection_timeout=300,
    )


def _obtener_engine_pg():
    return create_engine(
        f"postgresql+psycopg2://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}"
        f"@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_DB')}"
    )


# ─────────────────────────────────────────────
# FETCH -- SYSEDUCA (por año)
# ─────────────────────────────────────────────

QUERY_ASISTENCIAS_SYSEDUCA_ANO = """
SELECT
    oferta_disciplina_id,
    id AS aula_id,
    data,
    presenca
FROM ucp.coord_aula
WHERE YEAR(data) = %s
  AND config_filial_id IN (1, 3)
  AND status = 1
"""

QUERY_MATRICULADOS = """
SELECT  m.oferta_disciplina_id,
        p.ano_id,
        a.nome AS ano,
        p.periodo_anual_id,
        p3.descricao AS periodo_anual,
        o.disciplinas_id,
        d.nome AS disciplina,
        o.semestre_id AS id_semestre_disciplina,
        s2.descricao AS semestre_disciplina,
        o.turma_id,
        t.nome AS turma,
        o.funcionario_id,
        CONCAT(f.nome, ' ', f.sobrenome) AS docente,
        o.sala_id,
        s.nome AS sala,
        s.p_local_id,
        p2.nome AS local,
        m2.usuarios_id
FROM ucp.matricula_disciplina m
JOIN ucp.periodo_letivo p      ON m.periodo_letivo_id = p.id
JOIN ucp.matricula_curso m2    ON p.matricula_curso_id = m2.id
JOIN ucp.oferta_disciplina o   ON m.oferta_disciplina_id = o.id
JOIN ucp.funcionario f         ON o.funcionario_id = f.id
JOIN ucp.disciplinas d         ON o.disciplinas_id = d.id
JOIN ucp.turma t               ON o.turma_id = t.id
JOIN ucp.ano a                 ON p.ano_id = a.id
JOIN ucp.periodo_anual p3      ON p.periodo_anual_id = p3.id
JOIN ucp.semestre s2           ON o.semestre_id = s2.id
LEFT JOIN ucp.sala s           ON o.sala_id = s.id
LEFT JOIN ucp.p_local p2       ON s.p_local_id = p2.id
WHERE m.status = 1
  AND p.status = 1
  AND o.status = 1
"""


def fetch_asistencias_syseduca_ano(ano):
    """PASO 1a (SysEduca, MySQL): trae las filas crudas de coord_aula (con el
    JSON de presencia sin parsear) para un único año."""
    conn = _obtener_conexion_mysql()
    try:
        return pd.read_sql(QUERY_ASISTENCIAS_SYSEDUCA_ANO, conn, params=(ano,))
    finally:
        conn.close()


def fetch_matriculados():
    """Metadata de oferta + matrícula (MySQL) -- compartida entre SysEduca y
    Biometría, sin filtro de periodo (igual que hacía el script original en
    ambos bloques)."""
    conn = _obtener_conexion_mysql()
    try:
        return pd.read_sql(QUERY_MATRICULADOS, conn)
    finally:
        conn.close()


def procesar_anos_syseduca(anos, on_progress=None, cancel_check=None, indice_inicial=0, total=None):
    """Ejecuta fetch_asistencias_syseduca_ano() para cada año en `anos`.
    on_progress(indice, total, etiqueta) e indice_inicial/total permiten que
    el runner combine el conteo de progreso con la fase de Biometría (un solo
    contador continuo para las dos fases). Devuelve (df_crudo, anos_con_error,
    cancelado); df_crudo puede ser un DataFrame vacío si ningún año trajo
    filas (no es un error -- simplemente no hubo clases ese año)."""
    total = total if total is not None else len(anos)
    lista = []
    errores = []
    cancelado = False

    for offset, ano in enumerate(anos, start=1):
        if cancel_check is not None and cancel_check():
            cancelado = True
            break
        if on_progress is not None:
            on_progress(indice_inicial + offset, total, f"SysEduca {ano}")
        try:
            df = fetch_asistencias_syseduca_ano(ano)
        except Exception as exc:
            log.warning("Fallo la consulta SysEduca para año %s: %s", ano, exc)
            errores.append(ano)
            continue
        if not df.empty:
            lista.append(df)

    df_crudo = pd.concat(lista, ignore_index=True) if lista else pd.DataFrame(
        columns=["oferta_disciplina_id", "aula_id", "data", "presenca"]
    )
    return df_crudo, errores, cancelado


def parsear_detalle_syseduca(df_crudo):
    """Aplana el JSON de `presenca` (1 fila por aula/día) en una tabla larga:
    1 fila por (clase_id, oferta_disciplina_id, fecha, usuarios_id, presente).
    Se hace UNA sola vez -- el resultado se reutiliza tanto para v1 (todos)
    como para v2 (solo activos), sin volver a parsear el JSON."""
    registros = []
    for _, row in df_crudo.iterrows():
        try:
            data_json = json.loads(row["presenca"])[0]
        except Exception:
            continue
        oferta_id = int(row["oferta_disciplina_id"])
        clase_id = row["aula_id"]
        fecha = row["data"]
        for u_id, status in data_json.items():
            if u_id in ("aula_id", "oferta_disciplina_id"):
                continue
            try:
                usuarios_id = int(u_id)
            except (TypeError, ValueError):
                continue
            registros.append({
                "clase_id": clase_id,
                "oferta_disciplina_id": oferta_id,
                "fecha": fecha,
                "usuarios_id": usuarios_id,
                "presente": status == "P",
            })
    return pd.DataFrame(registros, columns=["clase_id", "oferta_disciplina_id", "fecha", "usuarios_id", "presente"])


COLUMNAS_SYSEDUCA_FINALES = [
    "fecha", "clase_id", "oferta_disciplina_id", "ano_id", "anho",
    "periodo_anual_id", "periodo_anual", "id_semestre_asignatura",
    "semestre_asignatura", "disciplinas_id", "asignatura", "turma_id",
    "seccion", "funcionario_id", "docente", "sala_id", "aula",
    "p_local_id", "sede", "matriculados", "presentes",
    "porc_presencia", "ausentes", "tipo_clase",
]


def _info_oferta(df_matriculados):
    return df_matriculados.drop_duplicates("oferta_disciplina_id").rename(columns={
        "ano": "anho",
        "id_semestre_disciplina": "id_semestre_asignatura",
        "semestre_disciplina": "semestre_asignatura",
        "disciplina": "asignatura",
        "turma": "seccion",
        "sala": "aula",
        "local": "sede",
    })


def _matriculados_pool(df_matriculados, ids_activos):
    if ids_activos is None:
        return df_matriculados
    return df_matriculados[df_matriculados["usuarios_id"].isin(ids_activos)]


def agregar_syseduca(df_detalle, df_matriculados, ids_activos=None):
    """ids_activos=None -> todos los alumnos (v1). ids_activos=<set> -> solo
    esos alumnos (v2). Devuelve el DataFrame en el shape final de SysEduca
    (COLUMNAS_SYSEDUCA_FINALES), listo para unificar_asistencias()."""
    if df_detalle.empty:
        return pd.DataFrame(columns=COLUMNAS_SYSEDUCA_FINALES)

    df_info_oferta = _info_oferta(df_matriculados)
    pool = _matriculados_pool(df_matriculados, ids_activos)

    total_matriculados = (
        pool.groupby("oferta_disciplina_id")["usuarios_id"].nunique().reset_index(name="matriculados")
    )

    detalle_validos = df_detalle.merge(
        pool[["oferta_disciplina_id", "usuarios_id"]].drop_duplicates(),
        on=["oferta_disciplina_id", "usuarios_id"],
        how="inner",
    )
    df_contagem_presenca = (
        detalle_validos[detalle_validos["presente"]]
        .groupby(["clase_id", "oferta_disciplina_id", "fecha"])
        .size()
        .reset_index(name="presentes")
    )

    df_final = df_contagem_presenca.merge(df_info_oferta, on="oferta_disciplina_id", how="left")
    df_final = df_final.merge(total_matriculados, on="oferta_disciplina_id", how="left")

    df_final["ausentes"] = df_final["matriculados"] - df_final["presentes"]
    df_final["porc_presencia"] = (
        df_final["presentes"] / df_final["matriculados"].replace(0, np.nan) * 100
    ).round(2)
    df_final["tipo_clase"] = "Teórica"

    df_final["docente"] = df_final["docente"].str.strip().str.replace(r"\s+", " ", regex=True).str.title()
    df_final["asignatura"] = df_final["disciplinas_id"].map(MAPA_DISCIPLINAS)
    df_final["fecha"] = pd.to_datetime(df_final["fecha"]).dt.strftime("%d/%m/%Y")
    df_final = df_final.dropna(subset=["ano_id"])

    return df_final[COLUMNAS_SYSEDUCA_FINALES].copy()


# ─────────────────────────────────────────────
# FETCH -- BIOMETRÍA (por periodo, ej. "2025.2")
# ─────────────────────────────────────────────

QUERY_ASISTENCIAS_BIOMETRIA_PERIODO = """
SELECT
    paa.fecha,
    paa.attendee_id,
    a2.system_id,
    a2."name" AS alumno,
    pa.oferta,
    paa.planificacion_horario_id,
    paa.asistencia AS status_id,
    CASE
        WHEN paa.asistencia = 1  THEN 'Presente'
        WHEN paa.asistencia = 2  THEN 'Ausente'
        WHEN paa.asistencia = 3  THEN 'Ausente Justificado'
        WHEN paa.asistencia = 99 THEN 'Clase Cancelada'
        ELSE 'Desconocido'
    END AS status,
    ph.planificacion_id,
    ph.grupo_id,
    CASE
        WHEN ph.grupo_id = 4 THEN 'Teórica'
        ELSE 'Práctica'
    END AS tipo_clase,
    ph.teacher_id,
    a."name"  AS teacher,
    p.anho,
    p.semestre_id,
    p.course_id,
    c."name"  AS course,
    p.seccion_id,
    s."name"  AS seccion,
    p.subsede_id,
    s2."name" AS subsede
FROM attendance.planilla_asistencia_alumnos paa
JOIN attendance.planificacionhorario ph  ON paa.planificacion_horario_id = ph.id
JOIN attendance.planificacion p          ON ph.planificacion_id = p.id
JOIN attendance.planificacion_attendee pa
     ON p.id = pa.planificacion_id AND paa.attendee_id = pa.attendee_id
JOIN attendance.attendee a               ON ph.teacher_id = a.id
JOIN attendance.course c                 ON p.course_id = c.id
JOIN attendance.seccion s                ON p.seccion_id = s.id
JOIN attendance.subsede s2               ON p.subsede_id = s2.id
JOIN attendance.attendee a2              ON paa.attendee_id = a2.id
WHERE p.anho = %(anho)s
  AND p.semestre_id = %(semestre_id)s
  AND paa.asistencia = 1
"""


def fetch_asistencias_biometria_periodo(anho, semestre_id):
    """PASO 1b (Biometría, Postgres): trae los eventos de presencia (ya
    filtrados a asistencia=1) para un único periodo. anho/semestre_id se
    derivan de un "periodo" tipo "2025.2" vía derivar_parametros_periodo
    (mismo esquema que usa el ETL de encuestas: semestre_bio = subperiodo+1)."""
    engine = _obtener_engine_pg()
    with engine.connect() as conn:
        return pd.read_sql(QUERY_ASISTENCIAS_BIOMETRIA_PERIODO, conn, params={"anho": anho, "semestre_id": semestre_id})


def procesar_periodos_biometria(periodos, on_progress=None, cancel_check=None, indice_inicial=0, total=None):
    """Análogo a procesar_anos_syseduca, pero por periodo (ej. "2025.2").
    Devuelve (df_crudo, periodos_con_error, cancelado). df_crudo ya viene en
    shape "detalle" (1 fila = 1 evento de presencia), no necesita parseo
    extra como SysEduca."""
    total = total if total is not None else len(periodos)
    lista = []
    errores = []
    cancelado = False

    for offset, periodo in enumerate(periodos, start=1):
        if cancel_check is not None and cancel_check():
            cancelado = True
            break
        if on_progress is not None:
            on_progress(indice_inicial + offset, total, f"Biometría {periodo}")
        try:
            parametros = derivar_parametros_periodo(periodo)
            df = fetch_asistencias_biometria_periodo(parametros["anho"], parametros["semestre_bio"])
        except Exception as exc:
            log.warning("Fallo la consulta Biometría para periodo %s: %s", periodo, exc)
            errores.append(periodo)
            continue
        if not df.empty:
            lista.append(df)

    df_crudo = pd.concat(lista, ignore_index=True) if lista else pd.DataFrame(
        columns=["fecha", "system_id", "oferta", "planificacion_horario_id", "tipo_clase"]
    )
    return df_crudo, errores, cancelado


COLUMNAS_BIOMETRIA_FINALES = [
    "fecha", "planificacion_horario_id", "oferta_disciplina_id", "ano_id", "anho",
    "periodo_anual_id", "periodo_anual", "id_semestre_asignatura",
    "semestre_asignatura", "disciplinas_id", "asignatura", "turma_id",
    "seccion", "funcionario_id", "docente", "sala_id", "aula",
    "p_local_id", "sede", "matriculados", "presentes",
    "porc_presencia", "ausentes", "tipo_clase",
]


def agregar_biometria(df_detalle, df_matriculados, ids_activos=None):
    """ids_activos=None -> todos (v1, sin filtrar por system_id).
    ids_activos=<set> -> solo esos alumnos (v2, igual al script original)."""
    if df_detalle.empty:
        return pd.DataFrame(columns=COLUMNAS_BIOMETRIA_FINALES)

    df_info_oferta = _info_oferta(df_matriculados)
    pool = _matriculados_pool(df_matriculados, ids_activos)
    total_matriculados = (
        pool.groupby("oferta_disciplina_id")["usuarios_id"].nunique().reset_index(name="matriculados")
    )

    detalle = df_detalle if ids_activos is None else df_detalle[df_detalle["system_id"].isin(ids_activos)]

    df_contagem_presenca = (
        detalle.groupby(["fecha", "oferta", "planificacion_horario_id", "tipo_clase"])
        .size()
        .reset_index(name="presentes")
        .rename(columns={"oferta": "oferta_disciplina_id"})
    )

    df_final = df_contagem_presenca.merge(df_info_oferta, on="oferta_disciplina_id", how="left")
    df_final = df_final.merge(total_matriculados, on="oferta_disciplina_id", how="left")

    df_final["presentes"] = df_final["presentes"].fillna(0)
    df_final["ausentes"] = df_final["matriculados"] - df_final["presentes"]
    df_final["porc_presencia"] = (
        df_final["presentes"] / df_final["matriculados"].replace(0, np.nan) * 100
    ).round(2)

    df_final["docente"] = df_final["docente"].str.strip().str.replace(r"\s+", " ", regex=True).str.title()
    df_final["fecha"] = pd.to_datetime(df_final["fecha"]).dt.strftime("%d/%m/%Y")
    df_final = df_final.dropna(subset=["ano_id"])

    columnas_validas = [c for c in COLUMNAS_BIOMETRIA_FINALES if c in df_final.columns]
    return df_final[columnas_validas].copy()


# ─────────────────────────────────────────────
# UNIFICACIÓN (SysEduca + Biometría)
# ─────────────────────────────────────────────

COLUMNAS_UNIFICADAS_FINALES = [
    "fuente", "fecha", "clase_id", "planificacion_horario_id", "oferta_disciplina_id",
    "ano_id", "anho", "periodo_anual_id", "periodo_anual", "id_semestre_asignatura",
    "semestre_asignatura", "disciplinas_id", "asignatura", "turma_id", "seccion",
    "funcionario_id", "docente", "sala_id", "aula", "p_local_id", "sede",
    "matriculados", "presentes", "ausentes", "porc_presencia", "tipo_clase",
]


def unificar_asistencias(df_syseduca, df_biometria):
    """Junta SysEduca + Biometría, alinea columnas de ID y filtra registros
    sin turma real (matriculados <= 1) -- igual que el script original."""
    df_sys = df_syseduca.copy()
    df_sys["fuente"] = "syseduca"
    df_sys["planificacion_horario_id"] = np.nan

    df_bio = df_biometria.copy()
    df_bio["fuente"] = "biometria"
    df_bio["clase_id"] = np.nan

    df_unificado = pd.concat([df_sys, df_bio], ignore_index=True, sort=False)

    columnas_validas = [c for c in COLUMNAS_UNIFICADAS_FINALES if c in df_unificado.columns]
    df_final = df_unificado[columnas_validas].copy()

    mask_validos = df_final["matriculados"].notna() & (df_final["matriculados"] > 1)
    return df_final[mask_validos].reset_index(drop=True)
