"""Explicações em linguagem simples para quem não é da área de orçamento público."""

# grupo -> (origem do dinheiro, explicação)
GRUPOS: dict[str, tuple[str, str]] = {
    "IPTU": ("Impostos e taxas do município",
             "Imposto anual sobre casas, apartamentos e terrenos da cidade. Inclui multas, juros e dívidas atrasadas."),
    "ITBI": ("Impostos e taxas do município",
             "Imposto pago quando um imóvel é comprado ou vendido."),
    "ISSQN": ("Impostos e taxas do município",
              "Imposto sobre serviços (ISS) prestados por empresas e autônomos, como oficinas, escolas e clínicas."),
    "IRRF": ("Impostos e taxas do município",
             "Imposto de Renda descontado dos salários dos servidores e de pagamentos feitos pela Prefeitura. "
             "Por lei, esse valor fica com o município."),
    "Taxas de Fiscalização": ("Impostos e taxas do município",
                              "Taxas de alvarás, licenças de funcionamento, publicidade, uso de calçadas e vigilância sanitária."),
    "Taxas de Serviços (Coleta de Lixo)": ("Impostos e taxas do município",
                                           "Taxa cobrada pela coleta de lixo."),
    "COSIP - Iluminação Pública": ("Impostos e taxas do município",
                                   "Contribuição cobrada na conta de luz para pagar a iluminação das ruas."),
    "Receita Patrimonial": ("Outras receitas próprias",
                            "Aluguéis e arrendamentos de imóveis da Prefeitura."),
    "Rendimentos de Aplicações Financeiras": ("Outras receitas próprias",
                                              "Juros recebidos pelo dinheiro da Prefeitura aplicado nos bancos."),
    "Receita de Serviços": ("Outras receitas próprias",
                            "Valores cobrados por serviços da Prefeitura, como cemitérios e coleta de lixo hospitalar."),
    "Multas e Outras Receitas Correntes": ("Outras receitas próprias",
                                           "Multas de fiscalização, indenizações, honorários de ações judiciais e outras receitas."),
    "Outras Receitas Correntes": ("Outras receitas próprias", "Demais receitas do dia a dia."),
    "FPM": ("Repasses do Governo Federal",
            "Fundo de Participação dos Municípios: parte do Imposto de Renda e do IPI arrecadados pela União, "
            "dividida entre todos os municípios. É uma das maiores receitas da cidade."),
    "ITR": ("Repasses do Governo Federal", "Parte do imposto federal sobre propriedades rurais."),
    "Compensações Financeiras (CFEM/FEP/Royalties)": ("Repasses do Governo Federal",
                                                      "Royalties de petróleo e de mineração repassados aos municípios."),
    "Transf. União - SUS": ("Repasses do Governo Federal",
                            "Dinheiro do Ministério da Saúde para manter postos de saúde, SAMU, agentes de saúde etc."),
    "Transf. União - FNDE/Educação": ("Repasses do Governo Federal",
                                      "Verbas federais para a educação: merenda (PNAE), transporte escolar (PNATE) e salário-educação."),
    "Transf. União - Assistência Social": ("Repasses do Governo Federal",
                                           "Verbas federais para CRAS, CREAS, Cadastro Único e outros serviços de assistência social."),
    "Outras Transferências da União": ("Repasses do Governo Federal", "Outros repasses fixos da União."),
    "ICMS": ("Repasses do Governo Estadual",
             "Parte (25%) do imposto estadual sobre mercadorias e serviços. É a maior receita da cidade."),
    "IPVA": ("Repasses do Governo Estadual",
             "Metade do imposto pago pelos veículos registrados na cidade."),
    "IPI-Exportação": ("Repasses do Governo Estadual", "Parte do IPI sobre produtos exportados, repassada via Estado."),
    "CIDE": ("Repasses do Governo Estadual", "Parte do imposto federal sobre combustíveis, repassada via Estado."),
    "Transf. Estado - SUS": ("Repasses do Governo Estadual", "Verbas do Estado para a saúde (ex.: Tabela SUS Paulista)."),
    "Transf. Estado - Educação (Merenda/Transporte)": ("Repasses do Governo Estadual",
                                                       "Verbas do Estado para a merenda e o transporte de alunos."),
    "Transf. Estado - Assistência Social": ("Repasses do Governo Estadual", "Verbas do Estado para assistência social."),
    "FUNDEB": ("FUNDEB (educação)",
               "Fundo da educação básica. O município contribui com parte de seus repasses e recebe de volta "
               "conforme o número de alunos matriculados. Só pode ser gasto com educação."),
    "(-) Dedução para o FUNDEB": ("FUNDEB (educação)",
                                  "20% do FPM, ICMS, IPVA, ITR e IPI ficam retidos automaticamente para formar o FUNDEB. "
                                  "Por isso aparece com valor negativo."),
    "Operações de Crédito": ("Não se repetem todo ano",
                             "Empréstimos e financiamentos contratados pela Prefeitura (ex.: para obras). "
                             "Não é arrecadação: é dinheiro que depois precisa ser devolvido."),
    "Outras Receitas Não Recorrentes": ("Não se repetem todo ano",
                                        "Emendas parlamentares, convênios e verbas para obras e equipamentos. "
                                        "Vêm em um ano, mas não há garantia de que venham no próximo."),
}

ORIGENS = ["Impostos e taxas do município", "Outras receitas próprias", "Repasses do Governo Federal",
           "Repasses do Governo Estadual", "FUNDEB (educação)", "Não se repetem todo ano"]


def origem(grupo: str) -> str:
    return GRUPOS.get(grupo, ("Outras receitas próprias", ""))[0]


def explicacao(grupo: str) -> str:
    return GRUPOS.get(grupo, ("", ""))[1]


TERMOS = {
    "Receita / Arrecadação": "Todo dinheiro que entra nos cofres da Prefeitura: impostos, taxas e repasses de outros governos.",
    "Previsto (orçamento / LOA)": "Quanto a Prefeitura estimou, no ano anterior, que iria arrecadar. "
                                  "Está na Lei Orçamentária Anual (LOA), aprovada pela Câmara.",
    "Realizado / Arrecadado": "Quanto efetivamente entrou até agora.",
    "Estimativa / Projeção": "Cálculo de quanto deve entrar até o fim do ano: o que já entrou + uma previsão "
                             "para os meses que faltam, baseada nos anos anteriores.",
    "Inflação / IPCA": "O IPCA é o índice oficial de inflação do Brasil (IBGE). Corrigir pela inflação permite comparar "
                       "anos diferentes de forma justa: R$ 100 em 2024 compravam mais coisas do que R$ 100 hoje.",
    "Crescimento real": "Quanto a arrecadação cresceu acima da inflação. Se arrecadou 5% a mais e a inflação foi 4%, "
                        "o crescimento real foi de cerca de 1%.",
    "Mês incompleto": "Mês cujos dados ainda não foram totalmente lançados. Não entra nas comparações para não "
                      "parecer que a arrecadação caiu.",
    "Receita não recorrente": "Dinheiro que entra uma vez e não se repete (emendas, convênios, empréstimos). "
                              "Fica fora da projeção, pois não dá para contar com ele no futuro.",
    "Anulação / estorno": "Lançamento desfeito (por erro ou reclassificação). O painel considera o valor final, já descontado.",
    "Multas, juros e dívida ativa": "Valores pagos com atraso. Foram somados ao imposto de origem (ex.: dívida de IPTU entra em IPTU).",
}
