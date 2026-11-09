"""Séries mensais, correção monetária, projeção e previsto x realizado."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from . import ipca as ipca_mod

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
LIMITE_CRESC = (-0.30, 0.50)   # trava da taxa de crescimento real anual no método de tendência


# ------------------------------------------------------------------ séries
def serie_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """Arrecadação líquida (créditos - anulações) por grupo/ano/mês, com grade completa."""
    m = df.groupby(["grupo", "recorrente", "ano", "mes"], as_index=False)["arrecadado"].sum()
    grupos = m[["grupo", "recorrente"]].drop_duplicates()
    anos = sorted(df["ano"].unique())
    grade = grupos.merge(pd.DataFrame({"ano": anos}), how="cross") \
                  .merge(pd.DataFrame({"mes": range(1, 13)}), how="cross")
    m = grade.merge(m, how="left", on=["grupo", "recorrente", "ano", "mes"]).fillna({"arrecadado": 0.0})
    m["periodo"] = pd.PeriodIndex.from_fields(year=m["ano"], month=m["mes"], freq="M")
    return m.rename(columns={"arrecadado": "nominal"})


def aplicar_correcao(m: pd.DataFrame, idx: pd.Series, base: pd.Period) -> pd.DataFrame:
    f = ipca_mod.fatores_correcao(idx, m["periodo"].unique(), base)
    out = m.copy()
    out["fator"] = out["periodo"].map(f)
    out["real"] = out["nominal"] * out["fator"]
    return out


def mes_fechado_padrao(df: pd.DataFrame, hoje: date | None = None) -> int:
    """Último mês considerado completo no exercício mais recente.

    O mês do último lançamento é tratado como incompleto (o arquivo pode ter
    sido extraído antes de todos os créditos do mês serem contabilizados),
    assim como o mês corrente. Exercício já encerrado -> 12.
    """
    hoje = hoje or date.today()
    ano = int(df["ano"].max())
    ultima = df.loc[df["ano"] == ano, "data"].max()
    if ano < hoje.year and ultima.month == 12 and ultima.day >= 28:
        return 12
    return max(0, min(int(ultima.month) - 1, (hoje.month - 1) if ano == hoje.year else 12))


# ------------------------------------------------------------------ projeção
def taxas_crescimento(real: pd.DataFrame, anos: list[int], mes_fechado: int) -> pd.DataFrame:
    """Crescimento real anual por grupo, comparando sempre a mesma janela de meses fechados.

    Ex.: com set/2026 fechado, compara jan-set/2025 x jan-set/2024 e
    jan-set/2026 x jan-set/2025. Retorna a média geométrica (travada em LIMITE_CRESC).
    """
    janela = mes_fechado if mes_fechado > 0 else 12
    tot = real[real["mes"] <= janela].groupby(["grupo", "ano"])["real"].sum().unstack("ano")
    linhas = []
    anos = sorted(anos)
    for g, row in tot.iterrows():
        fatores, detalhes = [], {}
        for a0, a1 in zip(anos[:-1], anos[1:]):
            v0, v1 = row.get(a0, 0.0), row.get(a1, 0.0)
            if abs(v0) > 1 and np.sign(v0) == np.sign(v1):
                r = v1 / v0
                fatores.append(r)
                detalhes[f"{a0}→{a1}"] = r - 1
            else:
                detalhes[f"{a0}→{a1}"] = np.nan
        g_med = float(np.prod(fatores) ** (1 / len(fatores)) - 1) if fatores else 0.0
        g_trav = float(np.clip(g_med, *LIMITE_CRESC))
        linhas.append({"grupo": g, **detalhes, "crescimento_medio": g_med, "crescimento_usado": g_trav})
    return pd.DataFrame(linhas)


def projetar(real: pd.DataFrame, ano_atual: int, mes_fechado: int, anos_hist: list[int],
             metodo: str) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Projeção (em R$ do mês-base) dos meses pendentes do ano atual, só para grupos recorrentes.

    metodo = "media"     -> média dos anos selecionados, corrigida pelo IPCA;
    metodo = "tendencia" -> cada ano histórico corrigido pelo IPCA e levado ao
                            ano atual pela taxa média de crescimento real observada
                            (mesma janela de meses), depois tirada a média.
    """
    rec = real[real["recorrente"] & real["ano"].isin(anos_hist)]
    pend = list(range(mes_fechado + 1, 13))
    if not pend or not anos_hist:
        return pd.DataFrame(columns=["grupo", "mes", "projecao"]), None
    rec = rec[rec["mes"].isin(pend)].copy()
    cresc = None
    if metodo == "tendencia":
        base_cresc = real[real["recorrente"] & real["ano"].isin(anos_hist + [ano_atual])]
        anos_c = sorted(set(anos_hist) | ({ano_atual} if mes_fechado > 0 else set()))
        cresc = taxas_crescimento(base_cresc, anos_c, mes_fechado)
        gmap = cresc.set_index("grupo")["crescimento_usado"]
        rec["real"] = rec["real"] * (1 + rec["grupo"].map(gmap).fillna(0.0)) ** (ano_atual - rec["ano"])
    proj = rec.groupby(["grupo", "mes"], as_index=False)["real"].mean().rename(columns={"real": "projecao"})
    return proj, cresc


def montar_estimativa(base: pd.DataFrame, proj: pd.DataFrame, ano_atual: int, mes_fechado: int,
                      regra_incompleto: str, col: str, fator_proj: pd.Series) -> pd.DataFrame:
    """Combina realizado e projeção para o ano atual, mês a mês.

    base: série (nominal ou real) do ano atual; col: coluna de valor.
    regra_incompleto: "maior" -> no mês incompleto usa max(realizado parcial, projeção);
                      "projecao" -> ignora o parcial e usa a projeção.
    fator_proj: converte a projeção (R$ do mês-base) para a unidade exibida, por mês.
    Grupos não recorrentes: apenas o realizado (sem projeção).
    """
    atual = base[base["ano"] == ano_atual][["grupo", "recorrente", "mes", col]].rename(columns={col: "realizado"})
    p = proj.copy()
    p["projecao"] = p["projecao"] * p["mes"].map(fator_proj).fillna(1.0)
    e = atual.merge(p, how="left", on=["grupo", "mes"])
    e["projecao"] = pd.to_numeric(e["projecao"], errors="coerce").astype(float).fillna(0.0)
    fechado = e["mes"] <= mes_fechado
    e["situacao"] = np.where(fechado, "Realizado", "Projetado")
    if regra_incompleto == "maior":
        pendente = np.where(e["projecao"] >= 0, np.maximum(e["realizado"], e["projecao"]),
                            np.minimum(e["realizado"], e["projecao"]))
    else:
        pendente = e["projecao"]
    e["estimado"] = np.where(fechado, e["realizado"],
                             np.where(e["recorrente"], pendente, e["realizado"]))
    return e


# ------------------------------------------------------------------ previsto
def previsto_por_grupo(df: pd.DataFrame) -> pd.DataFrame:
    """Previsão (LOA atualizada) somada por grupo/exercício, uma vez por ficha+fonte."""
    u = df.drop_duplicates(["exercicio", "ficha", "codigo", "fonte"])
    return u.groupby(["exercicio", "grupo"], as_index=False)["previsao"].sum() \
            .rename(columns={"exercicio": "ano"})


def sazonalidade(real: pd.DataFrame, anos_hist: list[int]) -> pd.DataFrame:
    """Participação média de cada mês no total anual do grupo (para distribuir o previsto)."""
    h = real[real["ano"].isin(anos_hist)]
    tot = h.groupby(["grupo", "ano"])["real"].transform("sum")
    h = h.assign(peso=np.where(tot.abs() > 1, h["real"] / tot.replace(0, np.nan), np.nan))
    s = h.groupby(["grupo", "mes"], as_index=False)["peso"].mean()
    s["peso"] = s["peso"].fillna(1 / 12)
    s["peso"] = s["peso"] / s.groupby("grupo")["peso"].transform("sum").replace(0, np.nan)
    s["peso"] = s["peso"].fillna(1 / 12)
    return s
