import pandas as pd

from utils.system_logging import log_exception


PERMANENCIA_INDICATORS = [
    {"nombre": "Índice de Permanencia I", "sem_origen": 1, "sem_destino": 2, "r_nivel": 1},
    {"nombre": "Índice de Permanencia II", "sem_origen": 2, "sem_destino": 3, "r_nivel": 2},
    {"nombre": "Índice de Permanencia III", "sem_origen": 3, "sem_destino": 4, "r_nivel": 3},
    {"nombre": "Índice de Permanencia IV", "sem_origen": 4, "sem_destino": 5, "r_nivel": 4},
    {"nombre": "Índice de Permanencia V", "sem_origen": 5, "sem_destino": 6, "r_nivel": 5},
]


def definir_momento_cambio(row, periodo_ref="2025.2"):
    estado = str(row.get("estado_matricula", "")).strip().lower()
    if estado == "activo":
        return "Activo"

    fecha_cambio = row.get("fecha_cambio")
    if pd.isnull(fecha_cambio):
        return "Sin fecha de cambio"

    try:
        semestre = int(row.get("semestre_20261", 0))
    except Exception as exc:
        log_exception("No se pudo convertir semestre en índice de permanencia", exc)
        semestre = 0

    if periodo_ref == "2026.1":
        limite = pd.to_datetime("2026-02-04") if semestre == 1 else pd.to_datetime("2026-02-09")
    elif periodo_ref == "2025.2":
        limite = pd.to_datetime("2025-07-30") if semestre == 1 else pd.to_datetime("2025-08-04")
    else:
        return "Periodo desconocido"

    fecha_dt = pd.to_datetime(fecha_cambio, errors="coerce", dayfirst=True)
    if pd.isnull(fecha_dt):
        return "Sin fecha de cambio válida"

    return "Antes del inicio de clases" if fecha_dt < limite else "Después del inicio de clases"


def format_monto_pagado(monto, es_pago):
    if not es_pago or pd.isnull(monto):
        return ""
    try:
        return f"Gs. {int(float(monto)):,.0f}".replace(",", ".")
    except Exception as exc:
        log_exception("No se pudo formatear monto en índice de permanencia", exc)
        return str(monto)


def prepare_permanencia_source(df_base):
    df_lista = df_base.copy()

    if "estado_matricula" in df_lista.columns:
        df_lista["estado_matricula"] = df_lista["estado_matricula"].fillna("").astype(str).str.strip().str.lower()

    if "status_academico" in df_lista.columns:
        df_lista["status_academico"] = df_lista["status_academico"].fillna("").astype(str).str.strip().str.lower()

    df_lista["momento_cambio"] = df_lista.apply(lambda row: definir_momento_cambio(row, "2025.2"), axis=1)
    df_lista["sem_252"] = pd.to_numeric(df_lista.get("semestre_20252", 0), errors="coerce").fillna(0).astype(int)
    df_lista["sem_261"] = pd.to_numeric(df_lista.get("semestre_20261", 0), errors="coerce").fillna(0).astype(int)

    df_lista = df_lista[df_lista["sem_252"] != 6]

    if "analise_primer_periodo" in df_lista.columns and "tipo_matricula" in df_lista.columns:
        is_primer_periodo = df_lista["analise_primer_periodo"].astype(str).str.strip() == "Primer Periodo"
        is_convalidado = df_lista["tipo_matricula"].astype(str).str.strip() == "Convalidado"
        df_lista = df_lista[~(is_primer_periodo & is_convalidado)]

    monto_252_col = "monto_factura_20252" if "monto_factura_20252" in df_lista.columns else None
    if monto_252_col:
        df_lista["Monto Pagado 2025.2"] = df_lista.apply(
            lambda row: format_monto_pagado(
                row[monto_252_col],
                pd.notna(row.get("estado_pago_20252")) and "paga" in str(row["estado_pago_20252"]).lower(),
            ),
            axis=1,
        )
    else:
        df_lista["Monto Pagado 2025.2"] = ""

    monto_261_col = "monto_factura_20261" if "monto_factura_20261" in df_lista.columns else None
    if monto_261_col:
        df_lista["Monto Pagado 2026.1"] = df_lista.apply(
            lambda row: format_monto_pagado(
                row[monto_261_col],
                pd.notna(row.get("estado_pago_20261")) and "paga" in str(row["estado_pago_20261"]).lower(),
            ),
            axis=1,
        )
    else:
        df_lista["Monto Pagado 2026.1"] = ""

    return df_lista


def calculate_permanencia_indicators(df_lista, incluir_convalidados=False, incluir_recursantes=False):
    is_convalid = _is_convalidado(df_lista)
    is_recurs = _is_recursante(df_lista)

    mask_resumen = pd.Series(True, index=df_lista.index)
    if not incluir_convalidados:
        mask_resumen &= ~is_convalid
    if not incluir_recursantes:
        mask_resumen &= ~is_recurs
    mask_resumen &= df_lista["momento_cambio"] != "Antes del inicio de clases"

    df_calc = df_lista[mask_resumen].copy()
    es_paga_252 = _is_pago(df_calc, "estado_pago_20252")
    es_paga_261 = _is_pago(df_calc, "estado_pago_20261")

    resultados_p = []
    resultados_nr = []
    df_todas_nr_list = []

    for indicator in PERMANENCIA_INDICATORS:
        base_mask = (df_calc["sem_252"] == indicator["sem_origen"]) & es_paga_252
        poblacion_base = df_calc[base_mask]
        total_base = len(poblacion_base)

        exito_mask = (
            poblacion_base["sem_261"].isin([indicator["sem_origen"], indicator["sem_destino"]])
            & es_paga_261[poblacion_base.index]
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
                "Inicio 2025.2": int(total_base),
                "Rematrícula 2026.1": int(total_exito),
                "% de Permanencia": f"{tasa:.0f}%",
                "Inicio_s": f"{indicator['sem_origen']} s",
                "Rematricula_s": f"{indicator['sem_destino']} s",
                "Descripcion": (
                    f"Los alumnos que inician el {indicator['sem_origen']}º semestre en el 2025.2 "
                    f"y al terminar se rematricularon para el {indicator['sem_destino']}º semestre "
                    "en el periodo 2026.1"
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


def _is_convalidado(df):
    if "tipo_matricula" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["tipo_matricula"].astype(str).str.lower().str.contains("convalid", na=False)


def _is_recursante(df):
    if "es_recursante" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["es_recursante"].astype(str).str.strip().str.lower().isin(["si", "true", "1", "s"])


def _is_pago(df, col):
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col].astype(str).str.lower().str.contains("paga", na=False)
