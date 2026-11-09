"""Leitura dos arquivos CSV de receitas exportados pelo sistema contábil.

Particularidades tratadas:
- separador ';' e codificação UTF-8 (com fallback para latin-1);
- registros quebrados em duas linhas (nome da receita com quebra de linha);
- datas no formato DMMAAAA / DDMMAAAA (com espaço à esquerda);
- valores com espaços de alinhamento.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

COLUNAS = ["ficha", "codigo", "receita", "fonte", "data",
           "previsao", "credito", "debito", "arrecadado"]
N_SEP = len(COLUNAS) - 1


def _ler_linhas(caminho: Path) -> list[list[str]]:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = caminho.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    linhas = texto.splitlines()
    registros, buffer = [], ""
    for linha in linhas[1:]:  # pula cabeçalho
        if not linha.strip() and not buffer:
            continue
        buffer = buffer + linha if buffer else linha
        n = buffer.count(";")
        if n >= N_SEP:
            partes = buffer.split(";")
            if n > N_SEP:  # ';' dentro do nome da receita
                excesso = n - N_SEP
                partes = partes[:2] + [";".join(partes[2:3 + excesso])] + partes[3 + excesso:]
            registros.append(partes)
            buffer = ""
    return registros


def ler_arquivo(caminho: str | Path) -> pd.DataFrame:
    caminho = Path(caminho)
    df = pd.DataFrame(_ler_linhas(caminho), columns=COLUNAS)
    for c in COLUNAS:
        df[c] = df[c].str.strip()
    for c in ("previsao", "credito", "debito", "arrecadado"):
        df[c] = pd.to_numeric(df[c].str.replace(",", ".", regex=False), errors="coerce").fillna(0.0)
    df["data"] = pd.to_datetime(df["data"].str.zfill(8), format="%d%m%Y", errors="coerce")
    df = df.dropna(subset=["data"])
    m = re.search(r"(20\d{2})", caminho.stem)
    df["exercicio"] = int(m.group(1)) if m else df["data"].dt.year.mode().iat[0]
    df["arquivo"] = caminho.name
    return df


def carregar_pasta(pasta: str | Path) -> pd.DataFrame:
    arquivos = sorted(Path(pasta).glob("*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum CSV encontrado em {pasta}")
    df = pd.concat([ler_arquivo(a) for a in arquivos], ignore_index=True)
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.month
    # lançamentos datados fora do exercício do arquivo são mantidos no exercício
    df.loc[df["ano"] != df["exercicio"], "ano"] = df["exercicio"]
    df["anulacao"] = df["arrecadado"] < 0
    return df
