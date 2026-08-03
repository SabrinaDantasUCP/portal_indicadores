#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import mysql.connector
import os
import pandas as pd
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONEXÃO
# ─────────────────────────────────────────────

def obtener_conexion():
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
        print(f"  [ERRO CONEXÃO] {e}")
        return None


# ─────────────────────────────────────────────
# QUERY
# ─────────────────────────────────────────────

def get_query(ano_loop):
    return f"""
    WITH alumnos_cde AS (
        SELECT DISTINCT m.usuarios_id
        FROM ucp.matricula_curso m
        JOIN ucp.periodo_letivo p ON p.matricula_curso_id = m.id
        JOIN ucp.ano a ON p.ano_id = a.id
        WHERE a.nome = {ano_loop}
          AND p.config_filial_id IN (1, 3)
          AND p.status = 1
    ),

    -- Limita ao ano corrente antes do ROW_NUMBER — evita varrer a tabela inteira
    melhor_tentativa AS (
        SELECT *
        FROM (
            SELECT et.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY ex_examen_id, oferta_disciplina_id, usuarios_id
                       ORDER BY nota DESC, id ASC
                   ) AS rn
            FROM ucp.ex_tentativa et
            WHERE et.status = 1
              AND et.usuarios_id IN (SELECT usuarios_id FROM alumnos_cde)
        ) ranked
        WHERE rn = 1
    ),

    melhor_trabalho AS (
        SELECT *
        FROM (
            SELECT ta.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY ex_trabalhos_id, oferta_disciplina_id, usuarios_id
                       ORDER BY nota DESC, id ASC
                   ) AS rn
            FROM ucp.ex_trabalhos_aluno ta
            WHERE ta.status = 1
              AND ta.usuarios_id IN (SELECT usuarios_id FROM alumnos_cde)
        ) ranked
        WHERE rn = 1
    ),

    max_pl_trabalho AS (
        SELECT oferta_disciplina_id, usuarios_id,
               MAX(periodo_letivo_id) AS periodo_letivo_id
        FROM ucp.ex_tentativa
        WHERE usuarios_id IN (SELECT usuarios_id FROM alumnos_cde)
        GROUP BY oferta_disciplina_id, usuarios_id
    ),

    coord_notas_aux AS (
        SELECT
            od.id AS oferta_disciplina_id,
            CAST(aluno.id_aluno AS UNSIGNED) AS id_alumno,
            MAX(CASE
                WHEN (f2.nome LIKE '%Recuperat%' OR f2.nome LIKE '%Regulariza%')
                    AND (f3.nome LIKE '%1%Parcial%' OR f3.nome LIKE '%Pratico%'
                        OR (f3.nome LIKE '%Parcial%' AND f3.nome NOT LIKE '%2%'))
                THEN nv.nota_val ELSE 0
            END) AS nota_maior_p1_recup,
            MAX(CASE
                WHEN (f2.nome LIKE '%Recuperat%' OR f2.nome LIKE '%Regulariza%')
                    AND f3.nome LIKE '%2%Parcial%'
                THEN nv.nota_val ELSE 0
            END) AS nota_maior_p2_recup,
            MAX(CASE
                WHEN f2.nome LIKE '%Complementar%'
                THEN nv.nota_val ELSE 0
            END) AS nota_maior_complementar,
            MAX(CASE
                WHEN (f2.nome LIKE '%Ordinario%' OR f2.nome LIKE '%Práctica%')
                    AND (f3.nome LIKE '%Final%' OR f3.nome LIKE '%Examen%' OR f3.nome LIKE '%Exame%')
                THEN nv.nota_val ELSE 0
            END) AS nota_maior_prova_final
        FROM ucp.coord_avaliacao c
        JOIN ucp.finan_oferta       f   ON f.id  = c.finan_oferta_id
        JOIN ucp.finan_centro_custo f2  ON f2.id = f.finan_centro_custo_id
        JOIN ucp.finan_departamento f3  ON f3.id = f.finan_departamento_id
        JOIN ucp.oferta_disciplina  od  ON od.id = c.oferta_disciplina_id
        JOIN ucp.matricula_disciplina md ON md.oferta_disciplina_id = od.id
        JOIN ucp.periodo_letivo     pl  ON pl.id = md.periodo_letivo_id
        JOIN ucp.matricula_curso    mc  ON mc.id = pl.matricula_curso_id
        JOIN ucp.ano                ano ON ano.id = pl.ano_id
        JOIN alumnos_cde            ac  ON mc.usuarios_id = ac.usuarios_id
        CROSS JOIN JSON_TABLE(
            JSON_KEYS(c.notas, '$[0]'),
            '$[*]' COLUMNS (id_aluno VARCHAR(50) PATH '$')
        ) AS aluno
        JOIN LATERAL (
            SELECT CAST(
                NULLIF(TRIM(JSON_UNQUOTE(JSON_EXTRACT(c.notas, CONCAT('$[0]."', aluno.id_aluno, '"')))), '')
            AS DECIMAL(10,2)) AS nota_val
        ) nv ON nv.nota_val IS NOT NULL
        WHERE c.status = 1
          AND md.status = 1
          AND ano.nome = {ano_loop}
          AND mc.usuarios_id = CAST(aluno.id_aluno AS UNSIGNED)
        GROUP BY od.id, aluno.id_aluno
    ),

    base_unificada AS (
        -- PARTE 1: EXAMES
        SELECT
            et.id, et.status,
            ano.nome             AS periodo,
            pa.descricao         AS sub_periodo,
            semestre.nome        AS semestre,
            cf.nome              AS filial,
            d.id                 AS id_asignatura,
            d.nome               AS asignatura,
            et.periodo_letivo_id AS id_periodo_lectivo,
            u.id                 AS id_alumno,
            te.id                AS tipo_examen_id,
            te.nome              AS tipo_examen,
            et.created_at        AS fecha_evaluacion,
            et.nota              AS puntos_logrados,
            'novo'               AS sistema
        FROM melhor_tentativa et
        JOIN alumnos_cde        ac  ON ac.usuarios_id = et.usuarios_id
        JOIN ucp.ex_examen      ex  ON ex.id  = et.ex_examen_id
        JOIN ucp.ex_tipo_examen te  ON te.id  = ex.tipo_examen_id
        JOIN ucp.usuarios       u   ON u.id   = et.usuarios_id
        JOIN ucp.oferta_disciplina od ON od.id = et.oferta_disciplina_id
        JOIN ucp.disciplinas    d   ON d.id   = od.disciplinas_id
        JOIN ucp.periodo_letivo pl  ON pl.id  = et.periodo_letivo_id
        JOIN ucp.ano            ano ON ano.id = pl.ano_id
        JOIN ucp.periodo_anual  pa  ON pa.id  = pl.periodo_anual_id
        JOIN ucp.semestre       semestre ON semestre.id = pl.semestre_id
        JOIN ucp.config_filial  cf  ON cf.id  = u.config_filial_id
        WHERE ano.nome = {ano_loop}

        UNION ALL

        -- PARTE 2: TRABALHOS
        SELECT
            ta.id, ta.status,
            ano.nome,
            pa.descricao,
            semestre.nome,
            cf.nome,
            d.id,
            d.nome,
            pl.id,
            u.id,
            999                              AS tipo_examen_id,
            'Trabajo'                        AS tipo_examen,
            ta.created_at                    AS fecha_evaluacion,
            CAST(ta.nota AS DECIMAL(10,2))   AS puntos_logrados,
            'novo'                           AS sistema
        FROM melhor_trabalho ta
        JOIN alumnos_cde        ac  ON ac.usuarios_id = ta.usuarios_id
        JOIN ucp.usuarios       u   ON u.id  = ta.usuarios_id
        JOIN ucp.oferta_disciplina od ON od.id = ta.oferta_disciplina_id
        JOIN ucp.disciplinas    d   ON d.id  = od.disciplinas_id
        JOIN max_pl_trabalho    mpl ON mpl.oferta_disciplina_id = od.id
                                   AND mpl.usuarios_id = u.id
        JOIN ucp.periodo_letivo pl  ON pl.id = mpl.periodo_letivo_id
        JOIN ucp.ano            ano ON ano.id = pl.ano_id
        JOIN ucp.periodo_anual  pa  ON pa.id  = pl.periodo_anual_id
        JOIN ucp.semestre       semestre ON semestre.id = pl.semestre_id
        JOIN ucp.config_filial  cf  ON cf.id  = u.config_filial_id
        WHERE ano.nome = {ano_loop}

        UNION ALL

        -- PARTE 3: COORD_AVALIACAO (sistema antigo)
        SELECT DISTINCT
            c.id, c.status,
            ano.nome,
            pa.descricao,
            semestre.nome,
            cf.nome,
            d.id,
            d.nome,
            pl.id,
            u.id,
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
            f3.nome         AS tipo_examen,
            c.data          AS fecha_evaluacion,
            nv.nota_val     AS puntos_logrados,
            'antigo'        AS sistema
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
        JOIN alumnos_cde            ac     ON ac.usuarios_id = u.id
        LEFT JOIN (
            ucp.matricula_disciplina md
            JOIN ucp.periodo_letivo  pl    ON pl.id  = md.periodo_letivo_id
            JOIN ucp.matricula_curso mc    ON mc.id  = pl.matricula_curso_id
        ) ON md.oferta_disciplina_id = od.id AND mc.usuarios_id = u.id
        LEFT JOIN ucp.ano           ano    ON ano.id  = pl.ano_id
        LEFT JOIN ucp.periodo_anual pa     ON pa.id   = pl.periodo_anual_id
        LEFT JOIN ucp.semestre      semestre ON semestre.id = pl.semestre_id
        LEFT JOIN ucp.config_filial cf     ON cf.id  = u.config_filial_id
        WHERE c.status = 1
          AND ano.nome = {ano_loop}
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
                OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS nota_extraordinaria
        FROM base_unificada b
    ),

    notas_unificadas AS (
        SELECT
            id_alumno,
            id_periodo_lectivo AS id_periodo_vincular,
            id_asignatura,
            MAX(CASE
                WHEN nota_extraordinaria > 0 THEN nota_extraordinaria
                ELSE nota_acumulada_final
            END) AS calificacion_final
        FROM (
            SELECT
                bm.id_alumno,
                bm.id_asignatura,
                bm.id_periodo_lectivo,
                bm.nota_extraordinaria,
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
                    WHEN tipo_examen_id = 15 AND tipo_examen LIKE '%Linea%'                            THEN 0
                    WHEN tipo_examen LIKE '%Proceso Integrado%'
                         AND (
                                (sub_periodo = '1'
                                    AND (fecha_evaluacion < STR_TO_DATE(CONCAT(periodo, '-01-01'), '%Y-%m-%d')
                                         OR fecha_evaluacion >= STR_TO_DATE(CONCAT(periodo, '-07-01'), '%Y-%m-%d')))
                             OR (sub_periodo = '2'
                                    AND (fecha_evaluacion < STR_TO_DATE(CONCAT(periodo, '-07-01'), '%Y-%m-%d')
                                         OR fecha_evaluacion >= STR_TO_DATE(CONCAT(CAST(periodo AS UNSIGNED) + 1, '-01-01'), '%Y-%m-%d')))
                             )                                                                          THEN 0
                    ELSE puntos_logrados
                END) OVER(PARTITION BY id_alumno, id_asignatura, id_periodo_lectivo) AS nota_acumulada_final
            FROM base_com_maximos bm
        ) AS calculo_final
        GROUP BY id_alumno, id_periodo_lectivo, id_asignatura
    )

    SELECT
        m.id AS id_matricula_curso,
        m.created AS created_matricula_curso,
        m.status AS status_matricula_curso,
        m.estrutura_curricular_id,
        e.descricao AS estrutura_curricular,
        u.created AS created_usuario,
        m.usuarios_id,
        u.nome_sobrenome,
        u.ano_id AS id_ano_convocatoria,
        a.nome AS ano_convocatoria,
        u.periodo_anual_id AS id_periodo_convocatoria,
        p2.descricao AS periodo_convocatoria,
        p.id AS id_periodo_letivo,
        p.created AS created_periodo_letivo,
        p.status AS status_periodo_letivo,
        p.ano_id,
        a2.nome AS ano_periodo_letivo,
        p.periodo_anual_id,
        p3.descricao AS periodo_anual_periodo_letivo,
        p.semestre_id AS id_semestre_alumno,
        s.descricao AS semestre_alumno,
        p.config_filial_id AS id_filial_periodo_letivo,
        CASE
            WHEN p.config_filial_id = 1 THEN 'CDE'
            WHEN p.config_filial_id = 2 THEN 'PJC'
            WHEN p.config_filial_id = 3 THEN 'CDE III'
        END AS filial_periodo_letivo,
        md.id AS id_matricula_disciplina,
        o.id AS id_oferta_disciplina,
        o.disciplinas_id,
        d.nome AS disciplina,
        o.turma_id,
        t.nome AS turma,
        o.funcionario_id AS id_docente,
        CONCAT(f.nome, ' ', f.sobrenome) AS docente,
        o.semestre_id AS id_semestre_disciplina,
        s2.descricao AS semestre_disciplina,
        o.tipo_materia_id,
        t2.nome AS tipo_materia,
        o.possui_pratica,
        CASE WHEN o.possui_pratica = 1 THEN 'Teórica/Práctica' ELSE 'Teórica' END AS modalidad_materia,
        n.calificacion_final,
        n_catraca.numero_catraca
    FROM ucp.matricula_curso m
    INNER JOIN alumnos_cde aa ON m.usuarios_id = aa.usuarios_id
    JOIN ucp.periodo_letivo p   ON p.matricula_curso_id = m.id
    JOIN ucp.matricula_disciplina md ON p.id = md.periodo_letivo_id
    JOIN ucp.oferta_disciplina o ON md.oferta_disciplina_id = o.id
    JOIN ucp.usuarios u          ON m.usuarios_id = u.id
    LEFT JOIN ucp.estrutura_curricular e  ON m.estrutura_curricular_id = e.id
    LEFT JOIN ucp.ano a                   ON u.ano_id = a.id
    LEFT JOIN ucp.periodo_anual p2        ON u.periodo_anual_id = p2.id
    LEFT JOIN ucp.ano a2                  ON p.ano_id = a2.id
    LEFT JOIN ucp.periodo_anual p3        ON p.periodo_anual_id = p3.id
    LEFT JOIN ucp.semestre s              ON p.semestre_id = s.id
    LEFT JOIN ucp.disciplinas d           ON o.disciplinas_id = d.id
    LEFT JOIN ucp.turma t                 ON o.turma_id = t.id
    LEFT JOIN ucp.funcionario f           ON o.funcionario_id = f.id
    LEFT JOIN ucp.semestre s2             ON o.semestre_id = s2.id
    LEFT JOIN ucp.tipo_materia t2         ON o.tipo_materia_id = t2.id
    LEFT JOIN notas_unificadas n
           ON n.id_periodo_vincular = p.id
          AND n.id_asignatura       = o.disciplinas_id
          AND n.id_alumno           = m.usuarios_id
    LEFT JOIN (
        SELECT usuarios_id, MAX(numero_catraca) AS numero_catraca
        FROM ucp.numero_catraca
        WHERE usuarios_id IS NOT NULL
        GROUP BY usuarios_id
    ) n_catraca ON n_catraca.usuarios_id = m.usuarios_id
    WHERE m.status != 5
      AND p.status = 1
      AND md.status = 1
      AND o.status = 1
      AND o.disciplinas_id != 216
      AND a2.nome = {ano_loop}
    """


# ─────────────────────────────────────────────
# PROCESSAMENTO ANO A ANO
# ─────────────────────────────────────────────

# Configurações de sessão MySQL para maximizar performance
SESSION_VARS = [
    "SET SESSION sort_buffer_size    = 67108864",   # 64 MB
    "SET SESSION join_buffer_size    = 67108864",   # 64 MB
    "SET SESSION tmp_table_size      = 268435456",  # 256 MB
    "SET SESSION max_heap_table_size = 268435456",  # 256 MB
    "SET SESSION wait_timeout        = 28800",      # 8h
    "SET SESSION interactive_timeout = 28800",      # 8h
    "SET SESSION net_read_timeout    = 3600",       # 1h
    "SET SESSION net_write_timeout   = 3600",       # 1h
]

def processar_ano(ano, pasta_temp):
    print(f"\n{'─'*50}")
    print(f"  [{ano}] Conectando...")

    conn = obtener_conexion()
    if not conn:
        print(f"  [{ano}] ✗ Falha na conexão, pulando.")
        return None

    try:
        cursor = conn.cursor(dictionary=True)

        # Aplica variáveis de sessão para maximizar memória e evitar timeout
        for var in SESSION_VARS:
            try:
                cursor.execute(var)
            except Error:
                pass  # Servidor pode não permitir alguns parâmetros; segue mesmo assim

        print(f"  [{ano}] Executando query...")
        cursor.execute(get_query(ano))

        # Lê em lotes para não explodir a RAM
        BATCH = 10_000
        rows = []
        while True:
            batch = cursor.fetchmany(BATCH)
            if not batch:
                break
            rows.extend(batch)
            print(f"  [{ano}]   ... {len(rows):,} linhas carregadas", end="\r")

        cursor.close()

        if not rows:
            print(f"  [{ano}] ✗ Nenhum dado encontrado.")
            return None

        df = pd.DataFrame(rows)

        # Ordena no pandas — muito mais rápido do que ORDER BY no MySQL
        df = df.sort_values(
            ['ano_periodo_letivo', 'nome_sobrenome', 'disciplina'],
            ascending=[False, True, True]
        ).reset_index(drop=True)

        caminho = os.path.join(pasta_temp, f"matriculas_notas_{ano}.csv")
        df.to_csv(caminho, index=False, sep=";", encoding="utf-8-sig")
        print(f"  [{ano}] ✓ {len(df):,} registros → {caminho}")
        return df

    except Error as e:
        print(f"  [{ano}] ✗ Erro MySQL: {e}")
        return None
    except Exception as e:
        print(f"  [{ano}] ✗ Erro: {e}")
        return None
    finally:
        conn.close()


def processar_anos():
    anos = range(2017, 2027)
    pasta_temp = "assets/data/temp_years"
    pasta_saida = "assets/data"
    os.makedirs(pasta_temp, exist_ok=True)
    os.makedirs(pasta_saida, exist_ok=True)

    lista_dfs = []
    erros = []

    print(f"\n=== EXTRAÇÃO POR ANO ({min(anos)}–{max(anos)}) ===")
    for ano in anos:
        df = processar_ano(ano, pasta_temp)
        if df is not None:
            lista_dfs.append(df)
        else:
            erros.append(ano)

    print(f"\n{'─'*50}")
    if lista_dfs:
        print("Consolidando arquivos parciais...")
        df_final = pd.concat(lista_dfs, ignore_index=True)
        arquivo_csv = os.path.join(
            pasta_saida,
            "Base_Consolidada_Matriculas_Notas_2017_2027.csv"
        )
        df_final.to_csv(arquivo_csv, index=False, sep=";", encoding="utf-8-sig")
        print(f"\n✓ Concluído! {len(df_final):,} registros totais → {arquivo_csv}")
    else:
        print("✗ Nenhum dado válido retornado em nenhum dos anos.")

    if erros:
        print(f"\n⚠ Anos com erro: {erros}")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    processar_anos()


# # ETL - TODOS LOS ALUMNOS

# In[ ]:


import os
import pandas as pd
import numpy as np

# --- DICCIONARIOS DE SOPORTE (Manteniendo todos los grupos originales) ---
MAPEO_GRUPOS = {
    (6, 73, 140): "Anatomía I", (7, 74, 141): "Anatomía II",
    (27, 94, 161): "Anatomía Patológica I", (32, 99, 166): "Anatomía Patológica II",
    (42, 109, 176): "Anestesiología", (10, 77, 144): "Bioestadística",
    (24, 91, 158): "Bioética", (15, 82, 149): "Biofísica",
    (3, 70, 137): "Biología", (14, 81, 148): "Bioquímica I",
    (23, 90, 157): "Bioquímica II", (220, 221, 235): "Bioseguridad",
    (238,): "Cirugía I", (246,): "Cirugía II", (256,): "Cirugía III",
    (53, 120, 187): "Clínica Quirugica I", (57, 124, 191): "Clínica Quirugica II",
    (44, 111, 178): "Dermatología", (5, 72, 139): "Embriología",
    (26, 93, 160): "Epidemiología y Salud Pública", (30, 97, 164): "Farmacología I",
    (33, 100, 167): "Farmacología II", (16, 83, 150): "Fisiología I",
    (21, 88, 155): "Fisiología II", (28, 95, 162): "Fisiopatología I",
    (36, 103, 170): "Fisiopatología II", (18, 85, 152): "Genética Humana",
    (37, 104, 171): "Gestión en Salud", (46, 113, 180): "Gineco–Obstetricia I",
    (54, 121, 188): "Gineco–Obstetricia II", (13, 80, 147): "Guaraní",
    (272, 273): "Guaraní con énfasis a prácticas hospitalarias",
    (50, 117, 184): "Hematología y Hemoterapia", (1, 68, 135): "Histología I",
    (8, 75, 142): "Histología II", (2, 69, 136): "Historia de la Medicina",
    (31, 98, 165): "Imagenología", (243, 244, 245): "Inducción al Preinternado",
    (55, 122, 189): "Infectología", (20, 87, 154): "Inglés Instrumental",
    (17, 84, 151): "Inmunología", (62, 129, 196): "Internado I – Medicina Interna",
    (63, 130, 197): "Internado II – Pediatría", (64, 131, 198): "Internado III – Cirugía",
    (65, 132, 199): "Internado IV – Ginecología", (66, 133, 200): "Internado V – Pasantía",
    (67, 134, 201): "Internado VI – Emergentología", (4, 71, 138): "Lengua Castellana",
    (11, 78, 145): "Medicina Comunitaria", (35, 102, 169): "Medicina de la Familia",
    (45, 112, 179): "Medicina Interna I", (51, 118, 185): "Medicina Interna II",
    (58, 125, 192): "Medicina Interna III", (29, 96, 163): "Medicina Legal",
    (247,): "Medicina Tropical y Enfermedades Infecciosas",
    (9, 76, 143): "Metodología de la Investigación", (19, 86, 153): "Microbiología I",
    (22, 89, 156): "Microbiología II", (49, 116, 183): "Neumología",
    (38, 105, 172): "Neurología", (25, 92, 159): "Nutrición",
    (39, 106, 173): "Oftalmología", (59, 126, 193): "Oncología",
    (225, 231, 252, 258, 260, 266, 262): "Optativa I",
    (228, 232, 253, 268, 269, 270, 263): "Optativa II",
    (240, 254, 264, 267): "Optativa III", (255, 265): "Optativa IV",
    (41, 108, 175): "Ortopedia y Traumatología", (60, 127, 194): "Otorrinolaringología",
    (52, 119, 186): "Pediatría I", (56, 123, 190): "Pediatría II",
    (239, 275): "Primeros Auxilios", (248,): "Principios Básicos de Anestesia en Urgencias Médicas",
    (12, 79, 146): "Psicología en Salud", (48, 115, 182): "Psiquiatría",
    (229,): "Redacción y Discusión de Trabalho Científico", (257,): "Rehabilitación",
    (61, 128, 195): "Salud Pública - Mercosur", (259,): "Seminario Integrador I",
    (34, 101, 168): "Semiología Médica I", (40, 107, 174): "Semiología Médica II",
    (219, 233, 234): "Titulación", (43, 110, 177): "Toxicología", (47, 114, 181): "Urología"
}
MAPA_DISCIPLINAS = {idx: nombre for ids, nombre in MAPEO_GRUPOS.items() for idx in ids}
DICCIONARIO_STATUS = {1: 'Activo', 2: 'Finalizado', 3: 'Trancado', 4: 'Suspenso'}
IDS_EXTRACURRICULARES = [221, 235, 220, 243, 245, 244, 272, 273]

# --- FUNCIONES DE LÓGICA ACADÉMICA ---

def calcular_ciclo_academico(row):
    """Calcula la cohorte inicial y final basada en el ingreso."""
    try:
        ano = int(row['ano_periodo_letivo'])
        sem_anual = int(row['periodo_anual_periodo_letivo'])
        sem_carreira = int(row['semestre_alumno'])

        # Retroceder linealmente hasta el semestre 1
        contagem_inicial = ((ano * 2) + (sem_anual - 1)) - (sem_carreira - 1)

        # Formatear Cohorte Inicial
        ano_ini = contagem_inicial // 2
        sem_ini = (contagem_inicial % 2) + 1
        c_inicial = f"{ano_ini}.{sem_ini}"

        # Calcular Cohorte Final (Suma de 11 periodos adicionales para completar 6 años)
        contagem_final = contagem_inicial + 11
        ano_fim = contagem_final // 2
        sem_fim = (contagem_final % 2) + 1
        c_final = f"{ano_fim}.{sem_fim}"

        return pd.Series([c_inicial, c_final])
    except:
        return pd.Series([None, None])

def verificar_trayectoria_blindada(group):
    """Verifica si el alumno es Regular o Irregular basado en saltos de tiempo o semestre."""
    # Convertir a numérico antes de procesar para evitar el TypeError
    group['ano_periodo_letivo'] = pd.to_numeric(group['ano_periodo_letivo'], errors='coerce')
    group['periodo_anual_periodo_letivo'] = pd.to_numeric(group['periodo_anual_periodo_letivo'], errors='coerce')
    group['semestre_alumno'] = pd.to_numeric(group['semestre_alumno'], errors='coerce')

    historico_unico = group.drop_duplicates(subset=['ano_periodo_letivo', 'periodo_anual_periodo_letivo']).sort_values(by=['ano_periodo_letivo', 'periodo_anual_periodo_letivo'])

    if historico_unico.empty: return 'Irregular'

    semestres_aluno = historico_unico['semestre_alumno'].tolist()
    anos = historico_unico['ano_periodo_letivo'].tolist()
    periodos_anuais = historico_unico['periodo_anual_periodo_letivo'].tolist()

    # --- REGLA 1: Sequencia de Semestre ---
    primeiro_semestre = semestres_aluno[0]
    sequencia_esperada = list(range(int(primeiro_semestre), int(primeiro_semestre) + len(semestres_aluno)))
    if [int(s) for s in semestres_aluno] != sequencia_esperada:
        return 'Irregular'

    # --- REGLA 2: Sequencia de Calendário (Lineal) ---
    contagem_linear = [(int(a) * 2) + (int(p) - 1) for a, p in zip(anos, periodos_anuais)]
    for i in range(len(contagem_linear) - 1):
        if contagem_linear[i+1] - contagem_linear[i] != 1:
            return 'Irregular'

    return 'Regular'

# --- FLUJO PRINCIPAL ---

def ejecutar_sistema():
    print("Extrayendo datos...")

    df = pd.read_csv("assets/data/Base_Consolidada_Matriculas_Notas_2017_2027.csv", sep=';')

    # 1. Tratamiento inicial de tipos y nulos
    cols_numericas = ['usuarios_id', 'id_periodo_letivo', 'semestre_alumno', 
                      'ano_periodo_letivo', 'periodo_anual_periodo_letivo', 'status_matricula_curso']
    for col in cols_numericas:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['calificacion_final'] = pd.to_numeric(df['calificacion_final'], errors='coerce').fillna(0)

    # Limpieza de nombres
    for col in ['nome_sobrenome', 'docente']:
        df[col] = df[col].str.strip().str.replace(r'\s+', ' ', regex=True).str.title()

    # 2. Mapeos de Disciplinas y Tipo
    df['disciplina'] = df['disciplinas_id'].map(MAPA_DISCIPLINAS)
    df['tipo_disciplina'] = np.where(df['disciplinas_id'].isin(IDS_EXTRACURRICULARES), 'Extracurricular', 'Regular')

    # 3. Lógica de Aprobación y Escala 1-5
    cond_aprob = [
        (df['tipo_disciplina'] == 'Regular') & (df['calificacion_final'] >= 60),
        (df['tipo_disciplina'] == 'Extracurricular') & (df['calificacion_final'] >= 20)
    ]
    df['resultado_final'] = np.select(cond_aprob, ['APROBADO', 'APROBADO'], default='REPROBADO')

    cond_escala = [
        (df['tipo_disciplina'] == 'Regular') & (df['calificacion_final'] <= 59),
        (df['tipo_disciplina'] == 'Regular') & (df['calificacion_final'] <= 69),
        (df['tipo_disciplina'] == 'Regular') & (df['calificacion_final'] <= 80),
        (df['tipo_disciplina'] == 'Regular') & (df['calificacion_final'] <= 90),
        (df['tipo_disciplina'] == 'Regular') & (df['calificacion_final'] > 90)
    ]
    df['calificacion_final_1a5'] = np.select(cond_escala, [1, 2, 3, 4, 5], default=0)

    # 4. Análisis de Trayectoria y Status de Alumno
    df = df.sort_values(by=['usuarios_id', 'id_periodo_letivo'])

    # Determinar primer periodo y status (Nuevo/Antiguo)
    menor_periodo = df.groupby('usuarios_id')['id_periodo_letivo'].transform('min')
    df['status_aluno'] = np.where(df['id_periodo_letivo'] == menor_periodo, 'N', 'A')

    # Tipo de Ingreso (basado en el registro 'N')
    df_n = df[df['status_aluno'] == 'N'].copy()
    df_n['tipo_ingresso'] = np.where(df_n['semestre_alumno'] == 1, 'Normal', 'Convalidado')

    # 5. Cálculo de Cohortes
    df_n[['ano_inicial_coorte', 'ano_final_coorte']] = df_n.apply(calcular_ciclo_academico, axis=1)

    # Mapear de vuelta al DF principal
    mapas = df_n.set_index('usuarios_id')[['tipo_ingresso', 'ano_inicial_coorte', 'ano_final_coorte']].to_dict()
    df['tipo_ingresso'] = df['usuarios_id'].map(mapas['tipo_ingresso'])
    df['ano_inicial_coorte'] = df['usuarios_id'].map(mapas['ano_inicial_coorte'])
    df['ano_final_coorte'] = df['usuarios_id'].map(mapas['ano_final_coorte'])
    df['cohorte'] = df['ano_inicial_coorte'].astype(str) + " - " + df['ano_final_coorte'].astype(str)

    # 6. Trayectoria Académica y Status Actual
    trayectorias = df.groupby('usuarios_id').apply(verificar_trayectoria_blindada).to_dict()
    df['trayectoria_academica'] = df['usuarios_id'].map(trayectorias)

    df['status_curso_actual'] = df.groupby('usuarios_id')['status_matricula_curso'].transform('last')
    df['nombre_status_actual'] = df['status_curso_actual'].map(DICCIONARIO_STATUS).fillna('No informado')

    # 7. Cruce con Egresados
    try:
        df_egr = pd.read_excel(r'assets\data\egressados.xlsx')
        df_egr['periodo_egresso_format'] = (
        df_egr['Año de Egreso'].astype(str) + '.' + df_egr['Periodo de Egreso'].astype(str))

        df_egr = df_egr.rename(columns={
            'Año de Egreso': 'ano_egresso', 'Periodo de Egreso': 'periodo_egresso','Titulado': 'estado_titulacion', 
            'Fecha de titulación': 'fecha_titulacion', 'DETALLE': 'detalle'
        })
        df = pd.merge(df, df_egr[['usuarios_id', 'ano_egresso','periodo_egresso','periodo_egresso_format', 'estado_titulacion', 'fecha_titulacion', 'detalle']], on='usuarios_id', how='left')

        df['fecha_titulacion'] = pd.to_datetime(df['fecha_titulacion'])
        df['fecha_titulacion'] = df['fecha_titulacion'].dt.strftime('%d/%m/%Y')


        df['periodo_egresso_format'] = df['periodo_egresso_format'].astype(str)
        df['estado_titulacion'] = df['estado_titulacion'].astype(str)
        df['fecha_titulacion'] = pd.to_datetime(df['fecha_titulacion'], dayfirst=True, errors='coerce')

    except Exception as e:
        print(f"Aviso: No se pudo cruzar con egresados: {e}")

    # 8. Exportación
    os.makedirs('assets/data', exist_ok=True)

    # alumnos_v1 — todos os dados
    df.to_csv('assets/data/alumnos_v1.csv', index=False, encoding='utf-8-sig')
    print(f"alumnos_v1 exportado: {len(df)} registros.")

    print("Exportación completada con éxito.")

if __name__ == "__main__":
    ejecutar_sistema()


# # ETL - ALUMNOS CON CORTE

# In[1]:


import os
import pandas as pd
import numpy as np

# 8. Exportación
os.makedirs('assets/data', exist_ok=True)

# alumnos_v1 — leitura do arquivo já gerado
df = pd.read_csv('assets/data/alumnos_v1.csv', encoding='utf-8-sig')
print(f"alumnos_v1 carregado: {len(df)} registros.")

# alumnos_v2 — apenas alunos presentes no base_datos_activos
base_activos = pd.read_csv('assets/data/base_datos_activos.csv', encoding='utf-8-sig')
df_v2 = df.merge(
    base_activos[['ID_Alumno']],
    left_on='usuarios_id',
    right_on='ID_Alumno',
    how='inner'
).drop(columns=['ID_Alumno'])

# -------------------------------------------------------------------
# Correção: 10 alunos com período/semestre incorreto ou ausente em 2026.1
# Atualiza TODAS as linhas do usuario_id + id_periodo_letivo informado
# Semestre conforme base_datos_activos (Excel de Sara)
# -------------------------------------------------------------------
correcoes = [
    # Semestre 11
    {'usuarios_id': 8133,  'id_periodo_letivo': 142561, 'id_semestre_alumno': 11, 'semestre_alumno': 11, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Tatiana Machado Campelo
    {'usuarios_id': 9204,  'id_periodo_letivo': 141686, 'id_semestre_alumno': 11, 'semestre_alumno': 11, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Melissa Oliveira Brito
    {'usuarios_id': 10092, 'id_periodo_letivo': 122294, 'id_semestre_alumno': 11, 'semestre_alumno': 11, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Enola Leandro Silva Mesquita
    {'usuarios_id': 10662, 'id_periodo_letivo': 163683, 'id_semestre_alumno': 11, 'semestre_alumno': 11, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Najana Cardoso De Araujo
    # Semestre 12
    {'usuarios_id': 7223,  'id_periodo_letivo': 165160, 'id_semestre_alumno': 12, 'semestre_alumno': 12, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Crislayne De Azevedo Lemos
    {'usuarios_id': 9435,  'id_periodo_letivo': 121346, 'id_semestre_alumno': 12, 'semestre_alumno': 12, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Edna De Oliveira Lima
    {'usuarios_id': 10077, 'id_periodo_letivo': 161489, 'id_semestre_alumno': 12, 'semestre_alumno': 12, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Leandro Dos Santos Pereira
    {'usuarios_id': 10756, 'id_periodo_letivo': 160573, 'id_semestre_alumno': 12, 'semestre_alumno': 12, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Audréia Damiana Silva Antonello Pereira
    {'usuarios_id': 11168, 'id_periodo_letivo': 132540, 'id_semestre_alumno': 12, 'semestre_alumno': 12, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Camilla Cristiane Azevedo Marinho
    {'usuarios_id': 11449, 'id_periodo_letivo': 161488, 'id_semestre_alumno': 12, 'semestre_alumno': 12, 'ano_periodo_letivo': 2026, 'periodo_anual_id': 1, 'periodo_anual_periodo_letivo': 1},  # Francieli De Mello Hesper
]

for correcao in correcoes:
    id_alumno      = correcao['usuarios_id']
    id_periodo     = correcao['id_periodo_letivo']

    mask = (df_v2['usuarios_id'] == id_alumno) & (df_v2['id_periodo_letivo'] == id_periodo)
    linhas = mask.sum()

    if linhas == 0:
        print(f"⚠️  ID {id_alumno} / periodo {id_periodo} não encontrado no df_v2, pulando.")
        continue

    # Atualiza todos os campos nas linhas encontradas
    campos = {k: v for k, v in correcao.items() if k not in ('usuarios_id', 'id_periodo_letivo')}
    for campo, valor in campos.items():
        if campo in df_v2.columns:
            df_v2.loc[mask, campo] = valor

    print(f"✅  ID {id_alumno} — {linhas} linha(s) atualizadas para 2026.1 semestre {correcao['semestre_alumno']}.")

# -------------------------------------------------------------------

df_v2.to_csv('assets/data/alumnos_v2.csv', index=False, encoding='utf-8-sig')
print(f"alumnos_v2 exportado: {len(df_v2)} registros.")

print("Exportación completada con éxito.")

