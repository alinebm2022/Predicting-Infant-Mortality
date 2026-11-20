"""Leitura consistente das bases CSV usadas pelos scripts do projeto."""

import csv
from pathlib import Path

import pandas as pd


ENCODINGS_POSSIVEIS = ("utf-8-sig", "cp1252", "latin-1")
SEPARADORES_POSSIVEIS = ",;\t|"


def ler_csv_com_deteccao(
    caminho: Path,
    *,
    dtype: type | None = None,
    preservar_texto: bool = False,
) -> tuple[pd.DataFrame, str, str]:
    """Detecta encoding e separador antes de ler o CSV com o mecanismo C."""
    for encoding in ENCODINGS_POSSIVEIS:
        try:
            with caminho.open("r", encoding=encoding, newline="") as arquivo:
                amostra = arquivo.read(65536)
        except UnicodeDecodeError:
            continue

        try:
            separador = csv.Sniffer().sniff(
                amostra, delimiters=SEPARADORES_POSSIVEIS
            ).delimiter
        except csv.Error as erro:
            raise ValueError(
                f"Não foi possível detectar o separador do arquivo {caminho}."
            ) from erro

        try:
            dados = pd.read_csv(
                caminho,
                sep=separador,
                encoding=encoding,
                low_memory=False,
                dtype=dtype,
                keep_default_na=not preservar_texto,
            )
        except UnicodeDecodeError:
            continue

        return dados, encoding, separador

    raise ValueError(f"Não foi possível detectar o encoding de {caminho}.")
