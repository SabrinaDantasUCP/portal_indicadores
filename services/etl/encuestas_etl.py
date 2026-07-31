"""
services/etl/encuestas_etl.py

Funciones puras de extracción/cálculo del ETL de encuestas — sin ningún
código ejecutable a nivel de módulo, así que es seguro hacer
`from services.etl.encuestas_etl import ...` desde el admin module o desde
el cron runner (services/etl/encuesta_runner.py) sin disparar consultas.

Para uso manual/notebook (con las mismas celdas de siempre), ver
scripts/etl_encuestas.py, que ahora es solo un wrapper fino sobre este
módulo.

Gera os indicadores de avance de encuestas docentes (2026-2) e exporta
CSVs prontos para serem consumidos pelo dashboard em Streamlit.

Gera:
  1. avance_por_materia_seccion_grupo -> % de avance quebrado por
     materia + sección + grupo (já dá pra derivar "por materia" ou
     "por sección" agrupando esse CSV no dashboard).
  2. avance_general -> resumo único: total de alumnos que TINHAM que
     responder x quantos JÁ responderam pelo menos uma (todas
     materias/secciones juntas) x quantos JÁ responderam TODAS as suas
     encuestas pendentes.
  3. avance_por_alumno -> grano de alumno individual: 1 línea por
     (alumno x materia/sección/grupo), com o booleano `respondio`. É a
     base que permite fazer um distinct real de alumnos em qualquer
     nível de agregación (materia, sección, grupo) no dashboard, em vez
     de depender de somas de conteos já agregados por docente.

Fontes de dados:
  1. Banco "bio" (Postgres)      -> query de planificación (o que era ESPERADO)
  2. Banco "Academico" (SQL Sv)  -> RespuestaUsuario (o que já foi RESPONDIDO)
  3. Banco "Academico" (SQL Sv)  -> QUERY_CONTACTO (quem REALMENTE deveria
     responder: alumnos com matrícula ativa no periodo/subperiodo/semestre
     configurados ali)

IMPORTANTE - confirmar antes de rodar em produção:
  - JOIN_KEY: qual campo liga os dois bancos.
      "planificacion_id" -> RespuestaUsuario.PlanificacionId = PlanificacionDetalle.planificacion_id (mais seguro, recomendado)
      "system_id"        -> RespuestaUsuario.IdAlumnoExterno = PlanificacionDetalle.system_id (fallback, menos preciso)
  - Se os nomes de materia/sección/grupo batem 100% em texto entre os dois bancos.
  - "respondio" é calculado por par (PlanificacionId, IdAlumnoExterno), sem
    considerar o docente. Se um grupo/sección tem mais de um docente
    (mais de uma linha em RespuestaUsuario para o mesmo PlanificacionId),
    o aluno é marcado como "respondio" assim que responder a QUALQUER um
    dos docentes daquele grupo — não necessariamente todos. Isso é uma
    limitação conhecida do pipeline atual, não introduzida agora.
  - O universo de "quem deveria responder" (alumnos_esperados) é
    restringido pela QUERY_CONTACTO: df_plan (planificación/bio) mantém
    as materias/secciones/grupos, mas só entram no cálculo os alumnos
    cujo system_id também aparece em QUERY_CONTACTO (id_syseduca =
    system_id). Isso é aplicado ANTES de calcular qualquer indicador
    (avance_por_materia_seccion_grupo, avance_general, avance_por_alumno)
    e é o que gera o primeiro CSV combinado.
    O filtro por base_datos_activos.csv continua existindo, mas como uma
    restrição ADICIONAL em cima dessa (só afeta o segundo CSV,
    avance_por_alumno_activos — ver exportar_avance_por_alumno_activos).

Como usar (VPNs separadas — bio e SQL Server não estão acessíveis ao mesmo tempo):

  0. Crie um .env (ou exporte no shell) com as variáveis abaixo:

       # SQL Server - ERP / Academico
       SQLSRV_ERP_USER=usuario
       SQLSRV_ERP_PASSWORD=senha
       SQLSRV_ERP_HOST=56.124.105.133
       SQLSRV_ERP_PORT=1433
       SQLSRV_ERP_DB=ERP.PRE

       # PostgreSQL - biometria (planificación)
       PG_USER=usuario
       PG_PASSWORD=senha
       PG_HOST=10.20.8.81
       PG_PORT=5432
       PG_DB=attendance

     pip install pandas sqlalchemy psycopg2-binary pyodbc python-dotenv

  1. Conecte na VPN da bio/Postgres e rode SÓ isso (gera planificacion_raw.csv):

       from generar_indicadores_encuestas import exportar_planificacion
       exportar_planificacion(anho=2026, semestre=2, output_dir="./output")

  2. Desconecte, conecte na VPN do SQL Server/ERP e rode SÓ isso
     (gera respuestas_raw.csv, contacto_raw.csv e encuesta_raw.csv):

       from generar_indicadores_encuestas import exportar_respuestas
       exportar_respuestas(id_encuesta=3, anho=2026, subperiodo=1, output_dir="./output")

  3. Sem precisar de nenhuma VPN, junte os CSVs e gere os indicadores:

       from generar_indicadores_encuestas import generar_indicadores
       exports = generar_indicadores(
           id_encuesta=3, anho=2026, semestre=2, subperiodo=1,
           offline_plan_csv="./output/planificacion_raw.csv",
           offline_resp_csv="./output/respuestas_raw.csv",
           offline_contacto_csv="./output/contacto_raw.csv",
           output_dir="./output",
       )

  Alternativa via terminal, se tiver as duas VPNs ativas ao mesmo tempo:
       python generar_indicadores_encuestas.py --id-encuesta 3 --anho 2026 --semestre 2 --subperiodo 1

  Nota: "subperiodo" (1 o 2) es el valor "de negocio" usado en QUERY_CONTACTO
  (ver derivar_parametros_periodo); "semestre" es el semestre_id que espera
  bio, con un offset fijo de +1 respecto al subperiodo.
"""

import os
import sys
import argparse
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text

try:
    from dotenv import load_dotenv

    load_dotenv()  # carrega o .env se existir, na pasta atual
except ImportError:
    pass

# --------------------------------------------------------------------------
# CONFIG - ajustar aqui ou via variáveis de ambiente
# --------------------------------------------------------------------------

def _build_pg_conn_string() -> str:
    user = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")
    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT", "5432")
    db = os.getenv("PG_DB")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def _build_mssql_conn_string() -> str:
    user = os.getenv("SQLSRV_ERP_USER")
    password = os.getenv("SQLSRV_ERP_PASSWORD")
    host = os.getenv("SQLSRV_ERP_HOST")
    port = os.getenv("SQLSRV_ERP_PORT", "1433")
    db = os.getenv("SQLSRV_ERP_DB")
    driver = os.getenv("SQLSRV_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    driver_q = driver.replace(" ", "+")
    return (
        f"mssql+pyodbc://{user}:{password}@{host}:{port}/{db}"
        f"?driver={driver_q}"
    )


CONFIG = {
    # Postgres - sistema "bio" / biometria (planificación)
    # Monta a partir de: PG_USER, PG_PASSWORD, PG_HOST, PG_PORT, PG_DB
    "PG_CONN_STRING": os.getenv("PG_CONN_STRING") or _build_pg_conn_string(),
    # SQL Server - sistema ERP / Academico (encuestas)
    # Monta a partir de: SQLSRV_ERP_USER, SQLSRV_ERP_PASSWORD, SQLSRV_ERP_HOST,
    # SQLSRV_ERP_PORT, SQLSRV_ERP_DB
    "MSSQL_CONN_STRING": os.getenv("MSSQL_CONN_STRING") or _build_mssql_conn_string(),
    # Pasta de saída dos CSVs
    "OUTPUT_DIR": os.getenv("OUTPUT_DIR", "./output"),
    # Qual chave usar para juntar planificación (bio) com respuestas (encuestas)
    #   "planificacion_id"  -> recomendado, mais seguro (junta por ID)
    #   "system_id"         -> junta por IdAlumnoExterno = system_id
    "JOIN_KEY": os.getenv("JOIN_KEY", "planificacion_id"),
    # "carrera" é o único metadado que NÃO existe em nenhum dos dois bancos.
    # sede / nombre_encuesta / vigencia vêm de Academico.Encuesta +
    # Parametrizacion.Sede (ver fetch_encuesta_metadata). periodo já vem
    # da planificación (bio).
    "CARRERA": os.getenv("CARRERA", "Medicina"),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# QUERIES
# --------------------------------------------------------------------------

QUERY_PLANIFICACION = """
SELECT DISTINCT
    p.attendee_id,
    a3.system_id,
    concat(a3.first_name, ' ', a3.last_name) AS alumno,
    p.grupo_id,
    g."name" AS grupo,
    concat(a2.first_name, ' ', a2.last_name) AS docente,
    p2.teacher_id AS docente_id,
    p3.anho,
    s2."name" AS periodo,
    c."name" AS asignatura,
    p3.course_id,
    s."name" AS seccion,
    p3.seccion_id AS seccion_id_bio,
    p3.semestre_id AS semestre_id_bio,
    p2.planificacion_id
FROM planificacion_horario_attendee p
JOIN planificacionhorario p2 ON p.planificacion_horario_id = p2.id
JOIN planificacion p3 ON p2.planificacion_id = p3.id
JOIN grupo g ON p.grupo_id = g.id
JOIN course c ON p3.course_id = c.id
JOIN seccion s ON p3.seccion_id = s.id
JOIN attendee a2 ON p2.teacher_id = a2.id
JOIN semestre s2 ON p3.semestre_id = s2.id
JOIN attendee a3 ON p.attendee_id = a3.id
JOIN planificacion_attendee pa
    ON p2.planificacion_id = pa.planificacion_id
   AND p.attendee_id = pa.attendee_id
WHERE pa.active = true
  AND p2.tipo_planificacion = 1 
  AND p2.referida_id is null
  AND p3.anho = :anho
  AND p3.semestre_id = :semestre
"""

QUERY_RESPUESTAS = """
SELECT
    ru.Id,
    ru.IdEncuesta,
    ru.IdPregunta,
    ru.IdRespuesta,
    ru.IdUsuario,
    ru.IdAlumnoExterno,
    ru.IdDocenteExterno,
    ru.IdGrupoExterno,
    ru.IdSeccionExterno,
    ru.IdAsignaturaExterno,
    ru.PlanificacionId,
    ru.IdInscripcion,
    ru.DocenteNombre,
    ru.AsignaturaNombre,
    ru.SeccionNombre,
    ru.GrupoNombre,
    ru.CreatedAt
FROM Academico.RespuestaUsuario ru
WHERE ru.IdEncuesta = :id_encuesta
"""

# ru.IdAlumnoExterno vem NULO na maioria dos casos. O ID externo real do
# aluno (o mesmo "system_id" da bio) é obtido via:
#   RespuestaUsuario.IdUsuario = Sistema.Usuario.Id
#   Sistema.Usuario.Id        = dbo.Contacto.IdUser
#   dbo.Contacto.IdExternoUsuario  <- valor que queremos (aliased como
#   IdAlumnoExterno pra manter o resto do pipeline sem precisar mudar nada)
#
# Além disso, QUERY_CONTACTO também traz id_syseduca: é essa coluna que
# define o universo de "quem deveria responder" (ver
# filtrar_planificacion_por_contacto), já que ela só traz alumnos com
# matrícula ativa no periodo/subperiodo/semestre configurados abaixo.

# QUERY_CONTACTO = """
# SELECT
#     s.Id AS IdUsuario,
#     c.IdExternoUsuario AS IdAlumnoExterno
# FROM Sistema.Usuario s
# JOIN dbo.Contacto c ON c.IdUser = s.Id
# WHERE s.DeletedAt is null AND c.DeletedAt is null
# """


QUERY_CONTACTO = """
SELECT
    s.Id AS IdUsuario,
    c.IdExternoUsuario AS IdAlumnoExterno,
    us.id_syseduca
FROM Sistema.Usuario s
JOIN dbo.Contacto c ON c.IdUser = s.Id
JOIN dbo.PeriodoLectivoSyseduca pl on pl.id_syseduca = c.IdExternoUsuario
JOIN dbo.UsuariosSyseduca us on us.id_syseduca = pl.id_syseduca
WHERE
s.DeletedAt is null AND c.DeletedAt is null
and pl.periodo = :anho
and pl.subperiodo = :subperiodo
and pl.status_inscripcion = 'Activo'
and pl.semestre IN (1,2,3,4,5,6,7,8,9,10)
and us.status_matricula = 'Activo'
AND (us.nombre_alumno NOT LIKE '%Test%' AND us.nombre_alumno NOT LIKE '%Prueba%')
AND (us.apellidos_alumno NOT LIKE '%Test%' AND us.apellidos_alumno NOT LIKE '%Prueba%');
"""

# Metadados da encuesta (nome, vigencia, sede, semestres habilitados) que
# não estavam sendo buscados antes. Mesma VPN/base que RespuestaUsuario
# (SQL Server). IMPORTANTE: filtra DeletedAt IS NULL tanto em Encuesta
# quanto em Sede. SemestresHabilitados vem de Academico.EncuestaSemestres +
# Parametrizacion.Semestre, agregados numa string só (ex: "2025-2, 2026-1").
QUERY_ENCUESTA = """
SELECT
    e.Id AS IdEncuesta,
    e.Nombre AS NombreEncuesta,
    e.FechaDesde,
    e.FechaHasta,
    e.IdSede,
    s.Nombre AS Sede,
    (
        SELECT STRING_AGG(sem.Nombre, ', ') WITHIN GROUP (ORDER BY sem.id)
        FROM [Academico].[EncuestaSemestres] es
        JOIN [Parametrizacion].[Semestre] sem ON sem.id = es.IdSemestre
        WHERE es.IdEncuesta = e.Id
    ) AS SemestresHabilitados
FROM [Academico].[Encuesta] e
LEFT JOIN [Parametrizacion].[Sede] s
    ON s.Id = e.IdSede AND s.DeletedAt IS NULL
WHERE e.Id = :id_encuesta AND e.DeletedAt IS NULL
"""


# --------------------------------------------------------------------------
# EXTRACAO
# --------------------------------------------------------------------------

def get_pg_engine():
    return create_engine(CONFIG["PG_CONN_STRING"])


def get_mssql_engine():
    return create_engine(CONFIG["MSSQL_CONN_STRING"])


def fetch_planificacion(anho: int, semestre: int) -> pd.DataFrame:
    log.info("Buscando planificación (bio) para anho=%s semestre=%s", anho, semestre)
    engine = get_pg_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(QUERY_PLANIFICACION), conn, params={"anho": anho, "semestre": semestre}
        )
    log.info("Planificación: %s linhas", len(df))
    return df


def fetch_respuestas(id_encuesta: int) -> pd.DataFrame:
    log.info("Buscando respuestas (Academico) para IdEncuesta=%s", id_encuesta)
    engine = get_mssql_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(QUERY_RESPUESTAS), conn, params={"id_encuesta": id_encuesta}
        )
    log.info("Respuestas: %s linhas", len(df))
    return df


def fetch_contacto(anho: int, subperiodo: int) -> pd.DataFrame:
    log.info(
        "Buscando Sistema.Usuario + dbo.Contacto (IdUsuario -> IdAlumnoExterno) "
        "para periodo=%s subperiodo=%s",
        anho, subperiodo,
    )
    engine = get_mssql_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(QUERY_CONTACTO), conn, params={"anho": anho, "subperiodo": subperiodo}
        )
    log.info("Contacto: %s linhas | colunas: %s", len(df), list(df.columns))
    return df


def derivar_parametros_periodo(periodo: str) -> dict:
    """Deriva año/subperiodo/semestre_bio a partir de un único "periodo" tipo
    "2026.1" o "2026.2" — así el resto del sistema (config de admin, cron)
    solo necesita pedir/guardar ese único valor.

    - anho: parte entera antes del punto (ej. 2026). Se pasa tal cual a
      QUERY_PLANIFICACION (bio) y a QUERY_CONTACTO (pl.periodo, ERP).
    - subperiodo: parte entera después del punto (1 o 2). Se pasa tal cual a
      QUERY_CONTACTO (pl.subperiodo, ERP) y es el valor "de negocio" que se
      usa en cualquier otro lugar del sistema.
    - semestre_bio: el "semestre_id" que espera la planificación en bio
      (QUERY_PLANIFICACION, parámetro :semestre) — tiene un offset fijo de
      +1 respecto al subperiodo (subperiodo 1 -> 2, subperiodo 2 -> 3), una
      particularidad conocida de cómo bio numera los semestres, distinta del
      resto del sistema (confirmado por el usuario).
    """
    anho_str, sep, sub_str = periodo.partition(".")
    if not sep or not anho_str.isdigit() or not sub_str.isdigit():
        raise ValueError(f"Periodo inválido: {periodo!r}. Formato esperado: 'AAAA.S' (ej. '2026.1').")

    anho = int(anho_str)
    subperiodo = int(sub_str)
    if subperiodo not in (1, 2):
        raise ValueError(f"Subperiodo inválido en {periodo!r}: {subperiodo}. Debe ser 1 o 2.")

    return {"anho": anho, "subperiodo": subperiodo, "semestre_bio": subperiodo + 1}


def fetch_encuesta_metadata(id_encuesta: int) -> pd.DataFrame:
    """Busca nome, vigencia (FechaDesde/FechaHasta) e sede da encuesta em
    Academico.Encuesta + Parametrizacion.Sede (mesma VPN/base que
    RespuestaUsuario). Retorna 1 única linha."""
    log.info("Buscando metadados da encuesta (Nombre/Vigencia/Sede) para IdEncuesta=%s", id_encuesta)
    engine = get_mssql_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(QUERY_ENCUESTA), conn, params={"id_encuesta": id_encuesta}
        )
    if df.empty:
        log.warning(
            "Nenhuma encuesta ativa (DeletedAt IS NULL) encontrada para IdEncuesta=%s "
            "em Academico.Encuesta. nombre_encuesta/vigencia/sede ficarão vazios.",
            id_encuesta,
        )
    return df


def _formatar_vigencia(fecha_desde, fecha_hasta) -> str:
    """Formata o par (FechaDesde, FechaHasta) como "dd/mm/aaaa - dd/mm/aaaa".
    Retorna string vazia se alguma das datas vier nula/ausente."""
    if pd.isna(fecha_desde) or pd.isna(fecha_hasta):
        return ""
    desde = pd.to_datetime(fecha_desde).strftime("%d/%m/%Y")
    hasta = pd.to_datetime(fecha_hasta).strftime("%d/%m/%Y")
    return f"{desde} - {hasta}"


def _extraer_metadatos_encuesta(df_encuesta: pd.DataFrame) -> dict:
    """Extrae nombre_encuesta / vigencia / sede / semestres_habilitados de
    la única fila esperada en df_encuesta. Devuelve strings vacíos si
    df_encuesta llegó vacío (encuesta no encontrada o soft-deletada)."""
    if df_encuesta.empty:
        return {"nombre_encuesta": "", "vigencia": "", "sede": "", "semestres_habilitados": ""}
    fila = df_encuesta.iloc[0]
    return {
        "nombre_encuesta": fila.get("NombreEncuesta", "") or "",
        "vigencia": _formatar_vigencia(fila.get("FechaDesde"), fila.get("FechaHasta")),
        "sede": fila.get("Sede", "") or "",
        "semestres_habilitados": fila.get("SemestresHabilitados", "") or "",
    }



def _normalizar_columnas(df: pd.DataFrame, esperadas: list) -> pd.DataFrame:
    """Renomeia as colunas de df para o nome 'canônico' esperado, comparando
    sem diferenciar maiúsculas/minúsculas e ignorando espaços nas pontas.
    Evita quebrar por diferenças de case/whitespace vindas do driver SQL.
    Lança um erro claro (com as colunas reais) se alguma não for encontrada.
    """
    mapa_atual = {c.strip().lower(): c for c in df.columns}
    renomear = {}
    faltando = []
    for nome in esperadas:
        chave = nome.strip().lower()
        if chave in mapa_atual:
            renomear[mapa_atual[chave]] = nome
        else:
            faltando.append(nome)
    if faltando:
        raise KeyError(
            f"As colunas esperadas {faltando} não foram encontradas. "
            f"Colunas realmente retornadas pelo SQL: {list(df.columns)}. "
            f"Confira o nome exato da(s) coluna(s) em dbo.Contacto/Sistema.Usuario "
            f"e ajuste QUERY_CONTACTO se necessário."
        )
    return df.rename(columns=renomear)


def enriquecer_respuestas_con_alumno_externo(
    df_resp: pd.DataFrame, df_contacto: pd.DataFrame
) -> pd.DataFrame:
    """Substitui/completa RespuestaUsuario.IdAlumnoExterno (que vem nulo)
    pelo IdAlumnoExterno real, obtido via:
    IdUsuario -> Sistema.Usuario.Id -> dbo.Contacto.IdUser -> Contacto.IdAlumnoExterno
    (o merge em si é feito por IdUsuario, já que df_contacto já vem com o
    join Usuario+Contacto pronto, feito em fetch_contacto())."""
    df_contacto = _normalizar_columnas(df_contacto, ["IdUsuario", "IdAlumnoExterno"])
    df_resp = _normalizar_columnas(df_resp, ["IdUsuario"])

    df = df_resp.drop(columns=["IdAlumnoExterno"], errors="ignore").merge(
        df_contacto[["IdUsuario", "IdAlumnoExterno"]].drop_duplicates("IdUsuario"),
        on="IdUsuario",
        how="left",
    )
    faltantes = df["IdAlumnoExterno"].isna().sum()
    if faltantes:
        log.warning(
            "%s respuestas ficaram sem IdAlumnoExterno após o merge com Contacto "
            "(IdUsuario não encontrado em Sistema.Usuario/dbo.Contacto).",
            faltantes,
        )
    return df


def filtrar_planificacion_por_contacto(
    df_plan: pd.DataFrame, df_contacto: pd.DataFrame
) -> pd.DataFrame:
    """Restringe df_plan (planificación/bio) apenas aos alumnos que também
    aparecem em QUERY_CONTACTO — ou seja, com matrícula ativa no
    periodo/subperiodo/semestre configurados ali. Liga por
    id_syseduca (Academico, QUERY_CONTACTO) == system_id (bio, df_plan).

    Esse é o universo real de "quem deveria responder": não é mais todo
    mundo que aparece na planificación, e sim só quem também está ativo
    segundo QUERY_CONTACTO. Deve ser aplicado ANTES de calcular qualquer
    indicador (avance_por_materia_seccion_grupo, avance_general,
    avance_por_alumno)."""
    df_contacto = _normalizar_columnas(df_contacto, ["id_syseduca"])
    ids_contacto = set(df_contacto["id_syseduca"].dropna().astype("int64"))

    df = df_plan.copy()
    df["system_id"] = df["system_id"].astype("int64")
    return df[df["system_id"].isin(ids_contacto)].reset_index(drop=True)


# --------------------------------------------------------------------------
# INDICADORES
# --------------------------------------------------------------------------

def _completado_pairs(df_resp: pd.DataFrame) -> pd.DataFrame:
    """Pares únicos (PlanificacionId, IdAlumnoExterno) que já têm ao menos
    uma resposta registrada. Uma linha por pregunta respondida vira 1 par
    após o drop_duplicates."""
    df = df_resp.dropna(subset=["PlanificacionId", "IdAlumnoExterno"]).copy()
    df["PlanificacionId"] = df["PlanificacionId"].astype("int64")
    df["IdAlumnoExterno"] = df["IdAlumnoExterno"].astype("int64")
    return df[["PlanificacionId", "IdAlumnoExterno"]].drop_duplicates()


def _marcar_respondio(df_plan: pd.DataFrame, df_resp: pd.DataFrame, join_key: str) -> pd.DataFrame:
    """Retorna uma cópia de df_plan com uma coluna booleana `respondio`,
    indicando se aquele par (aluno x planificación/materia) já respondeu.

    join_key = "planificacion_id" (recomendado): casa por
        df_plan.planificacion_id + df_plan.system_id
        ==
        df_resp.PlanificacionId + df_resp.IdAlumnoExterno
    Isso é seguro porque planificacion_id representa a inscrição do aluno
    naquela materia/sección/grupo específica.

    join_key = "system_id" (fallback, menos preciso): só verifica se o aluno
    respondeu QUALQUER coisa na encuesta, sem garantir que foi para essa
    materia específica. Útil só se PlanificacionId não vier preenchido.
    """
    plan = df_plan.copy()
    plan["system_id"] = plan["system_id"].astype("int64")
    plan["planificacion_id"] = plan["planificacion_id"].astype("int64")

    if join_key == "planificacion_id":
        pares = _completado_pairs(df_resp)
        merged = plan.merge(
            pares,
            left_on=["planificacion_id", "system_id"],
            right_on=["PlanificacionId", "IdAlumnoExterno"],
            how="left",
            indicator=True,
        )
        plan["respondio"] = (merged["_merge"] == "both").values
    else:
        alumnos_que_respondieron = set(
            df_resp["IdAlumnoExterno"].dropna().astype("int64")
        )
        plan["respondio"] = plan["system_id"].isin(alumnos_que_respondieron)

    return plan


def indicador_avance_por_materia_seccion_grupo(
    df_plan: pd.DataFrame, df_resp: pd.DataFrame, join_key: str = "planificacion_id"
) -> pd.DataFrame:
    """% de encuestas completadas respecto al total esperado, quebrado por
    materia + sección + grupo + docente (docente incluído porque cada
    grupo tem um professor responsável). No dashboard, se quiser "por
    materia" ou "por materia + sección" isolado, basta re-agrupar este
    mesmo CSV."""

    plan = _marcar_respondio(df_plan, df_resp, join_key)

    group_cols = ["asignatura", "seccion", "grupo", "docente", "docente_id"]
    esperado = (
        plan.groupby(group_cols)["system_id"].nunique().reset_index(name="alumnos_esperados")
    )
    respondido = (
        plan[plan["respondio"]]
        .groupby(group_cols)["system_id"]
        .nunique()
        .reset_index(name="alumnos_que_respondieron")
    )

    out = esperado.merge(respondido, on=group_cols, how="left").rename(
        columns={"asignatura": "materia"}
    )
    out["alumnos_que_respondieron"] = out["alumnos_que_respondieron"].fillna(0).astype(int)
    out["porcentaje_avance"] = (
        out["alumnos_que_respondieron"] / out["alumnos_esperados"].replace(0, pd.NA) * 100
    ).round(2)
    return out.sort_values(["materia", "seccion", "grupo"])


def indicador_avance_por_alumno(
    df_plan: pd.DataFrame, df_resp: pd.DataFrame, join_key: str = "planificacion_id"
) -> pd.DataFrame:
    """Grano de alumno individual: 1 línea por (alumno x materia/sección/
    grupo x docente, es decir, por planificación), con el booleano `respondio`. Inclui `docente`/`docente_id` para permitir visualizar também os docentes, não só os alumnos.

    Es la base que permite hacer un distinct real de alumnos en cualquier
    nivel de agregación (materia, sección, grupo) en el dashboard, en vez
    de depender de sumas de conteos ya agregados por docente. Se dedupica
    por (system_id, planificacion_id, grupo) — e NÃO só (system_id,
    planificacion_id) — porque um mesmo planificacion_id é compartilhado
    entre a Teórica e todos os subgrupos prácticos (G1, G2, G3, G1-MO,
    G1-MS, etc). Deduplicar só por (system_id, planificacion_id) descartava
    silenciosamente os outros grupos do aluno, mantendo só o primeiro que
    aparecia no CSV (normalmente "Teórica"). Incluir "grupo" na chave
    remove apenas a duplicata real (mesmo aluno + mesma planificación +
    mesmo grupo, com mais de um docente cadastrado)."""

    plan = _marcar_respondio(df_plan, df_resp, join_key)

    out = (
        plan.drop_duplicates(subset=["system_id", "planificacion_id", "grupo"])[
            [
                "system_id",
                "alumno",
                "asignatura",
                "seccion",
                "grupo",
                "docente",
                "docente_id",
                "planificacion_id",
                "respondio",
            ]
        ]
        .rename(columns={"asignatura": "materia"})
        .sort_values(["materia", "seccion", "grupo", "alumno"])
        .reset_index(drop=True)
    )
    return out


def indicador_avance_general(
    df_plan: pd.DataFrame, df_resp: pd.DataFrame, join_key: str = "planificacion_id"
) -> pd.DataFrame:
    """Resumo único considerando todas as materias/secciones/grupos juntos.
    Retorna 1 linha só, com três visões:
      - encuestas_esperadas/respondidas: conta pares (aluno x planificación),
        ou seja, cada materia que o aluno precisa responder conta 1x.
      - alumnos_unicos_*_al_menos_una: conta DISTINCT de alunos (system_id)
        que já responderam AO MENOS UMA de suas materias pendentes.
      - alumnos_unicos_*_todas: conta DISTINCT de alunos que já responderam
        TODAS as materias/planificaciones que tinham pendentes (nenhuma
        ficou sem responder).
    """

    plan = _marcar_respondio(df_plan, df_resp, join_key)

    # garante 1 linha por par (aluno x planificación), mesmo que df_plan
    # tenha vindo com linhas duplicadas do banco (ex: mais de um horário
    # pro mesmo grupo, que a query nao conseguiu colapsar com DISTINCT)
    pares = plan.drop_duplicates(subset=["system_id", "planificacion_id"])

    encuestas_esperadas = len(pares)
    encuestas_respondidas = int(pares["respondio"].sum())

    alumnos_unicos_esperados = pares["system_id"].nunique()
    alumnos_unicos_que_respondieron = pares.loc[pares["respondio"], "system_id"].nunique()

    # Por alumno: True só se TODAS as suas planificaciones pendentes tiverem
    # respondio == True (um alumno com 1 única pendencia sem responder já
    # não entra aqui, mesmo respondendo todas as demais).
    respondio_todas_por_alumno = pares.groupby("system_id")["respondio"].all()
    alumnos_unicos_que_respondieron_todas = int(respondio_todas_por_alumno.sum())

    porcentaje = (
        round(encuestas_respondidas / encuestas_esperadas * 100, 2)
        if encuestas_esperadas
        else None
    )
    porcentaje_alumnos = (
        round(alumnos_unicos_que_respondieron / alumnos_unicos_esperados * 100, 2)
        if alumnos_unicos_esperados
        else None
    )
    porcentaje_alumnos_todas = (
        round(alumnos_unicos_que_respondieron_todas / alumnos_unicos_esperados * 100, 2)
        if alumnos_unicos_esperados
        else None
    )

    return pd.DataFrame(
        [
            {
                "encuestas_esperadas": encuestas_esperadas,
                "encuestas_respondidas": encuestas_respondidas,
                "encuestas_pendientes": encuestas_esperadas - encuestas_respondidas,
                "porcentaje_avance_encuestas": porcentaje,
                "alumnos_unicos_esperados": alumnos_unicos_esperados,
                "alumnos_unicos_que_respondieron_al_menos_una": alumnos_unicos_que_respondieron,
                "porcentaje_avance_alumnos": porcentaje_alumnos,
                "alumnos_unicos_que_respondieron_todas": alumnos_unicos_que_respondieron_todas,
                "porcentaje_avance_alumnos_todas": porcentaje_alumnos_todas,
            }
        ]
    )


# --------------------------------------------------------------------------
# INDICADORES - AUTOEVALUACIÓN DO DOCENTE (encuesta tipo 2)
# --------------------------------------------------------------------------
# Mesma planificación (df_plan) do fluxo alumno->docente, mas aqui quem
# "deveria responder" e quem "respondeu" é o DOCENTE, não o alumno: cada
# docente precisa autoavaliar cada (materia x sección x grupo) em que está
# alocado (mesma granularidade usada em indicador_avance_por_materia_seccion_grupo,
# só que sem agregar).
#
# Diferenças-chave em relação ao fluxo alumno (_marcar_respondio /
# indicador_avance_por_alumno):
#   - Em RespuestaUsuario, para encuestas de docente, IdDocenteExterno já
#     vem preenchido corretamente (confirmado para produção) — não precisa
#     do enriquecimento via Contacto que o fluxo alumno precisa para
#     IdAlumnoExterno.
#   - Não se aplica filtrar_planificacion_por_contacto: a obrigação do
#     docente de se autoavaliar não depende de quantos alunos ativos ele
#     tem matriculados.
#   - Em produção, PlanificacionId sempre vem preenchido em
#     RespuestaUsuario (confirmado), então o join por planificacion_id é
#     seguro igual ao fluxo alumno.

def _completado_pairs_docente(df_resp: pd.DataFrame) -> pd.DataFrame:
    """Pares únicos (PlanificacionId, IdDocenteExterno, IdGrupoExterno) que
    já têm ao menos uma resposta registrada (autoevaluación do docente).

    IdGrupoExterno entra na chave porque um mesmo planificacion_id é
    compartilhado entre a Teórica e os grupos prácticos, e um docente pode
    estar alocado em mais de um desses grupos dentro da mesma planificación
    — sem o grupo na chave, responder a autoevaluación de UM desses grupos
    marcaria incorretamente TODOS os grupos daquele docente como
    respondidos."""
    df = df_resp.dropna(
        subset=["PlanificacionId", "IdDocenteExterno", "IdGrupoExterno"]
    ).copy()
    df["PlanificacionId"] = df["PlanificacionId"].astype("int64")
    df["IdDocenteExterno"] = df["IdDocenteExterno"].astype("int64")
    df["IdGrupoExterno"] = df["IdGrupoExterno"].astype("int64")
    return df[
        ["PlanificacionId", "IdDocenteExterno", "IdGrupoExterno"]
    ].drop_duplicates()


def _marcar_respondio_docente(
    df_plan: pd.DataFrame, df_resp: pd.DataFrame, join_key: str = "planificacion_id"
) -> pd.DataFrame:
    """Análogo a _marcar_respondio, mas a nível docente (autoevaluación):
    liga por (planificacion_id, docente_id, grupo_id) em vez de
    (planificacion_id, system_id). grupo_id (bio) é assumido como o mesmo
    valor de IdGrupoExterno (Academico) — mesmo padrão de IdAsignaturaExterno
    ~ course_id e IdSeccionExterno ~ seccion_id_bio já usado nas encuestas
    de docente."""
    plan = df_plan.copy()
    plan["docente_id"] = plan["docente_id"].astype("int64")
    plan["planificacion_id"] = plan["planificacion_id"].astype("int64")
    plan["grupo_id"] = plan["grupo_id"].astype("int64")

    if join_key == "planificacion_id":
        pares = _completado_pairs_docente(df_resp)
        merged = plan.merge(
            pares,
            left_on=["planificacion_id", "docente_id", "grupo_id"],
            right_on=["PlanificacionId", "IdDocenteExterno", "IdGrupoExterno"],
            how="left",
            indicator=True,
        )
        plan["respondio"] = (merged["_merge"] == "both").values
    else:
        docentes_que_respondieron = set(
            df_resp["IdDocenteExterno"].dropna().astype("int64")
        )
        plan["respondio"] = plan["docente_id"].isin(docentes_que_respondieron)

    return plan


def indicador_avance_por_docente(
    df_plan: pd.DataFrame, df_resp: pd.DataFrame, join_key: str = "planificacion_id"
) -> pd.DataFrame:
    """Grano de docente individual (autoevaluación): 1 línea por (docente x
    materia/sección/grupo, es decir, por planificación x grupo), con el
    booleano `respondio`. Dedup por (docente_id, planificacion_id, grupo)
    pelo mesmo motivo de indicador_avance_por_alumno: um planificacion_id é
    compartilhado entre grupos teóricos e prácticos, e um docente pode
    estar alocado em mais de um desses grupos."""

    plan = _marcar_respondio_docente(df_plan, df_resp, join_key)

    out = (
        plan.drop_duplicates(subset=["docente_id", "planificacion_id", "grupo"])[
            [
                "docente_id",
                "docente",
                "asignatura",
                "seccion",
                "grupo",
                "planificacion_id",
                "respondio",
            ]
        ]
        .rename(columns={"asignatura": "materia"})
        .sort_values(["materia", "seccion", "grupo", "docente"])
        .reset_index(drop=True)
    )
    return out


def indicador_avance_general_docente(
    df_plan: pd.DataFrame, df_resp: pd.DataFrame, join_key: str = "planificacion_id"
) -> pd.DataFrame:
    """Resumo único (autoevaluación docente), análogo a
    indicador_avance_general mas no grão de docente:
      - encuestas_esperadas/respondidas: conta pares (docente x
        planificación x grupo).
      - docentes_unicos_*_al_menos_una: conta DISTINCT de docentes que já
        autoavaliaram AO MENOS UMA de suas materias/secciones/grupos.
      - docentes_unicos_*_todas: conta DISTINCT de docentes que já
        autoavaliaram TODAS as suas materias/secciones/grupos pendentes.
    """

    plan = _marcar_respondio_docente(df_plan, df_resp, join_key)
    pares = plan.drop_duplicates(subset=["docente_id", "planificacion_id", "grupo"])

    encuestas_esperadas = len(pares)
    encuestas_respondidas = int(pares["respondio"].sum())

    docentes_unicos_esperados = pares["docente_id"].nunique()
    docentes_unicos_que_respondieron = pares.loc[pares["respondio"], "docente_id"].nunique()

    respondio_todas_por_docente = pares.groupby("docente_id")["respondio"].all()
    docentes_unicos_que_respondieron_todas = int(respondio_todas_por_docente.sum())

    porcentaje = (
        round(encuestas_respondidas / encuestas_esperadas * 100, 2)
        if encuestas_esperadas
        else None
    )
    porcentaje_docentes = (
        round(docentes_unicos_que_respondieron / docentes_unicos_esperados * 100, 2)
        if docentes_unicos_esperados
        else None
    )
    porcentaje_docentes_todas = (
        round(docentes_unicos_que_respondieron_todas / docentes_unicos_esperados * 100, 2)
        if docentes_unicos_esperados
        else None
    )

    return pd.DataFrame(
        [
            {
                "encuestas_esperadas": encuestas_esperadas,
                "encuestas_respondidas": encuestas_respondidas,
                "encuestas_pendientes": encuestas_esperadas - encuestas_respondidas,
                "porcentaje_avance_encuestas": porcentaje,
                "docentes_unicos_esperados": docentes_unicos_esperados,
                "docentes_unicos_que_respondieron_al_menos_una": docentes_unicos_que_respondieron,
                "porcentaje_avance_docentes": porcentaje_docentes,
                "docentes_unicos_que_respondieron_todas": docentes_unicos_que_respondieron_todas,
                "porcentaje_avance_docentes_todas": porcentaje_docentes_todas,
            }
        ]
    )



def _agregar_metadatos(
    df: pd.DataFrame,
    sede: str,
    carrera: str,
    periodo: str,
    nombre_encuesta: str,
    vigencia: str,
    semestres_habilitados: str,
) -> pd.DataFrame:
    """Insere as colunas de metadados que não vêm de nenhum banco (sede,
    carrera, nombre_encuesta, vigencia, semestres_habilitados) ou que
    precisam ser "achatadas" pra aparecer em todo indicador (periodo). São
    os mesmos 6 valores repetidos em todas as linhas do df — não são
    calculados, só carimbados."""
    df = df.copy()
    df.insert(0, "sede", sede)
    df.insert(1, "carrera", carrera)
    df.insert(2, "periodo", periodo)
    df.insert(3, "nombre_encuesta", nombre_encuesta)
    df.insert(4, "vigencia", vigencia)
    df.insert(5, "semestres_habilitados", semestres_habilitados)
    return df


def _inferir_periodo(df_plan: pd.DataFrame, anho: int, semestre: int) -> str:
    """O periodo (nome do semestre) já vem da query de planificación
    (coluna `periodo`, ex: "2026-2"). Usa o valor único se existir; caso
    contrário (ex: df_plan vazio) cai no fallback anho-semestre."""
    if "periodo" in df_plan.columns and df_plan["periodo"].notna().any():
        valores = df_plan["periodo"].dropna().unique()
        if len(valores) > 1:
            log.warning(
                "Mais de um valor de 'periodo' encontrado na planificación: %s. "
                "Usando o primeiro.",
                valores,
            )
        return str(valores[0])
    return f"{anho}-{semestre}"


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def exportar_planificacion(anho: int, semestre: int, output_dir: str = None) -> str:
    """PASSO 1 (rodar conectado na VPN da bio/Postgres).

    Busca só a planificación e salva em CSV. Não toca no SQL Server.

        from generar_indicadores_encuestas import exportar_planificacion
        exportar_planificacion(anho=2026, semestre=2, output_dir="./output")
    """
    output_dir = output_dir or CONFIG["OUTPUT_DIR"]
    os.makedirs(output_dir, exist_ok=True)
    df_plan = fetch_planificacion(anho, semestre)
    path = os.path.join(output_dir, "planificacion_raw.csv")
    df_plan.to_csv(path, index=False, encoding="utf-8-sig")
    log.info("Planificación exportada: %s (%s linhas)", path, len(df_plan))
    return path


def exportar_respuestas(id_encuesta: int, anho: int, subperiodo: int, output_dir: str = None) -> str:
    """PASSO 2 (rodar conectado na VPN do SQL Server / ERP).

    Busca as respuestas + Sistema.Usuario/dbo.Contacto (mesma VPN), corrige
    o IdAlumnoExterno (que vem nulo em RespuestaUsuario) via
    IdUsuario -> Sistema.Usuario.Id -> Contacto.IdUser -> Contacto.IdAlumnoExterno,
    e salva em CSV. Também busca (mesma VPN) e salva os metadados da
    encuesta (nombre, vigencia, sede) via Academico.Encuesta + Parametrizacion.Sede,
    e o próprio Contacto (QUERY_CONTACTO), que define quem deveria responder
    (filtrado por anho/subperiodo — ver derivar_parametros_periodo).

        from generar_indicadores_encuestas import exportar_respuestas
        exportar_respuestas(id_encuesta=3, anho=2026, subperiodo=1, output_dir="./output")
    """
    output_dir = output_dir or CONFIG["OUTPUT_DIR"]
    os.makedirs(output_dir, exist_ok=True)
    df_resp = fetch_respuestas(id_encuesta)
    df_contacto = fetch_contacto(anho, subperiodo)
    df_resp = enriquecer_respuestas_con_alumno_externo(df_resp, df_contacto)
    path = os.path.join(output_dir, "respuestas_raw.csv")
    df_resp.to_csv(path, index=False, encoding="utf-8-sig")
    log.info("Respuestas exportadas: %s (%s linhas)", path, len(df_resp))

    path_contacto = os.path.join(output_dir, "contacto_raw.csv")
    df_contacto.to_csv(path_contacto, index=False, encoding="utf-8-sig")
    log.info("Contacto exportado: %s (%s linhas)", path_contacto, len(df_contacto))

    df_encuesta = fetch_encuesta_metadata(id_encuesta)
    path_encuesta = os.path.join(output_dir, "encuesta_raw.csv")
    df_encuesta.to_csv(path_encuesta, index=False, encoding="utf-8-sig")
    log.info("Metadados da encuesta exportados: %s (%s linhas)", path_encuesta, len(df_encuesta))

    return path


def exportar_respuestas_docente(id_encuesta: int, output_dir: str = None) -> str:
    """PASSO 2, mas para as encuestas de DOCENTE (autoevaluación / evaluando
    par), rodar conectado na VPN do SQL Server/ERP.

    Diferente de exportar_respuestas (fluxo alumno), aqui NÃO faz
    enriquecimento via Contacto: para encuestas de docente,
    IdDocenteExterno já vem correto em RespuestaUsuario (confirmado em
    produção), então não precisa descobrir quem respondeu via
    IdUsuario -> Sistema.Usuario -> Contacto.

        from generar_indicadores_encuestas import exportar_respuestas_docente
        exportar_respuestas_docente(id_encuesta=23, output_dir="./output")
    """
    output_dir = output_dir or CONFIG["OUTPUT_DIR"]
    os.makedirs(output_dir, exist_ok=True)

    df_resp = fetch_respuestas(id_encuesta)
    path = os.path.join(output_dir, f"respuestas_docente_raw_{id_encuesta}.csv")
    df_resp.to_csv(path, index=False, encoding="utf-8-sig")
    log.info("Respuestas (docente) exportadas: %s (%s linhas)", path, len(df_resp))

    df_encuesta = fetch_encuesta_metadata(id_encuesta)
    path_encuesta = os.path.join(output_dir, f"encuesta_docente_raw_{id_encuesta}.csv")
    df_encuesta.to_csv(path_encuesta, index=False, encoding="utf-8-sig")
    log.info(
        "Metadados da encuesta (docente) exportados: %s (%s linhas)",
        path_encuesta, len(df_encuesta),
    )

    return path



def generar_indicadores(
    id_encuesta: int,
    anho: int,
    semestre: int,
    subperiodo: int,
    carrera: str = None,
    output_dir: str = None,
    offline_plan_csv: str = None,
    offline_resp_csv: str = None,
    offline_encuesta_csv: str = None,
    offline_contacto_csv: str = None,
) -> dict:
    """Función principal, pensada para ser llamada tanto desde la línea de
    comando (via main()) como directamente desde un notebook/Jupyter:

        from generar_indicadores_encuestas import generar_indicadores
        exports = generar_indicadores(
            id_encuesta=3, anho=2026, semestre=2, subperiodo=1,
            offline_plan_csv="./output/planificacion_raw.csv",
            offline_resp_csv="./output/respuestas_raw.csv",
            offline_encuesta_csv="./output/encuesta_raw.csv",
            offline_contacto_csv="./output/contacto_raw.csv",
        )

    subperiodo:
        Va de la mano de "anho" para filtrar QUERY_CONTACTO (pl.periodo,
        pl.subperiodo) — ver derivar_parametros_periodo. No confundir con
        "semestre", que es el semestre_id que espera bio (con su propio
        offset respecto al subperiodo).

    carrera:
        É o único metadado que não existe em nenhum dos dois bancos, então
        precisa ser informado manualmente (default: "Medicina", já que por
        enquanto é sempre isso). sede / nombre_encuesta / vigencia vêm de
        Academico.Encuesta + Parametrizacion.Sede (offline_encuesta_csv, ou
        busca ao vivo se não for passado). periodo vem da planificación
        (bio) e é inferido automaticamente.

    offline_contacto_csv:
        CSV já exportado de QUERY_CONTACTO (ver exportar_respuestas). Usado
        para restringir df_plan apenas aos alumnos ativos (ver
        filtrar_planificacion_por_contacto) ANTES de calcular qualquer
        indicador. Se não for passado, busca ao vivo via fetch_contacto()
        (precisa da VPN do SQL Server/ERP mesmo com offline_resp_csv).

    Retorna un dict {nombre_indicador: DataFrame} (cada uno ya con las
    columnas de metadados) y además escribe UN ÚNICO CSV combinado en
    output_dir.
    """
    output_dir = output_dir or CONFIG["OUTPUT_DIR"]
    os.makedirs(output_dir, exist_ok=True)

    carrera = carrera if carrera is not None else CONFIG["CARRERA"]

    # -------------------- Extracción --------------------
    if offline_plan_csv:
        log.info("Usando CSV offline de planificación: %s", offline_plan_csv)
        df_plan = pd.read_csv(offline_plan_csv)
    else:
        df_plan = fetch_planificacion(anho, semestre)

    if offline_resp_csv:
        log.info("Usando CSV offline de respuestas: %s", offline_resp_csv)
        df_resp = pd.read_csv(offline_resp_csv)
        if offline_contacto_csv:
            log.info("Usando CSV offline de contacto: %s", offline_contacto_csv)
            df_contacto = pd.read_csv(offline_contacto_csv)
        else:
            df_contacto = fetch_contacto(anho, subperiodo)
    else:
        df_resp = fetch_respuestas(id_encuesta)
        df_contacto = fetch_contacto(anho, subperiodo)
        df_resp = enriquecer_respuestas_con_alumno_externo(df_resp, df_contacto)

    if offline_encuesta_csv:
        log.info("Usando CSV offline de metadados da encuesta: %s", offline_encuesta_csv)
        df_encuesta = pd.read_csv(offline_encuesta_csv)
    else:
        df_encuesta = fetch_encuesta_metadata(id_encuesta)

    if df_plan.empty:
        log.warning("La planificación llegó vacía. Revisar anho/semestre o la conexión al bio.")
    if df_resp.empty:
        log.warning("Las respuestas llegaron vacías. Revisar IdEncuesta o la conexión a Academico.")

    # Restringe o universo esperado aos alumnos ativos segundo QUERY_CONTACTO
    # (ver filtrar_planificacion_por_contacto). Aplicado antes de qualquer
    # indicador, então avance_por_materia_seccion_grupo, avance_general e
    # avance_por_alumno já saem todos filtrados.
    filas_plan_antes = len(df_plan)
    df_plan = filtrar_planificacion_por_contacto(df_plan, df_contacto)
    log.info(
        "Planificación filtrada por QUERY_CONTACTO: %s -> %s linhas",
        filas_plan_antes, len(df_plan),
    )

    # -------------------- Cálculo de indicadores --------------------
    avance_materia_seccion_grupo = indicador_avance_por_materia_seccion_grupo(
        df_plan, df_resp, CONFIG["JOIN_KEY"]
    )
    avance_general = indicador_avance_general(df_plan, df_resp, CONFIG["JOIN_KEY"])
    avance_por_alumno = indicador_avance_por_alumno(df_plan, df_resp, CONFIG["JOIN_KEY"])

    periodo = _inferir_periodo(df_plan, anho, semestre)
    meta_encuesta = _extraer_metadatos_encuesta(df_encuesta)

    exports = {
        "avance_por_materia_seccion_grupo": avance_materia_seccion_grupo,
        "avance_general": avance_general,
        "avance_por_alumno": avance_por_alumno,
    }

    # -------------------- Carimba metadados + combina em 1 único CSV --------------------
    # sede/nombre_encuesta/vigencia vêm de Academico.Encuesta + Parametrizacion.Sede.
    # periodo vem da planificación (bio). carrera é o único manual.
    combinados = []
    for nombre, df in exports.items():
        tmp = _agregar_metadatos(
            df,
            sede=meta_encuesta["sede"],
            carrera=carrera,
            periodo=periodo,
            nombre_encuesta=meta_encuesta["nombre_encuesta"],
            vigencia=meta_encuesta["vigencia"],
            semestres_habilitados=meta_encuesta["semestres_habilitados"],
        )
        tmp.insert(6, "indicador", nombre)
        exports[nombre] = tmp  # o dict retornado também já vem com metadados
        combinados.append(tmp)
    df_combinado = pd.concat(combinados, ignore_index=True, sort=False)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path_combinado = os.path.join(output_dir, f"indicadores_encuestas_{timestamp}.csv")
    df_combinado.to_csv(path_combinado, index=False, encoding="utf-8-sig")
    log.info("Exportado (único CSV): %s (%s linhas)", path_combinado, len(df_combinado))

    return exports


def generar_indicadores_docente_autoeval(
    id_encuesta: int,
    anho: int,
    semestre: int,
    carrera: str = None,
    output_dir: str = None,
    offline_plan_csv: str = None,
    offline_resp_csv: str = None,
    offline_encuesta_csv: str = None,
) -> dict:
    """Equivalente a generar_indicadores(), mas para a encuesta de
    AUTOEVALUACIÓN do docente (id_encuesta diferente da encuesta
    alumno->docente). Reusa a MESMA planificación (bio) do semestre — pode
    reaproveitar o mesmo planificacion_raw.csv já exportado pelo fluxo
    alumno, desde que seja o mesmo anho/semestre.

        from generar_indicadores_encuestas import generar_indicadores_docente_autoeval
        exports_docente = generar_indicadores_docente_autoeval(
            id_encuesta=23, anho=2026, semestre=2,
            offline_plan_csv="./output/planificacion_raw.csv",
            offline_resp_csv="./output/respuestas_docente_raw_23.csv",
            output_dir="./output",
        )

    Diferenças em relação a generar_indicadores (fluxo alumno):
      - NÃO usa QUERY_CONTACTO/filtrar_planificacion_por_contacto: a
        obrigação do docente de se autoavaliar não depende de quantos
        alunos ativos ele tem matriculados.
      - NÃO enriquece IdDocenteExterno via Contacto (já vem correto).
      - O grão é por docente, não por alumno
        (indicador_avance_por_docente / indicador_avance_general_docente).
    """
    output_dir = output_dir or CONFIG["OUTPUT_DIR"]
    os.makedirs(output_dir, exist_ok=True)
    carrera = carrera if carrera is not None else CONFIG["CARRERA"]

    # -------------------- Extracción --------------------
    if offline_plan_csv:
        log.info("Usando CSV offline de planificación: %s", offline_plan_csv)
        df_plan = pd.read_csv(offline_plan_csv)
    else:
        df_plan = fetch_planificacion(anho, semestre)

    if offline_resp_csv:
        log.info("Usando CSV offline de respuestas (docente): %s", offline_resp_csv)
        df_resp = pd.read_csv(offline_resp_csv)
    else:
        df_resp = fetch_respuestas(id_encuesta)

    if offline_encuesta_csv:
        log.info("Usando CSV offline de metadados da encuesta: %s", offline_encuesta_csv)
        df_encuesta = pd.read_csv(offline_encuesta_csv)
    else:
        df_encuesta = fetch_encuesta_metadata(id_encuesta)

    if df_plan.empty:
        log.warning("La planificación llegó vacía. Revisar anho/semestre o la conexión al bio.")
    if df_resp.empty:
        log.warning("Las respuestas (docente) llegaron vacías. Revisar IdEncuesta o la conexión a Academico.")

    # -------------------- Cálculo de indicadores --------------------
    avance_general_docente = indicador_avance_general_docente(df_plan, df_resp, CONFIG["JOIN_KEY"])
    avance_por_docente = indicador_avance_por_docente(df_plan, df_resp, CONFIG["JOIN_KEY"])

    periodo = _inferir_periodo(df_plan, anho, semestre)
    meta_encuesta = _extraer_metadatos_encuesta(df_encuesta)

    exports = {
        "avance_general_docente": avance_general_docente,
        "avance_por_docente": avance_por_docente,
    }

    # -------------------- Carimba metadados + combina em 1 único CSV --------------------
    combinados = []
    for nombre, df in exports.items():
        tmp = _agregar_metadatos(
            df,
            sede=meta_encuesta["sede"],
            carrera=carrera,
            periodo=periodo,
            nombre_encuesta=meta_encuesta["nombre_encuesta"],
            vigencia=meta_encuesta["vigencia"],
            semestres_habilitados=meta_encuesta["semestres_habilitados"],
        )
        tmp.insert(6, "indicador", nombre)
        exports[nombre] = tmp
        combinados.append(tmp)
    df_combinado = pd.concat(combinados, ignore_index=True, sort=False)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path_combinado = os.path.join(
        output_dir, f"indicadores_encuestas_docente_autoeval_{timestamp}.csv"
    )
    df_combinado.to_csv(path_combinado, index=False, encoding="utf-8-sig")
    log.info(
        "Exportado (docente autoevaluación, único CSV): %s (%s linhas)",
        path_combinado, len(df_combinado),
    )

    return exports



# --------------------------------------------------------------------------
# FILTRO POR ALUMNOS ATIVOS (base_datos_activos.csv)
# --------------------------------------------------------------------------
# Gera um segundo CSV, alem do "com todos os dados" que generar_indicadores()
# ja produz: o mesmo indicador avance_por_alumno, mas restrito aos alumnos
# que aparecem em base_datos_activos.csv (match por ID_Alumno == system_id).
# Os demais indicadores (avance_general, avance_por_materia_seccion_grupo)
# sao agregados e nao tem 1 linha por alumno, entao nao sao recalculados
# aqui - o filtro vale so para avance_por_alumno.

def filtrar_avance_por_alumno_activos(
    df_avance_por_alumno: pd.DataFrame, activos_csv: str, id_col: str = "ID_Alumno"
) -> pd.DataFrame:
    """Retorna so as linhas de avance_por_alumno cujo system_id esta
    presente em base_datos_activos.csv (coluna id_col, default
    'ID_Alumno')."""
    activos = pd.read_csv(activos_csv, encoding="utf-8-sig")
    ids_activos = set(activos[id_col].dropna().astype("int64"))

    df = df_avance_por_alumno.copy()
    df["system_id"] = df["system_id"].astype("int64")
    return df[df["system_id"].isin(ids_activos)].reset_index(drop=True)


def exportar_avance_por_alumno_activos(
    exports: dict, activos_csv: str, output_dir: str = None, id_col: str = "ID_Alumno"
) -> str:
    """Recebe o dict retornado por generar_indicadores(), filtra
    avance_por_alumno pelos alumnos ativos e salva num CSV separado
    (sufixo _activos), sem alterar o CSV combinado "com todos os dados"."""
    output_dir = output_dir or CONFIG["OUTPUT_DIR"]
    os.makedirs(output_dir, exist_ok=True)

    df_total = exports["avance_por_alumno"]
    df_filtrado = filtrar_avance_por_alumno_activos(df_total, activos_csv, id_col)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"avance_por_alumno_activos_{timestamp}.csv")
    df_filtrado.to_csv(path, index=False, encoding="utf-8-sig")
    log.info(
        "Avance por alumno (so ativos) exportado: %s (%s de %s linhas totais)",
        path, len(df_filtrado), len(df_total),
    )
    return path
