"""Padronização e linkage determinístico das bases SINASC e SIM."""

import pandas as pd


CHAVES_NASCIMENTO = [
    "DTNASC_PAD",
    "SEXO_PAD",
    "PESO_PAD",
    "PARTO_PAD",
    "CODMUNNASC_PAD",
]
CHAVES_OBITO = [
    "DTNASC_PAD",
    "SEXO_PAD",
    "PESO_PAD",
    "PARTO_PAD",
    "CODMUNNATU_PAD",
]


def exigir_colunas(dados: pd.DataFrame, colunas: list[str], nome_base: str) -> None:
    """Interrompe a execução se faltar uma variável necessária ao linkage."""
    ausentes = [coluna for coluna in colunas if coluna not in dados.columns]
    if ausentes:
        raise ValueError(
            f"A base {nome_base} não contém as colunas obrigatórias: "
            f"{', '.join(ausentes)}"
        )


def padronizar_data(serie: pd.Series) -> pd.Series:
    """Converte datas ddmmaaaa sem zero inicial e invalida formatos incorretos."""
    texto = (
        serie.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(8)
    )
    return pd.to_datetime(texto, format="%d%m%Y", errors="coerce")


def padronizar_codigo_municipio(serie: pd.Series) -> pd.Series:
    """Mantém dígitos, remove o dígito verificador de códigos com sete dígitos."""
    codigo = serie.astype("string").str.replace(r"\D", "", regex=True)
    tamanho = codigo.str.len()
    codigo = codigo.mask(tamanho.eq(7), codigo.str.slice(0, 6))
    codigo = codigo.mask(tamanho.eq(0) | tamanho.gt(7))
    return codigo.str.zfill(6)


def padronizar_codigo_categoria(serie: pd.Series, ignorados: list[str]) -> pd.Series:
    """Mantém códigos categóricos como texto e converte ignorados em ausentes."""
    codigo = (
        serie.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )
    return codigo.mask(codigo.eq("") | codigo.isin(ignorados))


def padronizar_peso(serie: pd.Series) -> pd.Series:
    """Converte o peso para gramas inteiras e marca códigos inválidos como ausentes."""
    texto = (
        serie.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )
    peso = pd.to_numeric(texto, errors="coerce")
    peso = peso.mask(
        peso.isin([0, 9999]) | peso.mod(1).ne(0)
    )
    return peso.astype("Int64")


def padronizar_nascimentos(vivos: pd.DataFrame) -> pd.DataFrame:
    """Adiciona chaves padronizadas e ID rastreável sem remover colunas originais."""
    exigir_colunas(
        vivos,
        ["DTNASC", "CODMUNNASC", "PESO", "SEXO", "PARTO"],
        "SINASC",
    )
    dados = vivos.copy()
    dados["ID_NASC"] = range(1, len(dados) + 1)
    dados["DTNASC_PAD"] = padronizar_data(dados["DTNASC"])
    dados["CODMUNNASC_PAD"] = padronizar_codigo_municipio(dados["CODMUNNASC"])
    dados["SEXO_PAD"] = padronizar_codigo_categoria(dados["SEXO"], ["0", "9"])
    dados["PARTO_PAD"] = padronizar_codigo_categoria(dados["PARTO"], ["9"])
    dados["PESO_PAD"] = padronizar_peso(dados["PESO"])
    dados["UF_NASC_PAD"] = dados["CODMUNNASC_PAD"].str.slice(0, 2)
    return dados


def padronizar_obitos(mortos: pd.DataFrame) -> pd.DataFrame:
    """Adiciona chaves padronizadas e ID rastreável sem remover colunas originais."""
    exigir_colunas(
        mortos,
        [
            "TIPOBITO",
            "DTNASC",
            "DTOBITO",
            "CODMUNNATU",
            "CODMUNRES",
            "PESO",
            "SEXO",
            "PARTO",
        ],
        "SIM",
    )
    dados = mortos.copy()
    dados["ID_OBITO"] = range(1, len(dados) + 1)
    dados["DTNASC_PAD"] = padronizar_data(dados["DTNASC"])
    dados["DTOBITO_PAD"] = padronizar_data(dados["DTOBITO"])
    dados["CODMUNNATU_PAD"] = padronizar_codigo_municipio(dados["CODMUNNATU"])
    dados["CODMUNRES_PAD"] = padronizar_codigo_municipio(dados["CODMUNRES"])
    dados["SEXO_PAD"] = padronizar_codigo_categoria(dados["SEXO"], ["0", "9"])
    dados["PARTO_PAD"] = padronizar_codigo_categoria(dados["PARTO"], ["9"])
    dados["PESO_PAD"] = padronizar_peso(dados["PESO"])
    return dados


def distribuicao_uf(codigos: pd.Series) -> dict[str, int]:
    """Resume UFs por código municipal, incluindo explicitamente os ausentes."""
    uf = codigos.astype("string").str.slice(0, 2).fillna("<ausente>")
    return {str(chave): int(valor) for chave, valor in uf.value_counts().items()}


def filtrar_obitos_candidatos(
    mortos_padronizado: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Filtra óbitos infantis de nascidos em 2023, no RJ e com idade de 0-364 dias."""
    exigir_colunas(
        mortos_padronizado,
        [
            "TIPOBITO",
            "DTNASC_PAD",
            "DTOBITO_PAD",
            "CODMUNNATU_PAD",
            "CODMUNRES_PAD",
        ],
        "SIM padronizado",
    )
    relatorio: dict[str, object] = {
        "n_obitos_inicial": len(mortos_padronizado),
        "valores_tipobito": {
            str(chave) if pd.notna(chave) else "<ausente>": int(valor)
            for chave, valor in mortos_padronizado["TIPOBITO"]
            .value_counts(dropna=False)
            .items()
        },
    }

    # As distribuições geográficas são calculadas antes de aplicar qualquer filtro.
    nascidos_em_2023 = mortos_padronizado["DTNASC_PAD"].dt.year.eq(2023)
    obitos_data_2023 = mortos_padronizado.loc[nascidos_em_2023]
    relatorio["uf_natu_dtnasc_2023"] = distribuicao_uf(
        obitos_data_2023["CODMUNNATU_PAD"]
    )
    relatorio["uf_res_dtnasc_2023"] = distribuicao_uf(
        obitos_data_2023["CODMUNRES_PAD"]
    )
    relatorio["n_natu_ausente_dtnasc_2023"] = int(
        obitos_data_2023["CODMUNNATU_PAD"].isna().sum()
    )

    tipobito = mortos_padronizado["TIPOBITO"].astype("string").str.strip()
    apos_tipobito = mortos_padronizado.loc[tipobito.eq("2")].copy()
    relatorio["apos_tipobito_2"] = len(apos_tipobito)

    apos_ano = apos_tipobito.loc[apos_tipobito["DTNASC_PAD"].dt.year.eq(2023)].copy()
    relatorio["apos_dtnasc_2023"] = len(apos_ano)

    uf_natu = apos_ano["CODMUNNATU_PAD"].astype("string").str.slice(0, 2)
    uf_res = apos_ano["CODMUNRES_PAD"].astype("string").str.slice(0, 2)
    natu_rj = uf_natu.eq("33")
    natu_ausente = apos_ano["CODMUNNATU_PAD"].isna()
    res_rj = uf_res.eq("33")
    nat_rj_ou_res_fallback = natu_rj | (natu_ausente & res_rj)

    relatorio["uf_natu_rj"] = int(natu_rj.sum())
    relatorio["uf_natu_ausente_res_rj"] = int((natu_ausente & res_rj).sum())
    relatorio["excluidos_natu_outra_uf"] = int(
        (~natu_rj & ~natu_ausente).sum()
    )
    relatorio["excluidos_natu_ausente_res_fora_rj"] = int(
        (natu_ausente & ~res_rj).sum()
    )
    apos_uf = apos_ano.loc[nat_rj_ou_res_fallback].copy()
    relatorio["apos_regra_uf"] = len(apos_uf)

    idade_dias = (apos_uf["DTOBITO_PAD"] - apos_uf["DTNASC_PAD"]).dt.days
    idade_valida = idade_dias.between(0, 364, inclusive="both")
    relatorio["inconsistentes_data_ou_idade"] = int((~idade_valida).sum())
    candidatos = apos_uf.loc[idade_valida].copy()
    relatorio["obitos_candidatos"] = len(candidatos)
    return candidatos, relatorio


def linkage_deterministico(
    vivos_p: pd.DataFrame, obitos_candidatos: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Pareia somente chaves completas e únicas dos dois lados, sem reutilizar IDs."""
    exigir_colunas(vivos_p, CHAVES_NASCIMENTO + ["ID_NASC", "UF_NASC_PAD"], "SINASC")
    exigir_colunas(
        obitos_candidatos,
        CHAVES_OBITO + ["ID_OBITO", "DTOBITO_PAD"],
        "SIM candidato",
    )

    chaves_completas_nasc = vivos_p[CHAVES_NASCIMENTO].notna().all(axis=1)
    nascimentos_no_rj = vivos_p["UF_NASC_PAD"].eq("33").fillna(False)
    nascimentos_chaves = vivos_p.loc[
        chaves_completas_nasc & nascimentos_no_rj,
        ["ID_NASC"] + CHAVES_NASCIMENTO,
    ].copy()

    chaves_completas_obito = obitos_candidatos[CHAVES_OBITO].notna().all(axis=1)
    obitos_chaves = obitos_candidatos.loc[
        chaves_completas_obito,
        ["ID_OBITO", "DTOBITO_PAD"] + CHAVES_OBITO,
    ].rename(columns={"CODMUNNATU_PAD": "CODMUNNASC_PAD"})

    grupos_nasc = nascimentos_chaves.groupby(
        CHAVES_NASCIMENTO, as_index=False, dropna=False
    ).size()
    grupos_nasc = grupos_nasc.rename(columns={"size": "n_nasc"})
    grupos_obito = obitos_chaves.groupby(
        CHAVES_NASCIMENTO, as_index=False, dropna=False
    ).size()
    grupos_obito = grupos_obito.rename(columns={"size": "n_obito"})
    contagens = grupos_nasc.merge(
        grupos_obito, on=CHAVES_NASCIMENTO, how="outer"
    ).fillna({"n_nasc": 0, "n_obito": 0})

    grupos_com_obito = contagens.loc[contagens["n_obito"].gt(0)]
    grupos_ambiguos = grupos_com_obito.loc[
        grupos_com_obito["n_nasc"].gt(1)
        | grupos_com_obito["n_obito"].gt(1),
        CHAVES_NASCIMENTO,
    ]
    grupos_unicos = grupos_com_obito.loc[
        grupos_com_obito["n_nasc"].eq(1) & grupos_com_obito["n_obito"].eq(1),
        CHAVES_NASCIMENTO,
    ]

    nascimentos_unicos = nascimentos_chaves.merge(
        grupos_unicos,
        on=CHAVES_NASCIMENTO,
        how="inner",
        validate="many_to_one",
    )
    obitos_unicos = obitos_chaves.merge(
        grupos_unicos,
        on=CHAVES_NASCIMENTO,
        how="inner",
        validate="many_to_one",
    )
    pares = nascimentos_unicos.merge(
        obitos_unicos,
        on=CHAVES_NASCIMENTO,
        how="inner",
        validate="one_to_one",
    )
    nascimentos_ambiguos = nascimentos_chaves.merge(
        grupos_ambiguos,
        on=CHAVES_NASCIMENTO,
        how="inner",
        validate="many_to_one",
    )
    obitos_ambiguos = obitos_chaves.merge(
        grupos_ambiguos,
        on=CHAVES_NASCIMENTO,
        how="inner",
        validate="many_to_one",
    )
    obitos_sem_nascimento = obitos_chaves.merge(
        contagens.loc[contagens["n_nasc"].eq(0), CHAVES_NASCIMENTO],
        on=CHAVES_NASCIMENTO,
        how="inner",
        validate="many_to_one",
    )

    colunas_padronizadas = {
        "DTNASC_PAD",
        "CODMUNNASC_PAD",
        "SEXO_PAD",
        "PARTO_PAD",
        "PESO_PAD",
        "UF_NASC_PAD",
    }
    colunas_originais = [
        coluna for coluna in vivos_p.columns if coluna not in colunas_padronizadas
    ]
    resultado = vivos_p.loc[:, colunas_originais].copy()
    resultado["ID_OBITO"] = pd.Series(pd.NA, index=resultado.index, dtype="Int64")
    resultado["OBITO_INFANTIL"] = pd.Series(
        pd.NA, index=resultado.index, dtype="Int64"
    )
    resultado["STATUS_LINKAGE"] = "fora_rj"
    resultado.loc[nascimentos_no_rj, "STATUS_LINKAGE"] = "sem_obito"
    resultado.loc[
        nascimentos_no_rj & ~chaves_completas_nasc, "STATUS_LINKAGE"
    ] = "chave_ausente"
    resultado.loc[
        resultado["STATUS_LINKAGE"].eq("sem_obito"), "OBITO_INFANTIL"
    ] = 0
    resultado["DTOBITO"] = pd.NaT
    resultado["IDADE_DIAS"] = pd.Series(pd.NA, index=resultado.index, dtype="Int64")

    ids_ambiguos = set(nascimentos_ambiguos["ID_NASC"].tolist())
    resultado.loc[resultado["ID_NASC"].isin(ids_ambiguos), "STATUS_LINKAGE"] = (
        "ambiguo"
    )
    resultado.loc[
        resultado["ID_NASC"].isin(ids_ambiguos), "OBITO_INFANTIL"
    ] = pd.NA

    if not pares.empty:
        ids_pareados = pares["ID_NASC"]
        por_id = pares.set_index("ID_NASC")
        id_obito_por_nasc = por_id["ID_OBITO"]
        dto_obito_por_nasc = por_id["DTOBITO_PAD"]
        idade_por_nasc = (por_id["DTOBITO_PAD"] - por_id["DTNASC_PAD"]).dt.days
        indice_pareado = resultado["ID_NASC"].isin(ids_pareados)
        resultado.loc[indice_pareado, "STATUS_LINKAGE"] = "pareado"
        resultado.loc[indice_pareado, "OBITO_INFANTIL"] = 1
        resultado.loc[indice_pareado, "ID_OBITO"] = (
            resultado.loc[indice_pareado, "ID_NASC"]
            .map(id_obito_por_nasc)
            .astype("Int64")
        )
        resultado.loc[indice_pareado, "DTOBITO"] = (
            resultado.loc[indice_pareado, "ID_NASC"].map(dto_obito_por_nasc)
        )
        resultado.loc[indice_pareado, "IDADE_DIAS"] = (
            resultado.loc[indice_pareado, "ID_NASC"]
            .map(idade_por_nasc)
            .astype("Int64")
        )

    # Asserções tornam explícitos os invariantes do pareamento um-para-um.
    assert resultado["ID_NASC"].is_unique, "Um nascimento apareceu mais de uma vez."
    assert pares["ID_OBITO"].is_unique, "Um óbito foi usado em mais de um pareamento."
    assert len(resultado) == len(vivos_p), "O resultado perdeu ou duplicou nascimentos."

    resumo = {
        "obitos_com_chave_ausente": int((~chaves_completas_obito).sum()),
        "obitos_pareados": len(pares),
        "obitos_em_combinacoes_ambiguas": len(obitos_ambiguos),
        "obitos_sem_nascimento": len(obitos_sem_nascimento),
        "nascimentos_ambiguos": len(nascimentos_ambiguos),
    }
    return resultado, resumo
