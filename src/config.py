"""Configurações centrais do projeto de predição de óbito infantil."""

from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
DATA_RAW = RAIZ / "data" / "raw"
DATA_PROCESSED = RAIZ / "data" / "processed"
DATA_REDUZIDAS = RAIZ / "data" / "reduzidas"
OUTPUTS = RAIZ / "outputs"

ARQUIVO_SINASC = "DNRJ2023.csv"
ARQUIVO_SIM_2023 = "DOINF23.csv"
ARQUIVO_SIM_2024 = "DOINF24.csv"
ARQUIVO_VIVOS = "vivos.csv"
ARQUIVO_MORTOS = "mortos.csv"

RANDOM_STATE = 42
TEST_SIZE = 0.30
N_FOLDS = 5
SENSIBILIDADE_MINIMA = 0.70

COLUNAS_SINASC = [
    "CODMUNNASC",
    "APGAR5",
    "LOCNASC",
    "PESO",
    "SEXO",
    "PARTO",
    "DTNASC",
    "IDADEMAE",
    "ESTCIVMAE",
    "CODMUNRES",
    "GRAVIDEZ",
    "IDANOMAL",
    "ESCMAE2010",
    "QTDGESTANT",
    "KOTELCHUCK",
    "TPAPRESENT",
    "QTDPARTNOR",
    "QTDPARTCES",
    "SEMAGESTAC",
    "STTRABPART",
    "RACACOR",
]

COLUNAS_SIM = [
    "TIPOBITO",
    "PESO",
    "SEXO",
    "RACACOR",
    "ESCMAE2010",
    "PARTO",
    "DTNASC",
    "DTOBITO",
    "CODMUNRES",
    "CODMUNNATU",
    "GRAVIDEZ",
    "LOCOCOR",
]
