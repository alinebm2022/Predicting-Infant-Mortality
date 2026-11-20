# Predicting-Infant-Mortality
Data science project to predict infant mortality using Brazilian public health data (SINASC and SIM).

## Dados

Este projeto usa bases públicas do DATASUS: o SINASC (nascidos vivos) e o SIM
(óbitos infantis). Os arquivos originais não são versionados no repositório;
coloque `DNRJ2023.csv`, `DOINF23.csv` e `DOINF24.csv` em `data/raw/`.

Com o ambiente Python do projeto ativado e as dependências instaladas, gere
as bases reduzidas com:

```powershell
python scripts/02_reduzir_bases.py
```

O script seleciona as colunas definidas em `src/config.py` e grava
`data/reduzidas/vivos.csv` e `data/reduzidas/mortos.csv`. Os arquivos reduzidos
podem ser versionados; o relatório da execução é gravado em
`outputs/reducao_bases.txt`, pasta ignorada pelo Git.

## Linkage determinístico

Depois de gerar as bases reduzidas, execute o linkage com:

```powershell
python scripts/03_linkage_deterministico.py
```

O resultado é gravado em `data/processed/linkage_deterministico.csv`. Para
executar os testes automatizados:

```powershell
python -m pytest
```
