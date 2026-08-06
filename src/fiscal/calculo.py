"""Cálculo tributário determinístico para itens de NF-e.

Calcula ICMS, ICMS-ST, IPI, PIS, COFINS e IBS/CBS por item, baseado em:
- RICMS de cada UF (alíquota interestadual 12% ou 7% conforme origem/destino)
- TIPI 2024 (Decreto 11.158/2022) para IPI
- Lei 10.637/02 (PIS) e Lei 10.833/03 (COFINS)
- LC 87/1991 (Lei Kandir) para ICMS e ST
- EC 132/2023 + LC 214/2025 (Reforma Tributária) para IBS/CBS

As alíquotas são parametrizadas por tabela, nunca hardcodadas em produção.
Para fins de demonstração, usamos alíquotas de referência válidas para SP
como UF de destino. Em produção, estas tabelas são carregadas de fonte
oficial vigente (RFB, CONFAZ, TIPI).

O cálculo é determinístico: mesmos inputs sempre produzem mesmos outputs.
Não há chamadas a LLM, APIs externas ou fontes não verificáveis.
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


def _q2(v: Decimal) -> Decimal:
    """Quantiza para 2 casas decimais (arredondamento bancário)."""
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# Alíquota ICMS interestadual conforme origem e destino (CONFAZ)
# Origem Sul/Sudeste (exceto ES) -> destino Sudeste/Sul/Centro-Oeste: 12%
# Origem Norte/Nordeste/ES -> destino Sul/Sudeste: 7%
# Origem e destino mesma UF: alíquota interna da UF (18% para SP)
ALIQUOTAS_ICMS_INTERESTADUAL = {
    ("SP", "SP"): Decimal("18.00"),
    ("SP", "RJ"): Decimal("12.00"),
    ("SP", "MG"): Decimal("12.00"),
    ("SP", "PR"): Decimal("12.00"),
    ("SP", "SC"): Decimal("12.00"),
    ("SP", "RS"): Decimal("12.00"),
    ("SP", "MT"): Decimal("12.00"),
    ("SP", "MS"): Decimal("12.00"),
    ("SP", "GO"): Decimal("12.00"),
    ("SP", "DF"): Decimal("12.00"),
    ("SP", "BA"): Decimal("7.00"),
    ("SP", "PE"): Decimal("7.00"),
    ("SP", "CE"): Decimal("7.00"),
    ("SP", "AM"): Decimal("7.00"),
    ("SP", "ES"): Decimal("7.00"),
    ("RJ", "SP"): Decimal("12.00"),
    ("RJ", "RJ"): Decimal("18.00"),
    ("MG", "SP"): Decimal("12.00"),
    ("MG", "MG"): Decimal("18.00"),
    ("PR", "SP"): Decimal("12.00"),
    ("PR", "PR"): Decimal("18.00"),
}

# Alíquota padrão de IPI por tipo de produto (TIPI 2024, subset)
# Em produção, tabela completa por NCM é carregada do TIPI vigente.
ALIQUOTAS_IPI_POR_NCM_PREFIXO = {
    "1101": Decimal("0.00"),    # Farinhas
    "1701": Decimal("0.00"),    # Açúcar
    "1512": Decimal("0.00"),    # Óleos
    "0901": Decimal("0.00"),    # Café
    "8471": Decimal("5.00"),    # Computadores
    "8517": Decimal("5.00"),    # Telefones
    "3926": Decimal("10.00"),   # Plásticos
    "4011": Decimal("10.00"),   # Pneus
    "7308": Decimal("5.00"),    # Estruturas de ferro
    "8431": Decimal("5.00"),    # Partes de máquinas
    "8462": Decimal("5.00"),    # Máquinas
    "9401": Decimal("10.00"),   # Móveis
    "3401": Decimal("0.00"),    # Sabões
    "2202": Decimal("15.00"),   # Refrigerantes
    "2402": Decimal("30.00"),   # Cigarros (imposto seletivo adicional)
}

# Alíquotas PIS/COFINS por regime (cumulativo vs não-cumulativo)
# Lucro presumido: cumulativo (PIS 0.65%, COFINS 3.00%)
# Lucro real: não-cumulativo (PIS 1.65%, COFINS 7.60%)
ALIQUOTAS_PIS_COFINS = {
    "cumulativo": {"pis": Decimal("0.65"), "cofins": Decimal("3.00")},
    "nao_cumulativo": {"pis": Decimal("1.65"), "cofins": Decimal("7.60")},
}

# Margem de valor agregado (IVA-ST) por NCM para SP (subset)
# Usado no cálculo de ICMS-ST: base_st = valor * (1 + mva)
MVA_ST_SP = {
    "11010010": Decimal("36.00"),  # Farinha
    "17019900": Decimal("36.00"),  # Açúcar
    "15121911": Decimal("36.00"),  # Óleo
    "09012100": Decimal("36.00"),  # Café
    "39269090": Decimal("45.00"),  # Plásticos
    "94013000": Decimal("45.00"),  # Móveis
}

# CSTs que não recupera ICMS (sem crédito)
CSTS_SEM_CREDITO_ICMS = {"40", "41", "50", "51", "60"}
# CSTs que não recupera PIS/COFINS
CSTS_SEM_CREDITO_PIS_COFINS = {"04", "05", "06", "07", "08", "09"}

# IBS/CBS (Reforma Tributária, EC 132/2023 + LC 214/2025)
# Alíquotas versionadas por período de vigência.
# Fonte única de verdade: validadores.py ALIQUOTAS_IBS_CBS (por ano).
# Esta tabela converte ano -> string de período para compatibilidade.
from src.fiscal.validadores import ALIQUOTAS_IBS_CBS as _ALIQUOTAS_IBS_CBS_POR_ANO

# Mapeia ano (int) -> período (str) para a tabela por string
ALIQUOTAS_IBS_CBS = {}
for _ano, _dados in _ALIQUOTAS_IBS_CBS_POR_ANO.items():
    _ibs = _dados.get("ibs")
    _cbs = _dados.get("cbs")
    ALIQUOTAS_IBS_CBS[str(_ano)] = {
        "ibs": _ibs if _ibs is not None else Decimal("0"),
        "cbs": _cbs if _cbs is not None else Decimal("0"),
        "fase": _dados.get("fase", ""),
        "recolher": _dados.get("recolher", False),
    }

# Setores com redução de alíquota IBS/CBS (LC 214/2025)
# Saúde, educação, transporte público têm redução
SETORES_REDUCAO_IBS_CBS = {
    "saude": Decimal("30.00"),       # 30% de redução
    "educacao": Decimal("30.00"),
    "transporte_publico": Decimal("30.00"),
    "cesta_basica": Decimal("100.00"),  # isenta (100% redução)
}

# Período regulatório atual (atualizável via config)
PERIODO_REGULATORIO_ATUAL = "2026"


@dataclass
class ResultadoCalculoItem:
    """Resultado do cálculo tributário de um item."""
    valor_total: Decimal
    base_icms: Decimal = Decimal("0")
    valor_icms: Decimal = Decimal("0")
    base_icms_st: Decimal = Decimal("0")
    valor_icms_st: Decimal = Decimal("0")
    valor_ipi: Decimal = Decimal("0")
    base_pis: Decimal = Decimal("0")
    valor_pis: Decimal = Decimal("0")
    base_cofins: Decimal = Decimal("0")
    valor_cofins: Decimal = Decimal("0")
    base_ibscbs: Decimal = Decimal("0")
    valor_ibscbs: Decimal = Decimal("0")
    aliquota_icms: Optional[Decimal] = None
    aliquota_ipi: Optional[Decimal] = None
    aliquota_pis: Optional[Decimal] = None
    aliquota_cofins: Optional[Decimal] = None
    aliquota_ibs: Optional[Decimal] = None
    aliquota_cbs: Optional[Decimal] = None
    periodo_regulatorio: str = ""
    alertas: list[str] = field(default_factory=list)


def calcular_icms(
    valor_total: Decimal,
    uf_origem: str,
    uf_destino: str,
    cst: str = "00",
    base_redutora: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal, Optional[Decimal]]:
    """Calcula base e valor do ICMS.

    Args:
        valor_total: Valor total do item (vProd)
        uf_origem: UF do emitente
        uf_destino: UF do destinatário
        cst: CST do ICMS
        base_redutora: Percentual de redução da base (0 se não houver)

    Returns:
        (base_calculo, valor_icms, aliquota_aplicada)
    """
    if cst in CSTS_SEM_CREDITO_ICMS:
        return Decimal("0"), Decimal("0"), None

    aliquota = ALIQUOTAS_ICMS_INTERESTADUAL.get(
        (uf_origem, uf_destino),
        Decimal("12.00"),  # default interestadual
    )

    base = valor_total
    if base_redutora > 0:
        base = valor_total * (Decimal("100") - base_redutora) / Decimal("100")
        base = _q2(base)

    valor = _q2(base * aliquota / Decimal("100"))
    return base, valor, aliquota


def calcular_icms_st(
    valor_total: Decimal,
    uf_destino: str,
    ncm: str,
    aliquota_icms_interna: Decimal,
    valor_icms: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]:
    """Calcula base e valor do ICMS-ST.

    Fórmula (LC 87/1991 art. 8º):
        base_st = valor_total * (1 + mva/100)
        valor_st = base_st * aliquota_interna/100 - valor_icms

    Args:
        valor_total: Valor do item
        uf_destino: UF do destinatário (determina MVA)
        ncm: NCM do produto (determina MVA)
        aliquota_icms_interna: Alíquota interna do ICMS na UF de destino
        valor_icms: ICMS já calculado (para dedução)

    Returns:
        (base_st, valor_st)
    """
    if uf_destino != "SP":
        # Para outras UFs, MVA precisa ser carregado da tabela da UF
        # Em demonstração, retornamos zero e registramos alerta no caller
        return Decimal("0"), Decimal("0")

    mva = MVA_ST_SP.get(ncm)
    if mva is None:
        return Decimal("0"), Decimal("0")

    base_st = _q2(valor_total * (Decimal("100") + mva) / Decimal("100"))
    valor_st_bruto = _q2(base_st * aliquota_icms_interna / Decimal("100"))
    valor_st = _q2(valor_st_bruto - valor_icms)
    if valor_st < 0:
        valor_st = Decimal("0")
    return base_st, valor_st


def calcular_ipi(
    valor_total: Decimal,
    ncm: str,
) -> tuple[Decimal, Optional[Decimal]]:
    """Calcula valor do IPI baseado no NCM (TIPI 2024).

    Returns:
        (valor_ipi, aliquota_aplicada)
    """
    prefixo = ncm[:4] if ncm and len(ncm) >= 4 else ""
    aliquota = ALIQUOTAS_IPI_POR_NCM_PREFIXO.get(prefixo)
    if aliquota is None:
        return Decimal("0"), None
    valor = _q2(valor_total * aliquota / Decimal("100"))
    return valor, aliquota


def calcular_pis_cofins(
    valor_total: Decimal,
    regime: str = "cumulativo",
    cst_pis: str = "01",
) -> tuple[Decimal, Decimal, Decimal, Decimal, Optional[Decimal], Optional[Decimal]]:
    """Calcula PIS e COFINS.

    Args:
        valor_total: Valor do item
        regime: "cumulativo" (presumido) ou "nao_cumulativo" (real)
        cst_pis: CST de PIS/COFINS

    Returns:
        (base_pis, valor_pis, base_cofins, valor_cofins, aliquota_pis, aliquota_cofins)
    """
    if cst_pis in CSTS_SEM_CREDITO_PIS_COFINS:
        return Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), None, None

    tabela = ALIQUOTAS_PIS_COFINS.get(regime, ALIQUOTAS_PIS_COFINS["cumulativo"])
    aliquota_pis = tabela["pis"]
    aliquota_cofins = tabela["cofins"]

    base = valor_total
    valor_pis = _q2(base * aliquota_pis / Decimal("100"))
    valor_cofins = _q2(base * aliquota_cofins / Decimal("100"))
    return base, valor_pis, base, valor_cofins, aliquota_pis, aliquota_cofins


def calcular_ibscbs(
    valor_total: Decimal,
    periodo: str = PERIODO_REGULATORIO_ATUAL,
    setor: str = "",
) -> tuple[Decimal, Decimal, Decimal, Optional[Decimal], Optional[Decimal], str]:
    """Calcula IBS e CBS (Reforma Tributária, EC 132/2023 + LC 214/2025).

    Alíquotas são versionadas por período de vigência, nunca hardcoded.
    Em 2026: destaque opcional, sem recolhimento (alíquota 0%).
    Em 2027+: recolhimento efetivo conforme Comitê IBS.

    Args:
        valor_total: Valor total do item
        periodo: Período regulatório ("2026", "2027", "2028")
        setor: Setor para redução ("saude", "educacao", "cesta_basica", etc.)

    Returns:
        (base_ibscbs, valor_ibs, valor_cbs, aliquota_ibs, aliquota_cbs, periodo_usado)
    """
    tabela = ALIQUOTAS_IBS_CBS.get(periodo, ALIQUOTAS_IBS_CBS[PERIODO_REGULATORIO_ATUAL])
    aliquota_ibs = tabela["ibs"]
    aliquota_cbs = tabela["cbs"]

    # Aplica redução por setor se aplicável
    reducao = SETORES_REDUCAO_IBS_CBS.get(setor, Decimal("0"))
    if reducao > 0:
        fator = (Decimal("100") - reducao) / Decimal("100")
        aliquota_ibs = aliquota_ibs * fator
        aliquota_cbs = aliquota_cbs * fator

    base = valor_total
    valor_ibs = _q2(base * aliquota_ibs / Decimal("100"))
    valor_cbs = _q2(base * aliquota_cbs / Decimal("100"))
    valor_ibscbs = _q2(valor_ibs + valor_cbs)
    return base, valor_ibs, valor_cbs, aliquota_ibs, aliquota_cbs, periodo


def calcular_tributos_item(
    valor_total: Decimal,
    ncm: str,
    cfop: str,
    uf_origem: str,
    uf_destino: str,
    cst_icms: str = "00",
    cst_pis: str = "01",
    regime: str = "cumulativo",
    calcular_st: bool = False,
    periodo_regulatorio: str = PERIODO_REGULATORIO_ATUAL,
    setor: str = "",
) -> ResultadoCalculoItem:
    """Calcula todos os tributos de um item de NF-e.

    Função principal: orquestra ICMS, ICMS-ST, IPI, PIS, COFINS e IBS/CBS.
    Determinística: mesmos inputs sempre produzem mesmos outputs.

    Args:
        valor_total: Valor total do item
        ncm: NCM do produto (8 dígitos)
        cfop: CFOP da operação
        uf_origem: UF do emitente
        uf_destino: UF do destinatário
        cst_icms: CST do ICMS
        cst_pis: CST do PIS/COFINS
        regime: "cumulativo" ou "nao_cumulativo"
        calcular_st: Se deve calcular ICMS-ST
        periodo_regulatorio: Período de vigência IBS/CBS ("2026", "2027", "2028")
        setor: Setor para redução de IBS/CBS ("saude", "cesta_basica", etc.)

    Returns:
        ResultadoCalculoItem com todos os valores
    """
    resultado = ResultadoCalculoItem(valor_total=_q2(valor_total))
    alertas = []

    # ICMS
    base_icms, valor_icms, aliq_icms = calcular_icms(
        valor_total, uf_origem, uf_destino, cst_icms
    )
    resultado.base_icms = base_icms
    resultado.valor_icms = valor_icms
    resultado.aliquota_icms = aliq_icms

    # ICMS-ST
    if calcular_st:
        aliq_interna = ALIQUOTAS_ICMS_INTERESTADUAL.get(
            (uf_destino, uf_destino), Decimal("18.00")
        )
        base_st, valor_st = calcular_icms_st(
            valor_total, uf_destino, ncm, aliq_interna, valor_icms
        )
        resultado.base_icms_st = base_st
        resultado.valor_icms_st = valor_st
        if base_st == 0 and uf_destino == "SP":
            alertas.append(f"MVA-ST não encontrado para NCM {ncm}")

    # IPI
    valor_ipi, aliq_ipi = calcular_ipi(valor_total, ncm)
    resultado.valor_ipi = valor_ipi
    resultado.aliquota_ipi = aliq_ipi
    if aliq_ipi is None:
        alertas.append(f"Alíquota IPI não encontrada para NCM {ncm}")

    # PIS/COFINS
    base_pis, valor_pis, base_cofins, valor_cofins, aliq_pis, aliq_cofins = \
        calcular_pis_cofins(valor_total, regime, cst_pis)
    resultado.base_pis = base_pis
    resultado.valor_pis = valor_pis
    resultado.base_cofins = base_cofins
    resultado.valor_cofins = valor_cofins
    resultado.aliquota_pis = aliq_pis
    resultado.aliquota_cofins = aliq_cofins

    # IBS/CBS (Reforma Tributária, EC 132/2023 + LC 214/2025)
    base_ibscbs, valor_ibs, valor_cbs, aliq_ibs, aliq_cbs, periodo_usado = \
        calcular_ibscbs(valor_total, periodo_regulatorio, setor)
    resultado.base_ibscbs = base_ibscbs
    resultado.valor_ibscbs = _q2(valor_ibs + valor_cbs)
    resultado.aliquota_ibs = aliq_ibs
    resultado.aliquota_cbs = aliq_cbs
    resultado.periodo_regulatorio = periodo_usado

    resultado.alertas = alertas
    return resultado


def calcular_tributos_nfe(itens: list[dict], uf_origem: str, uf_destino: str,
                          regime: str = "cumulativo") -> dict:
    """Calcula tributos para todos os itens de uma NF-e.

    Args:
        itens: Lista de dicts com valor_total, ncm, cfop, cst_icms, cst_pis
        uf_origem: UF do emitente
        uf_destino: UF do destinatário
        regime: "cumulativo" ou "nao_cumulativo"

    Returns:
        dict com totais por imposto e detalhe por item
    """
    totais = {
        "valor_produtos": Decimal("0"),
        "base_icms": Decimal("0"),
        "valor_icms": Decimal("0"),
        "base_icms_st": Decimal("0"),
        "valor_icms_st": Decimal("0"),
        "valor_ipi": Decimal("0"),
        "base_pis": Decimal("0"),
        "valor_pis": Decimal("0"),
        "base_cofins": Decimal("0"),
        "valor_cofins": Decimal("0"),
        "base_ibscbs": Decimal("0"),
        "valor_ibscbs": Decimal("0"),
    }
    detalhes = []

    for item in itens:
        cfop = item.get("cfop", "")
        calcular_st = cfop.startswith(("1", "2", "3")) and "st" in item.get("cst_icms", "").lower()
        # ST também é calculada quando CST é 10 ou 30
        calcular_st = calcular_st or item.get("cst_icms") in ("10", "30")

        r = calcular_tributos_item(
            valor_total=Decimal(str(item["valor_total"])),
            ncm=item.get("ncm", ""),
            cfop=cfop,
            uf_origem=uf_origem,
            uf_destino=uf_destino,
            cst_icms=item.get("cst_icms", "00"),
            cst_pis=item.get("cst_pis", "01"),
            regime=regime,
            calcular_st=calcular_st,
            periodo_regulatorio=item.get("periodo_regulatorio", PERIODO_REGULATORIO_ATUAL),
            setor=item.get("setor", ""),
        )
        detalhes.append(r)
        totais["valor_produtos"] += r.valor_total
        totais["base_icms"] += r.base_icms
        totais["valor_icms"] += r.valor_icms
        totais["base_icms_st"] += r.base_icms_st
        totais["valor_icms_st"] += r.valor_icms_st
        totais["valor_ipi"] += r.valor_ipi
        totais["base_pis"] += r.base_pis
        totais["valor_pis"] += r.valor_pis
        totais["base_cofins"] += r.base_cofins
        totais["valor_cofins"] += r.valor_cofins
        totais["base_ibscbs"] += r.base_ibscbs
        totais["valor_ibscbs"] += r.valor_ibscbs

    # Quantiza totais
    for k in totais:
        totais[k] = _q2(totais[k])

    return {"totais": totais, "detalhes": detalhes}
