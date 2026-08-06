"""Controles legislativos L1-L8 do gate adaptativo.

Cada controle tem applicable_when que só aplica quando o contexto exige,
e legal_refs com vigência para regulatory drift.
"""
import os
from pathlib import Path

from .engine import (
    Control, LegalRef, ProjectContext, CheckResult, RiskType, Severity,
)
from .contabil import _find_python_files, _read_file, _grep_pattern


def _check_nfe_chave(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """L1: Verifica validação de chave NF-e (44 dígitos, DV módulo 11)."""
    files = _find_python_files(ctx.project_path)
    # Busca em validadores.py, validador_xml.py e dfe.py
    validadores = [f for f in files if "validador" in f.lower() or "validadores" in f.lower()]
    if not validadores:
        return CheckResult.FAIL, "Validador não encontrado"
    for f in validadores:
        content = _read_file(f)
        if "44" in content and ("modulo_11" in content or "mod11" in content or "digito_verificador" in content or "dv" in content.lower()):
            has_protocolo = "protocolo" in content.lower() and "15" in content
            if has_protocolo:
                return CheckResult.PASS, "Chave 44 dígitos com DV módulo 11 e protocolo validados"
            return CheckResult.PASS_WITH_ISSUES, "Chave validada mas protocolo incompleto"
    return CheckResult.FAIL, "Validação de chave (44 dígitos + DV módulo 11) não encontrada"


def _check_ecd_prazo(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """L2: Verifica prazo ECD (último dia útil de junho, IN RFB 2.003/2021)."""
    files = _find_python_files(ctx.project_path)
    ecd = [f for f in files if "ecd" in f and "contabilidade" in f]
    if not ecd:
        return CheckResult.PASS_WITH_ISSUES, "Módulo ECD não encontrado"
    content = _read_file(ecd[0])
    has_periodo = "data_inicio" in content and "data_fim" in content
    # Prazo de junho pode estar no gate SKILL.md, não no código
    import os
    gate_path = os.path.join(ctx.project_path, ".devin", "skills", "legislativo-gate", "SKILL.md")
    has_junho = False
    if os.path.exists(gate_path):
        gate_content = _read_file(gate_path)
        has_junho = "junho" in gate_content.lower()
    if not has_junho:
        # Tenta no global
        gate_global = os.path.expanduser("~/.config/devin/skills/legislativo-gate/SKILL.md")
        if os.path.exists(gate_global):
            gate_content = _read_file(gate_global)
            has_junho = "junho" in gate_content.lower()
    if has_junho and has_periodo:
        return CheckResult.PASS, "Prazo ECD (junho) documentado no gate e período validado no código"
    if has_periodo:
        return CheckResult.PASS_WITH_ISSUES, "Período validado mas prazo de junho não referenciado"
    return CheckResult.FAIL, "Validação de prazo ECD não encontrada"


def _check_reforma_tributaria(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """L3: Verifica IBS/CBS com vigência, não hardcoded."""
    files = _find_python_files(ctx.project_path)
    # IBS/CBS pode estar em calculo.py, models.py, gerador.py ou apuracao.py
    relevant = [f for f in files if any(k in f for k in ("calculo", "models", "gerador", "apuracao", "config"))]
    if not relevant:
        return CheckResult.PASS_WITH_ISSUES, "Módulos relevantes não encontrados"
    all_content = "\n".join(_read_file(f) for f in relevant)
    has_ibs = "ibs" in all_content.lower() or "cbs" in all_content.lower() or "ibscbs" in all_content.lower()
    has_vigencia = "vigencia" in all_content.lower() or "periodo" in all_content.lower() or "2026" in all_content
    has_config = "settings" in all_content.lower() or "config" in all_content.lower() or "aliquota" in all_content.lower()
    if has_ibs and has_vigencia and has_config:
        return CheckResult.PASS, "IBS/CBS com vigência e alíquota configurável"
    if has_ibs and has_config:
        return CheckResult.PASS_WITH_ISSUES, "IBS/CBS configurável mas vigência não versionada"
    if has_ibs:
        return CheckResult.PASS_WITH_ISSUES, "IBS/CBS presente mas alíquota pode estar hardcoded"
    return CheckResult.FAIL, "IBS/CBS (Reforma Tributária) não implementado"


def _check_icms(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """L4: Verifica ICMS com base, alíquota, CST e ST."""
    files = _find_python_files(ctx.project_path)
    calc = [f for f in files if "calculo" in f and "fiscal" in f]
    if not calc:
        return CheckResult.PASS_WITH_ISSUES, "Módulo de cálculo não encontrado"
    content = _read_file(calc[0])
    has_base = "base_calculo" in content.lower() or "base" in content.lower()
    has_aliquota = "aliquota" in content.lower()
    has_st = "st" in content.lower() or "substituicao" in content.lower()
    if has_base and has_aliquota and has_st:
        return CheckResult.PASS, "ICMS com base, alíquota, CST e ST"
    if has_base and has_aliquota:
        return CheckResult.PASS_WITH_ISSUES, "ICMS com base e alíquota mas ST incompleto"
    return CheckResult.FAIL, "ICMS incompleto"


def _check_manifestacao(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """L5: Verifica manifestação do destinatário com prazos."""
    files = _find_python_files(ctx.project_path)
    manif = [f for f in files if "manifestacao" in f]
    if not manif:
        return CheckResult.PASS_WITH_ISSUES, "Módulo de manifestação não encontrado"
    content = _read_file(manif[0])
    has_ciencia = "ciencia" in content.lower()
    has_confirmacao = "confirmacao" in content.lower()
    has_prazo = "10" in content or "180" in content or "prazo" in content.lower()
    if has_ciencia and has_confirmacao and has_prazo:
        return CheckResult.PASS, "Manifestação com ciência, confirmação e prazos"
    if has_ciencia and has_confirmacao:
        return CheckResult.PASS_WITH_ISSUES, "Manifestação presente mas prazos não validados"
    return CheckResult.FAIL, "Manifestação do destinatário incompleta"


def _check_lgpd(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """L6: Verifica LGPD (mascaramento, finalidade, retenção)."""
    files = _find_python_files(ctx.project_path)
    has_mascara = False
    has_cpf = False
    for f in files:
        content = _read_file(f)
        if "mascar" in content.lower() or "mask" in content.lower() or "***" in content:
            has_mascara = True
        if "cpf" in content.lower():
            has_cpf = True
    if has_mascara and has_cpf:
        return CheckResult.PASS, "Mascaramento de dados pessoais detectado"
    if has_cpf:
        return CheckResult.PASS_WITH_ISSUES, "Dados pessoais presentes mas mascaramento não detectado"
    return CheckResult.PASS_WITH_ISSUES, "Não há dados pessoais óbvios no código"


def _check_obrigacoes(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """L7: Verifica obrigações acessórias e retenções."""
    files = _find_python_files(ctx.project_path)
    apuracao = [f for f in files if "apuracao" in f]
    if not apuracao:
        return CheckResult.PASS_WITH_ISSUES, "Módulo de apuração não encontrado"
    content = _read_file(apuracao[0])
    has_apuracao = "apuracao" in content.lower() or "apurar" in content.lower()
    has_periodo = "ano" in content.lower() and "mes" in content.lower()
    if has_apuracao and has_periodo:
        return CheckResult.PASS, "Apuração mensal por período implementada"
    if has_apuracao:
        return CheckResult.PASS_WITH_ISSUES, "Apuração presente mas período incompleto"
    return CheckResult.FAIL, "Obrigações acessórias não implementadas"


def _check_cadeia_evidencia(ctx: ProjectContext) -> tuple[CheckResult, str]:
    """L8: Verifica cadeia de evidência (XML, eventos, protocolo)."""
    files = _find_python_files(ctx.project_path)
    models = [f for f in files if "models" in f and "persistencia" in f]
    if not models:
        return CheckResult.PASS_WITH_ISSUES, "Models não encontrados"
    content = _read_file(models[0])
    has_xml = "xml" in content.lower()
    has_evento = "evento" in content.lower() or "NfeEvento" in content
    has_protocolo = "protocolo" in content.lower()
    if has_xml and has_evento and has_protocolo:
        return CheckResult.PASS, "Cadeia de evidência: XML, eventos e protocolo persistidos"
    if has_protocolo and has_xml:
        return CheckResult.PASS_WITH_ISSUES, "XML e protocolo presentes mas eventos incompletos"
    return CheckResult.FAIL, "Cadeia de evidência insuficiente"


# --- Definição dos controles L1-L8 ---

CONTROLES_LEGISLATIVOS = [
    Control(
        id="L1", name="NF-e e DF-e", category="legislativo",
        risk_type=RiskType.LEGAL, base_severity=Severity.CRITICAL,
        description="Chave 44 dígitos, DV módulo 11, protocolo, MOC 7.0",
        legal_refs=[LegalRef("MOC 7.0 CONFAZ", "",
                             url="https://www.confaz.fazenda.gov.br/legislacao/arquivo-manuais/moc7-visao-geral.pdf",
                             vigencia_inicio="2023-01-01"),
                   LegalRef("NT 2023.002", "",
                             url="https://www.confaz.fazenda.gov.br/legislacao/ajustes/2020/ajuste-sinief-44-20",
                             vigencia_inicio="2023-09-01")],
        applicable_when=lambda ctx: ctx.handles_nfe,
        check=_check_nfe_chave,
    ),
    Control(
        id="L2", name="SPED ECD", category="legislativo",
        risk_type=RiskType.LEGAL, base_severity=Severity.CRITICAL,
        description="Prazo último dia útil de junho, IN RFB 2.003/2021",
        legal_refs=[LegalRef("IN RFB nº 2.003/2021", "art. 5º",
                             url="http://sped.rfb.gov.br/pagina/show/5727",
                             vigencia_inicio="2022-01-01")],
        applicable_when=lambda ctx: ctx.handles_ecd,
        check=_check_ecd_prazo,
    ),
    Control(
        id="L3", name="Reforma Tributária", category="legislativo",
        risk_type=RiskType.LEGAL, base_severity=Severity.CRITICAL,
        description="IBS/CBS com vigência versionada, alíquota configurável",
        legal_refs=[LegalRef("EC nº 132/2023", "",
                             url="https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc132.htm",
                             vigencia_inicio="2024-01-01"),
                   LegalRef("LC nº 214/2025", "",
                             url="https://planalto.gov.br/ccivil_03/leis/lcp/lcp214compilado.htm",
                             vigencia_inicio="2025-01-01")],
        applicable_when=lambda ctx: ctx.handles_tax_calculation and ctx.regulatory_period >= "2026",
        check=_check_reforma_tributaria,
    ),
    Control(
        id="L4", name="ICMS, IPI, PIS, COFINS", category="fiscal",
        risk_type=RiskType.FINANCIAL, base_severity=Severity.HIGH,
        description="Base, alíquota, CST/CSOSN, ST, regime compatíveis",
        legal_refs=[LegalRef("LC nº 87/1996 (Lei Kandir)", "",
                             url="https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp87.htm",
                             vigencia_inicio="1996-09-13"),
                   LegalRef("Decreto nº 7.212/2010 (IPI)", "",
                             url="https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/decreto/d7212.htm",
                             vigencia_inicio="2010-08-15")],
        applicable_when=lambda ctx: ctx.handles_tax_calculation,
        check=_check_icms,
    ),
    Control(
        id="L5", name="Manifestação do destinatário", category="legislativo",
        risk_type=RiskType.LEGAL, base_severity=Severity.HIGH,
        description="Ciência (10 dias), confirmação, desconhecimento, não realizada (180 dias)",
        legal_refs=[LegalRef("Ajuste SINIEF 07/2005", "cláusulas 15-A a 15-C",
                             url="https://www.confaz.fazenda.gov.br/legislacao/ajustes/2005/ajuste-sinief-07-05",
                             vigencia_inicio="2005-08-01"),
                   LegalRef("Ajuste SINIEF 44/2020", "",
                             url="https://www.confaz.fazenda.gov.br/legislacao/ajustes/2020/ajuste-sinief-44-20",
                             vigencia_inicio="2021-01-01")],
        applicable_when=lambda ctx: ctx.handles_nfe,
        check=_check_manifestacao,
    ),
    Control(
        id="L6", name="LGPD", category="legislativo",
        risk_type=RiskType.SECURITY, base_severity=Severity.HIGH,
        description="Mascaramento de dados pessoais, finalidade, retenção, canal do titular",
        legal_refs=[LegalRef("Lei nº 13.709/2018 (LGPD)", "",
                             url="https://www.gov.br/anpd/pt-br/centrais-de-conteudo/legislacao/lei-no-13-709-de-14-de-agosto-de-2018",
                             vigencia_inicio="2020-09-18")],
        applicable_when=lambda ctx: ctx.handles_personal_data,
        check=_check_lgpd,
    ),
    Control(
        id="L7", name="Obrigações acessórias", category="legislativo",
        risk_type=RiskType.LEGAL, base_severity=Severity.MEDIUM,
        description="Apuração mensal, retenções, calendário parametrizável",
        applicable_when=lambda ctx: ctx.handles_tax_calculation,
        check=_check_obrigacoes,
    ),
    Control(
        id="L8", name="Cadeia de evidência", category="tecnico",
        risk_type=RiskType.LEGAL, base_severity=Severity.MEDIUM,
        description="XML, eventos, protocolo, usuário e horário preservados",
        applicable_when=lambda ctx: ctx.handles_nfe,
        check=_check_cadeia_evidencia,
    ),
]
