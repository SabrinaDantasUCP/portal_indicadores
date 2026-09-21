"""
services/etl/activos_criterios_etl.py

Funciones puras de extracción/transformación del ETL de "Alumnos Activos
por Criterios": calcula automáticamente qué usuarios_id cuentan como
"activo" (equivalente al archivo usuarios_activos_ids.txt que hoy se sube a
mano en la pantalla de admin "Alumnos Activos" — ver
services/etl/activos_ids.py), reemplazando ese proceso manual.

Portado del script de referencia que trajo el usuario (algoritmo de 7
criterios de negocio ya validado en producción), RECORTADO a solo lo que
hace falta para el filtro v2 de Alumnos/Asistencias/Encuestas:

  - NO se genera la matriz periodo x semestre, ni el Excel con anomalías
    en rojo, ni el listado de "no activos" — eso era un reporte de
    diagnóstico aparte, fuera de este alcance.
  - SÍ se mantiene: los 7 criterios (asistencia, status de matrícula,
    atraso en recursado, límite de recursado, factura en mora, examen
    final), las listas de inclusión incondicional (egresados, Defensa de
    TFG, RUES), la corrección de período para los 59 alumnos convalidados
    (CELDAS_AJUSTE), y el ajuste por muestreo contra una tabla de
    referencia para los periodos 2018.2-2020.2 (donde los criterios solos
    no alcanzan por cobertura de datos incompleta de esa época).

Sin código ejecutable a nivel de módulo -- seguro importar desde el admin
module (modules/activos_config_etl.py) o el cron runner
(services/etl/activos_criterios_runner.py) sin disparar consultas.

Para uso manual/notebook, ver scripts/etl_activos_criterios.py.
"""

import json
import os
import time
import warnings

import numpy as np
import pandas as pd
import mysql.connector
from mysql.connector import Error
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from utils.system_logging import get_logger

# Silencia avisos ruidosos de pandas que no afectan el resultado (mismo
# criterio que el script de referencia): FutureWarning de fillna/astype en
# columnas object, y UserWarning de pd.read_sql con conexión mysql.connector
# directa (funciona correctamente igual, es solo informativo).
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

load_dotenv()

log = get_logger()

RANDOM_SEED = 42

# ─────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN / CONSTANTES DE NEGOCIO (portadas del script de referencia)
# ─────────────────────────────────────────────────────────────────────────

SEMESTRES_OBJETIVO = list(range(1, 13))
SEMESTRES_SIN_CRITERIO_ASISTENCIA = [11, 12]  # internato/estágio

# Periodos donde se eximen los criterios 2/3/4/6/7 para TODOS los alumnos
# (cobertura de datos incompleta de esa época) Y que además entran en el
# ajuste por muestreo forzado contra la tabla de referencia -- ver
# aplicar_ajuste_referencia().
PERIODOS_SIN_CRITERIO_ASISTENCIA = ["2018.2", "2019.1", "2019.2", "2020.1", "2020.2"]
PERIODOS_MUESTREO_FORZADO = PERIODOS_SIN_CRITERIO_ASISTENCIA

DISCIPLINAS_VIRTUALES = [
    2, 69, 136, 4, 71, 138, 9, 76, 143, 12, 79, 146,
    20, 87, 154, 24, 91, 158, 37, 104, 171, 61, 128, 195,
]

MC_STATUS_ELIMINADO = (5,)
MC_STATUS_VALIDOS_PARA_ACTIVO = (1, 2)
LIMITE_RECURSADOS = 3
NOTA_APROBACION = 60
MAX_SEMESTRES_ATRASO = 2
FILIALES = (1, 3)

MESES_ATRASO_FACTURA = 3
FACTURA_STATUS_PENDIENTE = 0

SEMESTRE_EGRESO_DEFAULT = 12
SEMESTRE_INTERNATO_DEFAULT = 12
SEMESTRE_RUES_DEFAULT = 1

# Corrección de período para 59 alumnos convalidados de otra institución:
# el SysEduca los registró con periodo_letivo de inicio en 2020.1 (cuando se
# cargaron sus datos) con semestre >= 7, pero su primer semestre real de
# actividad en CDE es 2020.2 (un período después). Se corrige SOLO el
# `periodo` de la fila exacta que cae "debajo de la diagonal" -- las demás
# filas del mismo alumno no se tocan. No modifica la base de datos, solo el
# DataFrame en memoria.
# Definidas en services.etl.alumnos_etl (no acá) para que
# generar_alumnos_v2 pueda aplicar EXACTAMENTE la misma corrección sobre
# alumnos_v2 -- si no, alumnos_v2 seguiría mostrando a estos alumnos con su
# periodo "crudo" (sin corregir) de SysEduca, inconsistente con el periodo
# en el que se los cuenta acá como activos.
from services.etl.alumnos_etl import (
    IDS_AJUSTE_PERIODO_CONVALIDADOS as IDS_AJUSTE_PERIODO,
    CELDAS_AJUSTE_CONVALIDADOS as CELDAS_AJUSTE,
)

MC_STATUS_LABELS = {1: "Activo", 2: "Finalizado", 3: "Trancado", 4: "Suspendido", 5: "Eliminado"}


# ─────────────────────────────────────────────────────────────────────────
# SQL HELPERS
# ─────────────────────────────────────────────────────────────────────────

def _periodos_where(periodos, alias_ano="a", alias_periodo="pa"):
    condiciones = []
    for periodo in periodos:
        ano, sem = periodo.split(".")
        condiciones.append(f"({alias_ano}.nome = {ano} AND {alias_periodo}.descricao = '{sem}')")
    return " OR ".join(condiciones) if condiciones else "1=0"


def _in_clause(valores):
    valores = [v for v in valores if pd.notna(v)]
    if not valores:
        return "(-1)"
    return "(" + ",".join(str(int(v)) for v in valores) + ")"


def _sql_in(valores):
    if isinstance(valores, (list, tuple, set)):
        vals = ",".join(str(v) for v in valores)
    else:
        vals = str(valores)
    return f"({vals})"


SESSION_VARS = [
    "SET SESSION sort_buffer_size    = 67108864",
    "SET SESSION join_buffer_size    = 67108864",
    "SET SESSION tmp_table_size      = 268435456",
    "SET SESSION max_heap_table_size = 268435456",
    "SET SESSION wait_timeout        = 28800",
    "SET SESSION interactive_timeout = 28800",
    "SET SESSION net_read_timeout    = 3600",
    "SET SESSION net_write_timeout   = 3600",
]


# ─────────────────────────────────────────────────────────────────────────
# CONEXIONES
# ─────────────────────────────────────────────────────────────────────────

def obtener_conexion_mysql():
    try:
        return mysql.connector.connect(
            host=os.getenv("MYSQL_HOST_SYS"),
            user=os.getenv("MYSQL_USER_SYS"),
            password=os.getenv("MYSQL_PASSWORD_SYS"),
            database=os.getenv("MYSQL_DB_SYS"),
            port=os.getenv("MYSQL_PORT_SYS", "3306"),
            connection_timeout=300,
        )
    except Error as e:
        log.error("Erro de conexão MySQL (syseduca) para activos_criterios: %s", e)
        return None


def obtener_engine_postgres():
    return create_engine(
        f"postgresql+psycopg2://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}"
        f"@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_DB')}"
    )


def asegurar_conexion(conn):
    try:
        conn.ping(reconnect=True, attempts=3, delay=5)
    except Error as e:
        log.warning("Conexão MySQL perdida (activos_criterios), reconectando: %s", e)
        raise


def aplicar_session_vars(conn):
    cursor = conn.cursor()
    for var in SESSION_VARS:
        try:
            cursor.execute(var)
        except Error:
            pass
    cursor.close()


# ─────────────────────────────────────────────────────────────────────────
# QUERIES — MYSQL
# ─────────────────────────────────────────────────────────────────────────

def query_universo_base(periodos):
    return f"""
    SELECT
        mc.usuarios_id,
        mc.id                              AS matricula_curso_id,
        mc.tipo_matricula_curso_id,
        mc.status                           AS status_matricula_curso,
        p.id                                AS periodo_letivo_id,
        a.nome                              AS ano_periodo,
        pa.descricao                        AS periodo_anual,
        CONCAT(a.nome, '.', pa.descricao)   AS periodo,
        s.descricao                         AS semestre_alumno
    FROM ucp.matricula_curso mc
    JOIN ucp.periodo_letivo p  ON p.matricula_curso_id = mc.id
    JOIN ucp.ano             a ON a.id  = p.ano_id
    JOIN ucp.periodo_anual  pa ON pa.id = p.periodo_anual_id
    JOIN ucp.semestre        s ON s.id  = p.semestre_id
    WHERE p.config_filial_id IN {_sql_in(FILIALES)}
      AND p.status = 1
      AND mc.status NOT IN {_sql_in(MC_STATUS_ELIMINADO)}
      AND s.descricao BETWEEN 1 AND 12
      AND ({_periodos_where(periodos)})
    """


def query_periodos_forzados(usuarios_ids, periodos):
    """Trae periodo_letivo/semestre para IDs forzados (egresados/TFG/RUES),
    sin aplicar ninguno de los 7 criterios -- solo exige que el alumno tenga
    al menos una matricula_disciplina activa en filiales CDE (excluye
    alumnos de PJC incluidos por error en esas listas)."""
    return f"""
    SELECT DISTINCT
        mc.usuarios_id,
        mc.status                           AS status_matricula_curso,
        p.id                                AS periodo_letivo_id,
        a.nome                              AS ano_periodo,
        pa.descricao                        AS periodo_anual,
        CONCAT(a.nome, '.', pa.descricao)   AS periodo,
        s.descricao                         AS semestre_alumno
    FROM ucp.matricula_curso mc
    JOIN ucp.periodo_letivo p  ON p.matricula_curso_id = mc.id
    JOIN ucp.ano             a ON a.id  = p.ano_id
    JOIN ucp.periodo_anual  pa ON pa.id = p.periodo_anual_id
    JOIN ucp.semestre        s ON s.id  = p.semestre_id
    WHERE p.status = 1
      AND mc.usuarios_id IN {_in_clause(usuarios_ids)}
      AND ({_periodos_where(periodos)})
      AND EXISTS (
          SELECT 1
          FROM ucp.matricula_curso mc2
          JOIN ucp.periodo_letivo p2       ON p2.matricula_curso_id = mc2.id
          JOIN ucp.matricula_disciplina md ON md.periodo_letivo_id = p2.id
          WHERE mc2.usuarios_id = mc.usuarios_id
            AND p2.config_filial_id IN {_sql_in(FILIALES)}
            AND md.status = 1
      )
    """


def query_matriculas_por_id(matricula_curso_ids):
    return f"""
    SELECT id AS matricula_curso_id, usuarios_id
    FROM ucp.matricula_curso
    WHERE id IN {_in_clause(matricula_curso_ids)}
    """


def query_materias_periodo(periodos):
    where_periodos = _periodos_where(periodos)
    return f"""
    SELECT
        mc.usuarios_id,
        p.id                         AS periodo_letivo_id,
        CONCAT(a.nome, '.', pa.descricao) AS periodo,
        s.descricao                  AS semestre_alumno,
        md.id                        AS matricula_disciplina_id,
        od.id                        AS oferta_disciplina_id,
        od.disciplinas_id,
        s2.descricao                 AS semestre_materia
    FROM ucp.matricula_curso mc
    JOIN ucp.periodo_letivo p        ON p.matricula_curso_id = mc.id
    JOIN ucp.ano             a       ON a.id  = p.ano_id
    JOIN ucp.periodo_anual  pa       ON pa.id = p.periodo_anual_id
    JOIN ucp.semestre        s       ON s.id  = p.semestre_id
    JOIN ucp.matricula_disciplina md ON md.periodo_letivo_id = p.id
    JOIN ucp.oferta_disciplina  od   ON od.id = md.oferta_disciplina_id
    JOIN ucp.semestre        s2      ON s2.id = od.semestre_id
    WHERE p.config_filial_id IN {_sql_in(FILIALES)}
      AND p.status = 1
      AND md.status = 1
      AND od.status = 1
      AND mc.status NOT IN {_sql_in(MC_STATUS_ELIMINADO)}
      AND s.descricao BETWEEN 1 AND 12
      AND ({where_periodos})
    """


def cargar_materias_periodo_por_lotes(conn, periodos, tamano_lote=1, on_progress=None, cancel_check=None):
    """Ejecuta query_materias_periodo() en lotes (1 periodo por vez por
    defecto), reconectando entre cada lote -- evita "Lost connection to
    MySQL server during query" con muchos periodos a la vez."""
    partes = []
    total_lotes = (len(periodos) - 1) // tamano_lote + 1 if periodos else 0
    for i in range(0, len(periodos), tamano_lote):
        if cancel_check is not None and cancel_check():
            break
        lote = periodos[i: i + tamano_lote]
        lote_num = i // tamano_lote + 1
        if on_progress is not None:
            on_progress(f"Materias matriculadas — periodo(s) {', '.join(lote)} ({lote_num}/{total_lotes})")
        try:
            asegurar_conexion(conn)
            df_lote = pd.read_sql(query_materias_periodo(lote), conn)
        except (Error, Exception) as e:
            log.warning("Falló el lote de materias %s (%s); reintentando tras reconectar...", lote, e)
            asegurar_conexion(conn)
            df_lote = pd.read_sql(query_materias_periodo(lote), conn)
        partes.append(df_lote)

    columnas = [
        "usuarios_id", "periodo_letivo_id", "periodo", "semestre_alumno",
        "matricula_disciplina_id", "oferta_disciplina_id", "disciplinas_id",
        "semestre_materia",
    ]
    if not partes:
        return pd.DataFrame(columns=columnas)
    return pd.concat(partes, ignore_index=True)


def query_historico_disciplinas(usuarios_ids):
    return f"""
    SELECT
        mc.usuarios_id,
        p.id                          AS periodo_letivo_id,
        a.nome                        AS ano_periodo,
        pa.descricao                  AS periodo_anual,
        s.descricao                   AS semestre_alumno,
        od.id                         AS oferta_disciplina_id,
        od.disciplinas_id,
        s2.descricao                  AS semestre_materia
    FROM ucp.matricula_curso mc
    JOIN ucp.periodo_letivo p        ON p.matricula_curso_id = mc.id
    JOIN ucp.ano             a       ON a.id  = p.ano_id
    JOIN ucp.periodo_anual  pa       ON pa.id = p.periodo_anual_id
    JOIN ucp.semestre        s       ON s.id  = p.semestre_id
    JOIN ucp.matricula_disciplina md ON md.periodo_letivo_id = p.id
    JOIN ucp.oferta_disciplina  od   ON od.id = md.oferta_disciplina_id
    JOIN ucp.semestre        s2      ON s2.id = od.semestre_id
    WHERE p.status = 1
      AND md.status = 1
      AND od.status = 1
      AND mc.status NOT IN {_sql_in(MC_STATUS_ELIMINADO)}
      AND mc.usuarios_id IN {_in_clause(usuarios_ids)}
    """


def query_notas_historicas(usuarios_ids, oferta_ids_legado):
    """Calificación final por (alumno, disciplina, periodo_letivo) +
    tiene_examen_final (criterio 7) -- misma lógica de cálculo (exámenes +
    trabajos + sistema antiguo coord_avaliacao) que ya usan
    services/etl/alumnos_etl.py y services/etl/permanencia_etl.py."""
    alumnos_clause = _in_clause(usuarios_ids)
    ofertas_clause = _in_clause(oferta_ids_legado)
    return f"""
    WITH melhor_tentativa AS (
        SELECT * FROM (
            SELECT et.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY ex_examen_id, oferta_disciplina_id, usuarios_id
                       ORDER BY nota DESC, id ASC
                   ) AS rn
            FROM ucp.ex_tentativa et
            WHERE et.status = 1
              AND et.usuarios_id IN {alumnos_clause}
        ) ranked WHERE rn = 1
    ),

    melhor_trabalho AS (
        SELECT * FROM (
            SELECT ta.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY ex_trabalhos_id, oferta_disciplina_id, usuarios_id
                       ORDER BY nota DESC, id ASC
                   ) AS rn
            FROM ucp.ex_trabalhos_aluno ta
            WHERE ta.status = 1
              AND ta.usuarios_id IN {alumnos_clause}
        ) ranked WHERE rn = 1
    ),

    max_pl_trabalho AS (
        SELECT oferta_disciplina_id, usuarios_id, MAX(periodo_letivo_id) AS periodo_letivo_id
        FROM ucp.ex_tentativa
        WHERE usuarios_id IN {alumnos_clause}
        GROUP BY oferta_disciplina_id, usuarios_id
    ),

    base_unificada AS (
        SELECT
            et.periodo_letivo_id AS id_periodo_lectivo,
            u.id                 AS id_alumno,
            d.id                 AS id_asignatura,
            te.id                AS tipo_examen_id,
            et.nota              AS puntos_logrados,
            'novo'               AS sistema
        FROM melhor_tentativa et
        JOIN ucp.ex_examen      ex  ON ex.id  = et.ex_examen_id
        JOIN ucp.ex_tipo_examen te  ON te.id  = ex.tipo_examen_id
        JOIN ucp.usuarios       u   ON u.id   = et.usuarios_id
        JOIN ucp.oferta_disciplina od ON od.id = et.oferta_disciplina_id
        JOIN ucp.disciplinas    d   ON d.id   = od.disciplinas_id

        UNION ALL

        SELECT
            mpl.periodo_letivo_id,
            u.id,
            d.id,
            999 AS tipo_examen_id,
            CAST(ta.nota AS DECIMAL(10,2)),
            'novo'
        FROM melhor_trabalho ta
        JOIN ucp.usuarios       u   ON u.id  = ta.usuarios_id
        JOIN ucp.oferta_disciplina od ON od.id = ta.oferta_disciplina_id
        JOIN ucp.disciplinas    d   ON d.id  = od.disciplinas_id
        JOIN max_pl_trabalho    mpl ON mpl.oferta_disciplina_id = od.id
                                   AND mpl.usuarios_id = u.id

        UNION ALL

        SELECT DISTINCT
            pl.id,
            u.id,
            d.id,
            CASE
                WHEN f2.nome LIKE '%Extraordinaria%'                                                     THEN 9
                WHEN (f2.nome LIKE '%Recuperat%' OR f2.nome LIKE '%Regulariza%')
                    AND (f3.nome LIKE '%1%Parcial%' OR f3.nome LIKE '%Pratico%'
                        OR (f3.nome LIKE '%Parcial%' AND f3.nome NOT LIKE '%2%'))                       THEN 3
                WHEN (f2.nome LIKE '%Recuperat%' OR f2.nome LIKE '%Regulariza%')
                    AND f3.nome LIKE '%2%Parcial%'                                                       THEN 6
                WHEN (f2.nome LIKE '%Ordinario%' OR f2.nome LIKE '%Práctica%')
                    AND f3.nome LIKE '%1%Parcial%'                                                       THEN 1
                WHEN (f2.nome LIKE '%Ordinario%' OR f2.nome LIKE '%Práctica%')
                    AND f3.nome LIKE '%Pratico%'                                                         THEN 1
                WHEN (f2.nome LIKE '%Ordinario%' OR f2.nome LIKE '%Práctica%')
                    AND f3.nome LIKE '%2%Parcial%'                                                       THEN 4
                WHEN (f2.nome LIKE '%Ordinario%' OR f2.nome LIKE '%Práctica%')
                    AND (f3.nome LIKE '%Final%' OR f3.nome LIKE '%Examen%' OR f3.nome LIKE '%Exame%')   THEN 8
                WHEN f2.nome LIKE '%Complementar%'                                                        THEN 7
                WHEN f3.nome LIKE '%Trabajo%' OR f3.nome LIKE '%Trabalho%'                               THEN 999
                WHEN f3.nome LIKE '%Extra%'                                                               THEN 15
                ELSE 1000
            END AS tipo_examen_id,
            nv.nota_val AS puntos_logrados,
            'antigo'
        FROM ucp.coord_avaliacao c
        JOIN ucp.finan_oferta       f      ON f.id   = c.finan_oferta_id
        JOIN ucp.finan_centro_custo f2     ON f2.id  = f.finan_centro_custo_id
        JOIN ucp.finan_departamento f3     ON f3.id  = f.finan_departamento_id
        JOIN ucp.oferta_disciplina  od     ON od.id  = c.oferta_disciplina_id
        JOIN ucp.disciplinas        d      ON d.id   = od.disciplinas_id
        CROSS JOIN JSON_TABLE(
            JSON_KEYS(c.notas, '$[0]'),
            '$[*]' COLUMNS (id_aluno VARCHAR(50) PATH '$')
        ) AS aluno
        JOIN LATERAL (
            SELECT CAST(
                NULLIF(TRIM(JSON_UNQUOTE(JSON_EXTRACT(c.notas, CONCAT('$[0]."', aluno.id_aluno, '"')))), '')
            AS DECIMAL(10,2)) AS nota_val
        ) nv ON nv.nota_val IS NOT NULL
        JOIN ucp.usuarios           u      ON u.id   = CAST(aluno.id_aluno AS UNSIGNED)
        LEFT JOIN (
            ucp.matricula_disciplina md
            JOIN ucp.periodo_letivo  pl    ON pl.id  = md.periodo_letivo_id
            JOIN ucp.matricula_curso mc    ON mc.id  = pl.matricula_curso_id
        ) ON md.oferta_disciplina_id = od.id AND mc.usuarios_id = u.id
        WHERE c.status = 1
          AND od.id IN {ofertas_clause}
          AND u.id IN {alumnos_clause}
          AND COALESCE(c.descricao, '') NOT IN (
              'CANCELADO','NO','DESCONSIDERAR','PRUEBA SISTEMA VAMOS ELIMINAR',
              'Examen duplicado','DUPLICADO','PRUEBA SISTEMA','teste'
          )
    ),

    base_com_maximos AS (
        SELECT
            b.*,
            MAX(CASE
                WHEN (sistema = 'antigo' AND tipo_examen_id = 1)
                  OR (sistema = 'novo'   AND tipo_examen_id = 2)
                THEN puntos_logrados ELSE 0 END)
                OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS max_p1_ord,
            MAX(CASE
                WHEN (sistema = 'antigo' AND tipo_examen_id = 4)
                  OR (sistema = 'novo'   AND tipo_examen_id = 5)
                THEN puntos_logrados ELSE 0 END)
                OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS max_p2_ord,
            MAX(CASE WHEN tipo_examen_id = 3  THEN puntos_logrados ELSE 0 END)
                OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS max_p1_recup,
            MAX(CASE WHEN tipo_examen_id = 6  THEN puntos_logrados ELSE 0 END)
                OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS max_p2_recup,
            MAX(CASE WHEN tipo_examen_id = 8  THEN puntos_logrados ELSE 0 END)
                OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS max_final_ord,
            MAX(CASE WHEN tipo_examen_id = 7  THEN puntos_logrados ELSE 0 END)
                OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS max_complementar,
            MAX(CASE WHEN tipo_examen_id = 9  THEN puntos_logrados ELSE 0 END)
                OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS nota_extraordinaria,
            MAX(CASE WHEN tipo_examen_id IN (7, 8, 9) THEN 1 ELSE 0 END)
                OVER(PARTITION BY id_alumno, id_periodo_lectivo) AS tiene_examen_final
        FROM base_unificada b
    )

    SELECT
        id_alumno            AS usuarios_id,
        id_periodo_lectivo AS periodo_letivo_id,
        id_asignatura       AS disciplinas_id,
        MAX(CASE
            WHEN nota_extraordinaria > 0 THEN nota_extraordinaria
            ELSE nota_acumulada_final
        END) AS calificacion_final,
        MAX(tiene_examen_final) AS tiene_examen_final
    FROM (
        SELECT
            bm.id_alumno, bm.id_asignatura, bm.id_periodo_lectivo, bm.nota_extraordinaria,
            bm.tiene_examen_final,
            SUM(CASE
                WHEN sistema = 'antigo' AND tipo_examen_id = 1 AND max_p1_recup > puntos_logrados  THEN 0
                WHEN sistema = 'novo'   AND tipo_examen_id = 2 AND max_p1_recup > puntos_logrados  THEN 0
                WHEN sistema = 'antigo' AND tipo_examen_id = 4 AND max_p2_recup > puntos_logrados  THEN 0
                WHEN sistema = 'novo'   AND tipo_examen_id = 5 AND max_p2_recup > puntos_logrados  THEN 0
                WHEN tipo_examen_id = 8 AND max_complementar > puntos_logrados                     THEN 0
                WHEN tipo_examen_id = 7 AND max_final_ord >= puntos_logrados                       THEN 0
                WHEN tipo_examen_id = 3 AND max_p1_ord >= puntos_logrados                          THEN 0
                WHEN tipo_examen_id = 6 AND max_p2_ord >= puntos_logrados                          THEN 0
                WHEN tipo_examen_id = 9                                                            THEN 0
                ELSE puntos_logrados
            END) OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS nota_acumulada_final
        FROM base_com_maximos bm
    ) AS calculo_final
    GROUP BY id_alumno, id_periodo_lectivo, id_asignatura
    """


def query_facturas(usuarios_ids):
    return f"""
    SELECT usuarios_id, periodo_letivo_id, data_vencimento, status
    FROM ucp.faturas
    WHERE usuarios_id IN {_in_clause(usuarios_ids)}
      AND periodo_letivo_id IS NOT NULL
      AND data_vencimento IS NOT NULL
    """


def query_asistencia_syseduca(oferta_ids):
    return f"""
    SELECT oferta_disciplina_id, id AS aula_id, presenca
    FROM ucp.coord_aula
    WHERE config_filial_id IN {_sql_in(FILIALES)}
      AND status = 1
      AND oferta_disciplina_id IN {_in_clause(oferta_ids)}
    """


def query_asistencia_biometria(oferta_ids):
    return text(f"""
        SELECT
            a2.system_id                AS usuarios_id,
            pa.oferta                   AS oferta_disciplina_id
        FROM attendance.planilla_asistencia_alumnos paa
        JOIN attendance.planificacionhorario ph  ON paa.planificacion_horario_id = ph.id
        JOIN attendance.planificacion p          ON ph.planificacion_id = p.id
        JOIN attendance.planificacion_attendee pa
             ON p.id = pa.planificacion_id AND paa.attendee_id = pa.attendee_id
        JOIN attendance.attendee a2              ON paa.attendee_id = a2.id
        WHERE paa.asistencia = 1
          AND pa.oferta IN {_in_clause(oferta_ids)}
    """)


# ─────────────────────────────────────────────────────────────────────────
# CARGA DE LISTAS FORZADAS (egresados / TFG / RUES)
# ─────────────────────────────────────────────────────────────────────────

def cargar_egresados_forzados(path):
    """Reaproveita el mismo egressados.xlsx que ya usa
    services/etl/alumnos_runner.py (EGRESADOS_XLSX_PATH), con el schema
    normalizado por services.etl.alumnos_etl.normalizar_egresados_columnas
    (acepta tanto "usuarios_id" como el alias "IDs_Solo" que manda
    Secretaría en las planillas más nuevas). Devuelve columnas
    [usuarios_id, periodo]."""
    from services.etl.alumnos_etl import normalizar_egresados_columnas

    columnas = ["usuarios_id", "periodo"]
    if not path or not os.path.exists(path):
        log.warning("No se encontró egressados.xlsx (%s): se omite el forzado de egresados.", path)
        return pd.DataFrame(columns=columnas)

    df = pd.read_excel(path)
    df = normalizar_egresados_columnas(df)
    requeridas = ("usuarios_id", "Año de Egreso", "Periodo de Egreso")
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        log.warning("egressados.xlsx no tiene las columnas esperadas para activos_criterios (faltan: %s)", faltantes)
        return pd.DataFrame(columns=columnas)

    df = df.dropna(subset=["usuarios_id"]).copy()
    df["usuarios_id"] = pd.to_numeric(df["usuarios_id"], errors="coerce")
    df = df.dropna(subset=["usuarios_id"])
    df["usuarios_id"] = df["usuarios_id"].astype(int)
    df["periodo"] = (
        pd.to_numeric(df["Año de Egreso"], errors="coerce").astype("Int64").astype(str)
        + "." + pd.to_numeric(df["Periodo de Egreso"], errors="coerce").astype("Int64").astype(str)
    )
    return df[columnas].drop_duplicates(subset="usuarios_id")


def _parse_semestre_tfg(valor):
    import re
    m = re.match(r"(\d+)", str(valor).strip())
    return int(m.group(1)) if m else SEMESTRE_INTERNATO_DEFAULT


def cargar_tfg_defensa(path):
    """Devuelve columnas [usuarios_id, periodo, semestre_tfg]. Formato
    esperado: hoja "Todos los Egresados", columnas IDs_Solo, "Convocatoria
    al cual pertenece" (ej. "2022/2"), Semestre_BD (ej. "12° Semestre")."""
    columnas = ["usuarios_id", "periodo", "semestre_tfg"]
    if not path or not os.path.exists(path):
        return pd.DataFrame(columns=columnas)

    try:
        df = pd.read_excel(path, sheet_name="Todos los Egresados")
    except Exception:
        df = pd.read_excel(path)

    requeridas = ("IDs_Solo", "Convocatoria al cual pertenece", "Semestre_BD")
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        log.warning("TFG.xlsx no tiene las columnas esperadas (faltan: %s)", faltantes)
        return pd.DataFrame(columns=columnas)

    df = df.rename(columns={"IDs_Solo": "usuarios_id"})
    df = df.dropna(subset=["usuarios_id"]).copy()
    df["usuarios_id"] = pd.to_numeric(df["usuarios_id"], errors="coerce")
    df = df.dropna(subset=["usuarios_id"])
    df["usuarios_id"] = df["usuarios_id"].astype(int)
    df["periodo"] = df["Convocatoria al cual pertenece"].astype(str).str.replace("/", ".", regex=False)
    df["semestre_tfg"] = df["Semestre_BD"].apply(_parse_semestre_tfg)
    return df[columnas].drop_duplicates(subset="usuarios_id")


def cargar_rues(path):
    """Devuelve columnas [matricula_curso_id, periodo] -- el usuarios_id se
    resuelve aparte con query_matriculas_por_id, porque el archivo trae
    CRM_INSCRIPCION_ID (= ucp.matricula_curso.id), no usuarios_id
    directo."""
    columnas = ["matricula_curso_id", "periodo"]
    if not path or not os.path.exists(path):
        return pd.DataFrame(columns=columnas)

    try:
        df = pd.read_excel(path, sheet_name="Hoja1")
    except Exception:
        df = pd.read_excel(path)

    requeridas = ("CRM_INSCRIPCION_ID", "CABECERA_PERIODO_ACADEMICO", "DETALLE_FECHA_MATRICULACION")
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        log.warning("RUES.xlsx no tiene las columnas esperadas (faltan: %s)", faltantes)
        return pd.DataFrame(columns=columnas)

    df = df.copy()
    df["DETALLE_FECHA_MATRICULACION"] = pd.to_datetime(df["DETALLE_FECHA_MATRICULACION"], errors="coerce")
    df = df.sort_values("DETALLE_FECHA_MATRICULACION").drop_duplicates(
        subset="CRM_INSCRIPCION_ID", keep="first"
    )
    ano = pd.to_numeric(df["CABECERA_PERIODO_ACADEMICO"], errors="coerce")
    mes = df["DETALLE_FECHA_MATRICULACION"].dt.month
    periodo_anual = mes.apply(lambda m: 1 if pd.notna(m) and m <= 6 else 2)
    df["periodo"] = ano.astype("Int64").astype(str) + "." + periodo_anual.astype(str)
    df = df.rename(columns={"CRM_INSCRIPCION_ID": "matricula_curso_id"})
    return df[columnas].drop_duplicates(subset="matricula_curso_id")


# ─────────────────────────────────────────────────────────────────────────
# EVALUACIÓN DE CRITERIOS (pandas)
# ─────────────────────────────────────────────────────────────────────────

def calcular_periodo_rank(ano, periodo_anual):
    return pd.to_numeric(ano, errors="coerce") * 2 + (pd.to_numeric(periodo_anual, errors="coerce") - 1)


def evaluar_recursado(historico_df, notas_df):
    df = historico_df.merge(
        notas_df, on=["usuarios_id", "disciplinas_id", "periodo_letivo_id"], how="left"
    )
    df["calificacion_final"] = pd.to_numeric(df["calificacion_final"], errors="coerce")
    df["periodo_rank"] = calcular_periodo_rank(df["ano_periodo"], df["periodo_anual"])
    df["reprobo"] = df["calificacion_final"].fillna(0) < NOTA_APROBACION

    df = df.sort_values(["usuarios_id", "disciplinas_id", "periodo_rank"])
    df["reprobaciones_acumuladas"] = (
        df.groupby(["usuarios_id", "disciplinas_id"])["reprobo"].cumsum().astype(int)
    )
    df["veces_recursada_antes"] = df["reprobaciones_acumuladas"] - df["reprobo"].astype(int)
    df["es_recursante"] = df["veces_recursada_antes"] > 0
    df["excede_limite_recursado"] = df["veces_recursada_antes"] >= LIMITE_RECURSADOS

    return df[[
        "usuarios_id", "disciplinas_id", "periodo_letivo_id", "semestre_alumno",
        "semestre_materia", "es_recursante", "excede_limite_recursado",
    ]]


def evaluar_atraso_materia(recursado_df):
    df = recursado_df.copy()
    df["semestre_alumno_num"] = pd.to_numeric(df["semestre_alumno"], errors="coerce")
    df["semestre_materia_num"] = pd.to_numeric(df["semestre_materia"], errors="coerce")
    df["atraso"] = df["semestre_alumno_num"] - df["semestre_materia_num"]
    df["viola_criterio_3"] = df["es_recursante"] & (df["atraso"] > MAX_SEMESTRES_ATRASO)
    df["viola_criterio_5"] = df["excede_limite_recursado"]
    return df


def evaluar_examen_final(notas_df, universo_base_df):
    tiene_examen = (
        notas_df.groupby(["usuarios_id", "periodo_letivo_id"])["tiene_examen_final"].max().reset_index()
    )
    base = universo_base_df[["usuarios_id", "periodo_letivo_id", "semestre_alumno"]].drop_duplicates()
    eval_df = base.merge(tiene_examen, on=["usuarios_id", "periodo_letivo_id"], how="left")
    eval_df["tiene_examen_final"] = eval_df["tiene_examen_final"].fillna(0)

    semestre_num = pd.to_numeric(eval_df["semestre_alumno"], errors="coerce")
    exento = semestre_num.isin(SEMESTRES_SIN_CRITERIO_ASISTENCIA)
    eval_df["viola_criterio_7"] = (eval_df["tiene_examen_final"] == 0) & ~exento
    return eval_df[["usuarios_id", "periodo_letivo_id", "viola_criterio_7"]]


def evaluar_facturas(facturas_df, universo_base_df):
    facturas_df = facturas_df.copy()
    facturas_df["data_vencimento"] = pd.to_datetime(facturas_df["data_vencimento"], errors="coerce")

    referencia = (
        facturas_df.groupby(["usuarios_id", "periodo_letivo_id"])["data_vencimento"]
        .max().reset_index().rename(columns={"data_vencimento": "referencia"})
    )
    pendientes = facturas_df[facturas_df["status"] == FACTURA_STATUS_PENDIENTE]
    oldest_pendiente = (
        pendientes.groupby("usuarios_id")["data_vencimento"]
        .min().reset_index().rename(columns={"data_vencimento": "pendiente_mas_antigua"})
    )

    base = universo_base_df[["usuarios_id", "periodo_letivo_id"]].drop_duplicates()
    eval_df = base.merge(referencia, on=["usuarios_id", "periodo_letivo_id"], how="left")
    eval_df = eval_df.merge(oldest_pendiente, on="usuarios_id", how="left")

    umbral = eval_df["referencia"] - pd.DateOffset(months=MESES_ATRASO_FACTURA)
    eval_df["viola_criterio_6"] = (
        eval_df["referencia"].notna()
        & eval_df["pendiente_mas_antigua"].notna()
        & (eval_df["pendiente_mas_antigua"] < umbral)
    )
    return eval_df[["usuarios_id", "periodo_letivo_id", "viola_criterio_6"]]


def _extraer_dict_presencia(raw_json):
    """Parsing defensivo del JSON de ucp.coord_aula.presenca -- ver
    docstring original en el script de referencia: normalmente es una lista
    con un único dict adentro, pero en periodos viejos puede venir como
    dict directo, lista anidada, o lista de varios dicts."""
    try:
        parsed = json.loads(raw_json)
    except Exception:
        return None

    if isinstance(parsed, dict):
        return parsed

    if isinstance(parsed, list):
        if len(parsed) == 0:
            return None
        primero = parsed[0]
        if isinstance(primero, dict):
            return primero
        if isinstance(primero, list):
            if len(primero) > 0 and isinstance(primero[0], dict):
                return primero[0]
            return None
        if all(isinstance(x, dict) for x in parsed):
            combinado = {}
            for x in parsed:
                combinado.update(x)
            return combinado
        return None

    return None


# ─────────────────────────────────────────────────────────────────────────
# AJUSTE POR MUESTREO CONTRA TABLA DE REFERENCIA (2018.2-2020.2)
# ─────────────────────────────────────────────────────────────────────────

def _muestrear_celda_con_prioridad(ids_presentes, cantidad_esperada, ids_egresados, ids_tfg_rues, seed):
    """Prioridad: egresados nunca se descartan; TFG/RUES se descartan si
    sobra cupo; alumnos no forzados son los primeros en salir."""
    serie = pd.Series(list(ids_presentes))
    if len(serie) <= cantidad_esperada:
        return set(serie)

    eg = serie[serie.isin(ids_egresados)]
    tr = serie[serie.isin(ids_tfg_rues) & ~serie.isin(ids_egresados)]
    nf = serie[~serie.isin(ids_egresados) & ~serie.isin(ids_tfg_rues)]

    seleccion = set(eg)
    cupo = max(0, cantidad_esperada - len(eg))
    tr_sel = tr.sample(min(cupo, len(tr)), random_state=seed) if len(tr) else tr
    seleccion |= set(tr_sel)
    cupo2 = max(0, cupo - len(tr_sel))
    nf_sel = nf.sample(min(cupo2, len(nf)), random_state=seed) if len(nf) else nf
    seleccion |= set(nf_sel)
    return seleccion


def aplicar_ajuste_referencia(activos_df, referencia, ids_egresados, ids_tfg, ids_rues):
    """Aplica el ajuste por muestreo (solo periodos en
    PERIODOS_MUESTREO_FORZADO) y el diagnóstico de validación (el resto de
    periodos presentes en `referencia`, sin descartar a nadie) contra la
    tabla de referencia periodo x semestre. Devuelve
    (activos_df_ajustado, diagnostico: list[dict])."""
    if activos_df.empty or not referencia:
        return activos_df, []

    ids_tfg_rues = set(ids_tfg) | set(ids_rues)
    df = activos_df.copy()
    df["semestre_alumno"] = pd.to_numeric(df["semestre_alumno"], errors="coerce")

    diagnostico = []
    filas_a_quitar = set()

    for (periodo, semestre), cantidad_esperada in sorted(referencia.items()):
        celda = df[(df["periodo"] == periodo) & (df["semestre_alumno"] == semestre)]
        if celda.empty:
            continue
        cantidad_actual = celda["usuarios_id"].nunique()

        if periodo not in PERIODOS_MUESTREO_FORZADO:
            diagnostico.append({
                "periodo": periodo, "semestre": semestre, "tipo": "validacion",
                "cantidad_actual": cantidad_actual, "cantidad_esperada": cantidad_esperada,
                "delta": cantidad_actual - cantidad_esperada,
            })
            continue

        if cantidad_actual <= cantidad_esperada:
            if cantidad_actual < cantidad_esperada:
                diagnostico.append({
                    "periodo": periodo, "semestre": semestre, "tipo": "shortfall",
                    "cantidad_actual": cantidad_actual, "cantidad_esperada": cantidad_esperada,
                    "delta": cantidad_actual - cantidad_esperada,
                })
            continue

        ids_mantener = _muestrear_celda_con_prioridad(
            celda["usuarios_id"].unique(), cantidad_esperada, ids_egresados, ids_tfg_rues, RANDOM_SEED
        )
        idx_a_quitar = celda[~celda["usuarios_id"].isin(ids_mantener)].index
        filas_a_quitar.update(idx_a_quitar)
        diagnostico.append({
            "periodo": periodo, "semestre": semestre, "tipo": "muestreo_aplicado",
            "cantidad_actual": cantidad_actual, "cantidad_esperada": cantidad_esperada,
            "delta": 0,
        })

    # Celdas "implícitas" en cero: la tabla de referencia solo guarda pares
    # (periodo, semestre) con cantidad_esperada > 0 (ver seed en
    # utils/db_pia.init_db) -- cualquier semestre de un periodo forzado que
    # NO aparece como key en `referencia` se interpreta como
    # cantidad_esperada = 0 (nadie debería figurar ahí). Sin este bloque,
    # esas celdas quedaban totalmente fuera del ajuste y cualquier alumno
    # que la extracción cruda pusiera ahí (por ejemplo, por datos
    # incompletos de la época) se colaba sin control.
    periodos_forzados_presentes = df.loc[df["periodo"].isin(PERIODOS_MUESTREO_FORZADO), "periodo"].unique()
    for periodo in periodos_forzados_presentes:
        semestres_con_datos = df.loc[df["periodo"] == periodo, "semestre_alumno"].dropna().unique()
        for semestre in semestres_con_datos:
            semestre = int(semestre)
            if (periodo, semestre) in referencia:
                continue  # ya procesado arriba
            celda = df[(df["periodo"] == periodo) & (df["semestre_alumno"] == semestre)]
            cantidad_actual = celda["usuarios_id"].nunique()
            if cantidad_actual == 0:
                continue
            ids_mantener = _muestrear_celda_con_prioridad(
                celda["usuarios_id"].unique(), 0, ids_egresados, ids_tfg_rues, RANDOM_SEED
            )
            idx_a_quitar = celda[~celda["usuarios_id"].isin(ids_mantener)].index
            filas_a_quitar.update(idx_a_quitar)
            diagnostico.append({
                "periodo": periodo, "semestre": semestre, "tipo": "muestreo_aplicado_cero_implicito",
                "cantidad_actual": cantidad_actual, "cantidad_esperada": 0,
                "delta": 0,
            })

    if filas_a_quitar:
        df = df.drop(index=list(filas_a_quitar))

    return df, diagnostico


# ─────────────────────────────────────────────────────────────────────────
# ORQUESTACIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────

def _corregir_cde3_a_cde(df, campo_semestre="semestre_alumno"):
    """Alumnos con múltiples registros en el mismo (usuarios_id, periodo)
    con periodo_letivo_id distintos (filiales CDE III cerrada / CDE):
    conserva el semestre MÍNIMO por (alumno, periodo) como el real."""
    df = df.copy()
    df["_sem_tmp"] = pd.to_numeric(df[campo_semestre], errors="coerce")
    tiene_multi = df.groupby(["usuarios_id", "periodo"])["_sem_tmp"].transform("nunique") > 1
    if tiene_multi.any():
        sem_min = df.groupby(["usuarios_id", "periodo"])["_sem_tmp"].transform("min")
        df["_sem_tmp"] = df["_sem_tmp"].where(~tiene_multi, other=sem_min)
        df = df.sort_values("_sem_tmp").drop_duplicates(subset=["usuarios_id", "periodo"], keep="first")
        df[campo_semestre] = df["_sem_tmp"].astype(str)
    return df.drop(columns=["_sem_tmp"], errors="ignore")


def calcular_ids_activos(periodos, egresados_path=None, tfg_path=None, rues_path=None,
                          referencia=None, on_progress=None, cancel_check=None):
    """Ejecuta el pipeline completo y devuelve:
    {
        "ids_activos": set[int],
        "total_universo": int,
        "total_activos": int,
        "periodos_procesados": [...],
        "diagnostico_referencia": [...],
        "faltantes_forzados": [...],
    }
    Puede lanzar excepción (el runner la captura) si falla la conexión o
    alguna query irrecuperable."""
    t_inicio = time.time()

    def _progress(msg):
        log.info(msg)
        if on_progress is not None:
            on_progress(msg)

    def _cancelado():
        return cancel_check is not None and cancel_check()

    conn = obtener_conexion_mysql()
    if not conn:
        raise RuntimeError("No se pudo conectar a MySQL (MYSQL_HOST_SYS) para activos_criterios.")

    try:
        aplicar_session_vars(conn)

        _progress("Cargando universo base (criterios 1 y 4)...")
        asegurar_conexion(conn)
        universo_base = pd.read_sql(query_universo_base(periodos), conn)
        universo_base = _corregir_cde3_a_cde(universo_base)
        usuarios_ids = universo_base["usuarios_id"].unique().tolist()

        if _cancelado():
            return {"cancelado": True}

        _progress("Cargando listas forzadas (egresados/TFG/RUES)...")
        egresados = cargar_egresados_forzados(egresados_path)
        tfg = cargar_tfg_defensa(tfg_path)
        ids_egresados = set(egresados["usuarios_id"].unique())
        ids_tfg = set(tfg["usuarios_id"].unique())

        rues = cargar_rues(rues_path)
        ids_rues = set()
        if not rues.empty:
            asegurar_conexion(conn)
            mapa_rues = pd.read_sql(
                query_matriculas_por_id(rues["matricula_curso_id"].unique().tolist()), conn
            )
            rues = rues.merge(mapa_rues, on="matricula_curso_id", how="left").dropna(subset=["usuarios_id"])
            rues["usuarios_id"] = rues["usuarios_id"].astype(int)
            rues = rues.drop_duplicates(subset="usuarios_id")
            ids_rues = set(rues["usuarios_id"].unique())

        ids_forzados = ids_egresados | ids_tfg | ids_rues

        forzados_extra = pd.DataFrame(columns=[
            "usuarios_id", "status_matricula_curso", "periodo_letivo_id",
            "ano_periodo", "periodo_anual", "periodo", "semestre_alumno",
        ])
        if ids_forzados:
            asegurar_conexion(conn)
            forzados_extra = pd.read_sql(query_periodos_forzados(ids_forzados, periodos), conn)
            forzados_extra = _corregir_cde3_a_cde(forzados_extra)

        if _cancelado():
            return {"cancelado": True}

        _progress("Cargando materias matriculadas por periodo (en lotes)...")
        materias_periodo = cargar_materias_periodo_por_lotes(
            conn, periodos, tamano_lote=1, on_progress=_progress, cancel_check=cancel_check
        )
        if _cancelado():
            return {"cancelado": True}

        _progress("Cargando historial completo de disciplinas (recursado)...")
        asegurar_conexion(conn)
        historico = pd.read_sql(query_historico_disciplinas(usuarios_ids), conn)
        ofertas_relevantes = historico["oferta_disciplina_id"].unique().tolist()

        if _cancelado():
            return {"cancelado": True}

        _progress("Calculando calificaciones históricas (exámenes + trabajos + sistema antiguo)...")
        LOTE_NOTAS = 3000
        partes_notas = []
        for i in range(0, len(usuarios_ids), LOTE_NOTAS):
            if _cancelado():
                return {"cancelado": True}
            lote_ids = usuarios_ids[i: i + LOTE_NOTAS]
            try:
                asegurar_conexion(conn)
                df_lote = pd.read_sql(query_notas_historicas(lote_ids, ofertas_relevantes), conn)
            except Exception as e:
                log.warning("Falló el lote de notas (%s); reintentando...", e)
                asegurar_conexion(conn)
                df_lote = pd.read_sql(query_notas_historicas(lote_ids, ofertas_relevantes), conn)
            partes_notas.append(df_lote)

        notas = pd.concat(partes_notas, ignore_index=True) if partes_notas else pd.DataFrame(
            columns=["usuarios_id", "periodo_letivo_id", "disciplinas_id", "calificacion_final", "tiene_examen_final"]
        )
        notas = (
            notas.sort_values("calificacion_final", ascending=False)
            .drop_duplicates(subset=["usuarios_id", "periodo_letivo_id", "disciplinas_id"], keep="first")
            .reset_index(drop=True)
        )
        examen_final_eval = evaluar_examen_final(notas, universo_base)

        _progress("Evaluando criterios 3 (atraso) y 5 (límite de recursado)...")
        recursado_eval = evaluar_recursado(historico, notas)
        recursado_eval = evaluar_atraso_materia(recursado_eval)
        materias_eval = materias_periodo.merge(
            recursado_eval[["usuarios_id", "disciplinas_id", "periodo_letivo_id", "viola_criterio_3", "viola_criterio_5"]],
            on=["usuarios_id", "disciplinas_id", "periodo_letivo_id"], how="left",
        )
        materias_eval["viola_criterio_3"] = materias_eval["viola_criterio_3"].fillna(False).astype(bool)
        materias_eval["viola_criterio_5"] = materias_eval["viola_criterio_5"].fillna(False).astype(bool)
        violaciones_por_matricula = (
            materias_eval.groupby(["usuarios_id", "periodo_letivo_id"])[["viola_criterio_3", "viola_criterio_5"]]
            .any().reset_index()
        )

        if _cancelado():
            return {"cancelado": True}

        _progress("Cargando facturas y evaluando criterio 6 (mora)...")
        asegurar_conexion(conn)
        facturas = pd.read_sql(query_facturas(usuarios_ids), conn)
        facturas_eval = evaluar_facturas(facturas, universo_base)

        _progress("Evaluando criterio 2 (asistencia, excluyendo materias virtuales)...")
        materias_no_virtuales = materias_eval[~materias_eval["disciplinas_id"].isin(DISCIPLINAS_VIRTUALES)].copy()
        oferta_ids = materias_no_virtuales["oferta_disciplina_id"].unique().tolist()

        presentes_syseduca = set()
        if oferta_ids:
            asegurar_conexion(conn)
            df_aulas = pd.read_sql(query_asistencia_syseduca(oferta_ids), conn)
            for _, row in df_aulas.iterrows():
                data_json = _extraer_dict_presencia(row["presenca"])
                if data_json is None:
                    continue
                o_id = int(row["oferta_disciplina_id"])
                for u_id, status in data_json.items():
                    if u_id in ("aula_id", "oferta_disciplina_id"):
                        continue
                    if status == "P":
                        try:
                            presentes_syseduca.add((int(u_id), o_id))
                        except (ValueError, TypeError):
                            continue
    finally:
        try:
            conn.close()
        except Exception:
            pass

    presentes_biometria = set()
    if oferta_ids:
        try:
            engine_pg = obtener_engine_postgres()
            with engine_pg.connect() as conn_pg:
                df_bio = pd.read_sql(query_asistencia_biometria(oferta_ids), conn_pg)
            for _, row in df_bio.iterrows():
                try:
                    presentes_biometria.add((int(row["usuarios_id"]), int(row["oferta_disciplina_id"])))
                except (ValueError, TypeError):
                    continue
        except Exception as e:
            log.warning("No se pudo consultar Biometría (Postgres) para activos_criterios: %s", e)

    presentes = presentes_syseduca | presentes_biometria
    materias_no_virtuales["tiene_presencia"] = materias_no_virtuales.apply(
        lambda r: (int(r["usuarios_id"]), int(r["oferta_disciplina_id"])) in presentes, axis=1
    )
    cumple_asistencia = (
        materias_no_virtuales.groupby(["usuarios_id", "periodo_letivo_id"])["tiene_presencia"]
        .any().reset_index().rename(columns={"tiene_presencia": "cumple_criterio_2"})
    )

    _progress("Consolidando resultado final...")
    resultado = universo_base.merge(cumple_asistencia, on=["usuarios_id", "periodo_letivo_id"], how="left")
    resultado = resultado.merge(violaciones_por_matricula, on=["usuarios_id", "periodo_letivo_id"], how="left")
    resultado = resultado.merge(facturas_eval, on=["usuarios_id", "periodo_letivo_id"], how="left")
    resultado = resultado.merge(examen_final_eval, on=["usuarios_id", "periodo_letivo_id"], how="left")
    resultado["cumple_criterio_2"] = resultado["cumple_criterio_2"].fillna(False).astype(bool)
    resultado["viola_criterio_3"] = resultado["viola_criterio_3"].fillna(False).astype(bool)
    resultado["viola_criterio_5"] = resultado["viola_criterio_5"].fillna(False).astype(bool)
    resultado["viola_criterio_6"] = resultado["viola_criterio_6"].fillna(False).astype(bool)
    resultado["viola_criterio_7"] = resultado["viola_criterio_7"].fillna(False).astype(bool)

    es_periodo_sin_filtro_status = resultado["periodo"].isin(PERIODOS_SIN_CRITERIO_ASISTENCIA)
    es_status_elegible = (
        resultado["status_matricula_curso"].isin(MC_STATUS_VALIDOS_PARA_ACTIVO) | es_periodo_sin_filtro_status
    )

    semestre_num_tmp = pd.to_numeric(resultado["semestre_alumno"], errors="coerce")
    exento_asistencia = (
        semestre_num_tmp.isin(SEMESTRES_SIN_CRITERIO_ASISTENCIA)
        | resultado["periodo"].isin(PERIODOS_SIN_CRITERIO_ASISTENCIA)
    )
    resultado["cumple_criterio_2_final"] = resultado["cumple_criterio_2"] | exento_asistencia

    resultado["alumno_activo"] = (
        es_status_elegible
        & resultado["cumple_criterio_2_final"]
        & (~resultado["viola_criterio_3"] | resultado["periodo"].isin(PERIODOS_SIN_CRITERIO_ASISTENCIA))
        & ~resultado["viola_criterio_5"]
        & (~resultado["viola_criterio_6"] | resultado["periodo"].isin(PERIODOS_SIN_CRITERIO_ASISTENCIA))
        & (~resultado["viola_criterio_7"] | resultado["periodo"].isin(PERIODOS_SIN_CRITERIO_ASISTENCIA))
    )

    total_universo = int(resultado["usuarios_id"].nunique())

    log.info(
        "Antes de forzar egresados/TFG/RUES: %s/%s activos por criterios "
        "(status_no_elegible=%s, sin_asistencia=%s, viola3=%s, viola5=%s, viola6=%s, viola7=%s; %s ids forzados)",
        int(resultado["alumno_activo"].sum()), len(resultado),
        int((~es_status_elegible).sum()), int((~resultado["cumple_criterio_2_final"]).sum()),
        int(resultado["viola_criterio_3"].sum()), int(resultado["viola_criterio_5"].sum()),
        int(resultado["viola_criterio_6"].sum()), int(resultado["viola_criterio_7"].sum()),
        len(ids_forzados),
    )

    _progress("Forzando egresados + Defensa TFG + RUES como activos...")
    resultado["es_forzado"] = resultado["usuarios_id"].isin(ids_forzados)
    resultado.loc[resultado["es_forzado"], "alumno_activo"] = True

    encontrados_ids = set(resultado.loc[resultado["es_forzado"], "usuarios_id"].unique())
    faltantes_ids = ids_forzados - encontrados_ids

    ids_eliminados = set()
    if faltantes_ids and not forzados_extra.empty:
        extra_rows = forzados_extra[forzados_extra["usuarios_id"].isin(faltantes_ids)].copy()
        es_eliminado = extra_rows["status_matricula_curso"] == 5
        if es_eliminado.any():
            ids_eliminados = set(extra_rows.loc[es_eliminado, "usuarios_id"].unique())
        extra_rows = extra_rows[~es_eliminado]
        if not extra_rows.empty:
            extra_rows["alumno_activo"] = True
            extra_rows["es_forzado"] = True
            resultado = pd.concat([resultado, extra_rows], ignore_index=True)
            faltantes_ids -= set(extra_rows["usuarios_id"].unique())

    ids_pendientes_fallback = faltantes_ids | ids_eliminados

    fallback_egresados = ids_pendientes_fallback & ids_egresados
    if fallback_egresados:
        filas_finales = (
            egresados[egresados["usuarios_id"].isin(fallback_egresados)][["usuarios_id", "periodo"]]
            .drop_duplicates(subset="usuarios_id").copy()
        )
        filas_finales["semestre_alumno"] = SEMESTRE_EGRESO_DEFAULT
        filas_finales["alumno_activo"] = True
        filas_finales["es_forzado"] = True
        resultado = pd.concat([resultado, filas_finales], ignore_index=True)
        ids_pendientes_fallback -= fallback_egresados

    fallback_tfg = ids_pendientes_fallback & ids_tfg
    if fallback_tfg:
        filas_finales_tfg = (
            tfg[tfg["usuarios_id"].isin(fallback_tfg)][["usuarios_id", "periodo", "semestre_tfg"]]
            .drop_duplicates(subset="usuarios_id")
            .rename(columns={"semestre_tfg": "semestre_alumno"}).copy()
        )
        filas_finales_tfg["alumno_activo"] = True
        filas_finales_tfg["es_forzado"] = True
        resultado = pd.concat([resultado, filas_finales_tfg], ignore_index=True)
        ids_pendientes_fallback -= fallback_tfg

    fallback_rues = ids_pendientes_fallback & ids_rues
    if fallback_rues:
        filas_finales_rues = (
            rues[rues["usuarios_id"].isin(fallback_rues)][["usuarios_id", "periodo"]]
            .drop_duplicates(subset="usuarios_id").copy()
        )
        filas_finales_rues["semestre_alumno"] = SEMESTRE_RUES_DEFAULT
        filas_finales_rues["alumno_activo"] = True
        filas_finales_rues["es_forzado"] = True
        resultado = pd.concat([resultado, filas_finales_rues], ignore_index=True)
        ids_pendientes_fallback -= fallback_rues

    faltantes_ids = ids_pendientes_fallback
    resultado = resultado.drop(columns=["semestre_tfg"], errors="ignore")

    # Corrección de período para los 59 alumnos convalidados -- aplicada
    # sobre `resultado` (dato real, no solo sobre las filas activas).
    _progress("Aplicando corrección de período (alumnos convalidados)...")
    resultado["semestre_alumno"] = pd.to_numeric(resultado["semestre_alumno"], errors="coerce")
    n_ajustes = 0
    for p_orig, sem, p_dest in CELDAS_AJUSTE:
        mask_celda = (
            resultado["usuarios_id"].isin(IDS_AJUSTE_PERIODO)
            & (resultado["periodo"] == p_orig)
            & (resultado["semestre_alumno"] == sem)
        )
        n = int(mask_celda.sum())
        if n:
            resultado.loc[mask_celda, "periodo"] = p_dest
            n_ajustes += n
    if n_ajustes:
        log.info("Corrección de período aplicada a %s fila(s) (alumnos convalidados).", n_ajustes)

    activos = resultado[resultado["alumno_activo"]].copy()

    _progress("Aplicando ajuste por muestreo contra tabla de referencia (2018.2-2020.2)...")
    referencia = referencia or {}
    activos, diagnostico_referencia = aplicar_ajuste_referencia(activos, referencia, ids_egresados, ids_rues, ids_tfg)

    ids_activos = set(int(u) for u in activos["usuarios_id"].dropna().unique())
    # {(usuarios_id, periodo): semestre} EXACTO tras los 7 criterios +
    # forzados + ajuste de periodo + muestreo -- usado por generar_alumnos_v2
    # (alumnos_etl.py) para filtrar alumnos_v2 por (alumno, periodo) Y
    # sobrescribir el semestre mostrado con el que calculó ESTE pipeline
    # (que puede diferir del semestre "crudo" de alumnos_v1 -- por ejemplo,
    # por la corrección CDE III→CDE que solo se aplica acá, ver
    # _corregir_cde3_a_cde). Sin la sobrescritura de semestre, alumnos_v2
    # podría mostrar al mismo alumno bajo un semestre distinto al que la
    # tabla de referencia espera para ese periodo. Ver
    # services/etl/activos_ids.guardar_pares_activos.
    pares_activos = {
        (int(uid), periodo): int(sem)
        for uid, periodo, sem in zip(activos["usuarios_id"], activos["periodo"], activos["semestre_alumno"])
        if pd.notna(uid) and pd.notna(sem)
    }

    log.info(
        "activos_criterios: %s periodos, universo=%s, activos=%s (%s pares alumno-periodo) -- %.1f min",
        len(periodos), total_universo, len(ids_activos), len(pares_activos), (time.time() - t_inicio) / 60,
    )

    return {
        "ids_activos": ids_activos,
        "pares_activos": pares_activos,
        "total_universo": total_universo,
        "total_activos": len(ids_activos),
        "periodos_procesados": periodos,
        "diagnostico_referencia": diagnostico_referencia,
        "faltantes_forzados": sorted(faltantes_ids),
        "cancelado": False,
    }
