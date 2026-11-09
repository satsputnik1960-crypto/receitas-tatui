"""Classificação das naturezas de receita em grupos analíticos.

As regras ficam em config/regras_receitas.csv e são avaliadas de cima para
baixo; a primeira que casar define o grupo. Uma regra pode casar por prefixo do
código, por palavra-chave no nome (separadas por '|') ou por ambos.

Isso resolve:
- aglutinação de principal + multas/juros + dívida ativa (mesmo prefixo);
- receitas que mudaram de numeração (prefixo comum ou regra explícita);
- receitas esporádicas (emendas, convênios) -> "Outras Receitas Não Recorrentes".
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

GRUPO_NAO_RECORRENTE = "Outras Receitas Não Recorrentes"


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.upper()).strip()


def carregar_regras(caminho: str | Path) -> pd.DataFrame:
    regras = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8").fillna("")
    for c in regras.columns:
        regras[c] = regras[c].str.strip()
    regras["recorrente"] = regras["recorrente"].str.upper().isin(["S", "SIM", "1", "TRUE"])
    regras["palavras_chave"] = regras["contem"].apply(
        lambda s: [normalizar(p) for p in s.split("|") if p.strip()])
    return regras


def classificar_codigo(codigo: str, nome: str, regras: pd.DataFrame) -> tuple[str, bool, int]:
    nome_n = normalizar(nome)
    for i, r in enumerate(regras.itertuples(index=False)):
        if r.prefixo and not codigo.startswith(r.prefixo):
            continue
        if r.palavras_chave and not any(p in nome_n for p in r.palavras_chave):
            continue
        if not r.prefixo and not r.palavras_chave:
            continue
        return r.grupo, bool(r.recorrente), i
    # sem regra: categoria econômica 1 = corrente (recorrente), demais não
    return (("Outras Receitas Correntes", True, -1) if codigo.startswith("1")
            else (GRUPO_NAO_RECORRENTE, False, -1))


def tipo_receita(codigo: str) -> str:
    """8º dígito da natureza (MCASP): 1 principal, 2 multas/juros, 3 dívida ativa, 4 DA multas/juros."""
    dig = re.sub(r"\D", "", codigo)
    return {"1": "Principal", "2": "Multas e Juros", "3": "Dívida Ativa",
            "4": "Dívida Ativa - Multas e Juros"}.get(dig[7:8], "Outros") if len(dig) >= 8 else "Outros"


def aplicar(df: pd.DataFrame, regras: pd.DataFrame) -> pd.DataFrame:
    nomes = df.groupby("codigo")["receita"].agg(lambda s: s.iloc[-1])
    mapa = {c: classificar_codigo(c, n, regras) for c, n in nomes.items()}
    out = df.copy()
    out["grupo"] = out["codigo"].map(lambda c: mapa[c][0])
    out["recorrente"] = out["codigo"].map(lambda c: mapa[c][1])
    out["regra"] = out["codigo"].map(lambda c: mapa[c][2])
    out["tipo"] = out["codigo"].map(tipo_receita)
    return out


# ---------------------------------------------------------------- diagnósticos
def tabela_codigos(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por código: grupo, anos em que aparece, totais e alertas."""
    piv = df.pivot_table(index="codigo", columns="exercicio", values="arrecadado",
                         aggfunc="sum", fill_value=0.0)
    piv.columns = [f"Arrecadado {c}" for c in piv.columns]
    cred = df.groupby("codigo")["credito"].sum()
    anul = df.loc[df["anulacao"]].groupby("codigo")["arrecadado"].sum()
    info = df.groupby("codigo").agg(receita=("receita", "last"), grupo=("grupo", "first"),
                                    recorrente=("recorrente", "first"), tipo=("tipo", "first"),
                                    anos=("exercicio", lambda s: ", ".join(map(str, sorted(s.unique())))))
    t = info.join(piv)
    t["Anulações"] = anul.reindex(t.index).fillna(0.0)
    liquido = piv.sum(axis=1)
    alertas = []
    nome_norm = df.groupby("codigo")["receita"].last().map(normalizar)
    anos_por_nome = df.assign(n=df["codigo"].map(nome_norm)).groupby("n")["codigo"].nunique()
    for cod in t.index:
        a = []
        if cred.get(cod, 0) > 0 and abs(liquido.get(cod, 0)) < 0.01:
            a.append("Anulada integralmente")
        elif cred.get(cod, 0) > 0 and abs(t.at[cod, "Anulações"]) > 0.2 * cred.get(cod, 0) and not cod.startswith("9"):
            a.append("Anulações > 20%")
        if anos_por_nome.get(nome_norm[cod], 1) > 1:
            a.append("Mesmo nome em outro código (renumeração?)")
        if len(t.at[cod, "anos"].split(",")) == 1 and df["exercicio"].nunique() > 1:
            a.append("Aparece em um só exercício")
        alertas.append("; ".join(a))
    t["alertas"] = alertas
    return t.reset_index()
