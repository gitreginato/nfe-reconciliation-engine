"""Testes dos contratos dos gates adaptativos.

Valida que os gates contábil e legislativo têm estrutura adaptativa:
- Fase 1: detecção de contexto (fase, domínio, stack, tamanho)
- Fase 2: controles com peso e severidade adaptativa
- Fase 3: score composto com threshold por fase
- Fase 4: veredito e recomendações contextuais
- Memória entre execuções
"""
from pathlib import Path


ROOT = Path(__file__).parents[2]


def _read_gate(name: str) -> str:
    path_devin = ROOT / ".devin" / "skills" / name / "SKILL.md"
    if path_devin.exists():
        return path_devin.read_text(encoding="utf-8")
    path_global = Path("/home/vsf/.config/devin/skills") / name / "SKILL.md"
    return path_global.read_text(encoding="utf-8")


# --- Testes do gate contábil ---


def test_contabil_gate_declara_controles_criticos():
    gate = _read_gate("contabil-gate")
    for controle in ("C1.", "C2.", "C3.", "C4.", "C5.", "C6.", "C7.", "C8.", "C9.", "C10.", "C11.", "C12."):
        assert controle in gate
    assert "Lei nº 6.404/1976" in gate
    assert "IN RFB nº 2.003/2021" in gate
    assert "último dia útil de junho" in gate


def test_contabil_gate_tem_estrutura_adaptativa():
    gate = _read_gate("contabil-gate")
    # Fase 1: detecção de contexto
    assert "Fase 1: Detectar contexto" in gate
    assert "MVP" in gate
    assert "homologacao" in gate
    assert "producao" in gate
    assert "domínio" in gate.lower() or "Domínio" in gate
    # Fase 2: pesos e severidade adaptativa
    assert "Fase 2: Aplicar controles" in gate
    assert "peso" in gate
    assert "Multiplicador" in gate
    # Fase 3: score composto
    assert "Fase 3: Calcular score" in gate
    assert "threshold" in gate.lower() or "Threshold" in gate
    assert "PASSA" in gate
    assert "PASSA_COM_LACUNA" in gate
    assert "FALHA" in gate
    # Fase 4: veredito
    assert "Fase 4: Veredito" in gate
    assert "BLOQUEIA" in gate
    assert "recomendações contextuais" in gate.lower() or "Recomendações contextuais" in gate


def test_contabil_gate_tem_memoria_entre_execucoes():
    gate = _read_gate("contabil-gate")
    assert "Memória entre execuções" in gate
    assert "gate-contabil-historico.json" in gate
    assert "resolvida" in gate
    assert "nova" in gate


def test_contabil_gate_controles_tem_peso_e_aplicabilidade():
    gate = _read_gate("contabil-gate")
    # Cada controle deve declarar peso e aplicabilidade por domínio
    for controle in ("C1.", "C2.", "C3.", "C4.", "C5.", "C6.", "C7.", "C8.", "C9.", "C10.", "C11.", "C12."):
        assert "peso" in gate
    assert "Aplica:" in gate
    assert "N/A" in gate or "Não aplica" in gate


# --- Testes do gate legislativo ---


def test_legislativo_gate_declara_fontes_e_veredito():
    gate = _read_gate("legislativo-gate")
    for controle in ("L1.", "L2.", "L3.", "L4.", "L5.", "L6.", "L7.", "L8."):
        assert controle in gate
    assert "PASSA COM LACUNA" in gate
    assert "BLOQUEIA" in gate
    assert "gov.br" in gate
    assert "Lei nº 13.709/2018" in gate


def test_legislativo_gate_tem_estrutura_adaptativa():
    gate = _read_gate("legislativo-gate")
    # Fase 1: detecção de contexto
    assert "Fase 1: Detectar contexto" in gate
    assert "MVP" in gate
    assert "homologacao" in gate
    assert "producao" in gate
    assert "regime tributário" in gate.lower() or "Regime tributário" in gate
    assert "Simples Nacional" in gate
    assert "Lucro Real" in gate
    # Fase 2: pesos e severidade adaptativa
    assert "Fase 2: Aplicar controles" in gate
    assert "peso" in gate
    assert "Multiplicador" in gate
    # Fase 3: score composto
    assert "Fase 3: Calcular score" in gate
    assert "threshold" in gate.lower() or "Threshold" in gate
    # Fase 4: veredito
    assert "Fase 4: Veredito" in gate
    assert "recomendações contextuais" in gate.lower() or "Recomendações contextuais" in gate


def test_legislativo_gate_tem_memoria_entre_execucoes():
    gate = _read_gate("legislativo-gate")
    assert "Memória entre execuções" in gate
    assert "gate-legislativo-historico.json" in gate
    assert "resolvida" in gate
    assert "recorrente" in gate


def test_legislativo_gate_adapta_por_regime_tributario():
    gate = _read_gate("legislativo-gate")
    assert "CSOSN" in gate
    assert "CST" in gate
    assert "DASN" in gate
    assert "ECF" in gate


# --- Testes do contrato ODD e spec SDD (mantidos) ---


def test_contrato_odd_documenta_lacunas_explicitamente():
    contrato = (ROOT / "docs" / "observability-contract.md").read_text(encoding="utf-8")
    assert "nfe.import" in contrato
    assert "reconciliation.run" in contrato
    assert "total_notas" in contrato
    assert "Spans OpenTelemetry" in contrato
    assert "[ ]" in contrato


def test_spec_sdd_tem_criterios_testaveis():
    spec = (ROOT / "docs" / "spec-testes.md").read_text(encoding="utf-8")
    assert "## 2. Critérios de aceitação testáveis" in spec
    assert "tests/unit/test_validadores.py" in spec
    assert "tests/integration/test_cenarios_reais.py" in spec
    assert "contabil-gate" in spec
    assert "legislativo-gate" in spec
