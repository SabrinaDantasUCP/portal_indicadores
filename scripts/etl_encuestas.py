#!/usr/bin/env python
# coding: utf-8

"""
scripts/etl_encuestas.py

Wrapper fino para uso MANUAL (terminal ou notebook/Jupyter, célula a célula
igual sempre foi) del ETL de encuestas. Toda la lógica real (queries,
fetch_*, indicador_*, exportar_*, generar_indicadores*) vive ahora en
services/etl/encuestas_etl.py — ese módulo no ejecuta nada a nivel de
código al importarlo, así que también es usado por el admin module y por
el cron (services/etl/encuesta_runner.py, scripts/run_etl_cron.py) sin
disparar consultas indeseadas.

Uso manual (VPNs separadas — bio y SQL Server no están accesibles al mismo
tiempo), igual que antes:

  1. Conecte na VPN da bio/Postgres e rode SÓ isso (gera planificacion_raw.csv):

       from scripts.etl_encuestas import exportar_planificacion
       exportar_planificacion(anho=2026, semestre=2, output_dir="./output")

  2. Desconecte, conecte na VPN do SQL Server/ERP e rode SÓ isso
     (gera respuestas_raw.csv, contacto_raw.csv e encuesta_raw.csv):

       from scripts.etl_encuestas import exportar_respuestas
       exportar_respuestas(id_encuesta=3, anho=2026, subperiodo=1, output_dir="./output")

  3. Sem precisar de nenhuma VPN, junte os CSVs e gere os indicadores:

       from scripts.etl_encuestas import generar_indicadores
       exports = generar_indicadores(
           id_encuesta=3, anho=2026, semestre=2, subperiodo=1,
           offline_plan_csv="./output/planificacion_raw.csv",
           offline_resp_csv="./output/respuestas_raw.csv",
           output_dir="./output",
       )

  Alternativa via terminal, se tiver as duas VPNs ativas ao mesmo tempo:
       python scripts/etl_encuestas.py --id-encuesta 3 --anho 2026 --semestre 2 --subperiodo 1

  Nota: "subperiodo" (1 o 2) es el valor "de negocio" (ver
  derivar_parametros_periodo en services/etl/encuestas_etl.py); "semestre"
  es el semestre_id que espera bio, con un offset fijo de +1 respecto al
  subperiodo (subperiodo 1 -> semestre 2, subperiodo 2 -> semestre 3).
"""

import argparse
import sys

from services.etl.encuestas_etl import (
    CONFIG,
    exportar_planificacion,
    exportar_respuestas,
    exportar_respuestas_docente,
    exportar_avance_por_alumno_activos,
    generar_indicadores,
    generar_indicadores_docente_autoeval,
)


def main():
    parser = argparse.ArgumentParser(description="Genera indicadores de avance de encuestas docentes")
    parser.add_argument("--id-encuesta", type=int, required=True, help="Id de Academico.Encuesta")
    parser.add_argument("--anho", type=int, required=True, help="Año de la planificación (bio)")
    parser.add_argument("--semestre", type=int, required=True, help="Id de semestre (bio)")
    parser.add_argument("--subperiodo", type=int, required=True, choices=[1, 2], help="Subperiodo (1 o 2), usado para filtrar QUERY_CONTACTO")
    parser.add_argument("--output-dir", type=str, default=CONFIG["OUTPUT_DIR"])
    parser.add_argument("--carrera", type=str, default=None, help="Carrera (default: Medicina; único metadado manual)")
    parser.add_argument(
        "--offline-plan-csv",
        type=str,
        default=None,
        help="En vez de conectar al Postgres, usa un CSV ya exportado con las columnas de la query de planificación",
    )
    parser.add_argument(
        "--offline-resp-csv",
        type=str,
        default=None,
        help="En vez de conectar al SQL Server, usa un CSV ya exportado con las columnas de RespuestaUsuario",
    )
    parser.add_argument(
        "--offline-encuesta-csv",
        type=str,
        default=None,
        help="En vez de conectar al SQL Server, usa un CSV ya exportado con nombre/vigencia/sede de Academico.Encuesta",
    )
    parser.add_argument(
        "--offline-contacto-csv",
        type=str,
        default=None,
        help="En vez de conectar al SQL Server, usa un CSV ya exportado con las columnas de QUERY_CONTACTO (IdUsuario/IdAlumnoExterno/id_syseduca)",
    )
    args = parser.parse_args()

    generar_indicadores(
        id_encuesta=args.id_encuesta,
        anho=args.anho,
        semestre=args.semestre,
        subperiodo=args.subperiodo,
        carrera=args.carrera,
        output_dir=args.output_dir,
        offline_plan_csv=args.offline_plan_csv,
        offline_resp_csv=args.offline_resp_csv,
        offline_encuesta_csv=args.offline_encuesta_csv,
        offline_contacto_csv=args.offline_contacto_csv,
    )


def _running_in_jupyter() -> bool:
    """Detecta se o código está rodando dentro de um kernel Jupyter/IPython
    (ex: notebook, JupyterLab, %run), em vez de um script chamado direto
    pelo terminal (python arquivo.py ...)."""
    return "ipykernel_launcher" in sys.argv[0] or "ipykernel" in sys.modules


if __name__ == "__main__":
    if _running_in_jupyter():
        # Dentro do Jupyter não dá pra usar argparse (sys.argv pertence ao
        # kernel, não aos parâmetros que você quer passar). Nesse caso, NÃO
        # roda nada automaticamente: só avisa como chamar a função certa.
        print(
            "Este script foi carregado dentro do Jupyter/IPython.\n"
            "Não use %run — em vez disso, chame a função diretamente, por exemplo:\n\n"
            "    exports = generar_indicadores(id_encuesta=3, anho=2026, semestre=2)\n"
        )
    else:
        main()


# In[3]:


exportar_planificacion(anho=2026, semestre=2, output_dir="./output")


# In[4]:


exportar_respuestas(id_encuesta=3, anho=2026, subperiodo=1, output_dir="./output")


# In[5]:


# Célula 4
exports = generar_indicadores(
    id_encuesta=3, anho=2026, semestre=2, subperiodo=1,
    offline_plan_csv="./output/planificacion_raw.csv",
    offline_resp_csv="./output/respuestas_raw.csv",
    output_dir="./output",
)


# In[6]:


# Celula 5 - gera o segundo CSV, filtrado so pelos alumnos ativos
# (usa o `exports` gerado na celula anterior)
exportar_avance_por_alumno_activos(
    exports,
    activos_csv=r"C:\Users\USUARIO\OneDrive - Central\BI\sistema_relatorios\sistema indicadores ETL\assets\data\base_datos_activos.csv",
    output_dir="./output",
)


# In[7]:


# --------------------------------------------------------------------------
# FLUXO 2 - AUTOEVALUACIÓN DO DOCENTE
# --------------------------------------------------------------------------
# Mesma planificación do fluxo alumno (não precisa rodar exportar_planificacion
# de novo). O que muda é o id_encuesta: cada tipo de encuesta (alumno->docente,
# autoevaluación) tem seu próprio id no Academico.Encuesta. Troque o valor
# abaixo pelo id da encuesta de autoevaluación EM PRODUÇÃO (23 foi só o id
# usado no ambiente de teste).
ID_ENCUESTA_DOCENTE_AUTOEVAL = 5  # TODO: confirmar id em produção


# In[8]:


exportar_respuestas_docente(id_encuesta=ID_ENCUESTA_DOCENTE_AUTOEVAL, output_dir="./output")


# In[9]:


exports_docente = generar_indicadores_docente_autoeval(
    id_encuesta=ID_ENCUESTA_DOCENTE_AUTOEVAL, anho=2026, semestre=2,
    offline_plan_csv="./output/planificacion_raw.csv",
    offline_resp_csv=f"./output/respuestas_docente_raw_{ID_ENCUESTA_DOCENTE_AUTOEVAL}.csv",
    output_dir="./output",
)
