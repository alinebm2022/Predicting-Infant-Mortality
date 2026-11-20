import pandas as pd

from src.linkage import (
    filtrar_obitos_candidatos,
    linkage_deterministico,
    padronizar_nascimentos,
    padronizar_obitos,
)


def criar_bases_sinteticas():
    """Cria casos mínimos para testar pares, ambiguidades, ausências e filtros."""
    vivos = pd.DataFrame(
        [
            ["01012023", "330455", "3000", "1", "1"],
            ["02012023", "330455", "3100", "2", "1"],
            ["02012023", "330455", "3100", "2", "1"],
            ["03012023", "330455", "", "1", "1"],
            ["04012023", "330455", "3200", "1", "1"],
            ["08012023", "350183", "3600", "1", "1"],
        ],
        columns=["DTNASC", "CODMUNNASC", "PESO", "SEXO", "PARTO"],
    )
    mortos = pd.DataFrame(
        [
            ["2", "01012023", "02012023", "330455", "330455", "3000", "1", "1"],
            ["2", "02012023", "03012023", "330455", "330455", "3100", "2", "1"],
            ["2", "03012023", "04012023", "330455", "330455", "", "1", "1"],
            ["2", "04012023", "04012024", "330455", "330455", "3200", "1", "1"],
            ["2", "05012023", "06012023", "350183", "330455", "3300", "1", "1"],
            ["2", "06012023", "07012023", "", "330455", "3400", "1", "1"],
            ["2", "07012023", "08012023", "", "350183", "3500", "1", "1"],
        ],
        columns=[
            "TIPOBITO",
            "DTNASC",
            "DTOBITO",
            "CODMUNNATU",
            "CODMUNRES",
            "PESO",
            "SEXO",
            "PARTO",
        ],
    )
    return vivos, mortos


def preparar_linkage(vivos, mortos):
    """Aplica as mesmas etapas públicas usadas pelo script de produção."""
    vivos_p = padronizar_nascimentos(vivos)
    mortos_p = padronizar_obitos(mortos)
    candidatos, resumo_filtro = filtrar_obitos_candidatos(mortos_p)
    resultado, resumo_linkage = linkage_deterministico(vivos_p, candidatos)
    return resultado, candidatos, resumo_filtro, resumo_linkage


def test_linkage_um_para_um_e_combinacao_ambigua():
    vivos, mortos = criar_bases_sinteticas()
    resultado, _, _, resumo = preparar_linkage(vivos, mortos)

    assert resultado.loc[0, "STATUS_LINKAGE"] == "pareado"
    assert resultado.loc[0, "OBITO_INFANTIL"] == 1
    assert resultado.loc[0, "IDADE_DIAS"] == 1
    assert resultado.loc[1, "STATUS_LINKAGE"] == "ambiguo"
    assert resultado.loc[2, "STATUS_LINKAGE"] == "ambiguo"
    assert pd.isna(resultado.loc[1, "OBITO_INFANTIL"])
    assert pd.isna(resultado.loc[2, "OBITO_INFANTIL"])
    assert resumo["obitos_pareados"] == 1
    assert resumo["obitos_em_combinacoes_ambiguas"] == 1


def test_chave_ausente_nao_pareia_e_obito_com_365_dias_e_inconsistente():
    vivos, mortos = criar_bases_sinteticas()
    resultado, candidatos, resumo_filtro, resumo = preparar_linkage(vivos, mortos)

    assert resultado.loc[3, "STATUS_LINKAGE"] == "chave_ausente"
    assert pd.isna(resultado.loc[3, "OBITO_INFANTIL"])
    assert resultado.loc[4, "STATUS_LINKAGE"] == "sem_obito"
    assert resultado.loc[4, "OBITO_INFANTIL"] == 0
    assert resultado.loc[5, "STATUS_LINKAGE"] == "fora_rj"
    assert pd.isna(resultado.loc[5, "OBITO_INFANTIL"])
    assert resumo["obitos_com_chave_ausente"] == 2
    assert 4 not in candidatos["ID_OBITO"].values
    assert resumo_filtro["inconsistentes_data_ou_idade"] == 1


def test_regra_geografica_usa_residencia_so_quando_naturalidade_ausente():
    vivos, mortos = criar_bases_sinteticas()
    _, candidatos, resumo_filtro, _ = preparar_linkage(vivos, mortos)

    ids_candidatos = set(candidatos["ID_OBITO"])
    assert 5 not in ids_candidatos
    assert 6 in ids_candidatos
    assert 7 not in ids_candidatos
    assert resumo_filtro["uf_natu_rj"] == 4
    assert resumo_filtro["uf_natu_ausente_res_rj"] == 1
    assert resumo_filtro["excluidos_natu_outra_uf"] == 1
    assert resumo_filtro["excluidos_natu_ausente_res_fora_rj"] == 1
