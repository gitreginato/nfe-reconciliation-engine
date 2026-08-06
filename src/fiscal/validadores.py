"""Validadores fiscais e contabeis.

Baseados em:
- NT 2023.002 (leiaute NF-e 4.00)
- MOC 7.0 (Manual de Orientacao do Contribuinte)
- TIPI 2024 (Decreto 11.158/2022)
- Tabela CFOP oficial (Ajuste SINIEF 07/05)
- Lei 6.404/76 art. 177 (partida dobrada)
- EC 132/2023 (Reforma Tributaria: IBS/CBS)
"""
import re
from decimal import Decimal
from datetime import date


# Tabela de CFOPs validos (subset mais comum, baseado em Ajuste SINIEF 07/05)
CFOPS_VALIDOS = {
    # Entradas (1xxx)
    "1101", "1102", "1103", "1111", "1113", "1116", "1117", "1118", "1201", "1202",
    "1120", "1121", "1122", "1124", "1125", "1126",
    "1251", "1252", "1253", "1254", "1255", "1256", "1257",
    "1303", "1304", "1305", "1306",
    "1403", "1407", "1409", "1410", "1411", "1414", "1415",
    "1501", "1503", "1504", "1505", "1506",
    "1551", "1552", "1553", "1554", "1555", "1556", "1557",
    "1601", "1602", "1603", "1604", "1605",
    "1652", "1653", "1658", "1659",
    "1901", "1902", "1903", "1904", "1905", "1906", "1908", "1909", "1910",
    "1911", "1912", "1913", "1914", "1915", "1916", "1917", "1918", "1919",
    "1920", "1921", "1922", "1923", "1924", "1925", "1926",
    "1933", "1949",
    # Saidas (2xxx) - espelha entradas
    "2101", "2102", "2111", "2113", "2116", "2117", "2118",
    "2201", "2202", "2204", "2205", "2206", "2207", "2208", "2209",
    "2251", "2252", "2253", "2254", "2255", "2256", "2257",
    "2303", "2304", "2305", "2306",
    "2403", "2407", "2409", "2410", "2411", "2414", "2415",
    "2501", "2503", "2504", "2505", "2506",
    "2551", "2552", "2553", "2554", "2555", "2556", "2557",
    "2603", "2604", "2605",
    "2652", "2653", "2658", "2659",
    "2901", "2902", "2903", "2904", "2905", "2906", "2908", "2909", "2910",
    "2911", "2912", "2913", "2914", "2915", "2916", "2917", "2918", "2919",
    "2920", "2921", "2922", "2923", "2924", "2925", "2926",
    "2933", "2949",
    # Entradas outras (3xxx)
    "3101", "3102",
    # Saidas outras (5xxx, 6xxx, 7xxx)
    "5101", "5102", "5103", "5104", "5105", "5106", "5109", "5110", "5111",
    "5112", "5113", "5114", "5115", "5116", "5117", "5118", "5119", "5120",
    "5122", "5123", "5124", "5125", "5126",
    "5201", "5202", "5205", "5206", "5207", "5208", "5209",
    "5251", "5252", "5253", "5254", "5255", "5256", "5257",
    "5403", "5405", "5409", "5410", "5411", "5412", "5413", "5414", "5415",
    "5501", "5502", "5503", "5504", "5505", "5506",
    "5551", "5552", "5553", "5554", "5555", "5556", "5557",
    "5603", "5605", "5606",
    "5652", "5653", "5658", "5659", "5660",
    "5901", "5902", "5903", "5904", "5905", "5906", "5907", "5908", "5909",
    "5910", "5911", "5912", "5913", "5914", "5915", "5916", "5917", "5918",
    "5919", "5920", "5921", "5922", "5923", "5924", "5925", "5926",
    "5933", "5949",
    "6101", "6102", "6103", "6104", "6105", "6106", "6107", "6108", "6109",
    "6110", "6111", "6112", "6113", "6114", "6115", "6116", "6117", "6118",
    "6119", "6120", "6122", "6123", "6124", "6125", "6126",
    "6201", "6202", "6205", "6206", "6207", "6208", "6209", "6210",
    "6401", "6402", "6403", "6404", "6405",
    "6501", "6502", "6503", "6504", "6505",
    "6551", "6552", "6553", "6554", "6555", "6556", "6557",
    "6603", "6604", "6605", "6606",
    "6901", "6902", "6903", "6904", "6905", "6906", "6907", "6908", "6909",
    "6910", "6911", "6912", "6913", "6914", "6915", "6916", "6917", "6918",
    "6919", "6920", "6921", "6922", "6923", "6924", "6925",
    "6933", "6949",
    "7101", "7102", "7105", "7106", "7107", "7108", "7111", "7112",
    "7127", "7128",
    "7201", "7202", "7205", "7206", "7207",
    "7501", "7502", "7503", "7504", "7505", "7506",
    "7551", "7552", "7553", "7554", "7555", "7556", "7557",
    "7901", "7902",
}

# CFOPs de servico (nao usam NCM, usam LC 116/2003)
CFOPS_SERVICO = {
    "1251", "1252", "1253", "1254", "1255", "1256", "1257",
    "1933", "2933", "5933", "6933",
    "2251", "2252", "2253", "2254", "2255", "2256", "2257",
    "5251", "5252", "5253", "5254", "5255", "5256", "5257",
    "6251", "6252", "6253", "6254", "6255", "6256", "6257",
}

# CFOPs de devolucao (geram estorno de compra)
CFOPS_DEVOLUCAO = {"1201", "1202", "1208", "1209", "1410", "1411", "1553", "1556",
                   "2201", "2202", "2208", "2209", "2410", "2411", "2553", "2556",
                   "5201", "5202", "5208", "5209", "5410", "5411", "5553", "5556",
                   "6201", "6202", "6208", "6209", "6410", "6411", "6553", "6556"}

# CFOPs de ativo imobilizado
CFOPS_ATIVO = {"1551", "1552", "1553", "1554", "1555", "1556", "1557",
               "2551", "2552", "2553", "2554", "2555", "2556", "2557",
               "3551", "3552", "3553", "3554", "3555", "3556", "3557"}

# CFOPs de material de consumo
CFOPS_CONSUMO = {"1103", "1104", "1105", "1106", "1107", "1108", "1109",
                 "2103", "2104", "2105", "2106", "2107", "2108", "2109"}

# CSTs ICMS validos (Ajuste SINIEF 04/04)
CSTS_ICMS_VALIDOS = {
    "00", "10", "20", "30", "40", "41", "50", "51", "60", "70", "90",
}

# CSOSN validos (Simples Nacional)
CSOSN_VALIDOS = {
    "101", "102", "103", "201", "202", "203", "300", "400", "500", "900",
}

# CSTs PIS/COFINS validos (Lei 10.637/02, Lei 10.833/03)
CSTS_PIS_COFINS_VALIDOS = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09",
    "49", "50", "51", "52", "53", "54", "55", "56", "60",
    "61", "62", "63", "64", "65", "66", "67", "70", "71", "72",
    "73", "74", "75", "76", "77", "78", "79", "98", "99",
}

# UF validas (codigo IBGE)
UFS_VALIDAS = {
    "11", "12", "13", "14", "15", "16", "17", "21", "22", "23", "24", "25",
    "26", "27", "28", "29", "31", "32", "33", "35", "41", "42", "43", "50",
    "51", "52", "53",
}

# Alíquotas IBS/CBS verificadas para 2026, conforme orientação oficial da
# Receita Federal. Os períodos posteriores exigem atualização por lei, ato ou
# nota técnica vigente e, por isso, não são inventados como constantes.
ALIQUOTAS_IBS_CBS = {
    2026: {
        "cbs": Decimal("0.90"),
        "ibs": Decimal("0.10"),
        "fase": "educativa",
        "recolher": False,
        "fonte": "RFB: orientações da reforma tributária para 2026",
    },
}


def validar_cfop(cfop: str) -> bool:
    """Valida se CFOP existe na tabela oficial (Ajuste SINIEF 07/05)."""
    if not cfop:
        return False
    cfop = cfop.strip()
    if len(cfop) != 4 or not cfop.isdigit():
        return False
    return cfop in CFOPS_VALIDOS


def validar_cfop_compatibilidade(cfop: str, tipo_operacao: str) -> bool:
    """Valida se CFOP e compativel com tipo de operacao (entrada=0, saida=1)."""
    if not validar_cfop(cfop):
        return False
    primeiro_digito = cfop[0]
    if tipo_operacao == "0":  # entrada
        return primeiro_digito in ("1", "2", "3")
    elif tipo_operacao == "1":  # saida
        return primeiro_digito in ("5", "6", "7")
    return False


def is_cfop_servico(cfop: str) -> bool:
    """Verifica se CFOP e de servico (LC 116/2003, nao usa NCM)."""
    return cfop in CFOPS_SERVICO


def is_cfop_devolucao(cfop: str) -> bool:
    """Verifica se CFOP e de devolucao (gera estorno de compra)."""
    return cfop in CFOPS_DEVOLUCAO


def is_cfop_ativo(cfop: str) -> bool:
    """Verifica se CFOP e de ativo imobilizado."""
    return cfop in CFOPS_ATIVO


def is_cfop_consumo(cfop: str) -> bool:
    """Verifica se CFOP e de material de consumo."""
    return cfop in CFOPS_CONSUMO


def categoria_contabil_cfop(cfop: str) -> str:
    """Retorna a categoria contábil do CFOP para mapeamento de contas.

    Categorias:
    - 'estoque': compra/venda de mercadorias para comercialização
    - 'ativo': compra/venda de bem do ativo imobilizado
    - 'consumo': material de uso e consumo
    - 'servico': prestação/aquisição de serviços (ISS)
    - 'devolucao': devolução de compra/venda (estorno)
    - 'generico': CFOP não classificado em categoria específica
    """
    if not validar_cfop(cfop):
        return "generico"
    if is_cfop_devolucao(cfop):
        return "devolucao"
    if is_cfop_ativo(cfop):
        return "ativo"
    if is_cfop_servico(cfop):
        return "servico"
    if is_cfop_consumo(cfop):
        return "consumo"
    # CFOPs de entrada/saída de mercadorias (estoque)
    primeiro = cfop[0]
    if primeiro in ("1", "5"):
        return "estoque"
    return "generico"


def validar_ncm(ncm: str) -> bool:
    """Valida formato do NCM (8 digitos numericos ou '00' para servicos)."""
    if not ncm:
        return False
    ncm = ncm.strip()
    if ncm == "00":
        return True  # servicos ou produtos isentos
    if len(ncm) != 8 or not ncm.isdigit():
        return False
    return True


def validar_cfop_ncm(cfop: str, ncm: str) -> bool:
    """Valida compatibilidade CFOP x NCM.

    CFOP de servico deve usar NCM '00'.
    CFOP de mercadoria deve usar NCM valido (8 digitos).
    """
    if is_cfop_servico(cfop):
        return ncm == "00"
    # CFOP de mercadoria: NCM deve ser 8 digitos (nao '00')
    return validar_ncm(ncm) and ncm != "00"


def validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ com digito verificador (modulo 11, pesos 2-9).

    Baseado em: Manual de Integracao NF-e v6.004.
    """
    if not cnpj:
        return False
    cnpj = re.sub(r"[^0-9]", "", cnpj)
    if len(cnpj) != 14:
        return False
    if cnpj == cnpj[0] * 14:  # todos digitos iguais
        return False
    # Calculo DV modulo 11
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    dv1 = 0 if resto < 2 else 11 - resto
    if int(cnpj[12]) != dv1:
        return False
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    dv2 = 0 if resto < 2 else 11 - resto
    return int(cnpj[13]) == dv2


def validar_cpf(cpf: str) -> bool:
    """Valida CPF com digito verificador (modulo 11)."""
    if not cpf:
        return False
    cpf = re.sub(r"[^0-9]", "", cpf)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    dv1 = 0 if resto < 2 else 11 - resto
    if int(cpf[9]) != dv1:
        return False
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    dv2 = 0 if resto < 2 else 11 - resto
    return int(cpf[10]) == dv2


def validar_chave_acesso_dv(chave: str) -> bool:
    """Valida chave de acesso NF-e (44 digitos) com digito verificador modulo 11.

    Baseado em: MOC 7.0 item 2.2.6, Manual do Contribuinte v6.00.
    Pesos: 2, 3, 4, 5, 6, 7, 8, 9 (ciclicos, da direita para esquerda).
    """
    if not chave or not isinstance(chave, str):
        return False
    if not re.fullmatch(r"\d{44}", chave):
        return False
    # Validar UF (primeiros 2 digitos)
    uf = chave[:2]
    if uf not in UFS_VALIDAS:
        return False
    # Validar mes (digitos 4-5, apos UF+ano)
    mes = int(chave[4:6])
    if mes < 1 or mes > 12:
        return False
    # Calcular DV modulo 11
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    for i in range(43):
        # Da direita para esquerda: posicao 43 (ultimo antes do DV) tem peso 2
        soma += int(chave[42 - i]) * pesos[i % 8]
    resto = soma % 11
    dv = 0 if resto < 2 else 11 - resto
    return int(chave[43]) == dv


def validar_protocolo(protocolo: str) -> bool:
    """Valida formato do protocolo de autorizacao (15 a 17 digitos numericos).

    Baseado em: NT 2025.002, MOC 7.0 item 5.1.
    Formato: tipo_autorizador(1) + UF(2) + ano(2) + sequencial(10 ou 12).
    """
    if not protocolo:
        return False
    protocolo = str(protocolo).strip()
    if not protocolo.isdigit():
        return False
    return len(protocolo) in (15, 17)


def validar_cst_icms(cst: str) -> bool:
    """Valida CST do ICMS (Ajuste SINIEF 04/04)."""
    if not cst:
        return False
    return cst.strip() in CSTS_ICMS_VALIDOS


def validar_csosn(csosn: str) -> bool:
    """Valida CSOSN (Simples Nacional)."""
    if not csosn:
        return False
    return csosn.strip() in CSOSN_VALIDOS


def validar_cst_pis_cofins(cst: str) -> bool:
    """Valida CST de PIS/COFINS (Lei 10.637/02, Lei 10.833/03)."""
    if not cst:
        return False
    return cst.strip() in CSTS_PIS_COFINS_VALIDOS


def validar_partida_dobrada(lancamentos: list) -> dict:
    """Valida integridade da partida dobrada (Lei 6.404/76 art. 177).

    Verifica:
    - Cada lancamento tem conta de debito E credito
    - Valor do debito = valor do credito (por lancamento)
    - Nenhum lancamento com valor <= 0
    - Soma total de debitos = soma total de creditos

    Returns:
        dict com 'valido' (bool), 'erros' (list[str]), 'soma_debitos', 'soma_creditos'
    """
    erros = []
    soma_debitos = Decimal("0")
    soma_creditos = Decimal("0")

    for i, lanc in enumerate(lancamentos):
        historico = getattr(lanc, "historico", f"lancamento_{i}")
        valor = Decimal(str(getattr(lanc, "valor", 0)))
        debito = getattr(lanc, "conta_debito_codigo", None)
        credito = getattr(lanc, "conta_credito_codigo", None)
        estornado = getattr(lanc, "estornado", False)

        if estornado:
            continue  # lancamentos estornados nao contam

        if valor <= 0:
            erros.append(f"Lançamento com valor <= 0: {historico}")
            continue

        if not debito:
            erros.append(f"Lançamento sem conta de débito: {historico}")
        if not credito:
            erros.append(f"Lançamento sem conta de crédito: {historico}")

        if debito and credito and valor > 0:
            soma_debitos += valor
            soma_creditos += valor

    if abs(soma_debitos - soma_creditos) > Decimal("0.01"):
        erros.append(
            f"Soma de débitos ({soma_debitos}) != soma de créditos ({soma_creditos})"
        )

    return {
        "valido": len(erros) == 0,
        "erros": erros,
        "soma_debitos": soma_debitos,
        "soma_creditos": soma_creditos,
    }


def validar_valor_total_nfe(valor_total: Decimal, soma_itens: Decimal,
                            valor_frete: Decimal = None,
                            valor_seguro: Decimal = None,
                            valor_outros: Decimal = None,
                            valor_desconto: Decimal = None) -> bool:
    """Valida se valor total da NF-e bate com soma dos itens + acrescimos - descontos.

    Baseado em: Manual de Integracao NF-e - validacao de totais.
    vNF = soma(vProd) + vFrete + vSeg + vOutro - vDesc
    """
    if not isinstance(valor_total, Decimal):
        valor_total = Decimal(str(valor_total))
    if not isinstance(soma_itens, Decimal):
        soma_itens = Decimal(str(soma_itens))

    adicionais = [valor_frete, valor_seguro, valor_outros, valor_desconto]
    if valor_total < 0 or soma_itens < 0 or any(
        valor is not None and Decimal(str(valor)) < 0 for valor in adicionais
    ):
        return False

    esperado = soma_itens
    if valor_frete:
        esperado += Decimal(str(valor_frete))
    if valor_seguro:
        esperado += Decimal(str(valor_seguro))
    if valor_outros:
        esperado += Decimal(str(valor_outros))
    if valor_desconto:
        esperado -= Decimal(str(valor_desconto))

    return abs(valor_total - esperado) <= Decimal("0.01")


def get_aliquota_ibscbs(ano: int) -> dict:
    """Retorna a parametrização de IBS/CBS verificada para o ano informado.

    Anos sem fonte vigente cadastrada retornam ``parametrizacao_pendente``
    para impedir cálculo silencioso com alíquota inventada.
    """
    return ALIQUOTAS_IBS_CBS.get(
        ano,
        {
            "cbs": None,
            "ibs": None,
            "fase": "parametrizacao_pendente",
            "recolher": None,
            "fonte": None,
        },
    )


def validar_data_emissao(data_emissao: date, data_referencia: date = None) -> bool:
    """Valida se data de emissao e razoavel (nao futura, nao anterior a 1950)."""
    if not data_emissao:
        return False
    ref = data_referencia or date.today()
    if data_emissao > ref:
        return False  # data futura
    if data_emissao.year < 1950:
        return False
    return True


def validar_periodo_ecd(data_inicio: date, data_fim: date) -> tuple[bool, str]:
    """Valida período para exportação ECD (IN RFB nº 2.003/2021).

    Returns:
        (valido, mensagem_erro)
    """
    if not data_inicio or not data_fim:
        return False, "Data inicial e final sao obrigatorias"
    if data_inicio > data_fim:
        return False, "Data inicial nao pode ser posterior a data final"
    dias = (data_fim - data_inicio).days
    if dias > 366:
        return False, "Periodo nao pode exceder 366 dias (1 ano calendario)"
    if dias < 0:
        return False, "Periodo invalido"
    return True, ""


def calcular_prazo_entrega_ecd(ano_calendario: int) -> date:
    """Calcula prazo de entrega da ECD (IN RFB nº 2.003/2021).

    Prazo: último dia útil de junho do ano seguinte ao calendário.
    Baseado no art. 5º da IN RFB nº 2.003/2021 e no Manual ECD Leiaute 9
    publicado pelo SPED em janeiro de 2026.
    """
    from datetime import date as date_cls, timedelta
    # Junho do ano seguinte
    ano_entrega = ano_calendario + 1
    # Último dia de junho
    ultimo = date_cls(ano_entrega, 6, 30)
    # Se for sabado (5) ou domingo (6), volta para sexta
    while ultimo.weekday() > 4:
        ultimo -= timedelta(days=1)
    return ultimo


def validar_obrigatoriedade_ecd(regime_tributario: str, faturamento_anual: float) -> bool:
    """Verifica se empresa e obrigatoria a ECD (IN RFB 2.003/2021).

    Obrigatorias:
    - Lucro real
    - Lucro presumido com faturamento > R$ 3.600.000/ano
    """
    if regime_tributario == "lucro_real":
        return True
    if regime_tributario == "lucro_presumido" and faturamento_anual > 3_600_000:
        return True
    return False


def validar_prazo_manifestacao(
    data_emissao: date,
    data_manifestacao: date,
    tipo_evento: str = "confirmacao_operacao",
) -> bool:
    """Valida o prazo do evento de manifestação do destinatário.

    Ciência da Emissão tem prazo de até 10 dias. Confirmação, Desconhecimento
    e Operação não Realizada podem ter prazo de até 180 dias, observadas as
    hipóteses específicas do Ajuste SINIEF 07/2005 e do Ajuste SINIEF 44/2020.
    """
    if not data_emissao or not data_manifestacao:
        return False
    limites = {
        "ciencia_emissao": 10,
        "confirmacao_operacao": 180,
        "desconhecimento_operacao": 180,
        "operacao_nao_realizada": 180,
    }
    limite = limites.get(tipo_evento)
    if limite is None:
        return False
    diff = (data_manifestacao - data_emissao).days
    return 0 <= diff <= limite


def mascara_cnpj(cnpj: str) -> str:
    """Mascara CNPJ para logs: 12.345.678/****-** (LGPD art. 5)."""
    if not cnpj:
        return ""
    cnpj = re.sub(r"[^0-9]", "", cnpj)
    if len(cnpj) != 14:
        return cnpj[:8] + "****"
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/****-**"


def mascara_chave(chave: str) -> str:
    """Mascara chave de acesso para logs: primeiros 20 chars + ..."""
    if not chave:
        return ""
    if len(chave) <= 20:
        return chave + "..."
    return chave[:20] + "..."
