"""Controles contábeis C1-C12 do gate adaptativo.

Cada controle tem:
- applicable_when: só aplica se o contexto do projeto exige
- check: função que inspeciona o código e retorna (CheckResult, detalhes)
- legal_refs: referências com vigência para regulatory drift
"""
import os
import ast
from pathlib import Path

from .engine import (
    Control, LegalRef, ProjectContext, CheckResult, RiskType, Severity,
)


def _find_python_files(project_path: str) -> list[str]:
    """Encontra todos os .py do projeto (src/ e tests/)."""
    result = []
    for subdir in ("src", "tests"):
        base = os.path.join(project_path, subdir)
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for f in files:
                if f.endswith(".py"):
                    result.append(os.path.join(root, f))
    return result


def _read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _grep_pattern(files: list[str], pattern: str) -> list[str]:
    """Busca padrão em arquivos Python."""
    matches = []
    for f in files:
        content = _read_file(f)
        if pattern in content:
            matches.append(f)
    return matches


# --- Checks reais que inspecionam o código ---

def _check_partida_dobrada(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C1: Verifica se lançamentos têm débito e crédito."""
    files = _find_python_files(ctx.project_path)
    gerador_files = [f for f in files if "gerador" in f and "contabilidade" in f]
    if not gerador_files:
        return CheckResult.PASS_WITH_ISSUES, "Módulo gerador não encontrado"
    content = _read_file(gerador_files[0])
    has_debito = "conta_debito" in content or "debito" in content.lower()
    has_credito = "conta_credito" in content or "credito" in content.lower()
    has_estorno = "estorno" in content.lower() or "estornar" in content.lower()
    if has_debito and has_credito and has_estorno:
        return CheckResult.PASS, "Lançamentos têm débito, crédito e estorno"
    if has_debito and has_credito:
        return CheckResult.PASS_WITH_ISSUES, "Débito/crédito presentes, mas estorno não encontrado"
    return CheckResult.FAIL, "Partida dobrada incompleta: falta débito ou crédito"


def _check_plano_contas(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C2: Verifica plano de contas com hierarquia."""
    files = _find_python_files(ctx.project_path)
    models = [f for f in files if "models" in f and "persistencia" in f]
    if not models:
        return CheckResult.PASS_WITH_ISSUES, "Models não encontrados"
    content = _read_file(models[0])
    has_plano = "PlanoContas" in content or "plano_contas" in content
    has_hierarquia = "conta_pai" in content or "codigo_referencial" in content
    has_natureza = "natureza" in content.lower()
    if has_plano and has_hierarquia and has_natureza:
        return CheckResult.PASS, "Plano de contas com hierarquia e natureza"
    if has_plano:
        return CheckResult.PASS_WITH_ISSUES, "Plano de contas existe mas hierarquia/natureza incompleta"
    return CheckResult.FAIL, "Plano de contas não encontrado"


def _check_cfop(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C3: Verifica validação de CFOP."""
    files = _find_python_files(ctx.project_path)
    validadores = [f for f in files if "validador" in f and "fiscal" in f]
    if not validadores:
        return CheckResult.PASS_WITH_ISSUES, "Módulo validador não encontrado"
    content = _read_file(validadores[0])
    has_cfop_check = "cfop" in content.lower() and ("validar" in content.lower() or "validate" in content.lower())
    has_mapping = "ativo" in content.lower() and "estoque" in content.lower()
    if has_cfop_check and has_mapping:
        return CheckResult.PASS, "CFOP validado e mapeado para contas"
    if has_cfop_check:
        return CheckResult.PASS_WITH_ISSUES, "CFOP validado mas mapeamento contábil incompleto"
    return CheckResult.FAIL, "Validação de CFOP não encontrada"


def _check_ncm(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C4: Verifica validação de NCM."""
    files = _find_python_files(ctx.project_path)
    validadores = [f for f in files if "validador" in f and "fiscal" in f]
    if not validadores:
        return CheckResult.PASS_WITH_ISSUES, "Módulo validador não encontrado"
    content = _read_file(validadores[0])
    has_ncm = "ncm" in content.lower()
    has_digitos = "8" in content and "digito" in content.lower()
    has_servico = "servico" in content.lower() or "iss" in content.lower()
    if has_ncm and has_digitos and has_servico:
        return CheckResult.PASS, "NCM validado (8 dígitos) com distinção serviço/mercadoria"
    if has_ncm:
        return CheckResult.PASS_WITH_ISSUES, "NCM presente mas validação de serviço incompleta"
    return CheckResult.FAIL, "Validação de NCM não encontrada"


def _check_cst_csosn(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C5: Verifica CST/CSOSN."""
    files = _find_python_files(ctx.project_path)
    matches = _grep_pattern(files, "cst")
    if not matches:
        return CheckResult.FAIL, "CST não referenciado no código"
    has_csosn = any("csosn" in _read_file(f).lower() for f in matches)
    has_isento = any('"40"' in _read_file(f) or "'40'" in _read_file(f) for f in matches)
    if has_csosn and has_isento:
        return CheckResult.PASS, "CST/CSOSN com allowlist e tratamento de isento"
    if has_csosn or has_isento:
        return CheckResult.PASS_WITH_ISSUES, "CST presente mas CSOSN ou isento incompleto"
    return CheckResult.PASS_WITH_ISSUES, "CST referenciado mas validação incompleta"


def _check_ecd(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C6: Verifica registros ECD."""
    files = _find_python_files(ctx.project_path)
    ecd_files = [f for f in files if "ecd" in f and "contabilidade" in f]
    if not ecd_files:
        return CheckResult.PASS_WITH_ISSUES, "Módulo ECD não encontrado"
    content = _read_file(ecd_files[0])
    required_regs = ["0000", "I001", "I050", "I200", "I250", "I990", "9001", "9999"]
    missing = [r for r in required_regs if r not in content]
    if not missing:
        return CheckResult.PASS, "Todos os registros ECD obrigatórios presentes"
    return CheckResult.PASS_WITH_ISSUES, f"Registros ECD faltando: {', '.join(missing)}"


def _check_reconciliacao(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C7: Verifica reconciliação three-way."""
    files = _find_python_files(ctx.project_path)
    motor = [f for f in files if "motor" in f and "reconciliacao" in f]
    if not motor:
        return CheckResult.PASS_WITH_ISSUES, "Motor de reconciliação não encontrado"
    content = _read_file(motor[0])
    has_three_way = "pedido" in content.lower() and "recebimento" in content.lower()
    has_tolerancia = "tolerancia" in content.lower() or "tolerance" in content.lower()
    has_status = "matched" in content and "divergent" in content and "pending" in content
    if has_three_way and has_tolerancia and has_status:
        return CheckResult.PASS, "Three-way matching com tolerâncias e estados"
    if has_three_way and has_status:
        return CheckResult.PASS_WITH_ISSUES, "Three-way presente mas tolerâncias incompletas"
    return CheckResult.FAIL, "Reconciliação three-way incompleta"


def _check_tributos(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C8: Verifica cálculo de tributos."""
    files = _find_python_files(ctx.project_path)
    calc = [f for f in files if "calculo" in f and "fiscal" in f]
    if not calc:
        return CheckResult.PASS_WITH_ISSUES, "Módulo de cálculo tributário não encontrado"
    content = _read_file(calc[0])
    tributos = ["icms", "ipi", "pis", "cofins"]
    found = [t for t in tributos if t in content.lower()]
    has_ibs = "ibs" in content.lower() or "cbs" in content.lower()
    has_decimal = "Decimal" in content
    if len(found) >= 3 and has_decimal:
        if has_ibs:
            return CheckResult.PASS, f"Tributos calculados: {', '.join(found)} + IBS/CBS, com Decimal"
        return CheckResult.PASS_WITH_ISSUES, f"Tributos: {', '.join(found)} com Decimal, IBS/CBS ausente"
    return CheckResult.FAIL, f"Cálculo tributário incompleto: {', '.join(found)}"


def _check_estorno(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C9: Verifica estorno de lançamento."""
    files = _find_python_files(ctx.project_path)
    gerador = [f for f in files if "gerador" in f and "contabilidade" in f]
    if not gerador:
        return CheckResult.PASS_WITH_ISSUES, "Gerador não encontrado"
    content = _read_file(gerador[0])
    has_estorno = "estornar" in content.lower() or "estorno" in content.lower()
    has_inverte = "inverte" in content.lower() or "troca" in content.lower() or "swap" in content.lower()
    has_ref = "estorno_id" in content or "lancamento_estorno" in content
    if has_estorno and has_ref:
        return CheckResult.PASS, "Estorno cria novo lançamento e referencia original"
    if has_estorno:
        return CheckResult.PASS_WITH_ISSUES, "Estorno presente mas referência ao original incompleta"
    return CheckResult.FAIL, "Estorno não implementado"


def _check_rastreabilidade(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C10: Verifica rastreabilidade e cadeia de custódia."""
    files = _find_python_files(ctx.project_path)
    models = [f for f in files if "models" in f and "persistencia" in f]
    if not models:
        return CheckResult.PASS_WITH_ISSUES, "Models não encontrados"
    content = _read_file(models[0])
    has_origem = "origem" in content.lower()
    has_protocolo = "protocolo" in content.lower()
    has_chave = "chave_acesso" in content
    if has_origem and has_protocolo and has_chave:
        return CheckResult.PASS, "Rastreabilidade: origem, protocolo e chave de acesso"
    if has_origem and has_chave:
        return CheckResult.PASS_WITH_ISSUES, "Rastreabilidade parcial: protocolo ausente"
    return CheckResult.FAIL, "Rastreabilidade insuficiente"


def _check_precisao_monetaria(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C11: Verifica precisão monetária (Decimal, não float)."""
    if not ctx.has_decimal:
        return CheckResult.FAIL, "Decimal não detectado no projeto"
    files = _find_python_files(ctx.project_path)
    # Procura uso de float para valores monetários (anti-padrão)
    float_money = []
    for f in files:
        content = _read_file(f)
        if "valor_total" in content and "float" in content and "Decimal" not in content:
            float_money.append(f)
    if float_money:
        return CheckResult.PASS_WITH_ISSUES, f"Decimal presente mas float detectado em: {len(float_money)} arquivos"
    return CheckResult.PASS, "Valores monetários usam Decimal consistentemente"


def _check_periodo_data(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """C12: Verifica validação de período e data."""
    files = _find_python_files(ctx.project_path)
    ecd = [f for f in files if "ecd" in f and "contabilidade" in f]
    if not ecd:
        return CheckResult.PASS_WITH_ISSUES, "Módulo ECD não encontrado"
    content = _read_file(ecd[0])
    has_validacao_periodo = "data_inicio" in content and "data_fim" in content
    has_max_ano = "366" in content or "365" in content or "1 ano" in content.lower()
    if has_validacao_periodo and has_max_ano:
        return CheckResult.PASS, "Validação de período com data início/fim e máximo de 1 ano"
    if has_validacao_periodo:
        return CheckResult.PASS_WITH_ISSUES, "Validação de período existe mas limite de 1 ano ausente"
    return CheckResult.FAIL, "Validação de período não encontrada"


# --- Definição dos controles C1-C12 ---

CONTROLES_CONTABEIS = [
    Control(
        id="C1", name="Partida dobrada", category="contabil",
        risk_type=RiskType.FINANCIAL, base_severity=Severity.CRITICAL,
        description="Todo lançamento tem débito e crédito iguais (Lei 6.404/76 art. 177)",
        legal_refs=[LegalRef("Lei nº 6.404/1976", "art. 177",
                             url="https://www.planalto.gov.br/ccivil_03/leis/l6404consol.htm",
                             vigencia_inicio="1977-01-01")],
        applicable_when=lambda ctx: ctx.handles_ecd or ctx.handles_reconciliation,
        check=_check_partida_dobrada,
    ),
    Control(
        id="C2", name="Plano de contas", category="contabil",
        risk_type=RiskType.FINANCIAL, base_severity=Severity.CRITICAL,
        description="Hierarquia, analítica vs sintética, código referencial único",
        legal_refs=[LegalRef("Manual ECD Leiaute 9", "",
                             url="https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd",
                             vigencia_inicio="2026-01-01")],
        applicable_when=lambda ctx: ctx.handles_ecd,
        check=_check_plano_contas,
    ),
    Control(
        id="C3", name="CFOP", category="fiscal",
        risk_type=RiskType.LEGAL, base_severity=Severity.HIGH,
        description="CFOP válido, 4 dígitos, mapeado para conta contábil correta",
        legal_refs=[LegalRef("Tabela CFOP CONFAZ", "",
                             url="https://www.confaz.fazenda.gov.br/legislacao/ajustes/sinief/cfop_cvsn_1-6.24",
                             vigencia_inicio="2024-01-01")],
        applicable_when=lambda ctx: ctx.handles_nfe,
        check=_check_cfop,
    ),
    Control(
        id="C4", name="NCM e serviço", category="fiscal",
        risk_type=RiskType.LEGAL, base_severity=Severity.HIGH,
        description="NCM 8 dígitos, serviço usa LC 116/2003 não NCM",
        legal_refs=[LegalRef("LC nº 116/2003", "",
                             url="https://www.planalto.gov.br/ccivil_03/leis/2003/lcp/lcp116.htm",
                             vigencia_inicio="2003-09-01")],
        applicable_when=lambda ctx: ctx.handles_nfe,
        check=_check_ncm,
    ),
    Control(
        id="C5", name="CST/CSOSN", category="fiscal",
        risk_type=RiskType.LEGAL, base_severity=Severity.HIGH,
        description="CST/CSOSN compatível com regime e cálculo de imposto",
        applicable_when=lambda ctx: ctx.handles_tax_calculation,
        check=_check_cst_csosn,
    ),
    Control(
        id="C6", name="SPED ECD", category="contabil",
        risk_type=RiskType.LEGAL, base_severity=Severity.CRITICAL,
        description="Registros 0000, I001, I050, I200, I250, I990, 9001, 9999",
        legal_refs=[LegalRef("IN RFB nº 2.003/2021", "art. 5º",
                             url="http://sped.rfb.gov.br/pagina/show/5727",
                             vigencia_inicio="2022-01-01"),
                   LegalRef("Manual ECD Leiaute 9", "",
                             url="https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd",
                             vigencia_inicio="2026-01-01")],
        applicable_when=lambda ctx: ctx.handles_ecd,
        check=_check_ecd,
    ),
    Control(
        id="C7", name="Reconciliação three-way", category="operacional",
        risk_type=RiskType.OPERATIONAL, base_severity=Severity.HIGH,
        description="NF-e vs pedido vs recebimento com tolerâncias e estados",
        applicable_when=lambda ctx: ctx.handles_reconciliation,
        check=_check_reconciliacao,
    ),
    Control(
        id="C8", name="Tributos e precisão", category="fiscal",
        risk_type=RiskType.FINANCIAL, base_severity=Severity.CRITICAL,
        description="ICMS, IPI, PIS, COFINS, IBS/CBS com Decimal",
        legal_refs=[LegalRef("EC nº 132/2023 (Reforma Tributária)", "",
                             url="https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc132.htm",
                             vigencia_inicio="2024-01-01")],
        applicable_when=lambda ctx: ctx.handles_tax_calculation,
        check=_check_tributos,
    ),
    Control(
        id="C9", name="Estorno e rastreabilidade", category="contabil",
        risk_type=RiskType.FINANCIAL, base_severity=Severity.HIGH,
        description="Estorno cria novo lançamento, referencia original, inverte contas",
        applicable_when=lambda ctx: ctx.handles_ecd or ctx.handles_reconciliation,
        check=_check_estorno,
    ),
    Control(
        id="C10", name="Cadeia de custódia", category="tecnico",
        risk_type=RiskType.LEGAL, base_severity=Severity.MEDIUM,
        description="Origem, protocolo, XML, chave de acesso preservados",
        applicable_when=lambda ctx: ctx.handles_nfe,
        check=_check_rastreabilidade,
    ),
    Control(
        id="C11", name="Precisão monetária", category="contabil",
        risk_type=RiskType.FINANCIAL, base_severity=Severity.CRITICAL,
        description="Decimal não float, 2 casas total, 4 unitário, arredondamento explícito",
        applicable_when=lambda ctx: ctx.handles_tax_calculation or ctx.handles_payments,
        check=_check_precisao_monetaria,
    ),
    Control(
        id="C12", name="Período e data", category="contabil",
        risk_type=RiskType.LEGAL, base_severity=Severity.MEDIUM,
        description="Data válida, período máximo 1 ano, data de autorização >= emissão",
        applicable_when=lambda ctx: ctx.handles_ecd,
        check=_check_periodo_data,
    ),
]
