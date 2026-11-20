"""Inspeciona as bases brutas sem alterá-las nem gerar dados processados."""

import sys
from pathlib import Path

import pandas as pd


RAIZ_REPOSITORIO = Path(__file__).resolve().parents[1]
if str(RAIZ_REPOSITORIO) not in sys.path:
    sys.path.insert(0, str(RAIZ_REPOSITORIO))

from src.config import (  # noqa: E402
    ARQUIVO_SIM_2023,
    ARQUIVO_SIM_2024,
    ARQUIVO_SINASC,
    COLUNAS_SIM,
    COLUNAS_SINASC,
    DATA_RAW,
    OUTPUTS,
)
from src.arquivo_csv import ler_csv_com_deteccao  # noqa: E402


COLUNAS_CATEGORICAS = [
    "SEXO",
    "PARTO",
    "GRAVIDEZ",
    "LOCNASC",
    "IDANOMAL",
    "ESTCIVMAE",
    "ESCMAE2010",
    "KOTELCHUCK",
    "TPAPRESENT",
    "STTRABPART",
    "RACACOR",
]
def formatar_contagens(serie: pd.Series) -> str:
    """Formata contagens preservando também os valores ausentes."""
    return serie.value_counts(dropna=False).to_string()


def converter_data_ddmmaaaa(serie: pd.Series) -> pd.Series:
    """Converte datas numéricas ddmmaaaa, incluindo valores sem zero inicial."""
    texto = (
        serie.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(8)
    )
    return pd.to_datetime(texto, format="%d%m%Y", errors="coerce")


def adicionar_distribuicao_ano(
    linhas: list[str], dados: pd.DataFrame, nome_coluna: str, rotulo: str
) -> pd.Series | None:
    """Registra a distribuição de anos e devolve as datas convertidas."""
    if nome_coluna not in dados.columns:
        linhas.append(f"{rotulo}: coluna {nome_coluna} ausente.")
        return None

    datas = converter_data_ddmmaaaa(dados[nome_coluna])
    linhas.append(f"{rotulo} (inclui datas inválidas como NaT):")
    linhas.append(datas.dt.year.value_counts(dropna=False).sort_index().to_string())
    return datas


def inspecionar_base(
    linhas: list[str],
    rotulo: str,
    caminho: Path,
    dados: pd.DataFrame,
    colunas_esperadas: list[str],
) -> None:
    """Registra metadados, colunas selecionadas e valores ausentes da base."""
    tamanho_mb = caminho.stat().st_size / (1024 * 1024)
    faltantes = [coluna for coluna in colunas_esperadas if coluna not in dados.columns]
    linhas.extend(
        [
            f"\n{'=' * 78}",
            f"{rotulo}: {caminho.name}",
            f"Shape: {dados.shape}",
            f"Tamanho: {tamanho_mb:.2f} MB",
            f"Colunas esperadas presentes: {len(colunas_esperadas) - len(faltantes)}"
            f"/{len(colunas_esperadas)}",
            f"Colunas ausentes: {faltantes if faltantes else 'nenhuma'}",
            "Tipos e valores ausentes nas colunas selecionadas:",
        ]
    )

    for coluna in colunas_esperadas:
        if coluna not in dados.columns:
            linhas.append(f"  {coluna}: ausente")
            continue
        ausentes = int(dados[coluna].isna().sum())
        percentual = ausentes / len(dados) * 100 if len(dados) else 0
        linhas.append(
            f"  {coluna}: dtype={dados[coluna].dtype}, "
            f"ausentes={ausentes} ({percentual:.2f}%)"
        )

    linhas.append(f"Linhas duplicadas inteiras: {int(dados.duplicated().sum())}")


def inspecionar_categorias(
    linhas: list[str], rotulo: str, dados: pd.DataFrame
) -> None:
    """Lista códigos e contagens das variáveis categóricas disponíveis."""
    linhas.append(f"\nValores categóricos — {rotulo}:")
    for coluna in COLUNAS_CATEGORICAS:
        if coluna not in dados.columns:
            continue
        linhas.append(f"  {coluna}:")
        linhas.append(formatar_contagens(dados[coluna]))


def inspecionar_partos(linhas: list[str], dados: pd.DataFrame) -> None:
    """Resume códigos ignorados e máximos das contagens de partos anteriores."""
    linhas.append("\nContagens de partos anteriores — SINASC:")
    for coluna in ("QTDPARTNOR", "QTDPARTCES"):
        if coluna not in dados.columns:
            linhas.append(f"  {coluna}: coluna ausente")
            continue
        valores = pd.to_numeric(dados[coluna], errors="coerce")
        linhas.append(
            f"  {coluna}: valor 99 (ignorado)={int(valores.eq(99).sum())}; "
            f"máximo observado={valores.max()}"
        )


def gerar_relatorio() -> str:
    """Lê as três bases brutas e monta o relatório de inspeção."""
    bases = [
        ("SINASC 2023", ARQUIVO_SINASC, COLUNAS_SINASC),
        ("SIM 2023", ARQUIVO_SIM_2023, COLUNAS_SIM),
        ("SIM 2024", ARQUIVO_SIM_2024, COLUNAS_SIM),
    ]
    linhas: list[str] = ["INSPEÇÃO INICIAL DAS BASES DATASUS"]
    dados_por_nome: dict[str, pd.DataFrame] = {}

    for rotulo, nome_arquivo, colunas in bases:
        caminho = DATA_RAW / nome_arquivo
        if not caminho.is_file():
            raise FileNotFoundError(
                f"Base não encontrada em {caminho}. "
                "Coloque os CSVs em data/raw antes de executar a inspeção."
            )
        dados, encoding, separador = ler_csv_com_deteccao(caminho)
        dados_por_nome[nome_arquivo] = dados
        inspecionar_base(linhas, rotulo, caminho, dados, colunas)
        linhas.append(f"Separador detectado: {separador!r}; encoding: {encoding}")

    sinasc = dados_por_nome[ARQUIVO_SINASC]
    linhas.append("\nAnálise de datas — SINASC 2023:")
    datas_sinasc = adicionar_distribuicao_ano(
        linhas, sinasc, "DTNASC", "Distribuição do ano de DTNASC"
    )
    if datas_sinasc is not None:
        linhas.append(
            f"Datas DTNASC inválidas: {int(datas_sinasc.isna().sum())}"
        )

    for nome_arquivo, rotulo in (
        (ARQUIVO_SIM_2023, "SIM 2023"),
        (ARQUIVO_SIM_2024, "SIM 2024"),
    ):
        dados = dados_por_nome[nome_arquivo]
        linhas.append(f"\nAnálise de datas e óbitos — {rotulo}:")
        if "TIPOBITO" in dados.columns:
            linhas.append("Contagem de TIPOBITO:")
            linhas.append(formatar_contagens(dados["TIPOBITO"]))
        else:
            linhas.append("Coluna TIPOBITO ausente.")

        datas_nascimento = adicionar_distribuicao_ano(
            linhas, dados, "DTNASC", "Distribuição do ano de DTNASC"
        )
        adicionar_distribuicao_ano(
            linhas, dados, "DTOBITO", "Distribuição do ano de DTOBITO"
        )
        if datas_nascimento is not None:
            linhas.append(
                "Óbitos com DTNASC em 2023: "
                f"{int(datas_nascimento.dt.year.eq(2023).sum())}"
            )

    for nome_arquivo, rotulo in (
        (ARQUIVO_SINASC, "SINASC 2023"),
        (ARQUIVO_SIM_2023, "SIM 2023"),
        (ARQUIVO_SIM_2024, "SIM 2024"),
    ):
        inspecionar_categorias(linhas, rotulo, dados_por_nome[nome_arquivo])

    inspecionar_partos(linhas, sinasc)
    return "\n".join(linhas) + "\n"


def main() -> None:
    """Gera e exibe o relatório sem modificar as bases de entrada."""
    relatorio = gerar_relatorio()
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    caminho_relatorio = OUTPUTS / "inspecao_dados.txt"
    caminho_relatorio.write_text(relatorio, encoding="utf-8")
    print(relatorio, end="")
    print(f"\nRelatório salvo em: {caminho_relatorio}")


if __name__ == "__main__":
    main()
