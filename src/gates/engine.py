"""Engine adaptativa para gates de validação.

Substitui checklist estático por sistema que:
1. Detecta contexto do projeto (fiscal, CRUD, pagamento, etc.)
2. Aplica só controles relevantes (applicable_when)
3. Pondera por risco (financeiro, legal, operacional, segurança)
4. Adapta threshold por ambiente (MVP, produção, auditoria)
5. Rastreia vigência legislativa (regulatory drift)
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional
from decimal import Decimal


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskType(str, Enum):
    FINANCIAL = "financial"
    LEGAL = "legal"
    SECURITY = "security"
    OPERATIONAL = "operational"


class Environment(str, Enum):
    MVP = "mvp"
    PRODUCTION = "production"
    AUDIT = "audit"
    DEMO = "demo"


class CheckResult(int, Enum):
    NOT_APPLICABLE = 0
    PASS = 1
    PASS_WITH_ISSUES = 2
    FAIL = 3


# Threshold por ambiente: score mínimo para PASSA
THRESHOLDS = {
    Environment.MVP: 70.0,
    Environment.PRODUCTION: 85.0,
    Environment.AUDIT: 95.0,
    Environment.DEMO: 50.0,
}

# Multiplicador de severidade por ambiente
# Em MVP, MEDIUM/LOW são warning; em auditoria, tudo pesa
SEVERITY_MULTIPLIER = {
    Environment.MVP: {
        Severity.CRITICAL: 1.0,
        Severity.HIGH: 1.0,
        Severity.MEDIUM: 0.5,
        Severity.LOW: 0.3,
    },
    Environment.PRODUCTION: {
        Severity.CRITICAL: 1.0,
        Severity.HIGH: 1.0,
        Severity.MEDIUM: 0.8,
        Severity.LOW: 0.5,
    },
    Environment.AUDIT: {
        Severity.CRITICAL: 1.0,
        Severity.HIGH: 1.0,
        Severity.MEDIUM: 1.0,
        Severity.LOW: 1.0,
    },
    Environment.DEMO: {
        Severity.CRITICAL: 0.7,
        Severity.HIGH: 0.5,
        Severity.MEDIUM: 0.3,
        Severity.LOW: 0.1,
    },
}

RISK_MULTIPLIER = {
    RiskType.FINANCIAL: 1.5,
    RiskType.LEGAL: 1.3,
    RiskType.SECURITY: 1.4,
    RiskType.OPERATIONAL: 1.0,
}


@dataclass
class LegalRef:
    """Referência legal com vigência para regulatory drift."""
    name: str
    article: str = ""
    url: str = ""
    vigencia_inicio: str = ""
    vigencia_fim: str = ""  # vazio = vigente
    fonte: str = ""

    def is_vigente(self, data_referencia: str = "2026-01-01") -> bool:
        if not self.vigencia_inicio:
            return True
        if self.vigencia_inicio > data_referencia:
            return False
        if self.vigencia_fim and self.vigencia_fim < data_referencia:
            return False
        return True


@dataclass
class ProjectContext:
    """Contexto detectado do projeto. Determina quais controles aplicam."""
    system_type: str = "generic"  # fiscal, crud, payment, ecommerce, generic
    handles_nfe: bool = False
    handles_ecd: bool = False
    handles_personal_data: bool = False
    handles_payments: bool = False
    handles_tax_calculation: bool = False
    handles_reconciliation: bool = False
    environment: Environment = Environment.MVP
    regulatory_period: str = "2026"
    # Detectado do codebase
    has_decimal: bool = False
    has_auth: bool = False
    has_encryption_rest: bool = False
    has_xsd_validation: bool = False
    has_digital_signature: bool = False
    # Path do projeto para inspeção
    project_path: str = "."


@dataclass
class Control:
    """Controle adaptativo do gate."""
    id: str
    name: str
    category: str  # contabil, fiscal, legislativo, tecnico
    risk_type: RiskType
    base_severity: Severity
    description: str = ""
    legal_refs: list[LegalRef] = field(default_factory=list)
    applicable_when: Callable[[ProjectContext], bool] = field(default=lambda ctx: True)
    check: Optional[Callable[[ProjectContext], tuple[CheckResult, str]]] = None

    def weight(self, env: Environment) -> float:
        sev_mult = SEVERITY_MULTIPLIER[env][self.base_severity]
        risk_mult = RISK_MULTIPLIER[self.risk_type]
        base = {Severity.CRITICAL: 3.0, Severity.HIGH: 2.0,
                Severity.MEDIUM: 1.0, Severity.LOW: 0.5}[self.base_severity]
        return base * sev_mult * risk_mult

    def is_applicable(self, ctx: ProjectContext) -> bool:
        return self.applicable_when(ctx)

    def legal_refs_vigentes(self, data: str = "2026-01-01") -> list[LegalRef]:
        return [r for r in self.legal_refs if r.is_vigente(data)]

    def has_lapsed_legislation(self, data: str = "2026-01-01") -> bool:
        return any(not r.is_vigente(data) for r in self.legal_refs)


@dataclass
class ControlEvaluation:
    control: Control
    result: CheckResult
    details: str = ""
    lacuna_id: Optional[int] = None

    def weighted_score(self, env: Environment) -> float:
        if self.result == CheckResult.NOT_APPLICABLE:
            return 0.0
        score_map = {CheckResult.PASS: 1.0, CheckResult.PASS_WITH_ISSUES: 0.5, CheckResult.FAIL: 0.0}
        return self.control.weight(env) * score_map[self.result]

    def weighted_max(self, env: Environment) -> float:
        if self.result == CheckResult.NOT_APPLICABLE:
            return 0.0
        return self.control.weight(env)


@dataclass
class GateReport:
    gate_name: str
    context: ProjectContext
    evaluations: list[ControlEvaluation]

    @property
    def threshold(self) -> float:
        return THRESHOLDS[self.context.environment]

    @property
    def score(self) -> float:
        total_max = sum(e.weighted_max(self.context.environment) for e in self.evaluations)
        if total_max == 0:
            return 100.0
        achieved = sum(e.weighted_score(self.context.environment) for e in self.evaluations)
        return round((achieved / total_max) * 100, 2)

    @property
    def verdict(self) -> str:
        failing_critical = any(
            e.result == CheckResult.FAIL and e.control.base_severity == Severity.CRITICAL
            for e in self.evaluations
        )
        if failing_critical:
            return "BLOQUEIA"
        if self.score >= self.threshold:
            has_issues = any(e.result == CheckResult.PASS_WITH_ISSUES for e in self.evaluations)
            return "PASSA COM LACUNAS" if has_issues else "PASSA"
        return "BLOQUEIA"

    @property
    def applicable(self) -> list[ControlEvaluation]:
        return [e for e in self.evaluations if e.result != CheckResult.NOT_APPLICABLE]

    @property
    def skipped(self) -> list[ControlEvaluation]:
        return [e for e in self.evaluations if e.result == CheckResult.NOT_APPLICABLE]

    @property
    def failing(self) -> list[ControlEvaluation]:
        return [e for e in self.evaluations if e.result == CheckResult.FAIL]

    @property
    def issues(self) -> list[ControlEvaluation]:
        return [e for e in self.evaluations if e.result == CheckResult.PASS_WITH_ISSUES]

    @property
    def passed(self) -> list[ControlEvaluation]:
        return [e for e in self.evaluations if e.result == CheckResult.PASS]

    @property
    def lapsed_legislation(self) -> list[Control]:
        return [e.control for e in self.evaluations
                if e.control.has_lapsed_legislation(self.context.regulatory_period + "-01-01")]


class AdaptiveGate:
    """Gate adaptativo que avalia controles com base no contexto."""

    def __init__(self, name: str, controls: list[Control]):
        self.name = name
        self.controls = controls

    def evaluate(self, ctx: ProjectContext) -> GateReport:
        evaluations = []
        for ctrl in self.controls:
            if not ctrl.is_applicable(ctx):
                evaluations.append(ControlEvaluation(
                    control=ctrl, result=CheckResult.NOT_APPLICABLE,
                    details="Não aplicável ao contexto detectado",
                ))
                continue

            if ctrl.check:
                try:
                    result, details = ctrl.check(ctx)
                except Exception as e:
                    result, details = CheckResult.FAIL, f"Erro na verificação: {e}"
            else:
                result, details = CheckResult.PASS_WITH_ISSUES, "Sem verificação automática"

            evaluations.append(ControlEvaluation(
                control=ctrl, result=result, details=details,
            ))

        return GateReport(
            gate_name=self.name,
            context=ctx,
            evaluations=evaluations,
        )


def detect_context(project_path: str = ".", environment: Environment = Environment.MVP) -> ProjectContext:
    """Detecta contexto do projeto inspecionando o codebase."""
    import os
    ctx = ProjectContext(project_path=project_path, environment=environment)

    src_path = os.path.join(project_path, "src")
    if not os.path.isdir(src_path):
        return ctx

    # Detecta módulos
    for root, dirs, files in os.walk(src_path):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                try:
                    content = open(fpath, encoding="utf-8").read()
                except Exception:
                    continue

                if "nfe" in content.lower() or "NF-e" in content or "chave_acesso" in content:
                    ctx.handles_nfe = True
                if "ecd" in content.lower() or "ECD" in content or "I050" in content:
                    ctx.handles_ecd = True
                if "cpf" in content.lower() or "lgpd" in content.lower() or "pessoal" in content.lower():
                    ctx.handles_personal_data = True
                if "payment" in content.lower() or "pagamento" in content.lower():
                    ctx.handles_payments = True
                if "icms" in content.lower() or "ipi" in content.lower() or "cofins" in content.lower():
                    ctx.handles_tax_calculation = True
                if "reconcil" in content.lower() or "three_way" in content.lower():
                    ctx.handles_reconciliation = True
                if "Decimal" in content:
                    ctx.has_decimal = True
                if "auth" in content.lower() or "jwt" in content.lower() or "oauth" in content.lower():
                    ctx.has_auth = True
                if "encrypt" in content.lower() or "fernet" in content.lower() or "aes" in content.lower():
                    ctx.has_encryption_rest = True
                if "xsd" in content.lower() or "xmlschema" in content.lower():
                    ctx.has_xsd_validation = True
                if "signature" in content.lower() or "assinatura" in content.lower():
                    ctx.has_digital_signature = True

    # Determina system_type
    if ctx.handles_nfe and ctx.handles_tax_calculation:
        ctx.system_type = "fiscal"
    elif ctx.handles_payments:
        ctx.system_type = "payment"
    elif ctx.handles_personal_data:
        ctx.system_type = "data"
    else:
        ctx.system_type = "generic"

    return ctx
