# -*- coding: utf-8 -*-
"""
Script de Aplicación de Ajustes Académicos de Dirección en Base V2
=================================================================
Este script ejecuta:
1. Purga definitiva de Josafa Leite Valadares (14328) y Julia Regis Santos Silva (12448)
   de los archivos globales de población activa:
   - assets/data/global/usuarios_activos_ids.txt
   - assets/data/global/usuarios_activos_periodos.csv
2. Respaldo de seguridad previo de assets/data/v2/alumnos_v2.parquet.
3. Eliminación histórica total de ambos alumnos en alumnos_v2.parquet.
4. Reasignación integral de comisión, oferta académica y docentes para los
   alumnos reubicados (preservando 100% sus notas y estado académico).
5. Exportación de nómina de auditoría detallada en informes/Nomina_Ajustes_Secciones_y_Bajas_V2.xlsx.
"""

import os
import shutil
import pandas as pd
import numpy as np

# Rutas de archivos
RUTA_V2 = "assets/data/v2/alumnos_v2.parquet"
RUTA_V1 = "assets/data/v1/alumnos_v1.parquet"
RUTA_BAK = "assets/data/v2/alumnos_v2.parquet.bak_pre_ajustes"
RUTA_IDS_TXT = "assets/data/global/usuarios_activos_ids.txt"
RUTA_PER_CSV = "assets/data/global/usuarios_activos_periodos.csv"
RUTA_EXCEL_AJUSTADO = r"C:\Users\arman\OneDrive\Documentos\Mis sistemas\Archivos a analizar\CANTIDAD ALUMNOS POR CONVOCATORIA - TI - AJUSTADO.xlsx"
RUTA_INFORME = "informes/Nomina_Ajustes_Secciones_y_Bajas_V2.xlsx"

# IDs de bajas definitivas (Decisión 3.1 - Opción B)
IDS_BAJAS = {14328, 12448}

def purgar_archivos_globales_activos():
    """Purga los IDs de bajas definitivas de los archivos globales de activos."""
    print("\n--- 1. Purgando archivos globales de activos ---")
    
    # 1.1 usuarios_activos_ids.txt
    if os.path.exists(RUTA_IDS_TXT):
        with open(RUTA_IDS_TXT, 'r', encoding='utf-8') as f:
            lineas = [l.strip() for l in f if l.strip()]
        total_antes = len(lineas)
        lineas_filtradas = [l for l in lineas if int(l) not in IDS_BAJAS]
        total_despues = len(lineas_filtradas)
        with open(RUTA_IDS_TXT, 'w', encoding='utf-8') as f:
            for l in lineas_filtradas:
                f.write(f"{l}\n")
        print(f"usuarios_activos_ids.txt: {total_antes} -> {total_despues} (eliminados {total_antes - total_despues} IDs)")
    
    # 1.2 usuarios_activos_periodos.csv
    if os.path.exists(RUTA_PER_CSV):
        df_per = pd.read_csv(RUTA_PER_CSV)
        total_antes_per = len(df_per)
        df_per_filtrado = df_per[~df_per['usuarios_id'].isin(IDS_BAJAS)].copy()
        total_despues_per = len(df_per_filtrado)
        df_per_filtrado.to_csv(RUTA_PER_CSV, index=False)
        print(f"usuarios_activos_periodos.csv: {total_antes_per} -> {total_despues_per} (eliminadas {total_antes_per - total_despues_per} filas)")

def aplicar_ajustes_en_v2():
    """Aplica bajas y reasignaciones integrales en alumnos_v2.parquet."""
    print("\n--- 2. Creando respaldo de alumnos_v2.parquet ---")
    if not os.path.exists(RUTA_BAK):
        shutil.copy2(RUTA_V2, RUTA_BAK)
        print(f"Respaldo creado en: {RUTA_BAK}")
    else:
        print(f"Respaldo ya existente en: {RUTA_BAK}")

    print("\n--- 3. Cargando bases de datos Parquet ---")
    df_v2 = pd.read_parquet(RUTA_V2)
    df_v1 = pd.read_parquet(RUTA_V1)
    print(f"Filas iniciales en V2: {len(df_v2)}")
    print(f"Filas en V1 (solo lectura): {len(df_v1)}")

    # 3.1 Bajas definitivas
    filas_bajas_v2 = df_v2['usuarios_id'].isin(IDS_BAJAS).sum()
    print(f"Filas de Josafa (14328) y Julia (12448) a eliminar en V2: {filas_bajas_v2}")
    df_v2 = df_v2[~df_v2['usuarios_id'].isin(IDS_BAJAS)].copy()
    print(f"Filas en V2 tras bajas: {len(df_v2)}")

    # 3.2 Cargar reasignaciones nominales del Excel ajustado
    print("\n--- 4. Cargando reasignaciones nominales aprobadas del Excel ---")
    df_al_excel = pd.read_excel(RUTA_EXCEL_AJUSTADO, sheet_name="Alumnos")
    df_movidos = df_al_excel[df_al_excel['Obs'].astype(str).str.contains("Reasignado de sección", na=False)].copy()
    print(f"Total alumnos reasignados en el Excel: {len(df_movidos)}")

    # Construir catálogo de ofertas por disciplina y sección destino desde df_v1
    cat_ofertas = df_v1.dropna(subset=['id_oferta_disciplina', 'turma']).copy()
    cat_ofertas['ano_int'] = pd.to_numeric(cat_ofertas['ano_periodo_letivo'], errors='coerce').astype('Int64')
    cat_ofertas['per_flt'] = pd.to_numeric(cat_ofertas['periodo_anual_periodo_letivo'], errors='coerce')
    cat_ofertas['turma_clean'] = cat_ofertas['turma'].astype(str).str.strip().str.upper()

    # Mapeo: (ano, per, disciplinas_id, turma_destino) -> (turma_id, id_oferta_disciplina, id_docente, docente)
    dict_ofertas = {}
    for _, row in cat_ofertas[['ano_int', 'per_flt', 'disciplinas_id', 'turma_clean', 'turma_id', 'id_oferta_disciplina', 'id_docente', 'docente']].drop_duplicates().iterrows():
        k = (row['ano_int'], row['per_flt'], row['disciplinas_id'], row['turma_clean'])
        if k not in dict_ofertas:
            dict_ofertas[k] = (row['turma_id'], row['id_oferta_disciplina'], row['id_docente'], row['docente'])

    # Aplicar reasignaciones en df_v2
    registros_modificados = []
    
    # Preparar columnas de fecha/periodo en v2 para matcheo rápido
    df_v2['ano_int_tmp'] = pd.to_numeric(df_v2['ano_periodo_letivo'], errors='coerce').astype('Int64')
    df_v2['per_flt_tmp'] = pd.to_numeric(df_v2['periodo_anual_periodo_letivo'], errors='coerce')

    for _, r in df_movidos.iterrows():
        ano_m = int(r['Año'])
        per_m = float(r['Periodo'])
        uid_m = int(r['ID Usuario'])
        sec_dest_m = str(r['Sección']).strip().upper()
        obs = str(r['Obs'])
        sec_orig_m = obs.split("Reasignado de sección ")[1].split(" a ")[0].strip().upper()

        # Localizar filas de ese alumno en ese periodo en V2
        mask_alumno = (
            (df_v2['ano_int_tmp'] == ano_m) &
            (df_v2['per_flt_tmp'] == per_m) &
            (df_v2['usuarios_id'] == uid_m)
        )
        sub_indices = df_v2[mask_alumno].index
        
        for idx in sub_indices:
            row_v2 = df_v2.loc[idx]
            disc_id = row_v2['disciplinas_id']
            turma_actual = str(row_v2['turma']).strip().upper() if pd.notna(row_v2['turma']) else ""
            
            # Reasignar si la materia pertenecía a la sección origen o al semestre correspondiente
            id_of_orig = row_v2['id_oferta_disciplina']
            id_doc_orig = row_v2['id_docente']
            doc_orig = row_v2['docente']

            # Buscar oferta en sección destino
            lookup_key = (ano_m, per_m, disc_id, sec_dest_m)
            if lookup_key in dict_ofertas:
                turma_id_nueva, id_of_nueva, id_doc_nuevo, doc_nuevo = dict_ofertas[lookup_key]
                df_v2.loc[idx, 'turma'] = sec_dest_m
                df_v2.loc[idx, 'turma_id'] = turma_id_nueva
                df_v2.loc[idx, 'id_oferta_disciplina'] = id_of_nueva
                df_v2.loc[idx, 'id_docente'] = id_doc_nuevo
                df_v2.loc[idx, 'docente'] = doc_nuevo
                
                registros_modificados.append({
                    "ano": ano_m,
                    "periodo": per_m,
                    "usuarios_id": uid_m,
                    "nombre": r['Nombre'],
                    "disciplina": row_v2['disciplina'],
                    "turma_antigua": turma_actual,
                    "turma_nueva": sec_dest_m,
                    "oferta_antigua": id_of_orig,
                    "oferta_nueva": id_of_nueva,
                    "docente_antiguo": doc_orig,
                    "docente_nuevo": doc_nuevo,
                    "calificacion_final": row_v2['calificacion_final'],
                    "resultado_final": row_v2['resultado_final']
                })
            else:
                # Si no hay oferta específica en esa turma (ej. materia común o no comisionada), actualizar solo la etiqueta de turma
                df_v2.loc[idx, 'turma'] = sec_dest_m
                registros_modificados.append({
                    "ano": ano_m,
                    "periodo": per_m,
                    "usuarios_id": uid_m,
                    "nombre": r['Nombre'],
                    "disciplina": row_v2['disciplina'],
                    "turma_antigua": turma_actual,
                    "turma_nueva": sec_dest_m,
                    "oferta_antigua": id_of_orig,
                    "oferta_nueva": id_of_orig,
                    "docente_antiguo": doc_orig,
                    "docente_nuevo": doc_orig,
                    "calificacion_final": row_v2['calificacion_final'],
                    "resultado_final": row_v2['resultado_final']
                })

    # Limpiar columnas temporales
    df_v2.drop(columns=['ano_int_tmp', 'per_flt_tmp'], inplace=True)

    print(f"Total registros-materia actualizados integralmente en V2: {len(registros_modificados)}")

    # Guardar alumnos_v2.parquet actualizado
    print("\n--- 5. Guardando assets/data/v2/alumnos_v2.parquet ---")
    df_v2.to_parquet(RUTA_V2, index=False)
    print(f"alumnos_v2.parquet guardado exitosamente con {len(df_v2)} filas.")

    # Guardar informe de auditoría
    os.makedirs("informes", exist_ok=True)
    df_auditoria = pd.DataFrame(registros_modificados)
    df_auditoria.to_excel(RUTA_INFORME, index=False)
    print(f"Informe de auditoría guardado en: {RUTA_INFORME}")

if __name__ == "__main__":
    purgar_archivos_globales_activos()
    aplicar_ajustes_en_v2()
    print("\n>>> ¡PROCESO DE AJUSTES EN V2 FINALIZADO EXITOSAMENTE! <<<")
