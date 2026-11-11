#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# -----------------------------------------------------------------------------
# NUEVA QUERY - 03/05/2026
# -----------------------------------------------------------------------------

import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DE CONEXÕES (COM QUOTE_PLUS E DOTENV)
# -----------------------------------------------------------------------------
load_dotenv()

# Base BIOMETRIA
pg_user = quote_plus(os.getenv("PG_USER", ""))
pg_password = quote_plus(os.getenv("PG_PASSWORD", ""))
pg_host = os.getenv("PG_HOST")
pg_port = os.getenv("PG_PORT")
pg_db = os.getenv("PG_DB")

# Base SYSEDUCA
mysql_user_sys = quote_plus(os.getenv("MYSQL_USER_SYS", ""))
mysql_password_sys = quote_plus(os.getenv("MYSQL_PASSWORD_SYS", ""))
mysql_host_sys = os.getenv("MYSQL_HOST_SYS")
mysql_port_sys = os.getenv("MYSQL_PORT_SYS", "3306")
mysql_db_sys = os.getenv("MYSQL_DB_SYS")

# Base BICDE para guardar los datos
mysql_user_bicde = quote_plus(os.getenv("MYSQL_USER_BICDE", ""))
mysql_password_bicde = quote_plus(os.getenv("MYSQL_PASSWORD_BICDE", ""))
mysql_host_bicde = os.getenv("MYSQL_HOST_BICDE")
mysql_port_bicde = os.getenv("MYSQL_PORT_BICDE", "3306")
mysql_db_bicde = os.getenv("MYSQL_DB_BICDE")

pg_engine = create_engine(f"postgresql+psycopg2://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}")
mysql_engine_sys = create_engine(f"mysql+mysqlconnector://{mysql_user_sys}:{mysql_password_sys}@{mysql_host_sys}:{mysql_port_sys}/{mysql_db_sys}")
mysql_engine_bicde = create_engine(f"mysql+mysqlconnector://{mysql_user_bicde}:{mysql_password_bicde}@{mysql_host_bicde}:{mysql_port_bicde}/{mysql_db_bicde}")

# -----------------------------------------------------------------------------
# 2. DEFINIÇÃO DAS QUERIES
# -----------------------------------------------------------------------------
query_assistencia = """
SELECT 
    p.attendee_id,
    p2.planificacion_id,
    p3.active AS planificacion_activa,
    -- TOTAIS TEÓRICAS (Regra: grupo_id = 4)
    COUNT(CASE WHEN p.grupo_id = 4 AND paa.asistencia != 99 THEN 1 END) AS clases_teoricas,
    COUNT(CASE WHEN p.grupo_id = 4 AND paa.asistencia = 1 THEN 1 END) AS presentes_teoricas,
    COUNT(CASE WHEN p.grupo_id = 4 AND paa.asistencia = 2 THEN 1 END) AS ausentes_teoricas,
    COUNT(CASE WHEN p.grupo_id = 4 AND paa.asistencia = 3 THEN 1 END) AS ausentes_justificadas_teoricas,
    -- TOTAIS PRÁTICAS (Regra: grupo_id != 4)
    COUNT(CASE WHEN p.grupo_id != 4 AND paa.asistencia != 99 THEN 1 END) AS clases_practicas,
    COUNT(CASE WHEN p.grupo_id != 4 AND paa.asistencia = 1 THEN 1 END) AS presentes_practicas,
    COUNT(CASE WHEN p.grupo_id != 4 AND paa.asistencia = 2 THEN 1 END) AS ausentes_practicas,
    COUNT(CASE WHEN p.grupo_id != 4 AND paa.asistencia = 3 THEN 1 END) AS ausentes_justificadas_practicas
FROM planificacion_horario_attendee p
JOIN planificacionhorario p2 ON p.planificacion_horario_id = p2.id
JOIN planificacion p3 ON p2.planificacion_id = p3.id
JOIN planilla_asistencia_alumnos paa ON paa.planificacion_horario_id = p2.id 
    AND paa.attendee_id = p.attendee_id
WHERE 1 = 1
  AND paa.fecha <= CURRENT_DATE -- Garante que só conta aulas passadas ou de hoje
  AND paa.active = true         
GROUP BY 
    p.attendee_id, 
    p2.planificacion_id, 
    p3.active
ORDER BY p2.planificacion_id;
"""

query_biometria_seccion = """
select 
    p.attendee_id, a3.system_id, concat(a3.first_name, ' ', a3.last_name) as alumno, 
    p.grupo_id, g."name" as grupo, a."name" as aula,
    concat(a2.first_name, ' ', a2.last_name) as docente, 
    p3.anho, s2."name" as periodo, c."name" as asignatura, s."name" as seccion,
    l."name" as lugar, p3.start_date, p3.end_date,
    p3.course_id, p3.seccion_id as seccion_id_bio, p3.semestre_id as semestre_id_bio,
    p2.planificacion_id, t."name" as tipo_clase
from planificacion_horario_attendee p 
join planificacionhorario p2 on p.planificacion_horario_id = p2.id
join planificacion p3 on p2.planificacion_id = p3.id
join grupo g on p.grupo_id = g.id
join course c on p3.course_id = c.id
join seccion s on p3.seccion_id = s.id
join aula a on p2.aula_id = a.id
join attendee a2 on p2.teacher_id = a2.id
join semestre s2 on p3.semestre_id = s2.id
join lugar l on p3.lugar_id = l.id
join tipoactividad t on p2.tipo_actividad_id = t.id
join attendee a3 on p.attendee_id = a3.id
join planificacion_attendee pa on  p2.planificacion_id = pa.planificacion_id and p.attendee_id = pa.attendee_id
where pa.active = true and p3.anho = 2026 and p3.semestre_id IN (2, 3) -- 2 = Semestre 1 (2026.1), 3 = Semestre 2 (2026.2)
"""

# --- QUERY ES_PRACTICA (16/09/2026) ---
# Não depende de planificacion_horario_attendee (grupo/horário atribuído ao aluno),
# só de o aluno estar ATIVO na planificación (planificacion_attendee) e essa
# planificación ter algum bloco de horário (planificacionhorario) de tipo prático.
# Motivo: descobrimos milhares de alunos ativos em bloco de Prática sem grupo/horário
# atribuído ainda na Biometria (ex.: Anatomía I 2026.2) — usando grupo_id essses casos
# ficavam incorretamente como "só teórica". Os tipos abaixo (Practicas/CONSULTORIO/
# SIMULACIÓN) foram os que, historicamente, quase sempre (>98%) usam grupo != Teórica;
# Plataforma/Optativas quase sempre usam grupo Teórica, por isso ficam de fora.
query_practica_biometria = """
select distinct
    a3.system_id, c."name" as asignatura, s."name" as seccion,
    p3.anho, s2."name" as periodo
from planificacion_attendee pa
join attendee a3 on pa.attendee_id = a3.id
join planificacion p3 on pa.planificacion_id = p3.id
join planificacionhorario p2 on p2.planificacion_id = p3.id
join tipoactividad t on p2.tipo_actividad_id = t.id
join course c on p3.course_id = c.id
join seccion s on p3.seccion_id = s.id
join semestre s2 on p3.semestre_id = s2.id
where pa.active = true and p3.anho = 2026 and p3.semestre_id IN (2, 3)
  and t."name" IN ('Practicas', 'CONSULTORIO', 'SIMULACIÓN')
"""

query_syseduca = """
WITH temp1 AS (
    SELECT md.id AS matricula_disciplina_id, md.oferta_disciplina_id, md.periodo_letivo_id,
        ofe.disciplinas_id, ofe.turma_id, dis.nome AS disciplina_nombre,
        dis.semestre_id AS semestre_disciplina_id, se.nome AS semestre_disciplina,
        se.descricao AS semestre_disciplina_nro, tu.nome AS seccion_nombre, ofe.possui_pratica as es_practica
    FROM ucp.matricula_disciplina md
    JOIN ucp.oferta_disciplina ofe ON md.oferta_disciplina_id = ofe.id
    JOIN ucp.disciplinas dis ON ofe.disciplinas_id = dis.id
    JOIN ucp.turma tu ON ofe.turma_id = tu.id
    JOIN ucp.semestre se ON dis.semestre_id = se.id
    WHERE md.config_filial_id IN (1,3) AND md.status = 1 AND se.descricao NOT IN (11,12)
      AND dis.id NOT IN (220, 221, 235, 243, 244, 245)
),
temp2 AS (
    SELECT t1.*, pl.ano_id, ano.nome AS ano, pl.periodo_anual_id, pa.nome AS periodo_anual,
        pl.semestre_id AS semestre_alumno_id, se.nome AS semestre_alumno, se.descricao AS semestre_nro, pl.matricula_curso_id
    FROM temp1 t1
    JOIN ucp.periodo_letivo pl ON t1.periodo_letivo_id = pl.id
    JOIN ucp.periodo_anual pa ON pl.periodo_anual_id = pa.id
    JOIN ucp.ano ano ON pl.ano_id = ano.id
    JOIN ucp.semestre se ON pl.semestre_id = se.id
    WHERE pl.ano_id IN (9,30) AND pl.periodo_anual_id IN (1,2,5,6) AND pl.status = 1 and se.descricao NOT IN (11,12)
    -- periodo_anual_id: 1/5 = Febrero (2026.1) e 2/6 = Agosto (2026.2), para os filiais 1 e 3
),
temp3 AS (
    SELECT t2.*, mc.usuarios_id, mc.status as status_alumno, us.nome_sobrenome, nc.numero_catraca
    FROM temp2 t2
    JOIN ucp.matricula_curso mc ON t2.matricula_curso_id = mc.id
    JOIN ucp.usuarios us ON mc.usuarios_id = us.id
    JOIN ucp.numero_catraca nc ON us.id = nc.usuarios_id
    WHERE mc.status = 1
)
SELECT * FROM temp3
WHERE UPPER(nome_sobrenome) NOT LIKE '%TEST%' AND UPPER(nome_sobrenome) NOT LIKE '%PRUEBA%'
"""

# =============================================================================
# ANÁLISIS: EXCLUSIÓN DE ALUMNOS INACTIVOS EN 2026.2 (11/11/2026)
# =============================================================================
# OBJETIVO
#   Sacar del BI a los alumnos de 2026.2 que están matriculados pero no tienen
#   actividad académica real en el período.
#
# REGLA: se excluye al alumno que cumple LAS DOS condiciones a la vez
#   (a) No rindió ningún Parcial ni Regularización/Recuperatoria de Parcial
#       en 2026.2 (Syseduca), Y
#   (b) No tiene ninguna asistencia en 2026.2, o su última asistencia es
#       hasta el 31/08/2026 (Biometría).
#
# CÓMO SE MIDE CADA CONDICIÓN
#   (a) Parcial rendido = tiene nota en ucp.ex_tentativa en un examen de tipo
#       2, 3, 5, 6, 10 u 11 (ucp.ex_tipo_examen) dentro del período 2026.2.
#       Los intentos sin nota no cuentan. Se usa solo ex_tentativa porque en
#       2026.2 el campo coord_avaliacao.notas está vacío en los parciales.
#   (b) Asistencia = registro con asistencia = 1 (presente) en
#       planilla_asistencia_alumnos. Ausencias (2) y ausencias justificadas (3)
#       no cuentan. Se toma la ÚLTIMA fecha de presencia del alumno.
#
# CRITERIO POR ALUMNO, NO POR MATERIA
#   Basta un parcial o una presencia posterior al 31/08 en CUALQUIER materia
#   para que el alumno permanezca con todas sus materias.
#
# POR QUÉ NO SE EXCLUYEN TODOS LOS QUE NO RINDIERON PARCIAL
#   Muchos alumnos sin parcial siguen asistiendo a clases después del 31/08;
#   como cumplen solo la condición (a), permanecen en el BI.
#
# RESULTADO CON LOS DATOS DEL 11/11/2026 (referencia; cambia en cada corrida)
#   Alumnos activos en 2026.2 (Syseduca) ........................... 6.979
#   Sin ningún parcial (condición a) ...............................   215
#     - Con asistencia después del 31/08  -> PERMANECEN ............   161
#     - Con asistencia solo hasta el 31/08 -> EXCLUIDOS ............    37
#     - Sin ninguna asistencia             -> EXCLUIDOS ............    16
#     - Sin planificación activa en Biometría -> EXCLUIDO ..........     1
#   TOTAL EXCLUIDOS ................................................    54
#
# EFECTO EN EL ETL
#   El filtro se aplica sobre df_sys ANTES de la validación, por eso los
#   excluidos desaparecen de diferencias_sys_bio y de resumen_asistencias.
#   Las filas de 2026.1 de esos alumnos no se tocan.
#   Cada corrida imprime este mismo resumen con los números del día y genera
#   alumnos_excluidos_inactivos_DD-MM-YYYY.csv con el detalle y el motivo.
# =============================================================================

# --- PARÁMETROS DE LA EXCLUSIÓN ---
PERIODO_EXCLUSION = '2026.2'
FECHA_CORTE_ASISTENCIA = '2026-08-31'
# ucp.ex_tipo_examen: 2 = 1º Parcial Ordinaria, 3 = 1º Parcial Recuperatória, 5 = 2º Parcial Ordinaria,
# 6 = 2º Parcial Recuperatória, 10 = 1º Regularizacion, 11 = 2° Regularizacion
TIPOS_EXAMEN_PARCIAL = (2, 3, 5, 6, 10, 11)

# (a) Alumnos que rindieron algún parcial/regularización en 2026.2 (Syseduca).
# En 2026.2 las notas de parcial están todas en ex_tentativa (coord_avaliacao.notas está vacío
# en las evaluaciones de ese período). Un intento sin nota (status 3) no cuenta como rendido.
query_parciales_syseduca = f"""
SELECT DISTINCT et.usuarios_id
FROM ucp.ex_tentativa et
JOIN ucp.ex_examen ex ON ex.id = et.ex_examen_id
JOIN ucp.periodo_letivo pl ON pl.id = et.periodo_letivo_id
WHERE ex.tipo_examen_id IN {TIPOS_EXAMEN_PARCIAL}
  AND (et.nota IS NOT NULL OR et.nota_decimal IS NOT NULL)
  AND pl.ano_id IN (9,30) AND pl.periodo_anual_id IN (2,6)   -- 2026.2 (Agosto), filiales 1 y 3
"""

# (b) Última presencia (asistencia = 1) de cada alumno en 2026.2 (Biometría), en cualquier materia.
# Se agrupa por system_id porque existen attendees duplicados para un mismo alumno.
query_ultima_presencia = """
select a3.system_id, max(paa.fecha) as ultima_presencia
from planilla_asistencia_alumnos paa
join planificacionhorario p2 on paa.planificacion_horario_id = p2.id
join planificacion p3 on p2.planificacion_id = p3.id
join attendee a3 on paa.attendee_id = a3.id
where p3.anho = 2026 and p3.semestre_id = 3      -- 3 = Semestre 2 (2026.2)
  and paa.active = true
  and paa.asistencia = 1                         -- 1 = presente
  and paa.fecha <= CURRENT_DATE
  and a3.system_id is not null
group by a3.system_id
"""

# -----------------------------------------------------------------------------
# 3. EXTRAÇÃO DOS DADOS
# -----------------------------------------------------------------------------
df_assistencia = pd.read_sql_query(query_assistencia, pg_engine)
df_bio = pd.read_sql_query(query_biometria_seccion, pg_engine)
df_practica_bio = pd.read_sql_query(query_practica_biometria, pg_engine)
df_sys = pd.read_sql_query(query_syseduca, mysql_engine_sys)
df_parciales = pd.read_sql_query(query_parciales_syseduca, mysql_engine_sys)
df_presencia = pd.read_sql_query(query_ultima_presencia, pg_engine)

# -----------------------------------------------------------------------------
# 4. PREPARAÇÃO, LIMPEZA E AGRUPAMENTO DE GRUPOS (g."name")
# -----------------------------------------------------------------------------
# Mapeamento de status e correção ortográfica básica no Syseduca
df_sys['status_alumno'] = df_sys['status_alumno'].map({1: 'Activo', 2: 'Finalizado', 3: 'Trancado', 4: 'Suspendido', 5: 'Eliminado'})
df_sys["disciplina_nombre"] = df_sys["disciplina_nombre"].str.replace("Quirugica", "Quirurgica", regex=False)

# Criação das chaves normalizadas (Maiúsculas, sem espaços e com traços/pontuação padronizados)
def normalizar_disc(serie):
    s = serie.astype(str).str.strip().str.upper()
    # unifica travessão (– U+2013), traço-em (— U+2014) e afins com o hífen normal (- U+002D),
    # porque o Syseduca grava "Gineco–Obstetricia" e a Biometria "Gineco-Obstetricia"
    s = s.str.replace(r'[‒-―]', '-', regex=True)
    s = s.str.replace(r'\s*-\s*', '-', regex=True)   # "GINECO - OBSTETRICIA" -> "GINECO-OBSTETRICIA"
    s = s.str.replace(r'\s+', ' ', regex=True)        # colapsa espaços internos
    return s.str.strip()

df_sys['disc_key'] = normalizar_disc(df_sys['disciplina_nombre'])
df_sys['sec_key'] = df_sys['seccion_nombre'].astype(str).str.strip().str.upper()

df_bio['disc_key'] = normalizar_disc(df_bio['asignatura'])
df_bio['sec_key'] = df_bio['seccion'].astype(str).str.strip().str.upper()

# --- CORREÇÃO DE NOMES DIVERGENTES ---
correcoes_nomes = {
    "SEMINARIO INTEGRADOR": "SEMINARIO INTEGRADOR I"
}
df_bio['disc_key'] = df_bio['disc_key'].replace(correcoes_nomes)

# --- CHAVE DE PERÍODO (2026.1 / 2026.2) ---
# Febrero = Semestre 1 e Agosto = Semestre 2 (mesma correspondência usada para filtrar
# as queries). Necessário para que a validação não compare disciplinas de períodos diferentes.
df_sys['periodo_key'] = df_sys['ano'].astype(str) + '.' + df_sys['periodo_anual'].map({'Febrero': '1', 'Agosto': '2'})
df_bio['periodo_key'] = df_bio['anho'].astype(str) + '.' + df_bio['periodo'].map({'Semestre 1': '1', 'Semestre 2': '2'})

# --- EXCLUSIÓN DE ALUMNOS INACTIVOS EN 2026.2 (11/11/2026) ---
# Ver la regla en el bloque "ANÁLISIS: EXCLUSIÓN DE ALUMNOS INACTIVOS EN 2026.2".
# Se aplica sobre df_sys ANTES de la validación, por eso esos alumnos desaparecen de los dos
# reportes (diferencias_sys_bio y resumen_asistencias). Sus filas de 2026.1 no se tocan.
ids_con_parcial = set(df_parciales['usuarios_id'].dropna().astype(int))

df_presencia['ultima_presencia'] = pd.to_datetime(df_presencia['ultima_presencia'])
ids_con_presencia_posterior = set(
    df_presencia.loc[
        df_presencia['ultima_presencia'] > pd.Timestamp(FECHA_CORTE_ASISTENCIA), 'system_id'
    ].dropna().astype(int)
)

mask_excluir = (
    (df_sys['periodo_key'] == PERIODO_EXCLUSION)
    & ~df_sys['usuarios_id'].isin(ids_con_parcial)               # (a) sin parcial/regularización
    & ~df_sys['usuarios_id'].isin(ids_con_presencia_posterior)   # (b) sin presencia después del corte
)

# Guarda quiénes salieron (para auditoría; se exporta a CSV en la sección 7)
df_excluidos = (
    df_sys.loc[mask_excluir, ['usuarios_id', 'nome_sobrenome', 'numero_catraca', 'semestre_alumno',
                              'ano', 'periodo_anual', 'disciplina_nombre', 'seccion_nombre']]
    .merge(df_presencia.rename(columns={'system_id': 'usuarios_id'}), on='usuarios_id', how='left')
)
df_excluidos['motivo'] = np.where(
    df_excluidos['ultima_presencia'].isna(),
    'Sin parcial y sin ninguna asistencia',
    'Sin parcial y con asistencia solo hasta ' + pd.Timestamp(FECHA_CORTE_ASISTENCIA).strftime('%d/%m/%Y')
)

# Resumen del análisis con los números de esta corrida (mismo cuadro del encabezado)
_ids_periodo = set(df_sys.loc[df_sys['periodo_key'] == PERIODO_EXCLUSION, 'usuarios_id'])
_ids_sin_parcial = _ids_periodo - ids_con_parcial
_ids_permanecen = _ids_sin_parcial & ids_con_presencia_posterior
_excl_por_motivo = df_excluidos.drop_duplicates('usuarios_id')['motivo'].value_counts()

print("-" * 70)
print(f"ANÁLISIS DE ALUMNOS INACTIVOS EN {PERIODO_EXCLUSION}")
print(f"  Alumnos activos en Syseduca: {len(_ids_periodo)}")
print(f"  Sin ningún parcial ni regularización: {len(_ids_sin_parcial)}")
print(f"    - Con asistencia después del {pd.Timestamp(FECHA_CORTE_ASISTENCIA).strftime('%d/%m/%Y')} (permanecen): {len(_ids_permanecen)}")
for _motivo, _n in _excl_por_motivo.items():
    print(f"    - {_motivo} (excluidos): {_n}")
print(f"  TOTAL EXCLUIDOS: {df_excluidos['usuarios_id'].nunique()} alumnos / "
      f"{int(mask_excluir.sum())} matrículas en disciplinas")
print("-" * 70)

df_sys = df_sys[~mask_excluir].copy()

# --- Seminario Integrador III em 2026.2 (16/09/2026) ---
# A exclusão dessa disciplina em 2026.2 foi REVERTIDA: houve um erro por parte de
# Atención al Alumno na matrícula de Seminario Integrador III nesse período — os
# alumnos matriculados incorretamente nessa disciplina devem ser ELIMINADOS
# (dados de matrícula corrigidos na origem/Syseduca), e não filtrados aqui no script.
# A disciplina volta a ser processada normalmente nos dois períodos (2026.1 e 2026.2).

# --- Optativa I em 2026.2 (16/09/2026) ---
# Também é erro de matrícula da Atención al Alumno, não falha de cruzamento: em 2026.2
# só a sección J de Optativa I tem planificación cadastrada na Biometria. Os alumnos
# matriculados em Syseduca nas sección G/H/I/E (~192 alumnos) não têm planificación
# nenhuma criada lá — por isso aparecem como "sin grupos cargados". Deveria existir
# matrícula apenas na sección que tem planificación (J); o restante precisa ser
# corrigido/eliminado na origem. Não há filtro aqui — o script deve continuar
# reportando essa divergência normalmente até a matrícula ser corrigida.

# Cálculo de contagem para validação posterior (dentro do mesmo período)
df_sys['count_sys'] = df_sys.groupby(['usuarios_id', 'disc_key', 'periodo_key'])['sec_key'].transform('count')
df_bio['count_bio'] = df_bio.groupby(['system_id', 'disc_key', 'periodo_key'])['sec_key'].transform('nunique')

# AGRUPAMENTO: Pega o g."name" (grupo) e separa por vírgulas em uma única coluna
df_grupos = df_bio.groupby(['system_id', 'disc_key', 'sec_key', 'periodo_key'])['grupo'].apply(
    lambda x: ', '.join(sorted(x.dropna().astype(str).unique()))
).reset_index(name='grupos_biometria')

# Adiciona a nova coluna com os grupos concatenados de volta na biometria
df_bio = pd.merge(df_bio, df_grupos, on=['system_id', 'disc_key', 'sec_key', 'periodo_key'], how='left')

# --- ES_PRACTICA calculado pela Biometria (16/09/2026, ajustado em 16/09/2026) ---
# Antes vinha de ofe.possui_pratica (Syseduca), que estava inconsistente (configurado por
# turma, não por disciplina). Primeira versão calculava pelo grupo_id (4 = Teórica) da
# planificación do aluno, mas isso depende de planificacion_horario_attendee — e existem
# ~12 mil vínculos aluno+matéria em 2026.2 ATIVOS num bloco de Prática (planificacion_attendee)
# que ainda não têm grupo/horário atribuído lá na Biometria (ex.: Anatomía I). Nesses casos o
# grupo_id não existe, então a versão anterior dava "só teórica" errado.
# Agora usa query_practica_biometria: independe do grupo/horário atribuído, só olha se o
# aluno está ATIVO numa planificación que tem algum bloco de tipo prático (Practicas/
# CONSULTORIO/SIMULACIÓN). Mantido como 1/0 (não texto "Sí"/"No") porque a coluna
# es_practica no BICDE é INT.
df_practica_bio['disc_key'] = normalizar_disc(df_practica_bio['asignatura'])
df_practica_bio['sec_key'] = df_practica_bio['seccion'].astype(str).str.strip().str.upper()
df_practica_bio['periodo_key'] = df_practica_bio['anho'].astype(str) + '.' + df_practica_bio['periodo'].map({'Semestre 1': '1', 'Semestre 2': '2'})
df_practica_bio['es_practica_biometria'] = 1
df_es_practica = df_practica_bio[['system_id', 'disc_key', 'sec_key', 'periodo_key', 'es_practica_biometria']].drop_duplicates()

df_bio = pd.merge(df_bio, df_es_practica, on=['system_id', 'disc_key', 'sec_key', 'periodo_key'], how='left')
df_bio['es_practica_biometria'] = df_bio['es_practica_biometria'].fillna(0).astype(int)

# -----------------------------------------------------------------------------
# 5. VALIDAÇÃO (SYSEDUCA x BIOMETRIA)
# -----------------------------------------------------------------------------
validacao = pd.merge(
    df_sys,
    df_bio.drop_duplicates(subset=['system_id', 'disc_key', 'sec_key', 'periodo_key']),
    left_on=['usuarios_id', 'disc_key', 'periodo_key'],
    right_on=['system_id', 'disc_key', 'periodo_key'],
    how='left'
)

def verificar_status_final(row):
    if row['count_sys'] > 1: return 'Alumno con múltiples disciplinas activas en syseduca'
    if pd.isna(row['system_id']): return 'Alumno en biometría, sin grupos cargados'
    if row['count_bio'] > 1: return 'Alumno con múltiples disciplinas activas en biometría'
    if row['sec_key_x'] != row['sec_key_y']: return 'Sección diferente entre syseduca y biometría'
    return 'OK'

validacao['status_final'] = validacao.apply(verificar_status_final, axis=1)

# Reporte 1: Validação geral incluindo a nova coluna de Grupos e o período (para filtro no Power BI)
resultado_final_validacao = validacao[[
    'usuarios_id', 'nome_sobrenome', 'numero_catraca', 'semestre_alumno',
    'ano', 'periodo_anual', 'status_alumno', 'disciplina_nombre', 'seccion_nombre',
    'asignatura', 'seccion', 'grupos_biometria', 'status_final'
]].copy()

resultado_final_validacao.columns = [
    'id_syseduca', 'nombre_alumno', 'catraca', 'semestre',
    'ano_syseduca', 'periodo_syseduca', 'status_alumno',
    'asignatura_syseduca', 'seccion_syseduca', 'asignatura_biometria', 'seccion_biometria',
    'grupos_biometria', 'resultado'
]

tipos = {
    'id_syseduca': 'int64',
    'nombre_alumno': 'object',
    'catraca': 'int64',
    'semestre': 'object',
    'ano_syseduca': 'object',
    'periodo_syseduca': 'object',
    'status_alumno': 'object',
    'asignatura_syseduca': 'object',
    'seccion_syseduca': 'object',
    'asignatura_biometria': 'object',
    'seccion_biometria': 'object',
    'grupos_biometria': 'object',
    'resultado': 'object'
}

resultado_final_validacao = resultado_final_validacao.astype(tipos)

# -----------------------------------------------------------------------------
# 6. RESUMO DE ASSISTÊNCIA PARA ALUNOS 'OK'
# -----------------------------------------------------------------------------
df_ok = validacao[validacao['status_final'] == 'OK'].copy()
df_ok = pd.merge(df_ok, df_assistencia, on=['attendee_id', 'planificacion_id'], how='left')

# Sobrescreve o es_practica vindo do Syseduca pelo calculado a partir da Biometria (ver bloco acima)
df_ok['es_practica'] = df_ok['es_practica_biometria']

cols_asist = ['clases_teoricas', 'presentes_teoricas', 'ausentes_teoricas', 'ausentes_justificadas_teoricas',
              'clases_practicas', 'presentes_practicas', 'ausentes_practicas', 'ausentes_justificadas_practicas']
df_ok[cols_asist] = df_ok[cols_asist].fillna(0)

# 1. Ajustando os totais (Removendo a trava do grupo_id se ele estiver causando o zero)
# Se 'clases_teoricas' já contém o total de aulas, use-o diretamente
df_ok['clases_teoricas_final'] = df_ok['clases_teoricas']
df_ok['clases_practicas_final'] = df_ok['clases_practicas']

# 2. Nova função de cálculo considerando Justificativas no Numerador (Abono)
def get_perc_justificada(pres, just, tot):
    # Somamos presença + justificativa para dar o "presente final"
    presenca_total = pres + just
    if tot > 0:
        perc = (presenca_total / tot) * 100
        return round(min(perc, 100.0), 2) # min garante que não passe de 100%
    return 0.0

# 3. Aplicando os cálculos
df_ok['porc_presente_teoricas'] = df_ok.apply(
    lambda x: get_perc_justificada(
        x['presentes_teoricas'], 
        x.get('ausentes_justificadas_teoricas', 0), 
        x['clases_teoricas_final']
    ), axis=1
)

df_ok['porc_presente_practicas'] = df_ok.apply(
    lambda x: get_perc_justificada(
        x['presentes_practicas'], 
        x.get('ausentes_justificadas_practicas', 0), 
        x['clases_practicas_final']
    ), axis=1
)

# 4. Porcentagem Final (Geral)
df_ok['porc_final'] = df_ok.apply(
    lambda x: get_perc_justificada(
        (x['presentes_teoricas'] + x['presentes_practicas']),
        (x.get('ausentes_justificadas_teoricas', 0) + x.get('ausentes_justificadas_practicas', 0)),
        (x['clases_teoricas'] + x['clases_practicas'])
    ), axis=1
)

# Mapeamento com UNDERLINES idêntico ao MySQL e com a correção de 'nombre_sobrenome'
mapeamento_colunas = {
    'anho': 'anho_biometria', 'semestre_id_bio': 'semestre_id_biometria', 'periodo': 'semestre_biometria',
    'attendee_id': 'attendee_id_biometria', 'alumno': 'alumno_biometria', 'system_id': 'system_id_biometria',
    'planificacion_id': 'planificacion_id_biometria', 'planificacion_activa': 'planificacion_activa_biometria',
    'course_id': 'course_id_biometria', 'asignatura': 'course_biometria', 'seccion_id_bio': 'seccion_id_biometria',
    'seccion': 'seccion_biometria', 'grupos_biometria': 'grupos_biometria', 
    'clases_teoricas': 'clases_teoricas_biometria', 'presentes_teoricas': 'presentes_teoricas_biometria', 
    'ausentes_teoricas': 'ausentes_teoricas_biometria', 'ausentes_justificadas_teoricas': 'ausentes_justificadas_teoricas_biometria',
    'clases_practicas': 'clases_practicas_biometria', 'presentes_practicas': 'presentes_practicas_biometria',
    'ausentes_practicas': 'ausentes_practicas_biometria', 'ausentes_justificadas_practicas': 'ausentes_justificadas_practicas_biometria',
    'tipo_clase': 'tipo_clase_biometria', 'usuarios_id': 'usuarios_id_biometria',
    'status_alumno': 'status_alumno_biometria', 'matricula_disciplina_id': 'matricula_disciplina_id_syseduca',
    'oferta_disciplina_id': 'oferta_disciplina_id_syseduca', 'periodo_letivo_id': 'periodo_letivo_id_syseduca',
    'disciplinas_id': 'disciplinas_id_syseduca', 'disciplina_nombre': 'disciplina_nombre_syseduca',
    'semestre_disciplina_id': 'semestre_disciplina_id_syseduca', 'semestre_disciplina': 'semestre_disciplina_syseduca',
    'semestre_disciplina_nro': 'semestre_disciplina_nro_syseduca', 'turma_id': 'turma_id_syseduca',
    'seccion_nombre': 'seccion_nombre_syseduca', 'ano_id': 'ano_id_syseduca', 'ano': 'ano_syseduca',
    'periodo_anual_id': 'periodo_anual_id_syseduca', 'periodo_anual': 'periodo_anual_syseduca',
    'semestre_alumno_id': 'semestre_alumno_id_syseduca', 'semestre_alumno': 'semestre_alumno_syseduca',
    'semestre_nro': 'semestre_nro_syseduca', 'matricula_curso_id': 'matricula_curso_id_syseduca',
    'nome_sobrenome': 'nombre_sobrenome_syseduca', 
    'numero_catraca': 'numero_catraca_syseduca', 'es_practica': 'es_practica'
}

df_resumo_final = df_ok.rename(columns=mapeamento_colunas)

# SAFEGUARD: Garante que não sobrou nenhum ponto no nome das colunas
df_resumo_final.columns = df_resumo_final.columns.str.replace('.', '_', regex=False)

colunas_finais = list(mapeamento_colunas.values()) + [
    'clases_teoricas_final', 'clases_practicas_final', 
    'porc_presente_teoricas', 'porc_presente_practicas', 'porc_final'
]

# Deixa no dataframe final apenas as colunas que realmente existem
colunas_existentes = [col for col in colunas_finais if col in df_resumo_final.columns]
df_resumo_final = df_resumo_final[colunas_existentes]

tipos2 = {
    'anho_biometria': 'Int64', 
    'semestre_id_biometria': 'Int64',
    'attendee_id_biometria': 'Int64',
    'system_id_biometria': 'Int64',
    'planificacion_id_biometria': 'Int64',
    'course_id_biometria': 'Int64',
    'seccion_id_biometria': 'Int64',
    'usuarios_id_biometria': 'Int64',
    'matricula_disciplina_id_syseduca': 'Int64',
    'oferta_disciplina_id_syseduca': 'Int64',
    'periodo_letivo_id_syseduca': 'Int64',
    'disciplinas_id_syseduca': 'Int64',
    'semestre_disciplina_id_syseduca': 'Int64',
    'turma_id_syseduca': 'Int64',
    'ano_id_syseduca': 'Int64',
    'periodo_anual_id_syseduca': 'Int64',
    'semestre_alumno_id_syseduca': 'Int64',
    'matricula_curso_id_syseduca': 'Int64',
    'numero_catraca_syseduca': 'Int64',
    'semestre_biometria': 'object',
    'alumno_biometria': 'object',
    'planificacion_activa_biometria': 'object',
    'course_biometria': 'object',
    'seccion_biometria': 'object',
    'grupos_biometria': 'object',
    'tipo_clase_biometria': 'object',
    'status_alumno_biometria': 'object',
    'disciplina_nombre_syseduca': 'object',
    'semestre_disciplina_syseduca': 'object',
    'semestre_disciplina_nro_syseduca': 'object',
    'seccion_nombre_syseduca': 'object',
    'ano_syseduca': 'object',
    'periodo_anual_syseduca': 'object',
    'semestre_alumno_syseduca': 'object',
    'semestre_nro_syseduca': 'object',
    'nombre_sobrenome_syseduca': 'object',
    'porc_presente_teoricas': 'float64',
    'porc_presente_practicas': 'float64',
    'porc_final': 'float64',
    'clases_teoricas_biometria': 'Int64',
    'presentes_teoricas_biometria': 'Int64',
    'ausentes_teoricas_biometria': 'Int64',
    'ausentes_justificadas_teoricas_biometria': 'Int64',
    'clases_practicas_biometria': 'Int64',
    'presentes_practicas_biometria': 'Int64',
    'ausentes_practicas_biometria': 'Int64',
    'ausentes_justificadas_practicas_biometria': 'Int64',
    'clases_teoricas_final': 'Int64',
    'clases_practicas_final': 'Int64',
    'es_practica': 'Int64'
}

# SAFEGUARD: Aplica a conversão de tipos apenas nas colunas que estão presentes no dataframe
tipos_aplicar = {col: tipo for col, tipo in tipos2.items() if col in df_resumo_final.columns}
df_resumo_final = df_resumo_final.astype(tipos_aplicar)

# -----------------------------------------------------------------------------
# 7. ADIÇÃO DA COLUNA DE ATUALIZAÇÃO E EXPORTAÇÃO PARA CSV
# -----------------------------------------------------------------------------
# Captura o momento exato em que o script roda
timestamp_atual = datetime.now()

# Adiciona a coluna com o timestamp nos dois DataFrames
resultado_final_validacao['ultima_actualizacion'] = timestamp_atual
df_resumo_final['ultima_actualizacion'] = timestamp_atual

# Formata a string de data para a criação da pasta e nome do arquivo (DD-MM-YYYY)
data_pasta = timestamp_atual.strftime("%d-%m-%Y")

# Identifica o diretório onde o script está sendo executado e cria a estrutura resultados/DD-MM-YYYY
diretorio_atual = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
pasta_resultados = os.path.join(diretorio_atual, "resultados", data_pasta)

# Cria a pasta caso ela não exista
os.makedirs(pasta_resultados, exist_ok=True)

# Define os caminhos dos arquivos CSV
csv_validacao_path = os.path.join(pasta_resultados, f"diferencias_sys_bio_{data_pasta}.csv")
csv_resumo_path = os.path.join(pasta_resultados, f"resumen_asistencias_{data_pasta}.csv")

# Exporta os arquivos CSV (o index=False evita que o pandas crie uma coluna de índice vazia)
resultado_final_validacao.to_csv(csv_validacao_path, index=False, encoding='utf-8')
df_resumo_final.to_csv(csv_resumo_path, index=False, encoding='utf-8')

# Lista de los alumnos excluidos por inactividad en 2026.2 (solo CSV, no se carga al BICDE)
csv_excluidos_path = os.path.join(pasta_resultados, f"alumnos_excluidos_inactivos_{data_pasta}.csv")
df_excluidos.to_csv(csv_excluidos_path, index=False, encoding='utf-8')

print(f"Backups em CSV gerados com sucesso na pasta: {pasta_resultados}")

# -----------------------------------------------------------------------------
# 8. TRUNCATE E INSERT NA BASE BICDE
# -----------------------------------------------------------------------------
try:
    print("Limpando tabelas no BICDE...")

    with mysql_engine_bicde.connect() as conn:
        conn.execute(text("TRUNCATE TABLE diferencias_sys_bio_20261"))
        conn.execute(text("TRUNCATE TABLE resumen_asistencias_20261"))
        conn.commit()

except Exception as e:
    print(f"Erro no TRUNCATE: {e}")
    mysql_engine_bicde.dispose()
    raise


try:
    print("Inserindo diferencias_sys_bio_20261...")

    df1 = resultado_final_validacao.copy()
    df1.to_sql(
        'diferencias_sys_bio_20261',
        con=mysql_engine_bicde,
        if_exists='append',
        index=False,
        chunksize=5000,
        method='multi'
    )

except Exception as e:
    print(f"Erro insert diferencias: {e}")
    mysql_engine_bicde.dispose()
    raise

try:
    print("Inserindo resumen_asistencias_20261...")

    df2 = df_resumo_final.copy()
    df2.to_sql(
        'resumen_asistencias_20261',
        con=mysql_engine_bicde,
        if_exists='append',
        index=False,
        chunksize=5000,
        method='multi'
    )

except Exception as e:
    print(f"Erro insert resumen: {e}")
    mysql_engine_bicde.dispose()
    raise

print("Carga no BICDE finalizada com sucesso!")



# In[2]:


# -----------------------------------------------------------------------------
# QUERY ANTIGA
# -----------------------------------------------------------------------------

# import os
# import pandas as pd
# import numpy as np
# from sqlalchemy import create_engine, text
# from urllib.parse import quote_plus
# from dotenv import load_dotenv
# from datetime import datetime

# # -----------------------------------------------------------------------------
# # 1. CONFIGURAÇÃO DE CONEXÕES (COM QUOTE_PLUS E DOTENV)
# # -----------------------------------------------------------------------------
# load_dotenv()

# # Base BIOMETRIA
# pg_user = quote_plus(os.getenv("PG_USER", ""))
# pg_password = quote_plus(os.getenv("PG_PASSWORD", ""))
# pg_host = os.getenv("PG_HOST")
# pg_port = os.getenv("PG_PORT")
# pg_db = os.getenv("PG_DB")

# # Base SYSEDUCA
# mysql_user_sys = quote_plus(os.getenv("MYSQL_USER_SYS", ""))
# mysql_password_sys = quote_plus(os.getenv("MYSQL_PASSWORD_SYS", ""))
# mysql_host_sys = os.getenv("MYSQL_HOST_SYS")
# mysql_port_sys = os.getenv("MYSQL_PORT_SYS", "3306")
# mysql_db_sys = os.getenv("MYSQL_DB_SYS")

# # Base BICDE para guardar los datos
# mysql_user_bicde = quote_plus(os.getenv("MYSQL_USER_BICDE", ""))
# mysql_password_bicde = quote_plus(os.getenv("MYSQL_PASSWORD_BICDE", ""))
# mysql_host_bicde = os.getenv("MYSQL_HOST_BICDE")
# mysql_port_bicde = os.getenv("MYSQL_PORT_BICDE", "3306")
# mysql_db_bicde = os.getenv("MYSQL_DB_BICDE")

# pg_engine = create_engine(f"postgresql+psycopg2://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}")
# mysql_engine_sys = create_engine(f"mysql+mysqlconnector://{mysql_user_sys}:{mysql_password_sys}@{mysql_host_sys}:{mysql_port_sys}/{mysql_db_sys}")
# mysql_engine_bicde = create_engine(f"mysql+mysqlconnector://{mysql_user_bicde}:{mysql_password_bicde}@{mysql_host_bicde}:{mysql_port_bicde}/{mysql_db_bicde}")

# # -----------------------------------------------------------------------------
# # 2. DEFINIÇÃO DAS QUERIES
# # -----------------------------------------------------------------------------
# query_assistencia = """
# WITH marcaciones_ordenadas AS (
#     SELECT
#         m2.attendee_id,
#         ph.planificacion_id,
#         ROW_NUMBER() OVER (
#             PARTITION BY m2.attendee_id, p.course_id, p.seccion_id, ph.tipo_actividad_id
#             ORDER BY COALESCE(m.entrada_real, m.salida_real) DESC NULLS LAST
#         ) AS rn
#     FROM marcacion_planificacion m
#     JOIN marcacion_controlid m2 ON m.marcacion_id = m2.id
#     JOIN planificacionhorario ph ON m.planificacion_horario_id = ph.id
#     JOIN planificacion p ON ph.planificacion_id = p.id
#     JOIN attendee a ON m2.attendee_id = a.id
#     WHERE a.tipo = 1
# )
# SELECT
#     par.attendee_id,
#     par.planificacion_id,
#     par.planificacion_activa,
#     par.clases_teoricas,
#     par.presentes_teoricas,
#     par.ausentes_teoricas,
#     par.ausentes_justificadas_teoricas,
#     par.clases_practicas,
#     par.presentes_practicas,
#     par.ausentes_practicas,
#     par.ausentes_justificadas_practicas,
#     mo.rn AS ultima_marcacion
# FROM planilla_asistencia_alumnos_resumen par
# LEFT JOIN marcaciones_ordenadas mo
#     ON par.attendee_id = mo.attendee_id
#    AND par.planificacion_id = mo.planificacion_id
#    AND mo.rn = 1
# WHERE par.planificacion_activa = true
# ORDER BY par.attendee_id, par.planificacion_id;
# """

# query_biometria_seccion = """
# select 
#     p.attendee_id, a3.system_id, concat(a3.first_name, ' ', a3.last_name) as alumno, 
#     p.grupo_id, g."name" as grupo, a."name" as aula,
#     concat(a2.first_name, ' ', a2.last_name) as docente, 
#     p3.anho, s2."name" as periodo, c."name" as asignatura, s."name" as seccion,
#     l."name" as lugar, p3.start_date, p3.end_date,
#     p3.course_id, p3.seccion_id as seccion_id_bio, p3.semestre_id as semestre_id_bio,
#     p2.planificacion_id, t."name" as tipo_clase
# from planificacion_horario_attendee p 
# join planificacionhorario p2 on p.planificacion_horario_id = p2.id
# join planificacion p3 on p2.planificacion_id = p3.id
# join grupo g on p.grupo_id = g.id
# join course c on p3.course_id = c.id
# join seccion s on p3.seccion_id = s.id
# join aula a on p2.aula_id = a.id
# join attendee a2 on p2.teacher_id = a2.id
# join semestre s2 on p3.semestre_id = s2.id
# join lugar l on p3.lugar_id = l.id
# join tipoactividad t on p2.tipo_actividad_id = t.id
# join attendee a3 on p.attendee_id = a3.id
# join planificacion_attendee pa on  p2.planificacion_id = pa.planificacion_id and p.attendee_id = pa.attendee_id  
# where pa.active = true and p3.anho = 2026 and p3.semestre_id = 2
# """

# query_syseduca = """ 
# WITH temp1 AS (
#     SELECT md.id AS matricula_disciplina_id, md.oferta_disciplina_id, md.periodo_letivo_id,
#         ofe.disciplinas_id, ofe.turma_id, dis.nome AS disciplina_nombre,
#         dis.semestre_id AS semestre_disciplina_id, se.nome AS semestre_disciplina,
#         se.descricao AS semestre_disciplina_nro, tu.nome AS seccion_nombre, ofe.possui_pratica as es_practica
#     FROM ucp.matricula_disciplina md
#     JOIN ucp.oferta_disciplina ofe ON md.oferta_disciplina_id = ofe.id
#     JOIN ucp.disciplinas dis ON ofe.disciplinas_id = dis.id
#     JOIN ucp.turma tu ON ofe.turma_id = tu.id
#     JOIN ucp.semestre se ON dis.semestre_id = se.id
#     WHERE md.config_filial_id IN (1,3) AND md.status = 1 AND se.descricao NOT IN (11,12)
#       AND dis.id NOT IN (220, 221, 235, 243, 244, 245)
# ),
# temp2 AS (
#     SELECT t1.*, pl.ano_id, ano.nome AS ano, pl.periodo_anual_id, pa.nome AS periodo_anual,
#         pl.semestre_id AS semestre_alumno_id, se.nome AS semestre_alumno, se.descricao AS semestre_nro, pl.matricula_curso_id
#     FROM temp1 t1
#     JOIN ucp.periodo_letivo pl ON t1.periodo_letivo_id = pl.id
#     JOIN ucp.periodo_anual pa ON pl.periodo_anual_id = pa.id
#     JOIN ucp.ano ano ON pl.ano_id = ano.id
#     JOIN ucp.semestre se ON pl.semestre_id = se.id
#     WHERE pl.ano_id IN (9,30) AND pl.periodo_anual_id IN (1,5) AND pl.status = 1 and se.descricao NOT IN (11,12)
# ),
# temp3 AS (
#     SELECT t2.*, mc.usuarios_id, mc.status as status_alumno, us.nome_sobrenome, nc.numero_catraca
#     FROM temp2 t2
#     JOIN ucp.matricula_curso mc ON t2.matricula_curso_id = mc.id
#     JOIN ucp.usuarios us ON mc.usuarios_id = us.id
#     JOIN ucp.numero_catraca nc ON us.id = nc.usuarios_id
#     WHERE mc.status = 1
# )
# SELECT * FROM temp3
# WHERE UPPER(nome_sobrenome) NOT LIKE '%TEST%' AND UPPER(nome_sobrenome) NOT LIKE '%PRUEBA%'
# """

# # -----------------------------------------------------------------------------
# # 3. EXTRAÇÃO DOS DADOS
# # -----------------------------------------------------------------------------
# df_assistencia = pd.read_sql_query(query_assistencia, pg_engine)
# df_bio = pd.read_sql_query(query_biometria_seccion, pg_engine)
# df_sys = pd.read_sql_query(query_syseduca, mysql_engine_sys) 

# # -----------------------------------------------------------------------------
# # 4. PREPARAÇÃO, LIMPEZA E AGRUPAMENTO DE GRUPOS (g."name")
# # -----------------------------------------------------------------------------
# # Mapeamento de status e correção ortográfica básica no Syseduca
# df_sys['status_alumno'] = df_sys['status_alumno'].map({1: 'Activo', 2: 'Finalizado', 3: 'Trancado', 4: 'Suspendido', 5: 'Eliminado'})
# df_sys["disciplina_nombre"] = df_sys["disciplina_nombre"].str.replace("Quirugica", "Quirurgica", regex=False)

# # Criação das chaves normalizadas (Maiúsculas e sem espaços)
# df_sys['disc_key'] = df_sys['disciplina_nombre'].astype(str).str.strip().str.upper()
# df_sys['sec_key'] = df_sys['seccion_nombre'].astype(str).str.strip().str.upper()

# df_bio['disc_key'] = df_bio['asignatura'].astype(str).str.strip().str.upper()
# df_bio['sec_key'] = df_bio['seccion'].astype(str).str.strip().str.upper()

# # --- CORREÇÃO DE NOMES DIVERGENTES ---
# correcoes_nomes = {
#     "SEMINARIO INTEGRADOR": "SEMINARIO INTEGRADOR I"
# }
# df_bio['disc_key'] = df_bio['disc_key'].replace(correcoes_nomes)

# # Cálculo de contagem para validação posterior
# df_sys['count_sys'] = df_sys.groupby(['usuarios_id', 'disc_key'])['sec_key'].transform('count')
# df_bio['count_bio'] = df_bio.groupby(['system_id', 'disc_key'])['sec_key'].transform('nunique')

# # AGRUPAMENTO: Pega o g."name" (grupo) e separa por vírgulas em uma única coluna
# df_grupos = df_bio.groupby(['system_id', 'disc_key', 'sec_key'])['grupo'].apply(
#     lambda x: ', '.join(sorted(x.dropna().astype(str).unique()))
# ).reset_index(name='grupos_biometria')

# # Adiciona a nova coluna com os grupos concatenados de volta na biometria
# df_bio = pd.merge(df_bio, df_grupos, on=['system_id', 'disc_key', 'sec_key'], how='left')

# # -----------------------------------------------------------------------------
# # 5. VALIDAÇÃO (SYSEDUCA x BIOMETRIA)
# # -----------------------------------------------------------------------------
# validacao = pd.merge(
#     df_sys, 
#     df_bio.drop_duplicates(subset=['system_id', 'disc_key', 'sec_key']), 
#     left_on=['usuarios_id', 'disc_key'], 
#     right_on=['system_id', 'disc_key'], 
#     how='left'
# )

# def verificar_status_final(row):
#     if row['count_sys'] > 1: return 'Alumno con múltiples disciplinas activas en syseduca'
#     if pd.isna(row['system_id']): return 'Alumno en biometría, sin grupos cargados'
#     if row['count_bio'] > 1: return 'Alumno con múltiples disciplinas activas en biometría'
#     if row['sec_key_x'] != row['sec_key_y']: return 'Sección diferente entre syseduca y biometría'
#     return 'OK'

# validacao['status_final'] = validacao.apply(verificar_status_final, axis=1)

# # Reporte 1: Validação geral incluindo a nova coluna de Grupos
# resultado_final_validacao = validacao[[
#     'usuarios_id', 'nome_sobrenome', 'numero_catraca', 'semestre_alumno', 
#     'status_alumno', 'disciplina_nombre', 'seccion_nombre', 
#     'asignatura', 'seccion', 'grupos_biometria', 'status_final'
# ]].copy()

# resultado_final_validacao.columns = [
#     'id_syseduca', 'nombre_alumno', 'catraca', 'semestre', 'status_alumno', 
#     'asignatura_syseduca', 'seccion_syseduca', 'asignatura_biometria', 'seccion_biometria', 
#     'grupos_biometria', 'resultado'
# ]

# tipos = {
#     'id_syseduca': 'int64',
#     'nombre_alumno': 'object',
#     'catraca': 'int64',
#     'semestre': 'object',
#     'status_alumno': 'object',
#     'asignatura_syseduca': 'object',
#     'seccion_syseduca': 'object',
#     'asignatura_biometria': 'object',
#     'seccion_biometria': 'object',  
#     'grupos_biometria': 'object',
#     'resultado': 'object'
# }

# resultado_final_validacao = resultado_final_validacao.astype(tipos)

# # -----------------------------------------------------------------------------
# # 6. RESUMO DE ASSISTÊNCIA PARA ALUNOS 'OK'
# # -----------------------------------------------------------------------------
# df_ok = validacao[validacao['status_final'] == 'OK'].copy()
# df_ok = pd.merge(df_ok, df_assistencia, on=['attendee_id', 'planificacion_id'], how='left')

# cols_asist = ['clases_teoricas', 'presentes_teoricas', 'ausentes_teoricas', 'ausentes_justificadas_teoricas',
#               'clases_practicas', 'presentes_practicas', 'ausentes_practicas', 'ausentes_justificadas_practicas']
# df_ok[cols_asist] = df_ok[cols_asist].fillna(0)

# # 1. Ajustando os totais (Removendo a trava do grupo_id se ele estiver causando o zero)
# # Se 'clases_teoricas' já contém o total de aulas, use-o diretamente
# df_ok['clases_teoricas_final'] = df_ok['clases_teoricas']
# df_ok['clases_practicas_final'] = df_ok['clases_practicas']

# # 2. Nova função de cálculo considerando Justificativas no Numerador (Abono)
# def get_perc_justificada(pres, just, tot):
#     # Somamos presença + justificativa para dar o "presente final"
#     presenca_total = pres + just
#     if tot > 0:
#         perc = (presenca_total / tot) * 100
#         return round(min(perc, 100.0), 2) # min garante que não passe de 100%
#     return 0.0

# # 3. Aplicando os cálculos
# df_ok['porc_presente_teoricas'] = df_ok.apply(
#     lambda x: get_perc_justificada(
#         x['presentes_teoricas'], 
#         x.get('ausentes_justificadas_teoricas', 0), 
#         x['clases_teoricas_final']
#     ), axis=1
# )

# df_ok['porc_presente_practicas'] = df_ok.apply(
#     lambda x: get_perc_justificada(
#         x['presentes_practicas'], 
#         x.get('ausentes_justificadas_practicas', 0), 
#         x['clases_practicas_final']
#     ), axis=1
# )

# # 4. Porcentagem Final (Geral)
# df_ok['porc_final'] = df_ok.apply(
#     lambda x: get_perc_justificada(
#         (x['presentes_teoricas'] + x['presentes_practicas']),
#         (x.get('ausentes_justificadas_teoricas', 0) + x.get('ausentes_justificadas_practicas', 0)),
#         (x['clases_teoricas'] + x['clases_practicas'])
#     ), axis=1
# )

# # Mapeamento com UNDERLINES idêntico ao MySQL e com a correção de 'nombre_sobrenome'
# mapeamento_colunas = {
#     'anho': 'anho_biometria', 'semestre_id_bio': 'semestre_id_biometria', 'periodo': 'semestre_biometria',
#     'attendee_id': 'attendee_id_biometria', 'alumno': 'alumno_biometria', 'system_id': 'system_id_biometria',
#     'planificacion_id': 'planificacion_id_biometria', 'planificacion_activa': 'planificacion_activa_biometria',
#     'course_id': 'course_id_biometria', 'asignatura': 'course_biometria', 'seccion_id_bio': 'seccion_id_biometria',
#     'seccion': 'seccion_biometria', 'grupos_biometria': 'grupos_biometria', 
#     'clases_teoricas': 'clases_teoricas_biometria', 'presentes_teoricas': 'presentes_teoricas_biometria', 
#     'ausentes_teoricas': 'ausentes_teoricas_biometria', 'ausentes_justificadas_teoricas': 'ausentes_justificadas_teoricas_biometria',
#     'clases_practicas': 'clases_practicas_biometria', 'presentes_practicas': 'presentes_practicas_biometria',
#     'ausentes_practicas': 'ausentes_practicas_biometria', 'ausentes_justificadas_practicas': 'ausentes_justificadas_practicas_biometria',
#     'tipo_clase': 'tipo_clase_biometria', 'usuarios_id': 'usuarios_id_biometria',
#     'status_alumno': 'status_alumno_biometria', 'matricula_disciplina_id': 'matricula_disciplina_id_syseduca',
#     'oferta_disciplina_id': 'oferta_disciplina_id_syseduca', 'periodo_letivo_id': 'periodo_letivo_id_syseduca',
#     'disciplinas_id': 'disciplinas_id_syseduca', 'disciplina_nombre': 'disciplina_nombre_syseduca',
#     'semestre_disciplina_id': 'semestre_disciplina_id_syseduca', 'semestre_disciplina': 'semestre_disciplina_syseduca',
#     'semestre_disciplina_nro': 'semestre_disciplina_nro_syseduca', 'turma_id': 'turma_id_syseduca',
#     'seccion_nombre': 'seccion_nombre_syseduca', 'ano_id': 'ano_id_syseduca', 'ano': 'ano_syseduca',
#     'periodo_anual_id': 'periodo_anual_id_syseduca', 'periodo_anual': 'periodo_anual_syseduca',
#     'semestre_alumno_id': 'semestre_alumno_id_syseduca', 'semestre_alumno': 'semestre_alumno_syseduca',
#     'semestre_nro': 'semestre_nro_syseduca', 'matricula_curso_id': 'matricula_curso_id_syseduca',
#     'nome_sobrenome': 'nombre_sobrenome_syseduca', 
#     'numero_catraca': 'numero_catraca_syseduca', 'es_practica': 'es_practica'
# }

# df_resumo_final = df_ok.rename(columns=mapeamento_colunas)

# # SAFEGUARD: Garante que não sobrou nenhum ponto no nome das colunas
# df_resumo_final.columns = df_resumo_final.columns.str.replace('.', '_', regex=False)

# colunas_finais = list(mapeamento_colunas.values()) + [
#     'clases_teoricas_final', 'clases_practicas_final', 
#     'porc_presente_teoricas', 'porc_presente_practicas', 'porc_final'
# ]

# # Deixa no dataframe final apenas as colunas que realmente existem
# colunas_existentes = [col for col in colunas_finais if col in df_resumo_final.columns]
# df_resumo_final = df_resumo_final[colunas_existentes]

# tipos2 = {
#     'anho_biometria': 'Int64', 
#     'semestre_id_biometria': 'Int64',
#     'attendee_id_biometria': 'Int64',
#     'system_id_biometria': 'Int64',
#     'planificacion_id_biometria': 'Int64',
#     'course_id_biometria': 'Int64',
#     'seccion_id_biometria': 'Int64',
#     'usuarios_id_biometria': 'Int64',
#     'matricula_disciplina_id_syseduca': 'Int64',
#     'oferta_disciplina_id_syseduca': 'Int64',
#     'periodo_letivo_id_syseduca': 'Int64',
#     'disciplinas_id_syseduca': 'Int64',
#     'semestre_disciplina_id_syseduca': 'Int64',
#     'turma_id_syseduca': 'Int64',
#     'ano_id_syseduca': 'Int64',
#     'periodo_anual_id_syseduca': 'Int64',
#     'semestre_alumno_id_syseduca': 'Int64',
#     'matricula_curso_id_syseduca': 'Int64',
#     'numero_catraca_syseduca': 'Int64',
#     'semestre_biometria': 'object',
#     'alumno_biometria': 'object',
#     'planificacion_activa_biometria': 'object',
#     'course_biometria': 'object',
#     'seccion_biometria': 'object',
#     'grupos_biometria': 'object',
#     'tipo_clase_biometria': 'object',
#     'status_alumno_biometria': 'object',
#     'disciplina_nombre_syseduca': 'object',
#     'semestre_disciplina_syseduca': 'object',
#     'semestre_disciplina_nro_syseduca': 'object',
#     'seccion_nombre_syseduca': 'object',
#     'ano_syseduca': 'object',
#     'periodo_anual_syseduca': 'object',
#     'semestre_alumno_syseduca': 'object',
#     'semestre_nro_syseduca': 'object',
#     'nombre_sobrenome_syseduca': 'object',
#     'porc_presente_teoricas': 'float64',
#     'porc_presente_practicas': 'float64',
#     'porc_final': 'float64',
#     'clases_teoricas_biometria': 'Int64',
#     'presentes_teoricas_biometria': 'Int64',
#     'ausentes_teoricas_biometria': 'Int64',
#     'ausentes_justificadas_teoricas_biometria': 'Int64',
#     'clases_practicas_biometria': 'Int64',
#     'presentes_practicas_biometria': 'Int64',
#     'ausentes_practicas_biometria': 'Int64',
#     'ausentes_justificadas_practicas_biometria': 'Int64',
#     'clases_teoricas_final': 'Int64',
#     'clases_practicas_final': 'Int64',
#     'es_practica': 'Int64'
# }

# # SAFEGUARD: Aplica a conversão de tipos apenas nas colunas que estão presentes no dataframe
# tipos_aplicar = {col: tipo for col, tipo in tipos2.items() if col in df_resumo_final.columns}
# df_resumo_final = df_resumo_final.astype(tipos_aplicar)

# # -----------------------------------------------------------------------------
# # 7. ADIÇÃO DA COLUNA DE ATUALIZAÇÃO E EXPORTAÇÃO PARA CSV
# # -----------------------------------------------------------------------------
# # Captura o momento exato em que o script roda
# timestamp_atual = datetime.now()

# # Adiciona a coluna com o timestamp nos dois DataFrames
# resultado_final_validacao['ultima_actualizacion'] = timestamp_atual
# df_resumo_final['ultima_actualizacion'] = timestamp_atual

# # Formata a string de data para a criação da pasta e nome do arquivo (DD-MM-YYYY)
# data_pasta = timestamp_atual.strftime("%d-%m-%Y")

# # Identifica o diretório onde o script está sendo executado e cria a estrutura resultados/DD-MM-YYYY
# diretorio_atual = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
# pasta_resultados = os.path.join(diretorio_atual, "resultados", data_pasta)

# # Cria a pasta caso ela não exista
# os.makedirs(pasta_resultados, exist_ok=True)

# # Define os caminhos dos arquivos CSV
# csv_validacao_path = os.path.join(pasta_resultados, f"diferencias_sys_bio_{data_pasta}.csv")
# csv_resumo_path = os.path.join(pasta_resultados, f"resumen_asistencias_{data_pasta}.csv")

# # Exporta os arquivos CSV (o index=False evita que o pandas crie uma coluna de índice vazia)
# resultado_final_validacao.to_csv(csv_validacao_path, index=False, encoding='utf-8')
# df_resumo_final.to_csv(csv_resumo_path, index=False, encoding='utf-8')

# print(f"Backups em CSV gerados com sucesso na pasta: {pasta_resultados}")

# # -----------------------------------------------------------------------------
# # 8. TRUNCATE E INSERT NA BASE BICDE
# # -----------------------------------------------------------------------------
# try:
#     with mysql_engine_bicde.begin() as conn:
#         print("Truncando as tabelas no banco de dados BICDE...")
#         conn.execute(text("TRUNCATE TABLE diferencias_sys_bio_20261;"))
#         conn.execute(text("TRUNCATE TABLE resumen_asistencias_20261;"))

#     print("Inserindo dados em diferencias_sys_bio_20261...")
#     resultado_final_validacao.to_sql('diferencias_sys_bio_20261', con=mysql_engine_bicde, if_exists='append', index=False)

#     print("Inserindo dados em resumen_asistencias_20261...")
#     df_resumo_final.to_sql('resumen_asistencias_20261', con=mysql_engine_bicde, if_exists='append', index=False)

#     print("Carga no banco de dados (BICDE) finalizada com sucesso!")
# except Exception as e:
#     print(f"Erro durante a inserção no banco de dados: {e}")

