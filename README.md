# Painel de Receitas – Tatuí

Painel web (Streamlit) para comparar a arrecadação com os anos anteriores, corrigir pelo IPCA,
projetar o fechamento do exercício e confrontar o previsto com o realizado.

## Como executar

```bash
pip install -r requirements.txt
streamlit run app.py
```

Ou dê dois cliques em `iniciar.bat`. O painel abre em http://localhost:8501.

## Dados

Coloque os arquivos exportados em `Dados/` com o ano no nome (`Receitas 2027.csv`).
Formato: `Ficha;Código;Receita;Fonte;Data;Previsão;Crédito;Débito;Arrecadado` (separador `;`).
Linhas quebradas (nome da receita com quebra de linha) são remontadas automaticamente.
Após trocar os arquivos, use **Recarregar arquivos CSV** na barra lateral.

## IPCA

Buscado na API do Banco Central (SGS 433), com fallback para o IBGE/SIDRA (tabela 1737), e gravado em
`cache/ipca.csv`. Botão **Atualizar IPCA via API** na barra lateral. Para meses ainda sem IPCA divulgado
usa-se a taxa informada (padrão: média dos últimos 12 meses).

## Abas

| Aba | Conteúdo |
|---|---|
| Comparativo entre anos | Arrecadação mensal e acumulada por ano, variação por grupo no mesmo período (só meses completos). |
| Projeção | Realizado + projeção dos meses pendentes, estimativa anual por grupo, download em CSV. |
| Previsto x Realizado | Previsão (LOA) x realizado x estimativa por grupo e acumulado mensal (sempre nominal). |
| Dados e classificação | Situação dos arquivos, código → grupo com alertas, anulações relevantes, tabela do IPCA. |

## Métodos de projeção (grupos recorrentes)

- **Média dos últimos anos:** para cada mês pendente, média dos anos-base corrigidos pelo IPCA.
- **Comportamento (tendência):** cada ano-base corrigido pelo IPCA é levado ao ano atual pela taxa média
  (geométrica) de crescimento real do grupo, medida sempre na mesma janela de meses completos
  (ex.: jan–set/24 → jan–set/25 → jan–set/26). A taxa é limitada a −30% / +50% ao ano.

Grupos não recorrentes (emendas, convênios, operações de crédito) não são projetados: entra apenas o
que já foi arrecadado.

## Casos especiais

- **Meses incompletos:** por padrão o mês do último lançamento (ex.: out/2026) e os seguintes são
  tratados como incompletos. Ajustável em *Último mês completo*. No mês incompleto pode-se usar o
  maior valor entre o parcial e a projeção, ou só a projeção.
- **Anulações/estornos:** usa-se o valor líquido; a análise é por grupo, então reclassificações
  dentro do mesmo grupo se compensam. A aba *Dados* lista códigos anulados integralmente ou com
  anulações > 20%.
- **Multas, juros e dívida ativa:** somados à receita principal.
- **Renumeração:** os códigos antigo e novo caem no mesmo grupo; a aba *Dados* aponta códigos
  com o mesmo nome em numerações diferentes.

## Regras de classificação – `config/regras_receitas.csv`

Lidas de cima para baixo; vale a **primeira** regra que casar.

| coluna | uso |
|---|---|
| `prefixo` | início do código (ex.: `1112.50` = IPTU e todos os seus desdobramentos) |
| `contem` | palavras no nome, separadas por `\|` (sem diferenciar acentos/maiúsculas) |
| `grupo` | nome do grupo no painel |
| `recorrente` | `S` entra na projeção; `N` não é projetado |

Exemplo: para tratar uma nova receita pontual `1723.50.0.1.30.00`, inclua acima das regras gerais:
`1723.50.0.1.30;;Outras Receitas Não Recorrentes;N;motivo`.
