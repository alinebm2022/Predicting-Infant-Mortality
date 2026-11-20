"""Executa o linkage determinístico e grava a base rotulada e seu relatório."""

import sys
from pathlib import Path

import pandas as pd


RAIZ_REPOSITORIO = Path(__file__).resolve().parents[1]
if str(RAIZ_REPOSITORIO) not in sys.path:
    sys.path.insert(0, str(RAIZ_REPOSITORIO))

from src.arquivo_csv import ler_csv_com_deteccao  # noqa: E402
from src.config import (  # noqa: E402
    ARQUIVO_MORTOS,
    ARQUIVO_VIVOS,
    DATA_PROCESSED,
    DATA_REDUZIDAS,
    OUTPUTS,
)
from src.linkage import (  # noqa: E402
    filtrar_obitos_candidatos,
    linkage_deterministico,
    padronizar_nascimentos,
    padronizar_obitos,
)


def caminho_base_reduzida(nome_arquivo: str) -> Path:
    """Localiza CSV simples ou comprimido, sem alterar os arquivos de entrada."""
    caminho = DATA_REDUZIDAS / nome_arquivo
    caminho_comprimido = caminho.with_suffix(caminho.suffix + ".gz")
    if caminho.is_file():
        return caminho
    if caminho_comprimido.is_file():
        return caminho_comprimido
    raise FileNotFoundError(
        f"Base reduzida não encontrada: {caminho} nem {caminho_comprimido}"
    )


def ler_base_reduzida(caminho: Path) -> tuple[pd.DataFrame, str]:
    """Lê uma base sem converter códigos, datas ou campos vazios."""
    dados, _, separador = ler_csv_com_deteccao(
        caminho, dtype=str, preservar_texto=True
    )
    return dados, separador


def distribuicao_tamanho_codigo(serie: pd.Series) -> dict[str, int]:
    """Resume comprimentos dos códigos originais para sinalizar formatos distintos."""
    digitos = serie.astype("string").str.replace(r"\D", "", regex=True)
    tamanhos = digitos.str.len().fillna(0).astype(int).replace(0, pd.NA)
    resumo = {
        str(chave): int(valor)
        for chave, valor in tamanhos.value_counts().sort_index().items()
    }
    ausentes = int(digitos.isna().sum() + digitos.eq("").sum())
    if ausentes:
        resumo["ausente"] = ausentes
    return resumo


def formatar_distribuicao(titulo: str, distribuicao: dict[str, int]) -> list[str]:
    """Gera linhas legíveis para relatórios de frequências."""
    return [f"{titulo}:"] + [
        f"  {codigo}: {contagem:,}"
        for codigo, contagem in sorted(distribuicao.items())
    ]


def montar_relatorio(
    vivos_originais: pd.DataFrame,
    vivos_padronizados: pd.DataFrame,
    candidatos: pd.DataFrame,
    resumo_filtro: dict[str, object],
    resultado: pd.DataFrame,
    resumo_linkage: dict[str, int],
    vivos_reduzidos: pd.DataFrame,
    mortos_reduzidos: pd.DataFrame,
) -> str:
    """Resume população, filtros, pares e prevalência sem selecionar coorte."""
    linhas = ["RELATÓRIO DO LINKAGE DETERMINÍSTICO"]
    uf_nasc = vivos_padronizados["UF_NASC_PAD"].fillna("<ausente>")
    distribuicao_uf_nasc = {
        str(uf): int(contagem)
        for uf, contagem in uf_nasc.value_counts().items()
    }
    fora_rj = vivos_padronizados["UF_NASC_PAD"].notna() & (
        vivos_padronizados["UF_NASC_PAD"] != "33"
    )
    uf_ausente = vivos_padronizados["UF_NASC_PAD"].isna()
    linhas.extend(
        [
            f"Nascimentos lidos: {len(vivos_originais):,}",
            *formatar_distribuicao(
                "Distribuição de UF em CODMUNNASC (SINASC)",
                distribuicao_uf_nasc,
            ),
            f"Nascimentos excluídos do linkage por UF diferente de 33: "
            f"{int(fora_rj.sum()):,}",
            f"Nascimentos com UF ausente em CODMUNNASC: {int(uf_ausente.sum()):,}",
            "",
            "Formato dos códigos municipais originais:",
        ]
    )
    tamanhos_nasc = distribuicao_tamanho_codigo(vivos_reduzidos["CODMUNNASC"])
    tamanhos_natu = distribuicao_tamanho_codigo(mortos_reduzidos["CODMUNNATU"])
    linhas.extend(
        formatar_distribuicao("  Comprimentos em CODMUNNASC", tamanhos_nasc)
    )
    linhas.extend(
        formatar_distribuicao("  Comprimentos em CODMUNNATU", tamanhos_natu)
    )
    comprimentos_nasc = {t for t in tamanhos_nasc if t != "ausente"}
    comprimentos_natu = {t for t in tamanhos_natu if t != "ausente"}
    if comprimentos_nasc != comprimentos_natu:
        linhas.append(
            "AVISO: os comprimentos de CODMUNNASC e CODMUNNATU diferem; "
            "os códigos foram normalizados para seis dígitos."
        )
    else:
        linhas.append(
            "Os comprimentos não ausentes de CODMUNNASC e CODMUNNATU "
            "são compatíveis."
        )

    linhas.extend(
        [
            "",
            f"Óbitos lidos: {int(resumo_filtro['n_obitos_inicial']):,}",
            "Valores encontrados em TIPOBITO:",
        ]
    )
    valores_tipobito = resumo_filtro["valores_tipobito"]
    for codigo, contagem in sorted(valores_tipobito.items()):
        linhas.append(f"  {codigo}: {contagem:,}")

    linhas.extend(
        [
            "",
            "UF de CODMUNNATU nos óbitos com DTNASC em 2023:",
            *formatar_distribuicao("", resumo_filtro["uf_natu_dtnasc_2023"])[1:],
            "UF de CODMUNRES nos óbitos com DTNASC em 2023:",
            *formatar_distribuicao("", resumo_filtro["uf_res_dtnasc_2023"])[1:],
            "CODMUNNATU ausente nesses óbitos: "
            f"{int(resumo_filtro['n_natu_ausente_dtnasc_2023']):,}",
            "",
            "Etapas do filtro de óbitos candidatos:",
            f"  Após TIPOBITO == 2: {int(resumo_filtro['apos_tipobito_2']):,}",
            "  Após DTNASC no ano de 2023: "
            f"{int(resumo_filtro['apos_dtnasc_2023']):,}",
            "  Mantidos: CODMUNNATU no RJ: "
            f"{int(resumo_filtro['uf_natu_rj']):,}",
            "  Mantidos: CODMUNNATU ausente e CODMUNRES no RJ: "
            f"{int(resumo_filtro['uf_natu_ausente_res_rj']):,}",
            "  Excluídos: CODMUNNATU em outra UF: "
            f"{int(resumo_filtro['excluidos_natu_outra_uf']):,}",
            "  Excluídos: CODMUNNATU ausente e CODMUNRES fora/ausente do RJ: "
            f"{int(resumo_filtro['excluidos_natu_ausente_res_fora_rj']):,}",
            "  Após a regra de UF: "
            f"{int(resumo_filtro['apos_regra_uf']):,}",
            "  Inconsistentes (data inválida, idade < 0 ou idade >= 365): "
            f"{int(resumo_filtro['inconsistentes_data_ou_idade']):,}",
            f"  Óbitos candidatos finais: {len(candidatos):,}",
            "",
            "Resultado do linkage:",
            "  Óbitos candidatos com alguma chave ausente (não pareáveis): "
            f"{resumo_linkage['obitos_com_chave_ausente']:,}",
            f"  Óbitos pareados 1:1: {resumo_linkage['obitos_pareados']:,}",
            "  Óbitos em combinações ambíguas: "
            f"{resumo_linkage['obitos_em_combinacoes_ambiguas']:,}",
            "  Óbitos sem nascimento correspondente: "
            f"{resumo_linkage['obitos_sem_nascimento']:,}",
        ]
    )
    proporcao_pareada = (
        resumo_linkage["obitos_pareados"] / len(candidatos) if len(candidatos) else 0
    )
    linhas.append(
        "  Proporção de candidatos pareados: "
        f"{proporcao_pareada:.2%} "
        f"({resumo_linkage['obitos_pareados']:,}/{len(candidatos):,})"
    )

    status = resultado["STATUS_LINKAGE"].value_counts()
    linhas.append("\nNascimentos por STATUS_LINKAGE:")
    for valor in (
        "fora_rj",
        "chave_ausente",
        "ambiguo",
        "pareado",
        "sem_obito",
    ):
        linhas.append(f"  {valor}: {int(status.get(valor, 0)):,}")

    desfecho_avaliavel = resultado["STATUS_LINKAGE"].isin(["pareado", "sem_obito"])
    n_avaliavel = int(desfecho_avaliavel.sum())
    prevalencia = (
        float(resultado.loc[desfecho_avaliavel, "OBITO_INFANTIL"].mean())
        if n_avaliavel
        else 0.0
    )
    linhas.append(
        "Prevalência de OBITO_INFANTIL entre pareados + sem_obito: "
        f"{prevalencia:.4%} "
        f"({int(resultado.loc[desfecho_avaliavel, 'OBITO_INFANTIL'].sum()):,}"
        f"/{n_avaliavel:,})"
    )

    idades = resultado.loc[
        resultado["STATUS_LINKAGE"].eq("pareado"), "IDADE_DIAS"
    ]
    if idades.empty:
        linhas.append("IDADE_DIAS entre pareados: sem pares.")
    else:
        linhas.append(
            "IDADE_DIAS entre pareados: "
            f"mínimo={int(idades.min())}, máximo={int(idades.max())}, "
            f"mediana={float(idades.median()):.1f}"
        )
    return "\n".join(linhas) + "\n"


def main() -> None:
    """Lê as bases reduzidas, executa o linkage e grava resultado e relatório."""
    caminho_vivos = caminho_base_reduzida(ARQUIVO_VIVOS)
    caminho_mortos = caminho_base_reduzida(ARQUIVO_MORTOS)
    vivos, separador_vivos = ler_base_reduzida(caminho_vivos)
    mortos, separador_mortos = ler_base_reduzida(caminho_mortos)
    if separador_vivos != separador_mortos:
        raise ValueError(
            "As bases reduzidas usam separadores diferentes "
            f"({separador_vivos!r} e {separador_mortos!r})."
        )

    vivos_p = padronizar_nascimentos(vivos)
    mortos_p = padronizar_obitos(mortos)
    candidatos, resumo_filtro = filtrar_obitos_candidatos(mortos_p)
    resultado, resumo_linkage = linkage_deterministico(vivos_p, candidatos)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    caminho_resultado = DATA_PROCESSED / "linkage_deterministico.csv"
    resultado.to_csv(
        caminho_resultado,
        sep=separador_vivos,
        encoding="utf-8",
        index=False,
    )

    relatorio = montar_relatorio(
        vivos,
        vivos_p,
        candidatos,
        resumo_filtro,
        resultado,
        resumo_linkage,
        vivos,
        mortos,
    )
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    caminho_relatorio = OUTPUTS / "linkage_deterministico_relatorio.txt"
    caminho_relatorio.write_text(relatorio, encoding="utf-8")
    print(relatorio, end="")
    print(f"\nResultado salvo em: {caminho_resultado}")
    print(f"Relatório salvo em: {caminho_relatorio}")


if __name__ == "__main__":
    main()
