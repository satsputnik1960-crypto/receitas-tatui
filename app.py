"""Painel de Receitas - Município de Tatuí.

Executar:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from receitas import analise, classificacao, glossario, ipca, leitura
from receitas.analise import MESES

RAIZ = Path(__file__).parent
PASTA_DADOS = RAIZ / "Dados"
ARQ_REGRAS = RAIZ / "config" / "regras_receitas.csv"
ARQ_IPCA = RAIZ / "cache" / "ipca.csv"
ARQ_OBS = RAIZ / "config" / "observacoes.csv"

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
CINZA = "#898781"
GRID = "rgba(137,135,129,0.25)"
MESES_EXT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
             "setembro", "outubro", "novembro", "dezembro"]
HOVER = "R$ %{y:,.1f} mi<extra>%{fullData.name}</extra>"
HOVER_H = "R$ %{x:,.1f} mi<extra>%{fullData.name}</extra>"

st.set_page_config(page_title="Receitas Tatuí", page_icon="📊", layout="wide")


# ======================================================================= utilidades
def md(txt: str) -> str:
    """Protege o '$' para o Streamlit não interpretar 'R$ ... R$' como fórmula matemática (LaTeX)."""
    return txt.replace("\\$", "$").replace("$", "\\$")


def _br(txt: str) -> str:
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v: float) -> str:
    """Valor resumido: R$ 523,4 milhões."""
    if v is None or not np.isfinite(v):
        return "-"
    s = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e9:
        return s + "R$ " + _br(f"{v / 1e9:,.2f}") + " bilhões"
    if v >= 1e6:
        return s + "R$ " + _br(f"{v / 1e6:,.1f}") + " milhões"
    if v >= 1e3:
        return s + "R$ " + _br(f"{v / 1e3:,.0f}") + " mil"
    return s + "R$ " + _br(f"{v:,.2f}")


def brl_cheio(v) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    return ("-" if v < 0 else "") + "R$ " + _br(f"{abs(v):,.2f}")


def pct(v: float, seta: bool = True) -> str:
    if v is None or not np.isfinite(v):
        return "-"
    txt = _br(f"{abs(v) * 100:.1f}") + "%"
    if not seta:
        return txt
    return ("▲ +" if v >= 0 else "▼ −") + txt


def var(a: float, b: float) -> float:
    return a / b - 1 if b and abs(b) > 1 else np.nan


def mais_menos(v: float) -> str:
    return "a mais" if v >= 0 else "a menos"


def mi(s):
    return np.asarray(s, dtype=float) / 1e6


def mostrar(fig: go.Figure, titulo: str, explicacao: str = "", altura: int = 400,
            hover: str = "x unified", eixo_valor: str = "y") -> None:
    """Título e explicação ficam fora do gráfico (evita sobreposição com a legenda)."""
    st.markdown(f"#### {titulo}")
    if explicacao:
        st.caption(explicacao)
    fig.update_layout(
        height=altura, margin=dict(l=10, r=10, t=10, b=10),
        separators=",.", hovermode=hover, barcornerradius=4, bargap=0.25, bargroupgap=0.08,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", size=13),
    )
    eixo_cat = "x" if eixo_valor == "y" else "y"
    fig.update_layout(**{f"{eixo_valor}axis": dict(gridcolor=GRID, zeroline=True, zerolinecolor=CINZA,
                                                   tickformat=",.0f", title_text="R$ milhões")})
    fig.update_layout(**{f"{eixo_cat}axis": dict(showgrid=False)})
    st.plotly_chart(fig, width="stretch")


def tabela(df: pd.DataFrame, moeda: list[str] = (), variacao: list[str] = (), perc: list[str] = (),
           altura: int | None = None, indice: bool = False) -> None:
    sty = df.style.format(brl_cheio, subset=list(moeda), na_rep="-") \
                  .format(lambda v: pct(v), subset=list(variacao), na_rep="-") \
                  .format(lambda v: pct(v, seta=False), subset=list(perc), na_rep="-")
    def cor(v):
        try:
            return "" if not np.isfinite(float(v)) else ("color:#0ca30c" if v >= 0 else "color:#d03b3b")
        except (TypeError, ValueError):
            return ""
    if variacao:
        sty = sty.map(cor, subset=list(variacao))
    st.dataframe(sty, width="stretch", hide_index=not indice,
                 height=altura or min(900, 38 + 35 * len(df)))


def cor_ano(ano: int, anos: list[int]) -> str:
    return SERIES[sorted(anos, reverse=True).index(ano) % len(SERIES)]


def mtimes(pasta: Path) -> tuple:
    return tuple(sorted((p.name, p.stat().st_mtime) for p in pasta.glob("*.csv")))


# ======================================================================= dados
@st.cache_data(show_spinner="Lendo arquivos de receita…")
def carregar(assinatura_dados: tuple, assinatura_regras: float) -> pd.DataFrame:
    df = leitura.carregar_pasta(PASTA_DADOS)
    return classificacao.aplicar(df, classificacao.carregar_regras(ARQ_REGRAS))


@st.cache_data(show_spinner=False)
def tabela_codigos(assinatura_dados: tuple, assinatura_regras: float, _df: pd.DataFrame) -> pd.DataFrame:
    return classificacao.tabela_codigos(_df)


def ler_observacoes() -> pd.DataFrame:
    """Receitas previstas que não aparecem nos arquivos (ex.: impedidas por decisão judicial)."""
    try:
        o = pd.read_csv(ARQ_OBS, sep=";", encoding="utf-8")
        o["valor_previsto"] = pd.to_numeric(o["valor_previsto"], errors="coerce").fillna(0.0)
        return o
    except Exception:  # noqa: BLE001 - arquivo opcional
        return pd.DataFrame(columns=["ano", "receita", "valor_previsto", "observacao"])


def avisos_observacoes(ano: int) -> pd.DataFrame:
    obs = ler_observacoes()
    obs = obs[obs["ano"] == ano]
    for _, o in obs.iterrows():
        st.warning(md(
            f"**{o['receita']}:** o orçamento de {ano} previa cerca de **{brl(o['valor_previsto'])}** "
            f"com esta receita. {o['observacao']} Como nada foi arrecadado, ela não aparece nos arquivos "
            f"e **não está somada** aos valores previstos deste painel."), icon="⚖️")
    return obs


def obter_ipca(ano_ini: int, forcar: bool = False):
    serie = None if forcar else ipca.ler_cache(ARQ_IPCA)
    if serie is not None:
        return serie, "cópia salva no computador"
    return ipca.atualizar(ARQ_IPCA, ano_ini)


assin = (mtimes(PASTA_DADOS), ARQ_REGRAS.stat().st_mtime)
try:
    df = carregar(*assin)
except Exception as e:  # noqa: BLE001
    st.error(f"Não foi possível ler os arquivos da pasta {PASTA_DADOS}: {e}")
    st.stop()

anos = sorted(int(a) for a in df["ano"].unique())
ano_atual = anos[-1]
ultima_data = df.loc[df["ano"] == ano_atual, "data"].max()

# ======================================================================= barra lateral
st.sidebar.title("⚙️ Opções")

st.sidebar.markdown("**1. Como mostrar os valores**")
unidade = st.sidebar.radio(
    "Valores", ["Corrigidos pela inflação", "Valores da época (sem correção)"], label_visibility="collapsed",
    help="Corrigir pela inflação (IPCA) permite comparar anos diferentes de forma justa: "
         "R\\$ 100 em 2024 compravam mais coisas do que R\\$ 100 hoje.")
corrigido = unidade.startswith("Corrigidos")

st.sidebar.markdown("**2. Como estimar os meses que faltam**")
metodo_lbl = st.sidebar.radio(
    "Método", ["Média dos anos anteriores", "Tendência de crescimento"], label_visibility="collapsed",
    help="• **Média dos anos anteriores:** supõe que cada mês que falta vai arrecadar a média do mesmo mês "
         "nos anos anteriores (já corrigida pela inflação).\n\n"
         "• **Tendência de crescimento:** faz o mesmo, mas acrescenta o crescimento acima da inflação que cada "
         "receita vem tendo de um ano para o outro.")
metodo = "media" if metodo_lbl.startswith("Média") else "tendencia"

st.sidebar.markdown("**3. Quais receitas incluir**")
so_rec = st.sidebar.checkbox(
    "Excluir receitas que não se repetem", value=False,
    help="Emendas parlamentares, convênios e empréstimos entram em um ano e podem não vir no próximo. "
         "Excluí-las deixa a comparação entre anos mais justa.")
todos_grupos = sorted(df["grupo"].unique())
opcoes = sorted(df.loc[df["recorrente"], "grupo"].unique()) if so_rec else todos_grupos
grupos_sel = st.sidebar.multiselect("Receitas", opcoes, default=opcoes, label_visibility="collapsed")

with st.sidebar.expander("🔧 Configurações avançadas"):
    if st.button("🔄 Atualizar inflação (IPCA) pela internet", width="stretch"):
        try:
            _, fonte_api = obter_ipca(anos[0] - 1, forcar=True)
            st.success(f"IPCA atualizado ({fonte_api}).")
        except Exception as e:  # noqa: BLE001
            st.error(str(e))
    try:
        serie_ipca, fonte_ipca = obter_ipca(anos[0] - 1)
    except Exception as e:  # noqa: BLE001
        st.error(f"Sem dados de inflação (internet indisponível e sem cópia salva): {e}")
        serie_ipca = pd.DataFrame({"periodo": pd.period_range(f"{anos[0]}-01", f"{ano_atual}-01", freq="M"),
                                   "ipca": 0.0})
        fonte_ipca = "indisponível"
    ultimo_ipca = serie_ipca["periodo"].max()
    st.caption(f"Inflação: {fonte_ipca}; último mês divulgado pelo IBGE: **{ultimo_ipca.strftime('%m/%Y')}**")
    periodos_base = list(serie_ipca["periodo"].sort_values().iloc[::-1])
    base = st.selectbox("Corrigir para valores de", periodos_base, index=0,
                        format_func=lambda p: p.strftime("%m/%Y"), disabled=not corrigido)
    ipca_fut = st.number_input(
        "Inflação mensal esperada (%)", value=round(ipca.media_mensal_12m(serie_ipca) * 100, 2),
        step=0.05, format="%.2f",
        help="Usada para os meses em que o IBGE ainda não divulgou o IPCA. "
             "Padrão: média dos últimos 12 meses.") / 100
    mes_padrao = analise.mes_fechado_padrao(df)
    mes_fechado = st.selectbox(
        f"Último mês completo de {ano_atual}", list(range(0, 13)), index=mes_padrao,
        format_func=lambda m: "Nenhum" if m == 0 else f"{MESES_EXT[m - 1]}/{ano_atual}",
        help="Os meses seguintes são considerados incompletos (dados ainda não lançados por inteiro). "
             "Eles não entram nas comparações e são estimados.")
    anos_hist = st.multiselect("Anos usados na estimativa", [a for a in anos if a < ano_atual],
                               default=[a for a in anos if a < ano_atual])
    regra_inc = st.radio(
        "No mês incompleto, usar", ["O maior entre o já arrecadado e o estimado", "Somente o estimado"],
        help="No mês incompleto já entrou parte do dinheiro. Por padrão, usa-se o maior valor entre o que já "
             "entrou e o que foi estimado para o mês.")
    regra_inc = "maior" if regra_inc.startswith("O maior") else "projecao"
    if st.button("♻️ Recarregar arquivos de dados", width="stretch"):
        st.cache_data.clear()
        st.rerun()

if not grupos_sel:
    st.warning("Escolha ao menos uma receita na barra lateral.")
    st.stop()

# ======================================================================= cálculos
fim = pd.Period(f"{ano_atual}-12", freq="M")
idx = ipca.indice_estendido(serie_ipca, fim, ipca_fut)
base_ef = base if corrigido else ultimo_ipca
mensal = analise.aplicar_correcao(analise.serie_mensal(df), idx, base_ef)
col = "real" if corrigido else "nominal"
unid_txt = f"corrigidos pela inflação até {base_ef.strftime('%m/%Y')}" if corrigido else "da época, sem correção"

proj, cresc = analise.projetar(mensal, ano_atual, mes_fechado, anos_hist, metodo)
meses_pend = range(mes_fechado + 1, 13)
f_nom = pd.Series({m: idx[pd.Period(f"{ano_atual}-{m:02d}", freq="M")] / idx[base_ef] for m in meses_pend},
                  dtype=float)
est_unid = analise.montar_estimativa(mensal, proj, ano_atual, mes_fechado, regra_inc, col,
                                     pd.Series(1.0, index=list(meses_pend)) if corrigido else f_nom)
est_nom = analise.montar_estimativa(mensal, proj, ano_atual, mes_fechado, regra_inc, "nominal", f_nom)
previsto = analise.previsto_por_grupo(df)

m_sel = mensal[mensal["grupo"].isin(grupos_sel)]
e_sel = est_unid[est_unid["grupo"].isin(grupos_sel)]
en_sel = est_nom[est_nom["grupo"].isin(grupos_sel)]

janela = mes_fechado if mes_fechado else 12
tot_ano = m_sel.groupby(["ano", "mes"])[col].sum().unstack("ano").reindex(range(1, 13)).fillna(0.0)
ytd = tot_ano.loc[1:janela].sum()
ytd_nom = m_sel[m_sel["mes"] <= janela].groupby("ano")["nominal"].sum()
ytd_real = m_sel[m_sel["mes"] <= janela].groupby("ano")["real"].sum()
estimativa_total = e_sel["estimado"].sum()
estimativa_nom = en_sel["estimado"].sum()
prev_atual = previsto[(previsto["ano"] == ano_atual) & previsto["grupo"].isin(grupos_sel)]["previsao"].sum()
periodo_txt = (f"janeiro a {MESES_EXT[janela - 1]}" if janela > 1 else "janeiro")
tem_ant = (ano_atual - 1) in ytd.index

# ======================================================================= cabeçalho
st.title("📊 Quanto a Prefeitura de Tatuí está arrecadando?")
st.markdown(
    f"Dados de **{', '.join(map(str, anos))}**, atualizados até **{ultima_data.strftime('%d/%m/%Y')}**. "
    f"Valores {unid_txt}.")

with st.expander("❓ Como ler este painel (clique para abrir)"):
    st.markdown(
        f"""
Este painel mostra **quanto dinheiro entrou nos cofres da Prefeitura** (impostos, taxas e repasses dos
governos Federal e Estadual) e compara com os anos anteriores.

- **Comparar com anos anteriores:** mostra se a arrecadação deste ano está maior ou menor que a dos anos passados.
  A comparação é sempre feita no **mesmo período** ({periodo_txt}), porque os meses seguintes ainda não estão completos.
- **Quanto vamos arrecadar:** estima quanto deve entrar até dezembro, com base no que aconteceu nos anos anteriores.
- **Orçado x Arrecadado:** compara o que estava previsto no orçamento (aprovado pela Câmara) com o que realmente entrou.
- **Glossário:** explica cada receita e cada termo usado.

**Por que corrigir pela inflação?** Com a inflação, R\\$ 100 hoje compram menos do que há dois anos. Para saber se
a arrecadação cresceu de verdade, os valores antigos são atualizados pelo IPCA (índice oficial de inflação, do IBGE).
Você pode desligar essa correção na barra lateral (à esquerda).

**Cores:** <span style="color:#0ca30c">▲ verde</span> = aumento; <span style="color:#d03b3b">▼ vermelho</span> = queda.
Passe o mouse sobre os gráficos para ver os valores.
""", unsafe_allow_html=True)

aba1, aba2, aba3, aba4, aba5 = st.tabs(["📈 Comparar com anos anteriores", f"🔮 Quanto vamos arrecadar em {ano_atual}",
                                        "🎯 Orçado x Arrecadado", "📖 Glossário", "🔎 Detalhes técnicos"])

# ======================================================================= ABA 1
with aba1:
    if tem_ant:
        vn = var(ytd_nom.get(ano_atual, 0), ytd_nom.get(ano_atual - 1, 0))
        vr = var(ytd_real.get(ano_atual, 0), ytd_real.get(ano_atual - 1, 0))
        st.info(md(
            f"De **{periodo_txt} de {ano_atual}**, a Prefeitura arrecadou **{brl(ytd_nom.get(ano_atual, 0))}**. "
            f"Isso é **{pct(abs(vn), False)} {mais_menos(vn)}** do que no mesmo período de {ano_atual - 1} "
            f"({brl(ytd_nom.get(ano_atual - 1, 0))}). "
            f"Descontada a inflação, a arrecadação {'cresceu' if vr >= 0 else 'caiu'} **{pct(abs(vr), False)}** de fato."),
            icon="💡")

    k = st.columns(3)
    v_ytd = var(ytd.get(ano_atual, 0), ytd.get(ano_atual - 1, 0)) if tem_ant else np.nan
    k[0].metric(f"Arrecadado em {ano_atual} ({MESES[0]}–{MESES[janela - 1]})", brl(ytd.get(ano_atual, 0)),
                f"{'+' if v_ytd >= 0 else '-'}{pct(abs(v_ytd), False)} {'acima' if v_ytd >= 0 else 'abaixo'} "
                f"de {ano_atual - 1}" if np.isfinite(v_ytd) else None,
                help="Comparação feita somente com os meses completos. Valores " + unid_txt + ".")
    if tem_ant:
        k[1].metric(f"Arrecadado em {ano_atual - 1} (mesmo período)", brl(ytd[ano_atual - 1]))
    k[2].metric(f"Estimativa para todo o ano de {ano_atual}", brl(estimativa_total),
                help="O que já entrou + a estimativa dos meses que faltam. Veja a aba 'Quanto vamos arrecadar'.")

    # --- barras mensais por ano
    fig = go.Figure()
    for a in anos:
        cor = cor_ano(a, anos)
        y = tot_ano[a]
        meses_c = list(range(1, (mes_fechado if a == ano_atual else 12) + 1))
        fig.add_bar(x=[MESES[m - 1] for m in meses_c], y=mi(y.loc[meses_c]), name=str(a),
                    marker_color=cor, offsetgroup=str(a), legendgroup=str(a), hovertemplate=HOVER)
        if a == ano_atual:
            meses_i = [m for m in range(mes_fechado + 1, 13) if abs(y.loc[m]) > 0]
            if meses_i:
                fig.add_bar(x=[MESES[m - 1] for m in meses_i], y=mi(y.loc[meses_i]),
                            name=f"{a} (mês ainda incompleto)", offsetgroup=str(a), legendgroup=str(a),
                            marker=dict(color=cor, opacity=0.45, pattern=dict(shape="/", fgcolor=cor, solidity=0.3)),
                            hovertemplate=HOVER)
    fig.update_xaxes(categoryorder="array", categoryarray=MESES)
    mostrar(fig, "Quanto entrou em cada mês",
            "Cada cor é um ano. Barras mais altas = mais dinheiro arrecadado naquele mês. "
            "A barra listrada é um mês que ainda não terminou de ser lançado, por isso parece menor.")

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        for a in anos:
            lim = mes_fechado if a == ano_atual else 12
            fig.add_scatter(x=MESES[:lim], y=mi(tot_ano[a].cumsum().iloc[:lim]), name=str(a), mode="lines+markers",
                            line=dict(color=cor_ano(a, anos), width=2), marker=dict(size=7), hovertemplate=HOVER)
        mostrar(fig, "Total acumulado ao longo do ano",
                "Soma do que entrou desde janeiro. Se a linha deste ano está acima das outras, "
                "a arrecadação está maior.", 380)

    with c2:
        org = m_sel[m_sel["mes"] <= janela].assign(origem=lambda d: d["grupo"].map(glossario.origem)) \
            .groupby(["origem", "ano"])[col].sum().unstack("ano")
        org = org.reindex([o for o in glossario.ORIGENS if o in org.index])
        fig = go.Figure()
        for a in anos[-2:]:
            if a in org:
                fig.add_bar(y=org.index, x=mi(org[a]), name=f"{a} ({MESES[0]}–{MESES[janela - 1]})",
                            orientation="h", marker_color=cor_ano(a, anos), hovertemplate=HOVER_H)
        fig.update_yaxes(autorange="reversed")
        mostrar(fig, "De onde vem o dinheiro",
                f"Arrecadação de {periodo_txt}, por origem. A maior parte vem de repasses dos governos "
                "Estadual e Federal.", 380, hover="y unified", eixo_valor="x")

    # --- variação por grupo
    g_ytd = m_sel[m_sel["mes"] <= janela].groupby(["grupo", "ano"])[col].sum().unstack("ano")
    if tem_ant and ano_atual in g_ytd:
        d = (g_ytd[ano_atual] - g_ytd[ano_atual - 1]).dropna().sort_values()
        d = d[d.abs() > 1000]
        fig = go.Figure(go.Bar(
            y=d.index, x=mi(d.values), orientation="h", name="Diferença",
            marker_color=np.where(d.values >= 0, "#0ca30c", "#d03b3b"),
            customdata=[glossario.explicacao(g) for g in d.index],
            hovertemplate="<b>%{y}</b><br>R$ %{x:,.1f} mi<br><i>%{customdata}</i><extra></extra>"))
        fig.update_layout(showlegend=False)
        mostrar(fig, f"Quais receitas aumentaram ou diminuíram ({periodo_txt}, {ano_atual} comparado com {ano_atual - 1})",
                "▲ Verde: entrou mais dinheiro que no ano anterior. ▼ Vermelho: entrou menos. "
                "Passe o mouse sobre a barra para ver o que é cada receita.",
                120 + 24 * len(d), hover="closest", eixo_valor="x")

    st.markdown(f"#### Tabela por receita — {periodo_txt} de cada ano")
    st.caption(f"Valores {unid_txt}. A coluna 'Variação' compara {ano_atual} com {ano_atual - 1}.")
    t = g_ytd.copy()
    t.columns = [str(c) for c in t.columns]
    if tem_ant:
        t["Variação"] = (t[str(ano_atual)] / t[str(ano_atual - 1)] - 1).where(t[str(ano_atual - 1)].abs() > 1)
    t.loc["TOTAL"] = t[[c for c in t if c.isdigit()]].sum()
    if tem_ant:
        t.at["TOTAL", "Variação"] = var(t.at["TOTAL", str(ano_atual)], t.at["TOTAL", str(ano_atual - 1)])
    t.insert(0, "O que é", [glossario.explicacao(g) for g in t.index])
    t.index.name = "Receita"
    tabela(t.reset_index(), moeda=[c for c in t if c.isdigit()], variacao=["Variação"] if tem_ant else [])

# ======================================================================= ABA 2
with aba2:
    if not anos_hist:
        st.warning("Escolha ao menos um ano em 'Configurações avançadas → Anos usados na estimativa'.")
    else:
        anos_txt = " e ".join(map(str, anos_hist)) if len(anos_hist) <= 2 else ", ".join(map(str, anos_hist))
        realiz_fech = e_sel.loc[e_sel["mes"] <= mes_fechado, "realizado"].sum()
        falta = e_sel.loc[e_sel["mes"] > mes_fechado, "estimado"].sum()
        real_ant = tot_ano[ano_atual - 1].sum() if (ano_atual - 1) in tot_ano else np.nan
        v_ant = var(estimativa_total, real_ant)
        frase_met = ("foi usada a média do mesmo mês em " + anos_txt if metodo == "media"
                     else "foi usado o mesmo mês em " + anos_txt + ", acrescido do crescimento que cada receita vem tendo")
        msg = (f"Se os próximos meses se comportarem como nos anos anteriores, a arrecadação de **{ano_atual}** deve fechar "
               f"em torno de **{brl(estimativa_total)}**")
        if np.isfinite(v_ant):
            msg += f", **{pct(abs(v_ant), False)} {mais_menos(v_ant)}** que em {ano_atual - 1} ({brl(real_ant)})"
        msg += (f". Para cada mês que falta, {frase_met}, com valores corrigidos pela inflação. "
                "Emendas, convênios e empréstimos **não** são estimados (entra só o que já chegou).")
        st.info(md(msg), icon="💡")
        for _, o in ler_observacoes().query("ano == @ano_atual").iterrows():
            st.caption(md(f"⚖️ {o['receita']} ({brl(o['valor_previsto'])} previstos no orçamento) não entra na "
                          f"estimativa: {o['observacao'][0].lower() + o['observacao'][1:]} "
                          "Veja a aba 'Orçado x Arrecadado'."))

        k = st.columns(3)
        k[0].metric(f"Já arrecadado ({MESES[0]}–{MESES[mes_fechado - 1] if mes_fechado else '-'})", brl(realiz_fech))
        k[1].metric(f"Estimado para os meses que faltam", brl(falta),
                    help="Inclui o mês incompleto. Receitas que não se repetem entram só com o que já chegou.")
        k[2].metric(f"Estimativa para {ano_atual}", brl(estimativa_total),
                    f"{'+' if v_ant >= 0 else '-'}{pct(abs(v_ant), False)} {'acima' if v_ant >= 0 else 'abaixo'} "
                    f"de {ano_atual - 1}"
                    if np.isfinite(v_ant) else None)

        # --- linha mensal
        fig = go.Figure()
        for a in anos:
            if a != ano_atual:
                fig.add_scatter(x=MESES, y=mi(tot_ano[a]), name=str(a), mode="lines",
                                line=dict(color=cor_ano(a, anos), width=2), opacity=0.7, hovertemplate=HOVER)
        em = e_sel.groupby("mes")[["realizado", "estimado"]].sum()
        cor = cor_ano(ano_atual, anos)
        if mes_fechado:
            fig.add_scatter(x=MESES[:mes_fechado], y=mi(em["estimado"].iloc[:mes_fechado]),
                            name=f"{ano_atual} – já arrecadado", mode="lines+markers",
                            line=dict(color=cor, width=3), marker=dict(size=8), hovertemplate=HOVER)
        if mes_fechado < 12:
            a0 = max(mes_fechado - 1, 0)
            fig.add_scatter(x=MESES[a0:], y=mi(em["estimado"].iloc[a0:]), name=f"{ano_atual} – estimativa",
                            mode="lines+markers", line=dict(color=cor, width=3, dash="dash"),
                            marker=dict(size=8, symbol="circle-open"), hovertemplate=HOVER)
            parc = em["realizado"].iloc[mes_fechado:]
            parc = parc[parc.abs() > 0]
            if len(parc):
                fig.add_scatter(x=[MESES[m - 1] for m in parc.index], y=mi(parc),
                                name=f"{ano_atual} – já entrou no mês incompleto", mode="markers",
                                marker=dict(color=cor, size=11, symbol="x"), hovertemplate=HOVER)
            fig.add_vrect(x0=mes_fechado - 0.5, x1=11.5, fillcolor=CINZA, opacity=0.08, line_width=0,
                          annotation_text="meses estimados", annotation_position="top left")
        mostrar(fig, "Mês a mês: o que já entrou e o que deve entrar",
                "Linha cheia = valores reais já arrecadados. Linha tracejada = estimativa. "
                "As linhas finas mostram os anos anteriores, para comparação. "
                "Dezembro costuma ser mais alto (13º do FPM, IPTU e ICMS de fim de ano).", 420)

        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure()
            hist = [a for a in anos if a < ano_atual]
            fig.add_bar(x=[str(a) for a in hist], y=mi([tot_ano[a].sum() for a in hist]), name="Ano completo",
                        marker_color=CINZA, hovertemplate=HOVER)
            nao_rec_pend = e_sel.loc[(e_sel["mes"] > mes_fechado) & ~e_sel["recorrente"], "estimado"].sum()
            fig.add_bar(x=[str(ano_atual)], y=mi([realiz_fech + nao_rec_pend]), name=f"{ano_atual} – já arrecadado",
                        marker_color=cor, hovertemplate=HOVER)
            fig.add_bar(x=[str(ano_atual)], y=mi([falta - nao_rec_pend]), name=f"{ano_atual} – estimativa",
                        marker=dict(color=cor, opacity=0.5, pattern=dict(shape="/", fgcolor=cor, solidity=0.3)),
                        hovertemplate=HOVER)
            fig.update_layout(barmode="stack", bargap=0.45)
            mostrar(fig, "Total do ano", f"Comparação do total de {ano_atual} (já arrecadado + estimativa) "
                                         "com os anos anteriores completos.", 380)
        with c2:
            st.markdown("#### Como a estimativa foi feita")
            if metodo == "media":
                st.markdown(
                    f"Para cada mês que falta, calculou-se **a média do mesmo mês em {anos_txt}**, "
                    "com os valores antigos atualizados pela inflação.\n\n"
                    f"*Exemplo:* para dezembro de {ano_atual}, usa-se a média de dezembro de {anos_txt}.\n\n"
                    "É um método **conservador**: supõe que a arrecadação não vai crescer além da inflação.")
            else:
                st.markdown(
                    "Igual à média, mas cada receita recebe o **crescimento acima da inflação** que vem tendo. "
                    f"O crescimento é medido comparando sempre {periodo_txt} de cada ano. "
                    "Para evitar exageros, o crescimento é limitado entre −30% e +50% ao ano.")
                if cresc is not None and len(cresc):
                    cv = cresc[cresc["grupo"].isin(grupos_sel)][["grupo", "crescimento_usado"]] \
                        .rename(columns={"grupo": "Receita", "crescimento_usado": "Crescimento real ao ano"}) \
                        .sort_values("Crescimento real ao ano", ascending=False)
                    tabela(cv, variacao=["Crescimento real ao ano"], altura=260)

        st.markdown(f"#### Estimativa por receita — {ano_atual}")
        st.caption(f"Valores {unid_txt}.")
        tg = e_sel.groupby(["grupo", "recorrente"]).apply(lambda d: pd.Series({
            "Já arrecadado": d["realizado"].sum(),
            "Estimativa do ano": d["estimado"].sum()}), include_groups=False).reset_index()
        tg["Falta arrecadar (estimado)"] = tg["Estimativa do ano"] - tg["Já arrecadado"]
        tg[f"Total de {ano_atual - 1}"] = tg["grupo"].map(
            mensal[mensal["ano"] == ano_atual - 1].groupby("grupo")[col].sum())
        tg[f"Comparado a {ano_atual - 1}"] = tg["Estimativa do ano"] / tg[f"Total de {ano_atual - 1}"] - 1
        tg["Estimada?"] = tg["recorrente"].map({True: "Sim", False: "Não (não se repete)"})
        tg = tg.drop(columns="recorrente").rename(columns={"grupo": "Receita"}) \
            .sort_values("Estimativa do ano", ascending=False)
        tot = tg.select_dtypes("number").sum().astype(object)
        tot["Receita"], tot["Estimada?"] = "TOTAL", ""
        tot[f"Comparado a {ano_atual - 1}"] = var(tot["Estimativa do ano"], tot[f"Total de {ano_atual - 1}"])
        tg = pd.concat([tg, tot.to_frame().T], ignore_index=True)
        tg = tg[["Receita", "Já arrecadado", "Falta arrecadar (estimado)", "Estimativa do ano",
                 f"Total de {ano_atual - 1}", f"Comparado a {ano_atual - 1}", "Estimada?"]]
        for c in tg.columns[1:-1]:
            tg[c] = pd.to_numeric(tg[c], errors="coerce")
        tabela(tg, moeda=list(tg.columns[1:5]), variacao=[f"Comparado a {ano_atual - 1}"])
        st.download_button("⬇️ Baixar a estimativa mês a mês (planilha CSV)",
                           e_sel.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                           file_name=f"estimativa_{ano_atual}_{metodo}.csv", mime="text/csv")

# ======================================================================= ABA 3
with aba3:
    ano_pr = st.selectbox("Escolha o ano", anos[::-1], index=0)
    prev_g = previsto[(previsto["ano"] == ano_pr) & previsto["grupo"].isin(grupos_sel)].set_index("grupo")["previsao"]
    real_g = mensal[(mensal["ano"] == ano_pr) & mensal["grupo"].isin(grupos_sel)].groupby("grupo")["nominal"].sum()
    comp = pd.DataFrame({"Previsto": prev_g, "Arrecadado": real_g})
    atual = ano_pr == ano_atual
    if atual:
        comp["Estimativa"] = en_sel.groupby("grupo")["estimado"].sum()
    comp = comp.fillna(0.0)
    comp = comp[(comp.abs() > 0).any(axis=1)].sort_values("Previsto", ascending=False)
    p_tot, r_tot = comp["Previsto"].sum(), comp["Arrecadado"].sum()

    if atual:
        dif = comp["Estimativa"].sum() - p_tot
        st.info(md(
            f"O orçamento de {ano_pr} previa arrecadar **{brl(p_tot)}**. Até {ultima_data.strftime('%d/%m/%Y')} "
            f"entraram **{brl(r_tot)}** ({pct(r_tot / p_tot, False) if p_tot else '-'} do previsto). "
            f"Pela estimativa, o ano deve fechar em **{brl(comp['Estimativa'].sum())}**, ou seja, "
            f"**{brl(abs(dif))} {'acima' if dif >= 0 else 'abaixo'}** do previsto no orçamento."), icon="💡")
        base_cmp = "Estimativa"
    else:
        dif = r_tot - p_tot
        st.info(md(
            f"O orçamento de {ano_pr} previa arrecadar **{brl(p_tot)}** e entraram **{brl(r_tot)}** "
            f"({pct(r_tot / p_tot, False) if p_tot else '-'} do previsto): "
            f"**{brl(abs(dif))} {'acima' if dif >= 0 else 'abaixo'}** do orçamento."), icon="💡")
        base_cmp = "Arrecadado"

    obs_ano = avisos_observacoes(ano_pr)
    if len(obs_ano):
        extra = obs_ano["valor_previsto"].sum()
        final = comp[base_cmp].sum()
        dif_total = final - (p_tot + extra)
        nomes = ", ".join(obs_ano["receita"])
        st.caption(md(
            f"Somando {nomes} ao previsto, o orçamento original de {ano_pr} seria de **{brl(p_tot + extra)}**, e o "
            f"{'estimado' if atual else 'arrecadado'} ficaria **{brl(abs(dif_total))} "
            f"{'acima' if dif_total >= 0 else 'abaixo'}** dele — sendo **{brl(extra)}** referentes a "
            f"receita que a Prefeitura está impedida de arrecadar."))

    comp["Diferença"] = comp[base_cmp] - comp["Previsto"]
    sig = comp[comp["Previsto"].abs() > 0]
    abaixo = sig.sort_values("Diferença").head(3)
    acima = sig.sort_values("Diferença", ascending=False).head(3)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**▼ Receitas que mais {'devem ficar' if atual else 'ficaram'} abaixo do previsto**")
        for g, r in abaixo[abaixo["Diferença"] < 0].iterrows():
            st.markdown(md(f"- **{g}**: {brl(abs(r['Diferença']))} a menos"))
    with c2:
        st.markdown(f"**▲ Receitas que mais {'devem ficar' if atual else 'ficaram'} acima do previsto**")
        for g, r in acima[acima["Diferença"] > 0].iterrows():
            st.markdown(md(f"- **{g}**: {brl(r['Diferença'])} a mais"))

    # --- barras por grupo
    cmp_plot = comp.sort_values("Previsto", ascending=True)
    fig = go.Figure()
    fig.add_bar(y=cmp_plot.index, x=mi(cmp_plot["Previsto"]), name="Previsto no orçamento", orientation="h",
                marker_color=CINZA, hovertemplate=HOVER_H)
    fig.add_bar(y=cmp_plot.index, x=mi(cmp_plot["Arrecadado"]), name="Já arrecadado" if atual else "Arrecadado",
                orientation="h", marker_color=SERIES[0], hovertemplate=HOVER_H)
    if atual:
        fig.add_bar(y=cmp_plot.index, x=mi(cmp_plot["Estimativa"]), name="Estimativa para o ano todo",
                    orientation="h", marker_color=SERIES[2], hovertemplate=HOVER_H)
    fig.update_layout(bargap=0.3)
    mostrar(fig, f"Previsto x arrecadado, por receita — {ano_pr}",
            "Cinza = quanto o orçamento previa. Azul = quanto entrou"
            + (". Verde = quanto deve entrar até dezembro." if atual else "."),
            120 + 30 * len(cmp_plot) * (3 if atual else 2) // 2, hover="y unified", eixo_valor="x")

    # --- acumulado mensal
    anos_saz = [a for a in anos if a < ano_atual] or anos
    saz = analise.sazonalidade(mensal, anos_saz)
    pm = saz.merge(prev_g.rename("prev").reset_index(), on="grupo")
    prev_mes = (pm["peso"] * pm["prev"]).groupby(pm["mes"]).sum().reindex(range(1, 13)).fillna(0.0)
    real_mes = mensal[(mensal["ano"] == ano_pr) & mensal["grupo"].isin(grupos_sel)].groupby("mes")["nominal"].sum() \
        .reindex(range(1, 13)).fillna(0.0)
    fig = go.Figure()
    fig.add_scatter(x=MESES, y=mi(prev_mes.cumsum()), name="Previsto no orçamento (acumulado)", mode="lines",
                    line=dict(color=CINZA, width=2.5), hovertemplate=HOVER)
    lim = mes_fechado if atual else 12
    fig.add_scatter(x=MESES[:lim], y=mi(real_mes.cumsum().iloc[:lim]), name="Arrecadado (acumulado)",
                    mode="lines+markers", line=dict(color=SERIES[0], width=3), marker=dict(size=8), hovertemplate=HOVER)
    if atual and mes_fechado < 12:
        est_mes = en_sel.groupby("mes")["estimado"].sum().reindex(range(1, 13)).fillna(0.0).cumsum()
        a0 = max(mes_fechado - 1, 0)
        fig.add_scatter(x=MESES[a0:], y=mi(est_mes.iloc[a0:]), name="Estimativa (acumulado)", mode="lines+markers",
                        line=dict(color=SERIES[2], width=3, dash="dash"), marker=dict(size=8, symbol="circle-open"),
                        hovertemplate=HOVER)
    mostrar(fig, f"O ano está andando conforme o orçamento? — {ano_pr}",
            "Soma desde janeiro. Se a linha azul está acima da cinza, a arrecadação está à frente do previsto. "
            "O previsto foi distribuído pelos meses conforme o padrão dos anos anteriores "
            "(ex.: o IPTU se concentra no início do ano).", 400)

    st.markdown(f"#### Tabela: previsto x arrecadado — {ano_pr}")
    st.caption("Valores da época, sem correção pela inflação (o orçamento é feito em valores da época).")
    tb = comp.copy()
    tb.loc["TOTAL"] = tb.sum()
    tb["% do previsto"] = tb[base_cmp] / tb["Previsto"].replace(0, np.nan)
    tb = tb.rename(columns={"Diferença": f"Diferença ({base_cmp.lower()} − previsto)"})
    tb.index.name = "Receita"
    tb = tb.reset_index()
    tabela(tb, moeda=[c for c in tb.columns if c not in ("Receita", "% do previsto")], perc=["% do previsto"])
    st.caption("Observação: receitas previstas no orçamento que não tiveram nenhum valor arrecadado no ano "
               "não aparecem nos arquivos e, por isso, não entram no total previsto.")

# ======================================================================= ABA 4
with aba4:
    st.markdown("#### O que significa cada termo")
    for termo, txt in glossario.TERMOS.items():
        st.markdown(md(f"**{termo}** — {txt}"))
    st.markdown("#### O que é cada receita")
    for origem in glossario.ORIGENS:
        grupos_o = [g for g in todos_grupos if glossario.origem(g) == origem]
        if not grupos_o:
            continue
        with st.expander(origem, expanded=False):
            for g in grupos_o:
                st.markdown(md(f"**{g}** — {glossario.explicacao(g)}"))

# ======================================================================= ABA 5
with aba5:
    st.caption("Esta aba é voltada à equipe técnica: mostra como os dados foram tratados.")
    st.markdown("#### Situação dos arquivos")
    info = df.groupby("exercicio").agg(arquivo=("arquivo", "first"), lancamentos=("codigo", "size"),
                                       primeira_data=("data", "min"), ultima_data=("data", "max"),
                                       anulacoes=("anulacao", "sum"))
    info["meses completos"] = [f"Jan–{MESES[mes_fechado - 1]}" if a == ano_atual and mes_fechado else
                               ("nenhum" if a == ano_atual else "Jan–Dez") for a in info.index]
    st.dataframe(info, width="stretch")
    st.markdown(
        "**Tratamentos aplicados**\n"
        "- **Anulações/estornos:** usa-se o valor líquido; como a análise é por grupo, reclassificações dentro "
        "do mesmo grupo se compensam.\n"
        "- **Multas, juros e dívida ativa:** somados à receita principal.\n"
        "- **Mudança de numeração:** códigos antigos e novos caem no mesmo grupo "
        "(ex.: rendimentos `1321.01.0` → `1321.01.1`; PNAE/PNATE desdobrados em 2026).\n"
        "- **Emendas, convênios e receitas pontuais:** grupo *Outras Receitas Não Recorrentes*, fora da estimativa.\n"
        "- **Meses incompletos:** fora das comparações e da base de crescimento; são estimados.\n"
        "- **Linhas quebradas nos CSV:** registros divididos em duas linhas são remontados na leitura.\n"
        "- Regras em `config/regras_receitas.csv` (vale a primeira que casar). Após editar, use "
        "*Recarregar arquivos de dados*.")

    st.markdown("#### Classificação por código")
    tc = tabela_codigos(*assin, df)
    c1, c2, c3 = st.columns([1, 1, 2])
    so_alerta = c1.checkbox("Somente com alertas", value=False)
    grupo_f = c2.selectbox("Grupo", ["(todos)"] + todos_grupos)
    busca = c3.text_input("Buscar (código ou nome)")
    v = tc
    if so_alerta:
        v = v[v["alertas"] != ""]
    if grupo_f != "(todos)":
        v = v[v["grupo"] == grupo_f]
    if busca:
        b = classificacao.normalizar(busca)
        v = v[v["codigo"].str.contains(busca, regex=False)
              | v["receita"].map(classificacao.normalizar).str.contains(b, regex=False)]
    tabela(v, moeda=[c for c in v.columns if c.startswith("Arrecadado") or c == "Anulações"], altura=500)
    st.download_button("⬇️ Baixar classificação (CSV)", tc.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                       file_name="classificacao_receitas.csv", mime="text/csv")

    st.markdown("#### Anulações relevantes por mês (exceto deduções do FUNDEB)")
    an = df[df["anulacao"] & ~df["codigo"].str.startswith("9")]
    an_m = an.groupby(["exercicio", "mes", "grupo"], as_index=False)["arrecadado"].sum()
    an_m = an_m[an_m["arrecadado"] < -10000].sort_values("arrecadado")
    an_m["mes"] = an_m["mes"].map(lambda m: MESES[m - 1])
    tabela(an_m.rename(columns={"arrecadado": "valor anulado"}), moeda=["valor anulado"], altura=300)

    st.markdown("#### IPCA mensal")
    ip = serie_ipca.copy().sort_values("periodo", ascending=False)
    ip["mês"] = ip["periodo"].dt.strftime("%m/%Y")
    ip["IPCA do mês"] = ip["ipca"]
    ip["fator de correção"] = ip["periodo"].map(ipca.fatores_correcao(idx, ip["periodo"], base_ef))
    st.dataframe(ip[["mês", "IPCA do mês", "fator de correção"]].style.format(
        {"IPCA do mês": lambda v: _br(f"{v * 100:.2f}") + "%", "fator de correção": lambda v: _br(f"{v:.6f}")}),
        hide_index=True, width="stretch", height=300)
