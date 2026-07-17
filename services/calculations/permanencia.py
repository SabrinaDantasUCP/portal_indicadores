import numpy as np
import pandas as pd

from utils.system_logging import log_exception


PERMANENCIA_INDICATORS = [
    {"nombre": "Índice de Permanencia I", "sem_origen": 1, "sem_destino": 2, "r_nivel": 1},
    {"nombre": "Índice de Permanencia II", "sem_origen": 2, "sem_destino": 3, "r_nivel": 2},
    {"nombre": "Índice de Permanencia III", "sem_origen": 3, "sem_destino": 4, "r_nivel": 3},
    {"nombre": "Índice de Permanencia IV", "sem_origen": 4, "sem_destino": 5, "r_nivel": 4},
    {"nombre": "Índice de Permanencia V", "sem_origen": 5, "sem_destino": 6, "r_nivel": 5},
]

# Periodos que se pueden analizar. "destino" es el periodo de rematrícula y los
# "limite_*" son las fechas de inicio de clases del periodo base.
# Las fechas de acá son solo el valor por defecto: si un admin las carga desde
# "Fechas de Permanencia", mandan las de la base (ver services/data/permanencia.py).
PERMANENCIA_PERIODOS = {
    "2025.2": {
        "anterior": "2025.1",
        "destino": "2026.1",
        "limite_primer_semestre": "2025-07-30",
        "limite_otros_semestres": "2025-08-04",
    },
    "2026.1": {
        "anterior": "2025.2",
        "destino": "2026.2",
        "limite_primer_semestre": "2026-02-04",
        "limite_otros_semestres": "2026-02-09",
    },
}

PERIODO_DEFAULT = "2025.2"


def get_periodo_config(periodo):
    try:
        return PERMANENCIA_PERIODOS[periodo]
    except KeyError as exc:
        raise KeyError(f"Periodo de permanencia no configurado: {periodo}") from exc


def listar_periodos():
    return list(PERMANENCIA_PERIODOS)


def definir_momento_cambio(row, periodo_ref=PERIODO_DEFAULT, config=None):
    estado = str(row.get("estado_matricula", "")).strip().lower()
    if estado == "activo":
        return "Activo"

    fecha_cambio = row.get("fecha_cambio")
    if pd.isnull(fecha_cambio):
        return "Sin fecha de cambio"

    if config is None:
        try:
            config = get_periodo_config(periodo_ref)
        except KeyError as exc:
            log_exception("Periodo desconocido en índice de permanencia", exc)
            return "Periodo desconocido"

    semestre = pd.to_numeric(row.get("semestre_proximo"), errors="coerce")
    limite_key = "limite_primer_semestre" if semestre == 1 else "limite_otros_semestres"
    limite = pd.to_datetime(config[limite_key])

    fecha_dt = pd.to_datetime(fecha_cambio, errors="coerce", dayfirst=True)
    if pd.isnull(fecha_dt):
        return "Sin fecha de cambio válida"

    return "Antes del inicio de clases" if fecha_dt < limite else "Después del inicio de clases"


# Semestres que entran en el indicador (IP 1 al 5).
BASE_SEMESTRES = [indicator["sem_origen"] for indicator in PERMANENCIA_INDICATORS]


def evaluar_base(df, incluir_convalidados=False, incluir_recursantes=False, periodo=None):
    """Decide qué alumnos entran en la base del indicador y por qué quedan afuera.

    Devuelve (mask_considerado, motivos). Es la única fuente de esta regla: la
    tabla de resumen y la lista detallada la usan las dos, así que no pueden
    contradecirse. Un alumno con motivo vacío es exactamente uno considerado.

    `periodo` solo aclara en el texto de qué periodo es la cuota impaga; la base
    siempre se define por el pago del periodo en curso, nunca por el siguiente.
    """
    motivo_impago = "No pagó la primera cuota"
    if periodo:
        motivo_impago += f" ({periodo})"

    reglas = [
        (~df["sem_atual"].isin(BASE_SEMESTRES), "Semestre fuera del alcance (1º a 5º)"),
        (df["momento_cambio"] == "Antes del inicio de clases", "Baja antes del inicio de clases"),
        (~es_pago(df, "estado_pago_atual"), motivo_impago),
    ]
    if not incluir_convalidados:
        reglas.append((es_convalidado(df), "Convalidado (excluido del cálculo)"))
    if not incluir_recursantes:
        reglas.append((es_recursante(df), "Recursante (excluido del cálculo)"))

    mask = pd.Series(True, index=df.index)
    motivos = pd.Series("", index=df.index)
    for cond, texto in reglas:
        cond = cond.fillna(False).astype(bool)
        mask &= ~cond
        separador = np.where(motivos.eq(""), "", " · ")
        motivos = pd.Series(np.where(cond, motivos + separador + texto, motivos), index=df.index)

    return mask, motivos


def prepare_permanencia_source(df_base, periodo=PERIODO_DEFAULT, config=None):
    # Se resuelve una sola vez y se pasa a cada fila: las fechas pueden venir de
    # la base y no queremos una consulta por alumno.
    config = config or get_periodo_config(periodo)
    df_lista = df_base.copy()

    if "estado_matricula" in df_lista.columns:
        df_lista["estado_matricula"] = df_lista["estado_matricula"].fillna("").astype(str).str.strip().str.lower()

    if "status_academico" in df_lista.columns:
        df_lista["status_academico"] = df_lista["status_academico"].fillna("").astype(str).str.strip().str.lower()

    df_lista["momento_cambio"] = df_lista.apply(lambda row: definir_momento_cambio(row, periodo, config), axis=1)
    df_lista["sem_atual"] = pd.to_numeric(df_lista.get("semestre_atual", 0), errors="coerce").fillna(0).astype(int)
    df_lista["sem_proximo"] = pd.to_numeric(df_lista.get("semestre_proximo", 0), errors="coerce").fillna(0).astype(int)

    df_lista = df_lista[df_lista["sem_atual"] != 6]

    if "analise_primer_periodo" in df_lista.columns and "tipo_matricula" in df_lista.columns:
        is_primer_periodo = df_lista["analise_primer_periodo"].astype(str).str.strip() == "Primer Periodo"
        is_convalidado = df_lista["tipo_matricula"].astype(str).str.strip() == "Convalidado"
        df_lista = df_lista[~(is_primer_periodo & is_convalidado)]

    for momento in ("atual", "proximo"):
        monto_col = f"monto_factura_{momento}"
        if monto_col in df_lista.columns:
            # Numérico, no texto: así la tabla ordena por valor. El símbolo "Gs."
            # lo pone la vista. Solo se muestra el monto si la cuota está paga.
            montos = pd.to_numeric(df_lista[monto_col], errors="coerce")
            df_lista[f"monto_pagado_{momento}"] = montos.where(es_pago(df_lista, f"estado_pago_{momento}"))
        else:
            df_lista[f"monto_pagado_{momento}"] = np.nan

    return df_lista


def calculate_permanencia_indicators(
    df_lista, incluir_convalidados=False, incluir_recursantes=False, periodo=PERIODO_DEFAULT
):
    periodo_destino = get_periodo_config(periodo)["destino"]

    # Misma regla que usa la lista detallada: ya filtra pago, momento de baja,
    # semestre en alcance, convalidados y recursantes.
    mask_base, _ = evaluar_base(df_lista, incluir_convalidados, incluir_recursantes)
    df_calc = df_lista[mask_base].copy()
    es_paga_proximo = es_pago(df_calc, "estado_pago_proximo")

    resultados_p = []
    resultados_nr = []
    df_todas_nr_list = []

    for indicator in PERMANENCIA_INDICATORS:
        poblacion_base = df_calc[df_calc["sem_atual"] == indicator["sem_origen"]]
        total_base = len(poblacion_base)

        exito_mask = (
            poblacion_base["sem_proximo"].isin([indicator["sem_origen"], indicator["sem_destino"]])
            & es_paga_proximo[poblacion_base.index]
        )
        total_exito = len(poblacion_base[exito_mask])
        poblacion_nr = poblacion_base[~exito_mask]

        c_trancados = 0
        c_reprobados = 0
        c_abandonos = 0
        ip_name = f"IP {indicator['r_nivel']}"

        if not poblacion_nr.empty:
            is_trancado = poblacion_nr["estado_matricula"] == "trancado"
            if "status_academico" in poblacion_nr.columns:
                is_reprobado = (~is_trancado) & poblacion_nr["status_academico"].astype(str).str.contains(
                    "reprovado|reprobado", case=False, na=False
                )
            else:
                is_reprobado = pd.Series(False, index=poblacion_nr.index)

            c_trancados = int(is_trancado.sum())
            c_reprobados = int(is_reprobado.sum())
            c_abandonos = int((~is_trancado & ~is_reprobado).sum())

            nr_copy = poblacion_nr.copy()
            nr_copy["Indicador"] = ip_name
            nr_copy["Motivo_NR"] = "Abandono"
            nr_copy.loc[is_reprobado, "Motivo_NR"] = "Reprobado"
            nr_copy.loc[is_trancado, "Motivo_NR"] = "Trancado"
            df_todas_nr_list.append(nr_copy)

        no_rematriculados = total_base - total_exito
        tasa = (total_exito / total_base * 100) if total_base > 0 else 0.0

        resultados_p.append(
            {
                "Indicador": ip_name,
                "Inicio": int(total_base),
                "Rematrícula": int(total_exito),
                "% de Permanencia": f"{tasa:.0f}%",
                "Inicio_s": f"{indicator['sem_origen']} s",
                "Rematricula_s": f"{indicator['sem_destino']} s",
                "Descripcion": (
                    f"Los alumnos que inician el {indicator['sem_origen']}º semestre en el {periodo} "
                    f"y al terminar se rematricularon para el {indicator['sem_destino']}º semestre "
                    f"en el periodo {periodo_destino}"
                ),
                "tasa_num": tasa,
            }
        )

        resultados_nr.append(
            {
                "Nivel": str(indicator["r_nivel"]),
                "No rematriculados": no_rematriculados,
                "Trancados": c_trancados,
                "Reprobados": c_reprobados,
                "Abandonos": c_abandonos,
            }
        )

    return pd.DataFrame(resultados_p), pd.DataFrame(resultados_nr), df_todas_nr_list


def es_convalidado(df):
    if "tipo_matricula" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["tipo_matricula"].astype(str).str.lower().str.contains("convalid", na=False)


def es_recursante(df):
    if "es_recursante" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["es_recursante"].astype(str).str.strip().str.lower().isin(["si", "true", "1", "s"])


def es_pago(df, col):
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col].astype(str).str.lower().str.contains("paga", na=False)
