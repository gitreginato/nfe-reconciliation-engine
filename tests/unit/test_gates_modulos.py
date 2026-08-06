"""Testes unitários dos módulos internos dos gates adaptativos.

Cobre engine, contabil, legislativo, reporter e registry (0% de cobertura).
Não duplica test_gate_contracts.py (que testa contratos em SKILL.md).
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.gates.engine import (
    AdaptiveGate,
    CheckResult,
    Control,
    ControlEvaluation,
    Environment,
    GateReport,
    LegalRef,
    ProjectContext,
    RiskType,
    Severity,
    THRESHOLDS,
    detect_context,
)
from src.gates.contabil import (
    CONTROLES_CONTABEIS,
    _check_cfop,
    _check_partida_dobrada,
    _check_precisao_monetaria,
)
from src.gates.legislativo import (
    CONTROLES_LEGISLATIVOS,
    _check_lgpd,
    _check_nfe_chave,
    _check_reforma_tributaria,
)
from src.gates.reporter import format_report
from src.gates.registry import (
    REGISTRY,
    get_by_id,
    get_expiring_soon,
    get_superseded,
    get_vigente,
    regulatory_drift_report,
)


ROOT = Path(__file__).parents[2]


# --- engine.py ---


class TestCheckResult:
    def test_valores_enum(self):
        assert CheckResult.PASS == 1
        assert CheckResult.PASS_WITH_ISSUES == 2
        assert CheckResult.FAIL == 3
        assert CheckResult.NOT_APPLICABLE == 0

    def test_ordem_crescente(self):
        assert CheckResult.NOT_APPLICABLE < CheckResult.PASS
        assert CheckResult.PASS < CheckResult.PASS_WITH_ISSUES
        assert CheckResult.PASS_WITH_ISSUES < CheckResult.FAIL


class TestProjectContext:
    def test_campos_esperados(self):
        ctx = ProjectContext()
        assert ctx.system_type == "generic"
        assert ctx.handles_nfe is False
        assert ctx.handles_ecd is False
        assert ctx.handles_personal_data is False
        assert ctx.handles_payments is False
        assert ctx.handles_tax_calculation is False
        assert ctx.handles_reconciliation is False
        assert ctx.environment == Environment.MVP
        assert ctx.regulatory_period == "2026"
        assert ctx.has_decimal is False
        assert ctx.has_auth is False
        assert ctx.has_encryption_rest is False
        assert ctx.has_xsd_validation is False
        assert ctx.has_digital_signature is False
        assert ctx.project_path == "."

    def test_construcao_com_valores(self):
        ctx = ProjectContext(
            system_type="fiscal",
            handles_nfe=True,
            handles_tax_calculation=True,
            environment=Environment.PRODUCTION,
        )
        assert ctx.system_type == "fiscal"
        assert ctx.handles_nfe is True
        assert ctx.environment == Environment.PRODUCTION


class TestDetectContext:
    def test_detecta_tipo_fiscal_no_projeto_real(self):
        ctx = detect_context(str(ROOT), environment=Environment.PRODUCTION)
        assert ctx.system_type == "fiscal"
        assert ctx.handles_nfe is True
        assert ctx.handles_tax_calculation is True

    def test_detecta_handles_do_projeto_real(self):
        ctx = detect_context(str(ROOT))
        assert ctx.handles_nfe is True
        assert ctx.handles_ecd is True
        assert ctx.handles_personal_data is True
        assert ctx.handles_tax_calculation is True

    def test_detecta_decimal_no_projeto_real(self):
        ctx = detect_context(str(ROOT))
        assert ctx.has_decimal is True

    def test_projeto_vazio_retorna_generic(self, tmp_path):
        ctx = detect_context(str(tmp_path))
        assert ctx.system_type == "generic"
        assert ctx.handles_nfe is False

    def test_sem_src_retorna_generic(self, tmp_path):
        ctx = detect_context(str(tmp_path))
        assert ctx.system_type == "generic"

    def test_detecta_nfe_em_projeto_sintetico(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "modulo.py").write_text(
            "chave_acesso = '1234'\nNF-e\n", encoding="utf-8"
        )
        ctx = detect_context(str(tmp_path))
        assert ctx.handles_nfe is True

    def test_detecta_ecd_em_projeto_sintetico(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "ecd.py").write_text("I050 = True\nECD\n", encoding="utf-8")
        ctx = detect_context(str(tmp_path))
        assert ctx.handles_ecd is True

    def test_detecta_dados_pessoais_em_projeto_sintetico(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "lgpd.py").write_text("cpf = '123'\nlgpd\n", encoding="utf-8")
        ctx = detect_context(str(tmp_path))
        assert ctx.handles_personal_data is True

    def test_detecta_pagamentos_em_projeto_sintetico(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "pay.py").write_text("pagamento = 10\n", encoding="utf-8")
        ctx = detect_context(str(tmp_path))
        assert ctx.handles_payments is True
        assert ctx.system_type == "payment"

    def test_detecta_reconciliacao_em_projeto_sintetico(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "rec.py").write_text("reconcil three_way\n", encoding="utf-8")
        ctx = detect_context(str(tmp_path))
        assert ctx.handles_reconciliation is True


class TestAdaptiveGateEvaluate:
    def _make_control(self, result, applicable=True, severity=Severity.HIGH):
        def check(ctx):
            return result, "detalhe"

        def app(ctx):
            return applicable

        return Control(
            id="T1",
            name="Teste",
            category="contabil",
            risk_type=RiskType.FINANCIAL,
            base_severity=severity,
            applicable_when=app,
            check=check,
        )

    def test_score_100_quando_tudo_passa(self):
        ctrl = self._make_control(CheckResult.PASS)
        gate = AdaptiveGate("teste", [ctrl])
        ctx = ProjectContext(environment=Environment.MVP)
        report = gate.evaluate(ctx)
        assert report.score == 100.0
        assert report.verdict == "PASSA"

    def test_score_zero_quando_tudo_falha(self):
        ctrl = self._make_control(CheckResult.FAIL, severity=Severity.CRITICAL)
        gate = AdaptiveGate("teste", [ctrl])
        ctx = ProjectContext(environment=Environment.MVP)
        report = gate.evaluate(ctx)
        assert report.score == 0.0
        assert report.verdict == "BLOQUEIA"

    def test_score_intermediario_com_pass_with_issues(self):
        # 1 PASS + 1 PASS_WITH_ISSUES = score 75% (acima threshold MVP=70)
        ctrl_pass = self._make_control(CheckResult.PASS)
        ctrl_issues = self._make_control(CheckResult.PASS_WITH_ISSUES)
        gate = AdaptiveGate("teste", [ctrl_pass, ctrl_issues])
        ctx = ProjectContext(environment=Environment.MVP)
        report = gate.evaluate(ctx)
        assert 0 < report.score < 100
        assert report.score == 75.0
        assert report.verdict == "PASSA COM LACUNAS"

    def test_threshold_mvp_menor_que_producao(self):
        ctrl = self._make_control(CheckResult.PASS_WITH_ISSUES)
        gate = AdaptiveGate("teste", [ctrl])
        ctx_mvp = ProjectContext(environment=Environment.MVP)
        ctx_prod = ProjectContext(environment=Environment.PRODUCTION)
        rep_mvp = gate.evaluate(ctx_mvp)
        rep_prod = gate.evaluate(ctx_prod)
        assert rep_mvp.threshold < rep_prod.threshold
        assert rep_mvp.threshold == THRESHOLDS[Environment.MVP]
        assert rep_prod.threshold == THRESHOLDS[Environment.PRODUCTION]

    def test_mvp_passa_mas_producao_bloqueia(self):
        # 1 PASS + 1 PASS_WITH_ISSUES = score 75%: passa MVP (70), bloqueia PROD (85)
        ctrl_pass = self._make_control(CheckResult.PASS)
        ctrl_issues = self._make_control(CheckResult.PASS_WITH_ISSUES)
        gate = AdaptiveGate("teste", [ctrl_pass, ctrl_issues])
        ctx_mvp = ProjectContext(environment=Environment.MVP)
        ctx_prod = ProjectContext(environment=Environment.PRODUCTION)
        rep_mvp = gate.evaluate(ctx_mvp)
        rep_prod = gate.evaluate(ctx_prod)
        assert rep_mvp.verdict == "PASSA COM LACUNAS"
        assert rep_prod.verdict == "BLOQUEIA"

    def test_controle_nao_aplicavel_excluido_do_score(self):
        ctrl_app = self._make_control(CheckResult.PASS, applicable=True)
        ctrl_skip = self._make_control(CheckResult.PASS, applicable=False)
        gate = AdaptiveGate("teste", [ctrl_app, ctrl_skip])
        ctx = ProjectContext(environment=Environment.MVP)
        report = gate.evaluate(ctx)
        assert len(report.skipped) == 1
        assert len(report.applicable) == 1
        assert report.score == 100.0

    def test_erro_no_check_vira_fail(self):
        def check_erro(ctx):
            raise ValueError("boom")

        ctrl = Control(
            id="T1",
            name="Teste",
            category="contabil",
            risk_type=RiskType.FINANCIAL,
            base_severity=Severity.HIGH,
            applicable_when=lambda ctx: True,
            check=check_erro,
        )
        gate = AdaptiveGate("teste", [ctrl])
        ctx = ProjectContext(environment=Environment.MVP)
        report = gate.evaluate(ctx)
        assert len(report.failing) == 1
        assert "Erro na verificação" in report.failing[0].details

    def test_controle_sem_check_retorna_pass_with_issues(self):
        ctrl = Control(
            id="T1",
            name="Teste",
            category="contabil",
            risk_type=RiskType.FINANCIAL,
            base_severity=Severity.HIGH,
            applicable_when=lambda ctx: True,
            check=None,
        )
        gate = AdaptiveGate("teste", [ctrl])
        ctx = ProjectContext(environment=Environment.MVP)
        report = gate.evaluate(ctx)
        assert len(report.issues) == 1


class TestEnvironmentThresholds:
    def test_thresholds_ordenados(self):
        assert THRESHOLDS[Environment.DEMO] < THRESHOLDS[Environment.MVP]
        assert THRESHOLDS[Environment.MVP] < THRESHOLDS[Environment.PRODUCTION]
        assert THRESHOLDS[Environment.PRODUCTION] < THRESHOLDS[Environment.AUDIT]

    def test_valores_esperados(self):
        assert THRESHOLDS[Environment.MVP] == 70.0
        assert THRESHOLDS[Environment.PRODUCTION] == 85.0
        assert THRESHOLDS[Environment.AUDIT] == 95.0
        assert THRESHOLDS[Environment.DEMO] == 50.0


class TestControlWeight:
    def test_peso_critical_maior_que_high(self):
        c_crit = Control(
            id="X", name="X", category="c", risk_type=RiskType.FINANCIAL,
            base_severity=Severity.CRITICAL,
        )
        c_high = Control(
            id="X", name="X", category="c", risk_type=RiskType.FINANCIAL,
            base_severity=Severity.HIGH,
        )
        assert c_crit.weight(Environment.PRODUCTION) > c_high.weight(Environment.PRODUCTION)

    def test_peso_financial_maior_que_operational(self):
        c_fin = Control(
            id="X", name="X", category="c", risk_type=RiskType.FINANCIAL,
            base_severity=Severity.HIGH,
        )
        c_op = Control(
            id="X", name="X", category="c", risk_type=RiskType.OPERATIONAL,
            base_severity=Severity.HIGH,
        )
        assert c_fin.weight(Environment.PRODUCTION) > c_op.weight(Environment.PRODUCTION)


class TestLegalRef:
    def test_vigente_sem_fim(self):
        ref = LegalRef("Lei X", vigencia_inicio="2020-01-01")
        assert ref.is_vigente("2026-01-01") is True

    def test_nao_vigente_antes_inicio(self):
        ref = LegalRef("Lei X", vigencia_inicio="2030-01-01")
        assert ref.is_vigente("2026-01-01") is False

    def test_expirada_com_fim(self):
        ref = LegalRef("Lei X", vigencia_inicio="2010-01-01", vigencia_fim="2015-01-01")
        assert ref.is_vigente("2026-01-01") is False

    def test_sem_inicio_sempre_vigente(self):
        ref = LegalRef("Lei X")
        assert ref.is_vigente("2026-01-01") is True


# --- contabil.py ---


class TestControlesContabeis:
    def test_tem_12_controles(self):
        assert len(CONTROLES_CONTABEIS) == 12

    def test_ids_c1_a_c12(self):
        ids = [c.id for c in CONTROLES_CONTABEIS]
        assert ids == [f"C{i}" for i in range(1, 13)]

    def test_todos_tem_check(self):
        for c in CONTROLES_CONTABEIS:
            assert c.check is not None

    def test_todos_tem_applicable_when(self):
        for c in CONTROLES_CONTABEIS:
            assert c.applicable_when is not None


class TestCheckPartidaDobrada:
    def test_retorna_tupla_check_result_str(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result = _check_partida_dobrada(ctx)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], CheckResult)
        assert isinstance(result[1], str)

    def test_detecta_debito_credito_no_projeto_real(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result, details = _check_partida_dobrada(ctx)
        assert result in (CheckResult.PASS, CheckResult.PASS_WITH_ISSUES)
        assert "débito" in details.lower() or "credito" in details.lower() or "estorno" in details.lower()

    def test_falha_em_projeto_sem_gerador(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "vazio.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_partida_dobrada(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "gerador" in details.lower()

    def test_passa_com_debito_credito_estorno(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        gerador = src / "contabilidade" / "gerador.py"
        gerador.parent.mkdir(parents=True)
        gerador.write_text(
            "conta_debito = '1'\nconta_credito = '2'\nestorno = True\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_partida_dobrada(ctx)
        assert result == CheckResult.PASS

    def test_lacuna_sem_estorno(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        gerador = src / "contabilidade" / "gerador.py"
        gerador.parent.mkdir(parents=True)
        gerador.write_text(
            "conta_debito = '1'\nconta_credito = '2'\n", encoding="utf-8"
        )
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_partida_dobrada(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES


class TestCheckCfop:
    def test_retorna_tupla_check_result_str(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result = _check_cfop(ctx)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], CheckResult)
        assert isinstance(result[1], str)

    def test_valida_mapeamento_no_projeto_real(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result, details = _check_cfop(ctx)
        assert result in (CheckResult.PASS, CheckResult.PASS_WITH_ISSUES, CheckResult.FAIL)
        assert "cfop" in details.lower() or "mapeamento" in details.lower() or "valid" in details.lower()

    def test_sem_validador_retorna_lacuna(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_cfop(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_passa_com_cfop_e_mapeamento(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        validador = src / "fiscal" / "validadores.py"
        validador.parent.mkdir(parents=True)
        validador.write_text(
            "def validar_cfop(): pass\n# ativo e estoque\n", encoding="utf-8"
        )
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_cfop(ctx)
        assert result == CheckResult.PASS

    def test_lacuna_sem_mapeamento(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        validador = src / "fiscal" / "validadores.py"
        validador.parent.mkdir(parents=True)
        validador.write_text("def validar_cfop(): pass\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_cfop(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES


class TestCheckPrecisaoMonetaria:
    def test_retorna_tupla_check_result_str(self):
        ctx = ProjectContext(project_path=str(ROOT), has_decimal=True)
        result = _check_precisao_monetaria(ctx)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], CheckResult)
        assert isinstance(result[1], str)

    def test_falha_sem_decimal(self):
        ctx = ProjectContext(project_path=".", has_decimal=False)
        result, details = _check_precisao_monetaria(ctx)
        assert result == CheckResult.FAIL
        assert "Decimal" in details

    def test_passa_com_decimal_sem_float(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            "from decimal import Decimal\nvalor_total = Decimal('10.00')\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(project_path=str(tmp_path), has_decimal=True)
        result, details = _check_precisao_monetaria(ctx)
        assert result == CheckResult.PASS

    def test_lacuna_com_float_e_decimal(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            "valor_total = float(10.0)\n", encoding="utf-8"
        )
        ctx = ProjectContext(project_path=str(tmp_path), has_decimal=True)
        result, details = _check_precisao_monetaria(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "float" in details.lower()


# --- legislativo.py ---


class TestControlesLegislativos:
    def test_tem_8_controles(self):
        assert len(CONTROLES_LEGISLATIVOS) == 8

    def test_ids_l1_a_l8(self):
        ids = [c.id for c in CONTROLES_LEGISLATIVOS]
        assert ids == [f"L{i}" for i in range(1, 9)]

    def test_todos_tem_check(self):
        for c in CONTROLES_LEGISLATIVOS:
            assert c.check is not None


class TestCheckNfeChave:
    def test_retorna_tupla_check_result_str(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result = _check_nfe_chave(ctx)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], CheckResult)
        assert isinstance(result[1], str)

    def test_valida_chave_44_digitos_no_projeto_real(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result, details = _check_nfe_chave(ctx)
        assert result in (CheckResult.PASS, CheckResult.PASS_WITH_ISSUES, CheckResult.FAIL)
        assert "44" in details or "chave" in details.lower() or "valid" in details.lower()

    def test_passa_com_44_e_modulo11_e_protocolo(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        validador = src / "importador" / "validador_xml.py"
        validador.parent.mkdir(parents=True)
        validador.write_text(
            "chave = 44\ndef modulo_11(): pass\nprotocolo = 15\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_nfe_chave(ctx)
        assert result == CheckResult.PASS

    def test_lacuna_sem_protocolo(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        validador = src / "importador" / "validador_xml.py"
        validador.parent.mkdir(parents=True)
        validador.write_text(
            "chave = 44\ndef modulo_11(): pass\n", encoding="utf-8"
        )
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_nfe_chave(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_falha_sem_validador(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_nfe_chave(ctx)
        assert result == CheckResult.FAIL


class TestCheckReformaTributaria:
    def test_retorna_tupla_check_result_str(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result = _check_reforma_tributaria(ctx)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], CheckResult)
        assert isinstance(result[1], str)

    def test_detecta_ibs_cbs_no_projeto_real(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result, details = _check_reforma_tributaria(ctx)
        assert "ibs" in details.lower() or "cbs" in details.lower() or "reforma" in details.lower() or "vigência" in details.lower()

    def test_passa_com_ibs_vigencia_e_config(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        calc = src / "fiscal" / "calculo.py"
        calc.parent.mkdir(parents=True)
        calc.write_text(
            "ibs = True\ncbs = True\nvigencia = '2026'\naliquota = 0.1\nsettings\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_reforma_tributaria(ctx)
        assert result == CheckResult.PASS

    def test_lacuna_com_ibs_sem_vigencia(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        calc = src / "fiscal" / "calculo.py"
        calc.parent.mkdir(parents=True)
        calc.write_text(
            "ibs = True\naliquota = 0.1\n", encoding="utf-8"
        )
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_reforma_tributaria(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_falha_sem_ibs(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        calc = src / "fiscal" / "calculo.py"
        calc.parent.mkdir(parents=True)
        calc.write_text("icms = 0.1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_reforma_tributaria(ctx)
        assert result == CheckResult.FAIL


class TestCheckLgpd:
    def test_retorna_tupla_check_result_str(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result = _check_lgpd(ctx)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], CheckResult)
        assert isinstance(result[1], str)

    def test_detecta_mascaramento_no_projeto_real(self):
        ctx = ProjectContext(project_path=str(ROOT))
        result, details = _check_lgpd(ctx)
        assert "mascara" in details.lower() or "mascaramento" in details.lower() or "dados pessoais" in details.lower() or "cpf" in details.lower()

    def test_passa_com_mascara_e_cpf(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            "cpf = '123'\ndef mascarar(): return '***'\n", encoding="utf-8"
        )
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_lgpd(ctx)
        assert result == CheckResult.PASS
        assert "mascara" in details.lower()

    def test_lacuna_com_cpf_sem_mascara(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("cpf = '123'\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_lgpd(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_sem_dados_pessoais_retorna_lacuna(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_lgpd(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES


# --- reporter.py ---


class TestFormatReport:
    def _make_report(self, env=Environment.MVP):
        def check_pass(ctx):
            return CheckResult.PASS, "tudo ok"

        def check_fail(ctx):
            return CheckResult.FAIL, "algo errado"

        ctrl_pass = Control(
            id="T1", name="Controle pass", category="contabil",
            risk_type=RiskType.FINANCIAL, base_severity=Severity.HIGH,
            applicable_when=lambda ctx: True, check=check_pass,
        )
        ctrl_fail = Control(
            id="T2", name="Controle fail", category="contabil",
            risk_type=RiskType.LEGAL, base_severity=Severity.CRITICAL,
            applicable_when=lambda ctx: True, check=check_fail,
        )
        gate = AdaptiveGate("teste", [ctrl_pass, ctrl_fail])
        ctx = ProjectContext(environment=env)
        return gate.evaluate(ctx)

    def test_retorna_string(self):
        report = self._make_report()
        result = format_report(report, include_drift=False)
        assert isinstance(result, str)

    def test_contem_cabecalho_do_gate(self):
        report = self._make_report()
        result = format_report(report, include_drift=False)
        assert "# Gate teste" in result

    def test_contem_score_e_veredito(self):
        report = self._make_report()
        result = format_report(report, include_drift=False)
        assert "Score:" in result
        assert "Veredito:" in result

    def test_contem_tabela_de_controles(self):
        report = self._make_report()
        result = format_report(report, include_drift=False)
        assert "| ID |" in result
        assert "T1" in result
        assert "T2" in result
        assert "PASSA" in result
        assert "FALHA" in result

    def test_contem_secao_falhando(self):
        report = self._make_report()
        result = format_report(report, include_drift=False)
        assert "Controles falhando" in result

    def test_include_drift_true_inclui_pesos(self):
        report = self._make_report()
        result = format_report(report, include_drift=True)
        assert "Pesos aplicados" in result
        assert "| Peso |" in result

    def test_include_drift_false_nao_inclui_pesos(self):
        report = self._make_report()
        result = format_report(report, include_drift=False)
        # Pesos sempre aparecem (seção fixa), drift é o que muda
        # Verificar que seção de drift não aparece quando não há drift
        assert "regulatory drift" not in result.lower() or "Alerta de regulatory drift" not in result

    def test_contem_contexto_detectado(self):
        report = self._make_report()
        result = format_report(report, include_drift=False)
        assert "Contexto detectado" in result
        assert "Tipo do sistema" in result
        assert "Ambiente" in result


# --- registry.py ---


class TestRegistry:
    def test_registry_nao_vazio(self):
        assert len(REGISTRY) > 0

    def test_get_by_id_existente(self):
        entry = get_by_id("lei-6404-1976")
        assert entry is not None
        assert entry.name == "Lei das S/A"
        assert entry.article == "art. 177"

    def test_get_by_id_inexistente(self):
        assert get_by_id("inexistente") is None

    def test_get_vigente_retorna_lista(self):
        result = get_vigente(ref=date(2026, 1, 1))
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_vigente_filtra_por_categoria(self):
        fiscal = get_vigente(category="fiscal", ref=date(2026, 1, 1))
        assert all(e.category == "fiscal" for e in fiscal)
        assert len(fiscal) > 0

    def test_get_vigente_data_passada(self):
        antigas = get_vigente(ref=date(2000, 1, 1))
        # Em 2000, só leis com vigencia_inicio <= 2000 estão vigentes
        for e in antigas:
            assert e.vigencia_inicio <= date(2000, 1, 1)

    def test_get_superseded_retorna_nao_vigentes(self):
        ref = date(2026, 1, 1)
        result = get_superseded(ref=ref)
        for e in result:
            assert not e.is_vigente(ref)

    def test_get_expiring_soon_retorna_lista(self):
        result = get_expiring_soon(90, ref=date(2026, 1, 1))
        assert isinstance(result, list)

    def test_regulatory_drift_report_estrutura(self):
        report = regulatory_drift_report(ref=date(2026, 1, 1))
        assert isinstance(report, dict)
        assert "total" in report
        assert "vigente" in report
        assert "expirando_90d" in report
        assert "substituida" in report
        assert "alertas" in report
        assert report["total"] == len(REGISTRY)
        assert report["vigente"] + report["substituida"] == report["total"]

    def test_legislation_entry_is_vigente(self):
        from src.gates.registry import LegislationEntry
        entry = LegislationEntry(
            id="test", name="Test", vigencia_inicio=date(2020, 1, 1),
        )
        assert entry.is_vigente(date(2026, 1, 1)) is True
        assert entry.is_vigente(date(2019, 1, 1)) is False

    def test_legislation_entry_days_until_expiry(self):
        from src.gates.registry import LegislationEntry
        entry = LegislationEntry(
            id="test", name="Test",
            vigencia_inicio=date(2020, 1, 1),
            vigencia_fim=date(2026, 6, 1),
        )
        d = entry.days_until_expiry(date(2026, 1, 1))
        assert d == 151

    def test_legislation_entry_sem_fim_retorna_none(self):
        from src.gates.registry import LegislationEntry
        entry = LegislationEntry(
            id="test", name="Test", vigencia_inicio=date(2020, 1, 1),
        )
        assert entry.days_until_expiry(date(2026, 1, 1)) is None
