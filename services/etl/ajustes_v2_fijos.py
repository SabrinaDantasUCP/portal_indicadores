# -*- coding: utf-8 -*-
"""
Ajustes Académicos Fijos para la Base V2 (Alumnos con Corte)
===========================================================
Este módulo contiene de forma fija, nominal e inmutable:
1. Bajas definitivas históricas por RUES (Josafa Leite Valadares y Julia Regis Santos Silva).
2. Reasignaciones nominales de comisiones aprobadas por Dirección (61 alumnos, 166 registros),
   documentando explícitamente el cambio de sección (ej. A -> C, G -> D, etc.).

VENTAJAS:
- 100% en memoria (ejecución en ~1 segundo para 500k+ filas).
- Sin dependencias de lectura de archivos Excel externos en tiempo de ejecución.
- Garantiza que calificaciones, notas 1 a 5 y resultados se preservan 100% intactos.
- Inmune a borrados accidentales de archivos en el servidor.
"""
import logging
import pandas as pd

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 1. BAJAS DEFINITIVAS HISTÓRICAS (RUES)
# ─────────────────────────────────────────────────────────────────────────────
IDS_BAJAS_DEFINITIVAS_V2 = {
    14328,  # Josafa Leite Valadares (baja total en todos los periodos históricos en V2)
    12448,  # Julia Regis Santos Silva (baja total en todos los periodos históricos en V2)
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. REASIGNACIONES NOMINALES INTEGRALES (61 ALUMNOS / 166 REGISTROS)
# Clave: (ano, periodo, usuarios_id, disciplina)
# Valor: (turma_antigua, turma_nueva, id_oferta_nueva, docente_nuevo)
# Comentario: # Nombre del Alumno | Cambio: turma_antigua -> turma_nueva
# ─────────────────────────────────────────────────────────────────────────────
REASIGNACIONES_NOMINALES_SECCIONES_V2 = {
    (2023, 1, 10323, None): (None, 'D', None, None),  # Jose Carlos Alves Magalhaes | Sección: Sin Sección -> D
    (2023, 1, 10323, None): (None, 'D', None, None),  # Jose Carlos Alves Magalhaes | Sección: Sin Sección -> D
    (2023, 1, 13398, 'Fisiología I'): ('G', 'D', 5676, 'Hector Quevedo'),  # Rayssa Sass | Sección: G -> D
    (2023, 1, 13398, 'Genética Humana'): ('G', 'D', 5678, 'Gabriela Beatriz Gonzalez Martinez'),  # Rayssa Sass | Sección: G -> D
    (2023, 2, 12538, 'Bioestadística'): ('A', 'B', 6677, 'Aldo René Arévalos Ysasi'),  # Ana Carolina Rodrigues Nascimento Soares | Sección: A -> B
    (2023, 2, 12538, 'Bioquímica II'): ('A', 'B', 6775, 'Aida Sylvana Marecos Prieto'),  # Ana Carolina Rodrigues Nascimento Soares | Sección: A -> B
    (2023, 2, 12538, 'Historia de la Medicina'): ('D', 'B', 6350, 'Derlis Adalberto Gonzalez Acosta'),  # Ana Carolina Rodrigues Nascimento Soares | Sección: D -> B
    (2023, 2, 12538, 'Lengua Castellana'): ('D', 'B', 6352, 'Wilma Cecilia Talavera De Flor'),  # Ana Carolina Rodrigues Nascimento Soares | Sección: D -> B
    (2023, 2, 12538, 'Microbiología II'): ('B', 'B', 6773, 'Carlos Javier Melgarejo Ocampos'),  # Ana Carolina Rodrigues Nascimento Soares | Sección: B -> B
    (2023, 2, 17049, 'Anatomía II'): ('G', 'E', 6695, 'Ruben Sosa Garcete'),  # Gardem Luiz Bino Bastos | Sección: G -> E
    (2023, 2, 18062, None): (None, 'G', None, None),  # Ketlyn De Paulo Rocha | Sección: Sin Sección -> G
    (2023, 2, 18510, 'Anatomía II'): ('G', 'E', 6695, 'Ruben Sosa Garcete'),  # Mirian ferreira De Almeida | Sección: G -> E
    (2023, 2, 18069, None): (None, 'G', None, None),  # Paulo Cesar Ipiranga Dos Santos | Sección: Sin Sección -> G
    (2024, 1, 19923, 'Anatomía II'): ('E', 'E', 7157, 'Ruben Sosa Garcete'),  # Anna Rafaela Kozideloski Luciano | Sección: E -> E
    (2024, 1, 19923, 'Bioestadística'): ('E', 'E', 7160, 'Aldo René Arévalos Ysasi'),  # Anna Rafaela Kozideloski Luciano | Sección: E -> E
    (2024, 1, 19923, 'Histología II'): ('E', 'E', 7158, 'Solanche Stefany Molinas Franco'),  # Anna Rafaela Kozideloski Luciano | Sección: E -> E
    (2024, 1, 16160, 'Anatomía I'): ('K', 'E', 7130, 'Victor Manuel Benitez Delgado'),  # Gicely Adriane Cruz Pires | Sección: K -> E
    (2024, 1, 21365, None): (None, 'E', None, None),  # Humberto De Souza Mercedes | Sección: Sin Sección -> E
    (2024, 1, 13032, 'Bioquímica II'): ('B', 'A', 7231, 'Aida Sylvana Marecos Prieto'),  # Kacio Rodrigues Cortez | Sección: B -> A
    (2024, 1, 13032, 'Fisiopatología II'): ('A', 'A', 7312, 'Jorge José Daniel Zorrilla Rivas'),  # Kacio Rodrigues Cortez | Sección: A -> A
    (2024, 1, 12860, 'Anestesiología'): ('G', 'D', 7665, 'Luis Gabriel González Britos'),  # Larissa Torres Da Silva | Sección: G -> D
    (2024, 1, 12860, 'Dermatología'): ('G', 'D', 7667, 'Gloria Beatriz Benitez Fleitas'),  # Larissa Torres Da Silva | Sección: G -> D
    (2024, 1, 12860, 'Neurología'): ('G', 'D', 7656, 'Rafael Estrada'),  # Larissa Torres Da Silva | Sección: G -> D
    (2024, 1, 12860, 'Oftalmología'): ('G', 'D', 7663, 'Liz Patricia Cardozo Davalos'),  # Larissa Torres Da Silva | Sección: G -> D
    (2024, 1, 12860, 'Ortopedia y Traumatología'): ('G', 'D', 7657, 'Agustin Rene Torres Corrales'),  # Larissa Torres Da Silva | Sección: G -> D
    (2024, 1, 12860, 'Toxicología'): ('G', 'D', 7666, 'Romina Lorena Acosta Santacruz'),  # Larissa Torres Da Silva | Sección: G -> D
    (2024, 1, 13048, 'Fisiología I'): ('F', 'D', 7195, 'Noelia Josefina Meaurio Pintos'),  # Pedro Henrique Ribeiro de Almeida | Sección: F -> D
    (2024, 1, 13505, 'Fisiopatología II'): ('B', 'A', 7312, 'Jorge José Daniel Zorrilla Rivas'),  # Ruhany Cristiny Rodrigues Ferraro | Sección: B -> A
    (2024, 1, 13505, 'Semiología Médica II'): ('B', 'A', 7313, 'Andressa Fernanda Britez Machado'),  # Ruhany Cristiny Rodrigues Ferraro | Sección: B -> A
    (2024, 1, 13894, 'Fisiopatología II'): ('B', 'A', 7312, 'Jorge José Daniel Zorrilla Rivas'),  # Suelli Da Silva Mota Morais | Sección: B -> A
    (2024, 1, 13894, 'Semiología Médica II'): ('B', 'A', 7313, 'Andressa Fernanda Britez Machado'),  # Suelli Da Silva Mota Morais | Sección: B -> A
    (2024, 2, 21491, 'Anatomía Patológica I'): ('G', 'B', 8380, 'Carmen Coba'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Farmacología I'): ('G', 'B', 8384, 'Willian David Velazquez Silva'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Fisiopatología I'): ('G', 'B', 8381, 'Eliana Maria Intes Chamorro Krauer'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Imagenología'): ('G', 'B', 8385, 'Hugo Ricardo Armoa'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Medicina de la Familia'): ('G', 'B', 8392, 'Andrea Villamayor Amarilla'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Semiología Médica I'): ('G', 'B', 8386, 'Lilian Antonia Nuñez Bogado'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Anatomía Patológica II'): ('G', 'B', 8444, 'Eliana Maria Intes Chamorro Krauer'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Farmacología II'): ('G', 'B', 8448, 'Willian David Velazquez Silva'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Fisiopatología II'): ('G', 'B', 8446, 'Rafael Estrada'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Gestión en Salud'): ('G', 'B', 8455, 'Andrea Beatriz Ruffinelli Adorno'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Medicina Legal'): ('G', 'B', 8454, 'Richard David Vazquez Castillo - Colaborador'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 21491, 'Semiología Médica II'): ('G', 'B', 8451, 'Lilian Antonia Nuñez Bogado'),  # André Bernardes Silva Filho | Sección: G -> B
    (2024, 2, 18847, 'Bioquímica I'): ('E', 'D', 8198, 'Andrea Lopez'),  # Clara Milena Pires Dos Santos | Sección: E -> D
    (2024, 2, 18847, 'Fisiología I'): ('E', 'D', 8200, 'Willian Jhonatan Gamarra Romero'),  # Clara Milena Pires Dos Santos | Sección: E -> D
    (2024, 2, 13445, None): (None, 'A', None, None),  # Kairo Neri Dos Santos | Sección: Sin Sección -> A
    (2024, 2, 13445, 'Gineco–Obstetricia I'): ('E', 'A', 8548, 'Fatima Yow Chin Lin Bogado'),  # Kairo Neri Dos Santos | Sección: E -> A
    (2024, 2, 13445, 'Hematología y Hemoterapia'): ('E', 'A', 8560, 'Nilse Noemi Cubilla Martinez'),  # Kairo Neri Dos Santos | Sección: E -> A
    (2024, 2, 13445, 'Medicina Interna I'): ('E', 'A', 8545, 'Rufino Yavin Barreto Segovia'),  # Kairo Neri Dos Santos | Sección: E -> A
    (2024, 2, 13445, 'Neumología'): ('E', 'A', 8555, 'Axel Raul Maizares Aguilera'),  # Kairo Neri Dos Santos | Sección: E -> A
    (2024, 2, 13445, 'Psiquiatría'): ('E', 'A', 8553, 'Gloria Beatriz Benitez Fleitas'),  # Kairo Neri Dos Santos | Sección: E -> A
    (2024, 2, 13445, 'Urología'): ('E', 'A', 8550, 'Diogenes Durañones Gongora'),  # Kairo Neri Dos Santos | Sección: E -> A
    (2024, 2, 21817, None): (None, 'B', None, None),  # Pedro Marcelo Granata Mendes Silva | Sección: Sin Sección -> B
    (2024, 2, 6848, 'Farmacología II'): ('C', 'A', 8426, 'Willian David Velazquez Silva'),  # Thais Lopes Araujo | Sección: C -> A
    (2025, 1, 23492, 'Anatomía I'): ('P', 'H', 9123, 'Natalia Chaveli Martinez Agüero'),  # Adryan Fernandes Plens | Sección: P -> H
    (2025, 1, 27078, 'Bioquímica I'): ('I', 'A', 9174, 'Gloria Beatriz Gennaro Medina'),  # Alexsander Fernando Gaelzer | Sección: I -> A
    (2025, 1, 27078, 'Bioética'): ('C', 'A', 9334, 'Silvia Raquel Nuarte De Lopez'),  # Alexsander Fernando Gaelzer | Sección: C -> A
    (2025, 1, 27078, 'Inglés Instrumental'): ('I', 'A', 9199, 'Janna Chahade Martinez'),  # Alexsander Fernando Gaelzer | Sección: I -> A
    (2025, 1, 27078, 'Inmunología'): ('I', 'A', 9190, 'Mariela Teresa Arguello Gonzalez'),  # Alexsander Fernando Gaelzer | Sección: I -> A
    (2025, 1, 27078, 'Lengua Castellana'): ('L', 'A', 9080, 'Wilma Cecilia Talavera De Flor'),  # Alexsander Fernando Gaelzer | Sección: L -> A
    (2025, 1, 27078, 'Microbiología I'): ('I', 'A', 9198, 'Miguel Martinez Ramirez'),  # Alexsander Fernando Gaelzer | Sección: I -> A
    (2025, 1, 27078, 'Nutrición'): ('C', 'A', 9335, 'Milva Rocio Cardozo Soto'),  # Alexsander Fernando Gaelzer | Sección: C -> A
    (2025, 1, 13388, None): (None, 'A', None, None),  # Andreia De Almeida Nascimento | Sección: Sin Sección -> A
    (2025, 1, 4493, 'Farmacología I'): ('F', 'A', 9365, 'Edgar Ariel Pineda Acuña'),  # Caio Domingos | Sección: F -> A
    (2025, 1, 23889, 'Anatomía Patológica I'): ('G', 'A', 9362, 'Carmen Coba'),  # Celina Cauana Ramos Silva | Sección: G -> A
    (2025, 1, 23889, 'Fisiopatología I'): ('G', 'A', 9363, 'Eliana Maria Intes Chamorro Krauer'),  # Celina Cauana Ramos Silva | Sección: G -> A
    (2025, 1, 23889, 'Semiología Médica I'): ('G', 'A', 9366, 'Natalia Elizabeth Duarte Pinto'),  # Celina Cauana Ramos Silva | Sección: G -> A
    (2025, 1, 18034, None): (None, 'A', None, None),  # Cristina Dos Santos Doria Costa | Sección: Sin Sección -> A
    (2025, 1, 22423, None): (None, 'H', None, None),  # Francisco Xavier de Menezes Junior | Sección: Sin Sección -> H
    (2025, 1, 18599, 'Fisiología II'): ('D', 'C', 9344, 'Laura Jazmin Rojas Arzamendia'),  # Gabriela Correia Da Silva | Sección: D -> C
    (2025, 1, 18599, 'Genética Humana'): ('D', 'C', 9230, 'Arturo Alexander Acuña Melgarejo'),  # Gabriela Correia Da Silva | Sección: D -> C
    (2025, 1, 18599, 'Microbiología II'): ('D', 'C', 9345, 'Laura Jazmin Rojas Arzamendia'),  # Gabriela Correia Da Silva | Sección: D -> C
    (2025, 1, 6371, 'Fisiología II'): ('C', 'C', 9344, 'Laura Jazmin Rojas Arzamendia'),  # Gleison Ihara Ribeiro | Sección: C -> C
    (2025, 1, 7102, 'Titulación'): ('TITULACION F', 'E', 9661, 'Gabriela De La Paz Medina Dal Molin'),  # Gysellen Correia Bernardo Bobato | Sección: TITULACION F -> E
    (2025, 1, 15718, 'Fisiopatología I'): ('G', 'A', 9363, 'Eliana Maria Intes Chamorro Krauer'),  # Harison Luidy Melo De Souza | Sección: G -> A
    (2025, 1, 26220, 'Biofísica'): ('G', 'A', 9175, 'Diego Armando Gutierrez Caballero'),  # Heitor Marques De Melo Mendes De Souza | Sección: G -> A
    (2025, 1, 26220, 'Genética Humana'): ('G', 'A', 9192, 'Gabriela Beatriz Gonzalez Martinez'),  # Heitor Marques De Melo Mendes De Souza | Sección: G -> A
    (2025, 1, 26220, 'Guaraní'): ('G', 'A', 9182, 'Ignacia Mabel Silva De Fleitas'),  # Heitor Marques De Melo Mendes De Souza | Sección: G -> A
    (2025, 1, 26220, 'Inmunología'): ('G', 'A', 9190, 'Mariela Teresa Arguello Gonzalez'),  # Heitor Marques De Melo Mendes De Souza | Sección: G -> A
    (2025, 1, 26220, 'Lengua Castellana'): ('L', 'A', 9080, 'Wilma Cecilia Talavera De Flor'),  # Heitor Marques De Melo Mendes De Souza | Sección: L -> A
    (2025, 1, 26220, 'Microbiología I'): ('G', 'A', 9198, 'Miguel Martinez Ramirez'),  # Heitor Marques De Melo Mendes De Souza | Sección: G -> A
    (2025, 1, 26220, 'Nutrición'): ('D', 'A', 9335, 'Milva Rocio Cardozo Soto'),  # Heitor Marques De Melo Mendes De Souza | Sección: D -> A
    (2025, 1, 26220, 'Psicología en Salud'): ('F', 'A', 9181, 'Silvia Raquel Nuarte De Lopez'),  # Heitor Marques De Melo Mendes De Souza | Sección: F -> A
    (2025, 1, 21044, 'Fisiología II'): ('A', 'C', 9344, 'Laura Jazmin Rojas Arzamendia'),  # Laura Luciana Alves Tavares | Sección: A -> C
    (2025, 1, 12526, 'Fisiología I'): ('J', 'C', 9228, 'Sergio Eduardo Zorrilla Rivas'),  # Lazaro Bruno Ribeiro Flores | Sección: J -> C
    (2025, 1, 12526, 'Microbiología I'): ('J', 'C', 9231, 'Miguel Martinez Ramirez'),  # Lazaro Bruno Ribeiro Flores | Sección: J -> C
    (2025, 1, 20128, 'Bioquímica II'): ('D', 'A', 9333, 'Gloria Beatriz Gennaro Medina'),  # Luanndra Alves De Freitas Tristao | Sección: D -> A
    (2025, 1, 20128, 'Fisiología I'): ('F', 'A', 9188, 'Sergio Eduardo Zorrilla Rivas'),  # Luanndra Alves De Freitas Tristao | Sección: F -> A
    (2025, 1, 20128, 'Microbiología II'): ('D', 'A', 9332, 'Nidia Rosanaa Piñanez'),  # Luanndra Alves De Freitas Tristao | Sección: D -> A
    (2025, 1, 27249, 'Bioestadística'): ('B', 'C', 8239, 'Aldo René Arévalos Ysasi'),  # Marianne Fortes De Avila Amaral | Sección: B -> C
    (2025, 1, 27249, 'Bioquímica I'): ('H', 'C', 9220, 'Andrea Lopez'),  # Marianne Fortes De Avila Amaral | Sección: H -> C
    (2025, 1, 27249, 'Bioética'): ('D', 'C', 9347, 'Silvia Raquel Nuarte De Lopez'),  # Marianne Fortes De Avila Amaral | Sección: D -> C
    (2025, 1, 27249, 'Inmunología'): ('H', 'C', 9229, 'Mariela Teresa Arguello Gonzalez'),  # Marianne Fortes De Avila Amaral | Sección: H -> C
    (2025, 1, 27249, 'Microbiología I'): ('H', 'C', 9231, 'Miguel Martinez Ramirez'),  # Marianne Fortes De Avila Amaral | Sección: H -> C
    (2025, 1, 27249, 'Nutrición'): ('D', 'C', 9348, 'Milva Rocio Cardozo Soto'),  # Marianne Fortes De Avila Amaral | Sección: D -> C
    (2025, 1, 14614, 'Anatomía Patológica II'): ('D', 'A', 9405, 'Eliana Maria Intes Chamorro Krauer'),  # Nayara Rebouças Da Silva | Sección: D -> A
    (2025, 1, 14614, 'Epidemiología y Salud Pública'): ('E', 'A', 9336, 'Diego Armando Gutierrez Caballero'),  # Nayara Rebouças Da Silva | Sección: E -> A
    (2025, 1, 14614, 'Farmacología II'): ('D', 'A', 9407, 'Luz Janette Quevedo Sosa'),  # Nayara Rebouças Da Silva | Sección: D -> A
    (2025, 1, 14614, 'Microbiología II'): ('B', 'A', 9332, 'Nidia Rosanaa Piñanez'),  # Nayara Rebouças Da Silva | Sección: B -> A
    (2025, 1, 17533, 'Bioquímica II'): ('B', 'B', 9339, 'Gloria Beatriz Gennaro Medina'),  # Samira Silva Nogueira | Sección: B -> B
    (2025, 1, 17533, 'Fisiología II'): ('E', 'B', 9337, 'Maria Fernanda Aveiro'),  # Samira Silva Nogueira | Sección: E -> B
    (2025, 1, 22574, None): (None, 'H', None, None),  # William Robert De Souza | Sección: Sin Sección -> H
    (2025, 2, 27449, 'Bioética'): ('A', 'A', 9964, 'Silvia Raquel Nuarte De Lopez'),  # Adriano Santos Cabral | Sección: A -> A
    (2025, 2, 27449, 'Genética Humana'): ('E', 'A', 9899, 'Dayssy Lorena Franco'),  # Adriano Santos Cabral | Sección: E -> A
    (2025, 2, 21917, 'Anatomía II'): ('J', 'H', 9858, 'Victor Manuel Benitez Delgado'),  # Ana Caroline Binek Stanski | Sección: J -> H
    (2025, 2, 21917, 'Bioquímica I'): ('G', 'H', 9992, 'Andrea Lopez'),  # Ana Caroline Binek Stanski | Sección: G -> H
    (2025, 2, 29986, None): (None, 'H', None, None),  # Augusto Henrique Rocha Vieira | Sección: Sin Sección -> H
    (2025, 2, 13120, 'Bioseguridad'): ('B', 'D', 10816, 'Edilson Sudario Diniz Junior'),  # Debora Gomes Martins | Sección: B -> D
    (2025, 2, 13120, 'Clínica Quirugica II'): ('B', 'D', 10687, 'Sandra Ester Pinto Benitez'),  # Debora Gomes Martins | Sección: B -> D
    (2025, 2, 13120, 'Medicina Interna III'): ('B', 'D', 10688, 'Liliana Carolina Portillo Orue'),  # Debora Gomes Martins | Sección: B -> D
    (2025, 2, 13120, 'Oncología'): ('B', 'D', 10689, 'Aldo Artemio Torres Rodriguez'),  # Debora Gomes Martins | Sección: B -> D
    (2025, 2, 13120, 'Otorrinolaringología'): ('B', 'D', 10690, 'Alba Maria Del Rosario Brun Ayala'),  # Debora Gomes Martins | Sección: B -> D
    (2025, 2, 13120, 'Pediatría II'): ('B', 'D', 10686, 'Karina Andrea Cáceres Vich'),  # Debora Gomes Martins | Sección: B -> D
    (2025, 2, 13120, 'Salud Pública - Mercosur'): ('B', 'D', 10691, 'Andrea Beatriz Ramirez Soto'),  # Debora Gomes Martins | Sección: B -> D
    (2025, 2, 21753, 'Anatomía II'): ('M', 'H', 9858, 'Victor Manuel Benitez Delgado'),  # Eduardo Maia Oliveira | Sección: M -> H
    (2025, 2, 21753, 'Inmunología'): ('G', 'H', 9997, 'Noelia Josefina Meaurio Pintos'),  # Eduardo Maia Oliveira | Sección: G -> H
    (2025, 2, 21697, 'Fisiología I'): ('H', 'H', 9996, 'Maria Fernanda Aveiro'),  # Fabricio Falcao Vargas | Sección: H -> H
    (2025, 2, 8696, 'Lengua Castellana'): ('H', 'D', 9758, 'Wilma Cecilia Talavera De Flor'),  # Genilson Soares Moreira Junior | Sección: H -> D
    (2025, 2, 12783, 'Bioseguridad'): ('B', 'D', 10816, 'Edilson Sudario Diniz Junior'),  # Higia Gomes Alcantara | Sección: B -> D
    (2025, 2, 12783, 'Clínica Quirugica II'): ('B', 'D', 10687, 'Sandra Ester Pinto Benitez'),  # Higia Gomes Alcantara | Sección: B -> D
    (2025, 2, 12783, 'Medicina Interna III'): ('B', 'D', 10688, 'Liliana Carolina Portillo Orue'),  # Higia Gomes Alcantara | Sección: B -> D
    (2025, 2, 12783, 'Oncología'): ('B', 'D', 10689, 'Aldo Artemio Torres Rodriguez'),  # Higia Gomes Alcantara | Sección: B -> D
    (2025, 2, 12783, 'Otorrinolaringología'): ('B', 'D', 10690, 'Alba Maria Del Rosario Brun Ayala'),  # Higia Gomes Alcantara | Sección: B -> D
    (2025, 2, 12783, 'Pediatría II'): ('B', 'D', 10686, 'Karina Andrea Cáceres Vich'),  # Higia Gomes Alcantara | Sección: B -> D
    (2025, 2, 12783, 'Salud Pública - Mercosur'): ('B', 'D', 10691, 'Andrea Beatriz Ramirez Soto'),  # Higia Gomes Alcantara | Sección: B -> D
    (2025, 2, 27448, 'Bioética'): ('A', 'A', 9964, 'Silvia Raquel Nuarte De Lopez'),  # Juliana Lima Montel | Sección: A -> A
    (2025, 2, 27448, 'Genética Humana'): ('E', 'A', 9899, 'Dayssy Lorena Franco'),  # Juliana Lima Montel | Sección: E -> A
    (2025, 2, 30325, None): (None, 'J', None, None),  # Matheus Da Veiga Ferro Artusi | Sección: Sin Sección -> J
    (2025, 2, 13707, 'Bioseguridad'): ('A', 'D', 10816, 'Edilson Sudario Diniz Junior'),  # Michele Alves De Oliveira | Sección: A -> D
    (2025, 2, 13707, 'Clínica Quirugica II'): ('A', 'D', 10687, 'Sandra Ester Pinto Benitez'),  # Michele Alves De Oliveira | Sección: A -> D
    (2025, 2, 13707, 'Medicina Interna III'): ('A', 'D', 10688, 'Liliana Carolina Portillo Orue'),  # Michele Alves De Oliveira | Sección: A -> D
    (2025, 2, 13707, 'Oncología'): ('A', 'D', 10689, 'Aldo Artemio Torres Rodriguez'),  # Michele Alves De Oliveira | Sección: A -> D
    (2025, 2, 13707, 'Otorrinolaringología'): ('A', 'D', 10690, 'Alba Maria Del Rosario Brun Ayala'),  # Michele Alves De Oliveira | Sección: A -> D
    (2025, 2, 13707, 'Pediatría II'): ('A', 'D', 10686, 'Karina Andrea Cáceres Vich'),  # Michele Alves De Oliveira | Sección: A -> D
    (2025, 2, 13707, 'Salud Pública - Mercosur'): ('A', 'D', 10691, 'Andrea Beatriz Ramirez Soto'),  # Michele Alves De Oliveira | Sección: A -> D
    (2026, 1, 25022, 'Bioética'): ('B', 'G', 11156, 'Silvia Raquel Nuarte De Lopez'),  # Alex Botelho Santos | Sección: B -> G
    (2026, 1, 25022, 'Epidemiología y Salud Pública'): ('B', 'G', 11158, 'Milena Elizabeth Espinola Bellei'),  # Alex Botelho Santos | Sección: B -> G
    (2026, 1, 25022, 'Microbiología II'): ('B', 'G', 11153, 'Nidia Rosanaa Piñanez'),  # Alex Botelho Santos | Sección: B -> G
    (2026, 1, 25022, 'Nutrición'): ('B', 'G', 11157, 'Johana Belen Leguizamon Vera'),  # Alex Botelho Santos | Sección: B -> G
    (2026, 1, 14657, 'Neurología'): ('F', 'A', 11178, 'Silvia Gabriela Duarte Chavez'),  # Angelica De Araujo Paz | Sección: F -> A
    (2026, 1, 13891, 'Fisiopatología II'): ('A', 'A', 11218, 'Sandrina Kassouf Acharam'),  # Joao Antonio Vaz | Sección: A -> A
    (2026, 1, 12370, 'Neurología'): ('E', 'A', 11178, 'Silvia Gabriela Duarte Chavez'),  # Pedro Otavio Gomes Sanchez | Sección: E -> A
    (2026, 1, 12370, 'Toxicología'): ('E', 'A', 11189, 'Ramon Mario Bellon Prestamo'),  # Pedro Otavio Gomes Sanchez | Sección: E -> A
    (2026, 1, 24309, 'Bioquímica II'): ('B', 'G', 11155, 'Cindy Paola Lisboa Morquillas'),  # Rafael Pontes de Oliveira | Sección: B -> G
    (2026, 1, 24309, 'Bioética'): ('B', 'G', 11156, 'Silvia Raquel Nuarte De Lopez'),  # Rafael Pontes de Oliveira | Sección: B -> G
    (2026, 1, 24309, 'Epidemiología y Salud Pública'): ('B', 'G', 11158, 'Milena Elizabeth Espinola Bellei'),  # Rafael Pontes de Oliveira | Sección: B -> G
    (2026, 1, 24309, 'Fisiología II'): ('B', 'G', 11152, 'Federico Martin Hoge Melgarejo'),  # Rafael Pontes de Oliveira | Sección: B -> G
    (2026, 1, 24309, 'Microbiología II'): ('B', 'G', 11153, 'Nidia Rosanaa Piñanez'),  # Rafael Pontes de Oliveira | Sección: B -> G
    (2026, 1, 24309, 'Nutrición'): ('B', 'G', 11157, 'Johana Belen Leguizamon Vera'),  # Rafael Pontes de Oliveira | Sección: B -> G
    (2026, 1, 14143, 'Farmacología II'): ('A', 'A', 11215, 'Belen Veronica Vega Godoy'),  # Rodrigo Martins Dos Reis | Sección: A -> A
    (2026, 1, 14143, 'Fisiopatología II'): ('A', 'A', 11218, 'Sandrina Kassouf Acharam'),  # Rodrigo Martins Dos Reis | Sección: A -> A
    (2026, 1, 14699, 'Fisiología I'): ('O', 'A', 10918, 'Noelia Josefina Meaurio Pintos'),  # Suellen Nayra Barbosa De  Almeida | Sección: O -> A
    (2026, 1, 14698, 'Fisiología I'): ('O', 'A', 10918, 'Noelia Josefina Meaurio Pintos'),  # Suely Mayara Barbosa De Almeida | Sección: O -> A
    (2026, 1, 24189, 'Bioquímica II'): ('B', 'G', 11155, 'Cindy Paola Lisboa Morquillas'),  # Thais Diamantino de Sousa | Sección: B -> G
    (2026, 1, 24189, 'Bioética'): ('B', 'G', 11156, 'Silvia Raquel Nuarte De Lopez'),  # Thais Diamantino de Sousa | Sección: B -> G
    (2026, 1, 24189, 'Epidemiología y Salud Pública'): ('B', 'G', 11158, 'Milena Elizabeth Espinola Bellei'),  # Thais Diamantino de Sousa | Sección: B -> G
    (2026, 1, 24189, 'Fisiología II'): ('B', 'G', 11152, 'Federico Martin Hoge Melgarejo'),  # Thais Diamantino de Sousa | Sección: B -> G
    (2026, 1, 24189, 'Microbiología II'): ('B', 'G', 11153, 'Nidia Rosanaa Piñanez'),  # Thais Diamantino de Sousa | Sección: B -> G
    (2026, 1, 24189, 'Nutrición'): ('B', 'G', 11157, 'Johana Belen Leguizamon Vera'),  # Thais Diamantino de Sousa | Sección: B -> G
    (2026, 1, 10622, 'Dermatología'): ('E', 'A', 11192, 'Janna Chahade Martinez'),  # Vinicius Jardinetti Poiani | Sección: E -> A
    (2026, 1, 24222, 'Bioquímica II'): ('B', 'G', 11155, 'Cindy Paola Lisboa Morquillas'),  # Vivian Bonometti Sturza | Sección: B -> G
    (2026, 1, 24222, 'Bioética'): ('B', 'G', 11156, 'Silvia Raquel Nuarte De Lopez'),  # Vivian Bonometti Sturza | Sección: B -> G
    (2026, 1, 24222, 'Epidemiología y Salud Pública'): ('B', 'G', 11158, 'Milena Elizabeth Espinola Bellei'),  # Vivian Bonometti Sturza | Sección: B -> G
    (2026, 1, 24222, 'Fisiología II'): ('B', 'G', 11152, 'Federico Martin Hoge Melgarejo'),  # Vivian Bonometti Sturza | Sección: B -> G
    (2026, 1, 24222, 'Microbiología II'): ('B', 'G', 11153, 'Nidia Rosanaa Piñanez'),  # Vivian Bonometti Sturza | Sección: B -> G
    (2026, 1, 24222, 'Nutrición'): ('B', 'G', 11157, 'Johana Belen Leguizamon Vera'),  # Vivian Bonometti Sturza | Sección: B -> G
}

def aplicar_ajustes_direccion_v2(df_v2):
    """Aplica las bajas definitivas históricas y reasignaciones integrales
    de comisiones solicitadas por Dirección exclusivamente sobre V2 en memoria pura.
    Garantiza que las calificaciones, notas en escala y resultados queden 100% intactos.
    """
    if df_v2 is None or df_v2.empty:
        return df_v2

    df = df_v2.copy()

    # 1. Bajas definitivas de alumnos en todos los periodos de V2
    if IDS_BAJAS_DEFINITIVAS_V2:
        n_prev = len(df)
        df = df[~df['usuarios_id'].isin(IDS_BAJAS_DEFINITIVAS_V2)].copy()
        log.info("Ajustes V2: %d fila(s) eliminadas por bajas definitivas RUES: %s",
                 n_prev - len(df), IDS_BAJAS_DEFINITIVAS_V2)

    # 2. Reasignaciones nominales de ofertas (turma, id_oferta_disciplina, docente)
    if REASIGNACIONES_NOMINALES_SECCIONES_V2:
        disciplinas_limpias = [d if pd.notna(d) else None for d in df['disciplina']]
        claves = list(zip(
            pd.to_numeric(df['ano_periodo_letivo'], errors='coerce').fillna(0).astype(int),
            pd.to_numeric(df['periodo_anual_periodo_letivo'], errors='coerce').fillna(0).astype(int),
            pd.to_numeric(df['usuarios_id'], errors='coerce').fillna(0).astype(int),
            disciplinas_limpias
        ))

        turma_mods = 0
        turma_vals = df['turma'].to_numpy(copy=True)
        oferta_vals = df['id_oferta_disciplina'].to_numpy(copy=True)
        docente_vals = df['docente'].to_numpy(copy=True)

        for idx, k in enumerate(claves):
            if k in REASIGNACIONES_NOMINALES_SECCIONES_V2:
                _t_ant, t_nueva, of_nueva, doc_nuevo = REASIGNACIONES_NOMINALES_SECCIONES_V2[k]
                turma_vals[idx] = t_nueva
                if of_nueva is not None:
                    oferta_vals[idx] = of_nueva
                if doc_nuevo is not None:
                    docente_vals[idx] = doc_nuevo
                turma_mods += 1

        df['turma'] = turma_vals
        df['id_oferta_disciplina'] = oferta_vals
        df['docente'] = docente_vals
        log.info("Ajustes V2: %d registro(s) reasignados de sección con oferta y docente.", turma_mods)

    return df
