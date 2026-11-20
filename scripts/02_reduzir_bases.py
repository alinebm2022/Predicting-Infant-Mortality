"""Cria bases reduzidas mantendo os valores originais como texto."""

import sys
import tempfile
from pathlib import Path

import pandas as pd


RAIZ_REPOSITORIO = Path(__file__).resolve().parents[1]
if str(RAIZ_REPOSITORIO) not in sys.path:
    sys.path.insert(0, str(RAIZ_REPOSITORIO))

from src.arquivo_csv import ler_csv_com_deteccao  # noqa: E402
from src.config import (  # noqa: E402
    ARQUIVO_MORTOS,
    ARQUIVO_SIM_2023,
    ARQUIVO_SIM_2024,
    ARQUIVO_SINASC,
    ARQUIVO_VIVOS,
    COLUNAS_SIM,
    COLUNAS_SINASC,
    DATA_RAW,
    DATA_REDUZIDAS,
    OUTPUTS,
)


TAMANHO_MAXIMO_MB = 50
ARQUIVO_ORIGEM = "ARQUIVO_ORIGEM"


def ler_base_original(
    nome_arquivo: str, colunas_necessarias: list[str]
) -> tuple[pd.DataFrame, int, int, float, str]:
    """Lê a base toda como texto e falha claramente se faltarem colunas."""
    caminho = DATA_RAW / nome_arquivo
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo original não encontrado: {caminho}")

    dados, encoding, separador = ler_csv_com_deteccao(
        caminho, dtype=str, preservar_texto=True
    )
    ausentes = [coluna for coluna in colunas_necessarias if coluna not in dados.columns]
    if ausentes:
        raise ValueError(
            f"O arquivo {nome_arquivo} não contém as colunas obrigatórias: "
            f"{', '.join(ausentes)}"
        )

    tamanho_mb = caminho.stat().st_size / (1024 * 1024)
    return dados, len(dados), len(dados.columns), tamanho_mb, separador


def tamanho_mb(caminho: Path) -> float:
    """Retorna o tamanho do arquivo em MiB para os relatórios."""
    return caminho.stat().st_size / (1024 * 1024)


def medir_tamanho_csv(dados: pd.DataFrame, separador: str) -> float:
    """Mede o tamanho UTF-8 da seleção antes da concatenação das bases SIM."""
    DATA_REDUZIDAS.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=DATA_REDUZIDAS, suffix=".csv", delete=False
    ) as arquivo_temporario:
        caminho_temporario = Path(arquivo_temporario.name)

    try:
        dados.to_csv(
            caminho_temporario,
            sep=separador,
            encoding="utf-8",
            index=False,
        )
        return tamanho_mb(caminho_temporario)
    finally:
        caminho_temporario.unlink(missing_ok=True)


def salvar_base_reduzida(
    dados: pd.DataFrame, caminho_csv: Path, separador: str
) -> Path:
    """Salva CSV UTF-8 e comprime se o arquivo exceder 50 MB."""
    caminho_csv.parent.mkdir(parents=True, exist_ok=True)
    dados.to_csv(caminho_csv, sep=separador, encoding="utf-8", index=False)
    if tamanho_mb(caminho_csv) <= TAMANHO_MAXIMO_MB:
        return caminho_csv

    caminho_gzip = caminho_csv.with_suffix(caminho_csv.suffix + ".gz")
    dados.to_csv(
        caminho_gzip,
        sep=separador,
        encoding="utf-8",
        index=False,
        compression="gzip",
    )
    caminho_csv.unlink()
    return caminho_gzip


def linhas_base(
    rotulo: str,
    nome_arquivo: str,
    linhas_antes: int,
    colunas_antes: int,
    tamanho_antes: float,
    dados_reduzidos: pd.DataFrame,
    tamanho_depois: float,
) -> list[str]:
    """Formata as dimensões antes e depois da seleção de colunas."""
    return [
        f"\n{rotulo} ({nome_arquivo}):",
        f"  Antes: {linhas_antes:,} linhas x {colunas_antes} colunas; "
        f"{tamanho_antes:.2f} MB",
        f"  Depois da seleção: {len(dados_reduzidos):,} linhas x "
        f"{len(dados_reduzidos.columns)} colunas; {tamanho_depois:.2f} MB",
    ]


def gerar_bases_reduzidas() -> str:
    """Seleciona colunas e concatena os dois arquivos do SIM sem alterar linhas."""
    relatorio = ["REDUÇÃO DAS BASES DATASUS"]

    sinasc, n_sinasc, p_sinasc, mb_sinasc, sep_sinasc = ler_base_original(
        ARQUIVO_SINASC, COLUNAS_SINASC
    )
    vivos = sinasc.loc[:, COLUNAS_SINASC].copy()
    del sinasc

    caminho_vivos = salvar_base_reduzida(
        vivos, DATA_REDUZIDAS / ARQUIVO_VIVOS, sep_sinasc
    )
    vivos_mb = tamanho_mb(caminho_vivos)
    relatorio.extend(
        linhas_base(
            "SINASC — vivos",
            ARQUIVO_SINASC,
            n_sinasc,
            p_sinasc,
            mb_sinasc,
            vivos,
            vivos_mb,
        )
    )
    relatorio.append(
        f"  Arquivo gerado: {caminho_vivos.relative_to(RAIZ_REPOSITORIO)} "
        f"({vivos_mb:.2f} MB)"
    )
    relatorio.append(
        "  Verificação de linhas: "
        f"{len(vivos):,} == {n_sinasc:,} "
        f"({'OK' if len(vivos) == n_sinasc else 'FALHOU'})"
    )

    sim_2023, n_2023, p_2023, mb_2023, sep_2023 = ler_base_original(
        ARQUIVO_SIM_2023, COLUNAS_SIM
    )
    reduzido_2023 = sim_2023.loc[:, COLUNAS_SIM].copy()
    del sim_2023

    sim_2024, n_2024, p_2024, mb_2024, sep_2024 = ler_base_original(
        ARQUIVO_SIM_2024, COLUNAS_SIM
    )
    reduzido_2024 = sim_2024.loc[:, COLUNAS_SIM].copy()
    del sim_2024

    if sep_2023 != sep_2024:
        raise ValueError(
            "Os arquivos SIM 2023 e SIM 2024 usam separadores diferentes "
            f"({sep_2023!r} e {sep_2024!r}); não é possível gerar um CSV combinado "
            "com o mesmo separador das duas fontes."
        )

    indice_2023 = pd.MultiIndex.from_frame(reduzido_2023.drop_duplicates())
    duplicadas_entre_sim = int(
        pd.MultiIndex.from_frame(reduzido_2024).isin(indice_2023).sum()
    )
    relatorio.extend(
        linhas_base(
            "SIM — origem",
            ARQUIVO_SIM_2023,
            n_2023,
            p_2023,
            mb_2023,
            reduzido_2023,
            medir_tamanho_csv(reduzido_2023, sep_2023),
        )
    )
    relatorio.extend(
        linhas_base(
            "SIM — origem",
            ARQUIVO_SIM_2024,
            n_2024,
            p_2024,
            mb_2024,
            reduzido_2024,
            medir_tamanho_csv(reduzido_2024, sep_2024),
        )
    )
    relatorio.append(
        "\nLinhas do SIM 2024 que também aparecem no SIM 2023 "
        f"(nas colunas selecionadas): {duplicadas_entre_sim:,}"
    )

    reduzido_2023[ARQUIVO_ORIGEM] = Path(ARQUIVO_SIM_2023).stem
    reduzido_2024[ARQUIVO_ORIGEM] = Path(ARQUIVO_SIM_2024).stem
    mortos = pd.concat([reduzido_2023, reduzido_2024], ignore_index=True)
    del reduzido_2023, reduzido_2024, indice_2023

    caminho_mortos = salvar_base_reduzida(
        mortos, DATA_REDUZIDAS / ARQUIVO_MORTOS, sep_2023
    )
    mortos_mb = tamanho_mb(caminho_mortos)
    total_sim = n_2023 + n_2024
    relatorio.extend(
        [
            "\nSIM concatenado — mortos:",
            f"  Antes: {n_2023:,} + {n_2024:,} linhas; "
            f"{p_2023} + {p_2024} colunas nos arquivos de origem",
            f"  Depois: {len(mortos):,} linhas x {len(mortos.columns)} colunas; "
            f"{mortos_mb:.2f} MB",
            f"  Arquivo gerado: {caminho_mortos.relative_to(RAIZ_REPOSITORIO)}",
            "  Verificação de linhas: "
            f"{len(mortos):,} == {n_2023:,} + {n_2024:,} = {total_sim:,} "
            f"({'OK' if len(mortos) == total_sim else 'FALHOU'})",
        ]
    )

    if caminho_vivos.suffixes[-2:] == [".csv", ".gz"]:
        relatorio.append(
            f"\nAVISO: {caminho_vivos.name} foi comprimido por exceder 50 MB."
        )
    if caminho_mortos.suffixes[-2:] == [".csv", ".gz"]:
        relatorio.append(
            f"\nAVISO: {caminho_mortos.name} foi comprimido por exceder 50 MB."
        )

    return "\n".join(relatorio) + "\n"


def main() -> None:
    """Gera as bases reduzidas e imprime e grava o relatório."""
    relatorio = gerar_bases_reduzidas()
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    caminho_relatorio = OUTPUTS / "reducao_bases.txt"
    caminho_relatorio.write_text(relatorio, encoding="utf-8")
    print(relatorio, end="")
    print(f"\nRelatório salvo em: {caminho_relatorio}")


if __name__ == "__main__":
    main()
