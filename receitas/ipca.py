"""IPCA mensal via API pública (Banco Central - SGS 433; fallback IBGE/SIDRA 1737).

O resultado é gravado em cache local para o painel funcionar sem internet.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import requests

URL_BCB = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados"
           "?formato=json&dataInicial={ini}&dataFinal={fim}")
URL_SIDRA = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/63/p/{ini}-{fim}"


def _bcb(ano_ini: int) -> pd.DataFrame:
    url = URL_BCB.format(ini=f"01/01/{ano_ini}", fim=date.today().strftime("%d/%m/%Y"))
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    d = pd.DataFrame(r.json())
    d["periodo"] = pd.to_datetime(d["data"], format="%d/%m/%Y").dt.to_period("M")
    d["ipca"] = pd.to_numeric(d["valor"]) / 100
    return d[["periodo", "ipca"]]


def _sidra(ano_ini: int) -> pd.DataFrame:
    url = URL_SIDRA.format(ini=f"{ano_ini}01", fim=f"{date.today().year}12")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    d = pd.DataFrame(r.json()[1:])
    d = d[pd.to_numeric(d["V"], errors="coerce").notna()]
    d["periodo"] = pd.PeriodIndex(d["D3C"].str[:4] + "-" + d["D3C"].str[4:], freq="M")
    d["ipca"] = pd.to_numeric(d["V"]) / 100
    return d[["periodo", "ipca"]]


def atualizar(cache: str | Path, ano_ini: int) -> tuple[pd.DataFrame, str]:
    """Busca o IPCA na API e grava o cache. Retorna (série, fonte usada)."""
    erros = []
    for nome, func in (("Banco Central (SGS 433)", _bcb), ("IBGE/SIDRA (tabela 1737)", _sidra)):
        try:
            serie = func(ano_ini).sort_values("periodo").reset_index(drop=True)
            if serie.empty:
                raise ValueError("série vazia")
            Path(cache).parent.mkdir(parents=True, exist_ok=True)
            serie.assign(periodo=serie["periodo"].astype(str)).to_csv(cache, sep=";", index=False)
            return serie, nome
        except Exception as e:  # noqa: BLE001 - tenta a próxima fonte
            erros.append(f"{nome}: {e}")
    raise RuntimeError("Falha ao obter IPCA. " + " | ".join(erros))


def ler_cache(cache: str | Path) -> pd.DataFrame | None:
    p = Path(cache)
    if not p.exists():
        return None
    d = pd.read_csv(p, sep=";")
    d["periodo"] = pd.PeriodIndex(d["periodo"], freq="M")
    return d


def indice_estendido(serie: pd.DataFrame, ate: pd.Period, ipca_futuro: float) -> pd.Series:
    """Número-índice mensal (fim do mês), indexado por Period.

    Para meses após o último IPCA divulgado usa `ipca_futuro` (taxa mensal),
    o que permite deflacionar meses recentes e inflacionar a projeção.
    """
    s = serie.set_index("periodo")["ipca"].sort_index()
    ultimo = s.index.max()
    if ate > ultimo:
        futuros = pd.period_range(ultimo + 1, ate, freq="M")
        s = pd.concat([s, pd.Series(ipca_futuro, index=futuros)])
    return (1 + s).cumprod()


def fatores_correcao(idx: pd.Series, periodos, base: pd.Period) -> pd.Series:
    """Fator que leva o valor de cada mês para R$ do mês-base (I_base / I_mês)."""
    i0 = idx.iloc[0]
    i_base = idx.get(base, i0)
    return pd.Series([i_base / idx.get(p, i0) for p in periodos], index=list(periodos))


def media_mensal_12m(serie: pd.DataFrame) -> float:
    ult = serie.sort_values("periodo").tail(12)["ipca"]
    return float((1 + ult).prod() ** (1 / len(ult)) - 1) if len(ult) else 0.0
