"""
services/etl/permanencia_etl.py

Funciones puras del ETL de Índice de Permanencia (financiero + académico,
MySQL/SysEduca). Sin código ejecutable a nivel de módulo -- seguro importar
desde el admin module o el cron runner (services/etl/permanencia_runner.py)
sin disparar consultas.

Refactor de services/etl/etl_indice_permanencia.py (notebook, ejecutaba todo
al importar). La lógica de negocio (queries, recursión de negociación,
cálculo de notas) es la MISMA, solo modularizada y parametrizada por
`periodo` en vez de constantes hardcodeadas al tope del script.

MAPEO periodo -> ano_id/periodo_anual_id:
ucp.periodo_letivo usa IDs internos (ano_id, periodo_anual_id) que NO
coinciden con el año/semestre "de negocio" -- cada año tiene hasta 3 IDs
(uno por filial: CDE=1, PJC=2, CDE III=3). Esta tabla de referencia (2016 a
2031) venía hardcodeada en los comentarios del script original; acá se
mantiene igual, y derivar_ids_periodo() filtra siempre la filial PJC (2),
mismo criterio que el resto del sistema (config_filial_id IN (1,3)).

periodo_anual_id, en cambio, NO depende del año: subperiodo 1 siempre son
los IDs (1,3,5) y subperiodo 2 siempre (2,4,6) (uno por filial otra vez),
confirmado por los valores hardcodeados del script original.
"""

import json
import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

from utils.system_logging import get_logger

load_dotenv()

log = get_logger()


# ─────────────────────────────────────────────
# TABLA DE REFERENCIA: periodo -> ano_id / periodo_anual_id
# ─────────────────────────────────────────────

# año -> [(id, filial), ...] (filial: 1=CDE, 2=PJC, 3=CDE III)
ANO_ID_TABLE = {
    2016: [(11, 2)],
    2017: [(12, 2), (44, 1)],
    2018: [(1, 1), (13, 2), (45, 1)],
    2019: [(2, 1), (14, 2), (23, 3)],
    2020: [(3, 1), (15, 2), (24, 3)],
    2021: [(4, 1), (16, 2), (25, 3)],
    2022: [(5, 1), (17, 2), (26, 3)],
    2023: [(6, 1), (18, 2), (27, 3)],
    2024: [(7, 1), (19, 2), (28, 3)],
    2025: [(8, 1), (20, 2), (29, 3)],
    2026: [(9, 1), (21, 2), (30, 3)],
    2027: [(10, 1), (22, 2), (31, 3)],
    2028: [(32, 2), (33, 1), (34, 3)],
    2029: [(35, 1), (36, 2), (37, 3)],
    2030: [(41, 2), (43, 1)],
    2031: [(42, 2), (46, 1)],
}

# subperiodo (1 o 2) -> [(id, filial), ...] -- fijo, NO depende del año.
PERIODO_ANUAL_ID_TABLE = {
    1: [(1, 1), (3, 2), (5, 3)],
    2: [(2, 1), (4, 2), (6, 3)],
}

FILIAL_EXCLUIDA = 2  # PJC -- mismo criterio que config_filial_id IN (1,3) en el resto del sistema


def _ano_ids(anho):
    if anho not in ANO_ID_TABLE:
        raise ValueError(
            f"Año {anho} no está en la tabla de referencia de ano_id (rango soportado: "
            f"{min(ANO_ID_TABLE)}-{max(ANO_ID_TABLE)}). Agregarlo a ANO_ID_TABLE si corresponde."
        )
    return tuple(sorted(id_ for id_, filial in ANO_ID_TABLE[anho] if filial != FILIAL_EXCLUIDA))


def _periodo_ids(subperiodo):
    return tuple(sorted(id_ for id_, filial in PERIODO_ANUAL_ID_TABLE[subperiodo] if filial != FILIAL_EXCLUIDA))


def _parse_periodo(periodo):
    anho_str, sep, sub_str = periodo.partition(".")
    if not sep or not anho_str.isdigit() or sub_str not in ("1", "2"):
        raise ValueError(f"Periodo inválido: {periodo!r}. Formato esperado: 'AAAA.S' (ej. '2026.1').")
    return int(anho_str), int(sub_str)


def derivar_ids_periodo(periodo):
    """A partir de un único 'periodo' (ej. '2026.1'), deriva los ano_id/
    periodo_anual_id (actual/anterior/próximo) que espera montar_query(), y
    los labels usados para nombrar los archivos (ej. '20261')."""
    anho, subperiodo = _parse_periodo(periodo)

    if subperiodo == 1:
        anho_anterior, sub_anterior = anho - 1, 2
        anho_proximo, sub_proximo = anho, 2
    else:
        anho_anterior, sub_anterior = anho, 1
        anho_proximo, sub_proximo = anho + 1, 1

    return {
        "ano_actual_ids": _ano_ids(anho),
        "periodo_actual_ids": _periodo_ids(subperiodo),
        "ano_anterior_ids": _ano_ids(anho_anterior),
        "periodo_anterior_ids": _periodo_ids(sub_anterior),
        "ano_proximo_ids": _ano_ids(anho_proximo),
        "periodo_proximo_ids": _periodo_ids(sub_proximo),
        "label_actual": f"{anho}{subperiodo}",
        "label_proximo": f"{anho_proximo}{sub_proximo}",
    }


# ─────────────────────────────────────────────
# CONEXIÓN
# ─────────────────────────────────────────────

def obtener_engine():
    usuario = quote_plus(os.getenv("MYSQL_USER_SYS", ""))
    clave = quote_plus(os.getenv("MYSQL_PASSWORD_SYS", ""))
    host = os.getenv("MYSQL_HOST_SYS")
    port = os.getenv("MYSQL_PORT_SYS", "3306")
    db = os.getenv("MYSQL_DB_SYS")
    return create_engine(f"mysql+mysqlconnector://{usuario}:{clave}@{host}:{port}/{db}")


# ─────────────────────────────────────────────
# QUERY (idéntica al script original, solo parametrizada)
# ─────────────────────────────────────────────

def _sql_in(valores):
    """Convierte una lista/tupla/valor único en un string listo para una
    cláusula SQL 'IN (...)', evitando el repr de una tupla de 1 elemento
    (ej: (8,) que rompe el SQL)."""
    if isinstance(valores, (list, tuple, set)):
        vals = ",".join(str(v) for v in valores)
    else:
        vals = str(valores)
    return f"({vals})"


def montar_query(anos, periodos, com_recursante=True, ano_recursante=None, periodo_recursante=None,
                  requer_matricula_disciplina=True):
    """anos / periodos: ano_id y periodo_anual_id del período que la query va a
    traer (ver derivar_ids_periodo). com_recursante: si es True, calcula la
    columna 'es_recursante' comparando con ano_recursante/periodo_recursante
    (el período anterior). requer_matricula_disciplina: True exige que el
    alumno ya tenga matricula_disciplina activa en el período (JOIN INNER);
    False (para el período próximo, donde la matrícula académica todavía no
    fue lanzada) usa LEFT JOIN para no perder alumnos con factura financiera
    pero sin matrícula académica aún."""
    cte_rec_content = f"""
    , Matriculados_Periodo_Anterior AS (
        SELECT DISTINCT
            mc.usuarios_id,
            s.descricao as semestre_anterior
        FROM ucp.periodo_letivo pl
        JOIN ucp.matricula_curso mc ON mc.id = pl.matricula_curso_id
        JOIN ucp.semestre s ON s.id = pl.semestre_id
        WHERE pl.ano_id IN {_sql_in(ano_recursante)}
          AND pl.periodo_anual_id IN {_sql_in(periodo_recursante)}
          AND pl.status = 1
          AND mc.status IN (1,3,4)
    )""" if com_recursante else ""

    col_rec = "CASE WHEN m251.semestre_anterior = s.descricao THEN 'SI' ELSE '-' END" if com_recursante else "'-'"
    join_rec = "LEFT JOIN Matriculados_Periodo_Anterior m251 ON m251.usuarios_id = mc.usuarios_id" if com_recursante else ""

    join_md = ("JOIN ucp.matricula_disciplina md ON md.periodo_letivo_id = pl.id" if requer_matricula_disciplina
               else "LEFT JOIN ucp.matricula_disciplina md ON md.periodo_letivo_id = pl.id")
    where_md = "AND md.status = 1" if requer_matricula_disciplina else ""

    return f"""
    WITH FaturasCandidatas AS (
        SELECT
            f.usuarios_id, f.periodo_letivo_id, f.parcela, f.id as factura_id, f.valor,
            f.status as factura_status, f.data_pagamento, f.negociacao_id,
            ROW_NUMBER() OVER (
                PARTITION BY f.usuarios_id, f.periodo_letivo_id, f.parcela
                ORDER BY f.created ASC
            ) as linha_num_parcela
        FROM ucp.faturas f
        LEFT JOIN ucp.finan_oferta fo ON fo.id = f.finan_oferta_id
        LEFT JOIN ucp.finan_centro_custo fcc ON fcc.id = fo.finan_centro_custo_id
        LEFT JOIN ucp.finan_departamento fd ON fd.id = fo.finan_departamento_id
        WHERE f.status NOT IN (3, 4)
          AND (f.parcela = 1 OR f.parcela = 2)
          AND (fd.nome LIKE '%%Contrato%%' OR fcc.nome LIKE '%%Recursada%%')
    ),
    -- Se a fatura de uma parcela foi cancelada (status 4, já excluída acima),
    -- linha_num_parcela=1 pega a fatura válida mais antiga da MESMA parcela --
    -- ou seja, a que foi gerada em substituição (reemissão) e pode já estar paga.
    FaturasValidas AS (
        SELECT
            usuarios_id, periodo_letivo_id, factura_id, valor, factura_status, data_pagamento, negociacao_id,
            ROW_NUMBER() OVER (PARTITION BY usuarios_id, periodo_letivo_id ORDER BY parcela ASC) as linha_num
        FROM FaturasCandidatas
        WHERE linha_num_parcela = 1
    ),
    HistoricoAnterior AS (
        SELECT
            mc_h.usuarios_id,
            MIN(pl_h.id) as primeiro_pl_id_eterno
        FROM ucp.periodo_letivo pl_h
        JOIN ucp.matricula_curso mc_h ON mc_h.id = pl_h.matricula_curso_id
        WHERE pl_h.status = 1
        GROUP BY mc_h.usuarios_id
    ){cte_rec_content}
    SELECT DISTINCT
        mc.usuarios_id as id_alumno,
        pl.id as periodo_letivo_id,
        u.nome_sobrenome as nombre_apellido,
        CASE
            WHEN pl.id = ha.primeiro_pl_id_eterno THEN 'Primer Periodo'
            ELSE 'Veterano'
        END AS analise_primer_periodo,
        CASE WHEN pl.tipo_aluno = 1 then 'A' ELSE 'N' END AS tipo_alumno,
        CASE
            WHEN mc.status = 1 then 'Activo'
            WHEN mc.status = 3 then 'Trancado'
            WHEN mc.status = 4 then 'Suspenso'
        END AS estado_matricula,
        s.descricao as semestre,
        {col_rec} AS es_recursante,
        CASE
            WHEN fv.factura_status = 1 THEN 'Paga'
            WHEN fv.factura_status = 7 THEN 'Negociada'
            WHEN fv.factura_status = 0 THEN 'Pendiente'
            WHEN fv.factura_id IS NULL THEN 'Sin Factura'
        END AS estado_pago,
        fv.factura_id,
        fv.factura_status as factura_status_id,
        fv.negociacao_id,
        fv.data_pagamento as fecha_pago,
        fv.valor as monto_factura,
        mc.id as matricula_curso_id,
        pl.id as periodo_lectivo_id,
        CASE
            WHEN mc.tipo_matricula_curso_id = 1 THEN 'Normal'
            WHEN mc.tipo_matricula_curso_id = 2 THEN 'Convalidado'
            ELSE ' - '
        END AS tipo_matricula,
        nc.numero_catraca
    FROM ucp.periodo_letivo pl
    JOIN ucp.matricula_curso mc ON mc.id = pl.matricula_curso_id
    JOIN ucp.usuarios u ON u.id = mc.usuarios_id
    JOIN ucp.semestre s ON s.id = pl.semestre_id
    {join_md}
    LEFT JOIN ucp.numero_catraca nc on nc.usuarios_id = u.id
    LEFT JOIN FaturasValidas fv ON fv.usuarios_id = mc.usuarios_id
        AND fv.periodo_letivo_id = pl.id
        AND fv.linha_num = 1
    LEFT JOIN HistoricoAnterior ha ON ha.usuarios_id = mc.usuarios_id
    {join_rec}
    WHERE 1=1
        AND pl.ano_id IN {_sql_in(anos)}
        AND pl.periodo_anual_id IN {_sql_in(periodos)}
        AND pl.status = 1
        {where_md}
        AND mc.status IN (1,3,4)
        AND s.descricao IN (1,2,3,4,5,6)
        AND (u.nome_sobrenome NOT LIKE '%%Test%%' AND u.nome_sobrenome NOT LIKE '%%Prueba%%');
    """


# ─────────────────────────────────────────────
# NEGOCIACIÓN DE FACTURAS (recursivo)
# ─────────────────────────────────────────────

def obtener_status_real_recursivo(factura_id, conn, hoje, nivel=0):
    sql_neg = text("SELECT negociacao_id FROM ucp.negociacao_faturas WHERE faturas_id = :f_id ORDER BY negociacao_id DESC LIMIT 1")
    res_neg = conn.execute(sql_neg, {"f_id": factura_id}).fetchone()

    if not res_neg:
        return "Sem Detalhes", nivel

    neg_id = res_neg[0]

    sql_filhas = text("""
        SELECT id, status, data_vencimento
        FROM ucp.faturas
        WHERE negociacao_id = :n_id AND status NOT IN (3, 4)
    """)
    faturas_filhas = conn.execute(sql_filhas, {"n_id": neg_id}).fetchall()

    if not faturas_filhas:
        return "Vazia", nivel

    tem_vencida = False
    tem_pendente = False
    todas_pagas = True
    nivel_maximo_alcancado = nivel

    for f_id_filha, f_status, f_vencimento in faturas_filhas:
        vencimento_date = f_vencimento.date() if hasattr(f_vencimento, "date") else f_vencimento
        status_atual = ""

        if f_status == 7:
            status_atual, nivel_filho = obtener_status_real_recursivo(f_id_filha, conn, hoje, nivel + 1)
            if nivel_filho > nivel_maximo_alcancado:
                nivel_maximo_alcancado = nivel_filho
        elif f_status == 1:
            status_atual = "Paga"
        elif (f_status == 0 and vencimento_date < hoje) or f_status == 2:
            status_atual = "Vencida"
        else:
            status_atual = "Pendiente"

        if "Vencida" in status_atual:
            tem_vencida = True
            todas_pagas = False
        elif any(x in status_atual for x in ["Pendiente", "Sem Detalhes", "Vazia"]):
            tem_pendente = True
            todas_pagas = False
        elif status_atual != "Paga":
            todas_pagas = False

    if tem_vencida:
        res = "Vencida"
    elif tem_pendente:
        res = "Pendiente"
    elif todas_pagas:
        res = "Paga"
    else:
        res = "Indefinida"

    return res, nivel_maximo_alcancado


def verificar_status_negociacion(row, engine):
    if row["factura_status_id"] != 7:
        return row["estado_pago"]

    factura_id = row["factura_id"]
    hoje = pd.Timestamp.now().date()

    try:
        with engine.connect() as conn:
            status_final, nivel_final = obtener_status_real_recursivo(factura_id, conn, hoje, nivel=0)
            prefixo = "Renegociada" if nivel_final > 0 else "Negociada"
            return f"{prefixo} - {status_final}"
    except Exception as e:
        return f"Negociada (Erro: {str(e)})"


# ─────────────────────────────────────────────
# PASOS DEL PIPELINE (uno por cada on_progress -- ver permanencia_runner.py)
# ─────────────────────────────────────────────

def extraer_matriculas_financiero(engine, ids):
    """Trae actual + próximo (2 queries) y aplica el análisis de negociación.
    Devuelve (df_atual, df_proximo)."""
    df_atual = pd.read_sql(
        montar_query(ids["ano_actual_ids"], ids["periodo_actual_ids"], True,
                     ids["ano_anterior_ids"], ids["periodo_anterior_ids"]),
        engine,
    ).drop_duplicates("id_alumno")

    df_proximo = pd.read_sql(
        montar_query(ids["ano_proximo_ids"], ids["periodo_proximo_ids"], False,
                     requer_matricula_disciplina=False),
        engine,
    ).drop_duplicates("id_alumno")

    df_atual["estado_pago"] = df_atual.apply(lambda row: verificar_status_negociacion(row, engine), axis=1)
    df_proximo["estado_pago"] = df_proximo.apply(lambda row: verificar_status_negociacion(row, engine), axis=1)

    return df_atual, df_proximo


def extraer_auditoria(engine, df_atual):
    ids_mc = [str(int(x)) for x in df_atual["matricula_curso_id"].dropna().unique()]
    if not ids_mc:
        return pd.DataFrame(columns=["matricula_curso_id", "fecha_cambio", "usuario_cambio", "desc_audit_log"])

    query_audit = f"""
        SELECT id_affected as matricula_curso_id, modified as fecha_cambio,
        CONCAT(f.nome, ' ', f.sobrenome) as usuario_cambio, new_value
        FROM ucp.audit_log a
        JOIN ucp.funcionario f ON f.id = a.modified_by_user_id
        WHERE a.field_name = 'matricula_curso' AND a.id_affected IN ({','.join(ids_mc)})
    """
    df_log = pd.read_sql(query_audit, engine)
    if df_log.empty:
        df_log["matricula_curso_id"] = pd.Series(dtype=str)
        return df_log

    def parse_descricao(x):
        if not x:
            return ""
        try:
            return json.loads(x, strict=False).get("descricao", "")
        except (json.JSONDecodeError, AttributeError):
            return ""

    df_log["desc_audit_log"] = df_log["new_value"].apply(parse_descricao)
    df_log = df_log.sort_values("fecha_cambio", ascending=False).drop_duplicates("matricula_curso_id")
    df_log["matricula_curso_id"] = df_log["matricula_curso_id"].astype(str)
    return df_log


def calcular_notas(engine, ids_alumnos, ids_periodos):
    """Aprobado/reprobado por alumno (nota mínima del periodo actual). Devuelve
    un DataFrame [id_alumno, status_academico] (vacío si no hay alumnos/periodos)."""
    lista_alunos = ",".join(str(int(x)) for x in ids_alumnos)
    lista_periodos = ",".join(str(int(x)) for x in ids_periodos)

    if not lista_alunos or not lista_periodos:
        return pd.DataFrame(columns=["id_alumno", "status_academico"])

    query_notas = f"""
    SELECT
        id_alumno, id_asignatura,
        CASE
            WHEN nota_extraordinaria > 0 THEN nota_extraordinaria
            ELSE nota_acumulada_final
        END AS calificacion_final_calculada
    FROM (
        SELECT
            base.*,
            MAX(CASE WHEN tipo_examen_id = 9 THEN puntos_logrados ELSE 0 END)
                OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) as nota_extraordinaria,
            SUM(CASE
                WHEN tipo_examen_id = 2 AND nota_maior_p1_recup > puntos_logrados THEN 0
                WHEN tipo_examen_id = 5 AND nota_maior_p2_recup > puntos_logrados THEN 0
                WHEN tipo_examen_id = 7 AND nota_maior_complementar > puntos_logrados THEN 0
                WHEN tipo_examen_id = 8 AND nota_maior_prova_final >= puntos_logrados THEN 0
                WHEN tipo_examen_id IN (9, 15) THEN 0
                ELSE puntos_logrados
            END) OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS nota_acumulada_final
        FROM (
            SELECT
                u.id AS id_alumno, d.id AS id_asignatura, et.periodo_letivo_id AS id_periodo_lectivo,
                te.id as tipo_examen_id, et.nota AS puntos_logrados,
                MAX(CASE WHEN te.id = 3 THEN et.nota ELSE 0 END) OVER(PARTITION BY u.id, d.id, et.periodo_letivo_id) as nota_maior_p1_recup,
                MAX(CASE WHEN te.id = 6 THEN et.nota ELSE 0 END) OVER(PARTITION BY u.id, d.id, et.periodo_letivo_id) as nota_maior_p2_recup,
                MAX(CASE WHEN te.id = 8 THEN et.nota ELSE 0 END) OVER(PARTITION BY u.id, d.id, et.periodo_letivo_id) as nota_maior_prova_final,
                MAX(CASE WHEN te.id = 7 THEN et.nota ELSE 0 END) OVER(PARTITION BY u.id, d.id, et.periodo_letivo_id) as nota_maior_complementar
            FROM ucp.ex_tentativa et
            JOIN ucp.ex_examen ex ON ex.id = et.ex_examen_id
            JOIN ucp.ex_tipo_examen te ON te.id = ex.tipo_examen_id
            JOIN ucp.usuarios u ON u.id = et.usuarios_id
            JOIN ucp.oferta_disciplina od ON od.id = et.oferta_disciplina_id
            JOIN ucp.disciplinas d ON d.id = od.disciplinas_id
            WHERE et.status = 1 AND u.id IN ({lista_alunos}) AND et.periodo_letivo_id IN ({lista_periodos})

            UNION ALL

            SELECT
                u.id, d.id, pl.id,
                999, CAST(ta.nota AS DECIMAL(10,2)),
                0, 0, 0, 0
            FROM ucp.ex_trabalhos_aluno ta
            JOIN ucp.usuarios u ON u.id = ta.usuarios_id
            JOIN ucp.oferta_disciplina od ON od.id = ta.oferta_disciplina_id
            JOIN ucp.disciplinas d ON d.id = od.disciplinas_id
            JOIN ucp.periodo_letivo pl ON pl.id = (
                SELECT MAX(periodo_letivo_id) FROM ucp.ex_tentativa
                WHERE oferta_disciplina_id = od.id AND usuarios_id = u.id
            )
            WHERE ta.status = 1 AND u.id IN ({lista_alunos}) AND pl.id IN ({lista_periodos})
        ) AS base
    ) AS calculo_final
    """
    df_notas = pd.read_sql(query_notas, engine)
    if df_notas.empty:
        return pd.DataFrame(columns=["id_alumno", "status_academico"])

    df_notas = df_notas[["id_alumno", "id_asignatura", "calificacion_final_calculada"]].drop_duplicates()
    df_status = df_notas.groupby("id_alumno")["calificacion_final_calculada"].min().reset_index()
    df_status["status_academico"] = np.where(df_status["calificacion_final_calculada"] < 60, "REPROBADO", "APROBADO")
    return df_status[["id_alumno", "status_academico"]]


COLUMNAS_FINALES = [
    "id_alumno", "numero_catraca", "nombre_apellido", "analise_primer_periodo", "tipo_alumno",
    "estado_matricula", "es_recursante", "status_academico",
    "periodo_lectivo_id", "semestre_atual", "semestre_proximo", "estado_pago_atual", "estado_pago_proximo",
    "factura_id_atual", "factura_id_proximo", "factura_status_id_atual", "factura_status_id_proximo",
    "fecha_pago_atual", "fecha_pago_proximo", "monto_factura_atual", "monto_factura_proximo",
    "matricula_curso_id", "tipo_matricula", "fecha_cambio", "usuario_cambio", "desc_audit_log",
]


def unificar(df_atual, df_proximo, df_log, df_status_notas):
    """Combina actual + próximo + auditoría + notas en el DataFrame final,
    con la misma limpieza/formato que el script original."""
    df_atual = df_atual.copy()
    df_atual["mc_str"] = df_atual["matricula_curso_id"].astype(str)
    df_final = pd.merge(df_atual, df_log, left_on="mc_str", right_on="matricula_curso_id", how="left", suffixes=("", "_audit"))

    cols_proximo = ["id_alumno", "semestre", "estado_pago", "fecha_pago", "monto_factura", "factura_id", "factura_status_id"]
    df_final = pd.merge(df_final, df_proximo[cols_proximo], on="id_alumno", how="left", suffixes=("_atual", "_proximo"))

    if not df_status_notas.empty:
        df_final = pd.merge(df_final, df_status_notas, on="id_alumno", how="left")
    else:
        df_final["status_academico"] = np.nan
    df_final["status_academico"] = df_final["status_academico"].fillna("SEM NOTAS")

    cols_limpar = ["fecha_cambio", "usuario_cambio", "desc_audit_log"]
    df_final.loc[df_final["estado_matricula"] == "Activo", cols_limpar] = np.nan

    for c in ["fecha_pago_atual", "fecha_pago_proximo", "fecha_cambio"]:
        if c in df_final.columns:
            df_final[c] = pd.to_datetime(df_final[c], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")

    for col in COLUMNAS_FINALES:
        if col not in df_final.columns:
            df_final[col] = np.nan

    return df_final[COLUMNAS_FINALES].copy()
