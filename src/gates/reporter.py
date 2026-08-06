"""Reporter para gates adaptativos.

Gera relatório com score, veredito, controles aplicáveis/pulados/falhando,
e alertas de regulatory drift.
"""
from typing import Optional
from .engine import GateReport, ProjectContext, Environment, CheckResult, Severity
from .registry import regulatory_drift_report


def format_report(report: GateReport, include_drift: bool = True) -> str:
    """Formata relatório do gate em texto estruturado."""
    ctx = report.context
    lines = []
    lines.append(f"# Gate {report.gate_name}")
    lines.append(f"")
    lines.append(f"## Contexto detectado")
    lines.append(f"- Tipo do sistema: {ctx.system_type}")
    lines.append(f"- Ambiente: {ctx.environment.value}")
    lines.append(f"- Período regulatório: {ctx.regulatory_period}")
    lines.append(f"- Handles NF-e: {ctx.handles_nfe}")
    lines.append(f"- Handles ECD: {ctx.handles_ecd}")
    lines.append(f"- Handles dados pessoais: {ctx.handles_personal_data}")
    lines.append(f"- Handles pagamentos: {ctx.handles_payments}")
    lines.append(f"- Handles cálculo tributário: {ctx.handles_tax_calculation}")
    lines.append(f"- Handles reconciliação: {ctx.handles_reconciliation}")
    lines.append(f"")
    lines.append(f"## Score")
    lines.append(f"- Score: **{report.score:.1f}/100**")
    lines.append(f"- Threshold ({ctx.environment.value}): {report.threshold:.0f}")
    lines.append(f"- Veredito: **{report.verdict}**")
    lines.append(f"")
    lines.append(f"## Controles aplicáveis ({len(report.applicable)})")
    lines.append(f"")
    lines.append(f"| ID | Controle | Severidade | Risco | Resultado | Detalhes |")
    lines.append(f"|----|----------|------------|-------|-----------|----------|")
    for e in report.applicable:
        c = e.control
        result_str = {CheckResult.PASS: "PASSA", CheckResult.PASS_WITH_ISSUES: "LACUNA",
                      CheckResult.FAIL: "FALHA"}[e.result]
        lines.append(f"| {c.id} | {c.name} | {c.base_severity.value} | {c.risk_type.value} | {result_str} | {e.details[:60]} |")
    lines.append(f"")
    if report.skipped:
        lines.append(f"## Controles não aplicáveis ({len(report.skipped)})")
        lines.append(f"")
        for e in report.skipped:
            lines.append(f"- {e.control.id} ({e.control.name}): {e.details}")
        lines.append(f"")
    if report.failing:
        lines.append(f"## Controles falhando ({len(report.failing)})")
        lines.append(f"")
        for e in report.failing:
            c = e.control
            lines.append(f"- **{c.id} ({c.name})** [{c.base_severity.value}/{c.risk_type.value}]: {e.details}")
            if c.legal_refs:
                for ref in c.legal_refs:
                    lines.append(f"  - Ref: {ref.name} {ref.article} ({ref.url})")
        lines.append(f"")
    if report.issues:
        lines.append(f"## Controles com lacunas ({len(report.issues)})")
        lines.append(f"")
        for e in report.issues:
            c = e.control
            lines.append(f"- {c.id} ({c.name}): {e.details}")
        lines.append(f"")
    if include_drift:
        drift = regulatory_drift_report()
        if drift["expirando_90d"] > 0 or drift["substituida"] > 0:
            lines.append(f"## Alerta de regulatory drift")
            lines.append(f"")
            lines.append(f"- Legislação vigente: {drift['vigente']}/{drift['total']}")
            lines.append(f"- Expirando em <=90 dias: {drift['expirando_90d']}")
            lines.append(f"- Substituída: {drift['substituida']}")
            for alerta in drift["alertas"]:
                lines.append(f"  - {alerta['name']} ({alerta['id']}): {alerta['dias_para_expirar']} dias")
            lines.append(f"")
    lines.append(f"## Pesos aplicados (ambiente: {ctx.environment.value})")
    lines.append(f"")
    lines.append(f"| ID | Peso | Severidade | Risco |")
    lines.append(f"|----|------|------------|-------|")
    for e in report.applicable:
        w = e.control.weight(ctx.environment)
        lines.append(f"| {e.control.id} | {w:.2f} | {e.control.base_severity.value} | {e.control.risk_type.value} |")
    lines.append(f"")
    return "\n".join(lines)


def report_as_dict(report: GateReport, include_drift: bool = True) -> dict:
    """Retorna relatório como dict (para API/JSON)."""
    return {
        "gate": report.gate_name,
        "context": {
            "system_type": report.context.system_type,
            "environment": report.context.environment.value,
            "regulatory_period": report.context.regulatory_period,
            "handles_nfe": report.context.handles_nfe,
            "handles_ecd": report.context.handles_ecd,
            "handles_personal_data": report.context.handles_personal_data,
            "handles_payments": report.context.handles_payments,
            "handles_tax_calculation": report.context.handles_tax_calculation,
            "handles_reconciliation": report.context.handles_reconciliation,
        },
        "score": report.score,
        "threshold": report.threshold,
        "verdict": report.verdict,
        "applicable": len(report.applicable),
        "skipped": len(report.skipped),
        "failing": len(report.failing),
        "issues": len(report.issues),
        "passed": len(report.passed),
        "controls": [
            {
                "id": e.control.id,
                "name": e.control.name,
                "severity": e.control.base_severity.value,
                "risk_type": e.control.risk_type.value,
                "weight": round(e.control.weight(report.context.environment), 2),
                "result": {CheckResult.PASS: "pass", CheckResult.PASS_WITH_ISSUES: "issues",
                           CheckResult.FAIL: "fail", CheckResult.NOT_APPLICABLE: "n/a"}[e.result],
                "details": e.details,
                "legal_refs": [
                    {"name": r.name, "article": r.article, "url": r.url,
                     "vigente": r.is_vigente(report.context.regulatory_period + "-01-01")}
                    for r in e.control.legal_refs
                ],
            }
            for e in report.evaluations
        ],
        "regulatory_drift": regulatory_drift_report() if include_drift else None,
    }
