"""Testes unitários diretos das funções _check_* de contabil.py e legislativo.py.

Cada _check_* recebe um ProjectContext e retorna tuple[CheckResult, str].
Estes testes criam diretórios temporários com arquivos .py específicos para
exercitar cada caminho: PASS, PASS_WITH_ISSUES e FAIL.

Notas sobre nomes reais das funções (o briefing usava nomes aproximados):
- contabil.py: _check_ecd (no _check_sped_ecd), _check_tributos (no
  _check_tributos_precisao), _check_rastreabilidade (no _check_custodia)
- legislativo.py: _check_nfe_chave (no _check_nfe_dfe), _check_ecd_prazo
  (no _check_sped_ecd), _check_icms (no _check_icms_ipi_pis_cofins),
  _check_obrigacoes (no _check_obrigacoes_acessorias)
"""
from pathlib import Path

import pytest

from src.gates.engine import CheckResult, Environment, ProjectContext
from src.gates.contabil import (
    _check_partida_dobrada,
    _check_plano_contas,
    _check_cfop,
    _check_ncm,
    _check_cst_csosn,
    _check_ecd,
    _check_reconciliacao,
    _check_tributos,
    _check_estorno,
    _check_rastreabilidade,
    _check_precisao_monetaria,
    _check_periodo_data,
)
from src.gates.legislativo import (
    _check_nfe_chave,
    _check_ecd_prazo,
    _check_reforma_tributaria,
    _check_icms,
    _check_manifestacao,
    _check_lgpd,
    _check_obrigacoes,
    _check_cadeia_evidencia,
)


# --- Helpers ---


def _write(tmp_path: Path, rel: str, content: str) -> Path:
    """Escreve arquivo em tmp_path/rel e retorna o Path."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _ctx(tmp_path: Path, **kwargs) -> ProjectContext:
    """Cria ProjectContext apontando para tmp_path."""
    defaults: dict = {"project_path": str(tmp_path), "environment": Environment.MVP}
    defaults.update(kwargs)
    return ProjectContext(**defaults)


def _empty_src(tmp_path: Path) -> Path:
    """Cria src/ vazio para que _find_python_files não retorne lista vazia."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    return src


# =============================================================================
# contabil.py - 12 checks
# =============================================================================


class TestCheckPartidaDobrada:
    """C1: Lançamentos têm debito, credito e estorno."""

    def test_pass_com_debito_credito_estorno(self, tmp_path):
        _write(tmp_path, "src/contabilidade/gerador.py",
               "conta_debito = '1'\nconta_credito = '2'\nestorno = True\n")
        result, details = _check_partida_dobrada(_ctx(tmp_path))
        assert result == CheckResult.PASS
        assert "dbito" in details or "crdito" in details or "estorno" in details

    def test_pass_with_issues_sem_estorno(self, tmp_path):
        _write(tmp_path, "src/contabilidade/gerador.py",
               "conta_debito = '1'\nconta_credito = '2'\n")
        result, details = _check_partida_dobrada(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "estorno" in details.lower()

    def test_fail_sem_debito_credito(self, tmp_path):
        _write(tmp_path, "src/contabilidade/gerador.py", "x = 1\n")
        result, details = _check_partida_dobrada(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "partida dobrada" in details.lower()


class TestCheckPlanoContas:
    """C2: Plano de contas com hierarquia e natureza."""

    def test_pass_com_hierarquia_natureza(self, tmp_path):
        _write(tmp_path, "src/persistencia/models.py",
               "class PlanoContas: pass\nconta_pai = None\nnatureza = 'ativo'\n")
        result, details = _check_plano_contas(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_hierarquia(self, tmp_path):
        _write(tmp_path, "src/persistencia/models.py",
               "class PlanoContas: pass\n")
        result, details = _check_plano_contas(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "hierarquia" in details.lower() or "natureza" in details.lower()

    def test_fail_sem_plano_contas(self, tmp_path):
        _write(tmp_path, "src/persistencia/models.py", "class Outro: pass\n")
        result, details = _check_plano_contas(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "plano de contas" in details.lower()


class TestCheckCfop:
    """C3: CFOP validado e mapeado para contas."""

    def test_pass_com_validacao_e_mapeamento(self, tmp_path):
        _write(tmp_path, "src/fiscal/validador.py",
               "def validar_cfop(): pass\n# mapeamento ativo e estoque\n")
        result, details = _check_cfop(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_mapeamento(self, tmp_path):
        _write(tmp_path, "src/fiscal/validador.py",
               "def validar_cfop(): pass\n")
        result, details = _check_cfop(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "mapeamento" in details.lower()

    def test_fail_sem_cfop(self, tmp_path):
        _write(tmp_path, "src/fiscal/validador.py", "x = 1\n")
        result, details = _check_cfop(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "cfop" in details.lower()


class TestCheckNcm:
    """C4: NCM validado (8 digitos) com distincao servico/mercadoria."""

    def test_pass_com_ncm_digitos_servico(self, tmp_path):
        _write(tmp_path, "src/fiscal/validador.py",
               "ncm = '12345678'\n# valida 8 digitos\nservico = True\niss = 0\n")
        result, details = _check_ncm(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_servico(self, tmp_path):
        _write(tmp_path, "src/fiscal/validador.py",
               "ncm = '12345678'\n# valida 8 digitos\n")
        result, details = _check_ncm(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "servio" in details.lower() or "incompleta" in details.lower()

    def test_fail_sem_ncm(self, tmp_path):
        _write(tmp_path, "src/fiscal/validador.py", "x = 1\n")
        result, details = _check_ncm(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "ncm" in details.lower()


class TestCheckCstCsosn:
    """C5: CST/CSOSN com allowlist e tratamento de isento."""

    def test_pass_com_csosn_e_isento(self, tmp_path):
        _write(tmp_path, "src/fiscal/mod.py",
               "cst = '01'\ncsosn = '101'\nisento = '40'\n")
        result, details = _check_cst_csosn(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_isento(self, tmp_path):
        _write(tmp_path, "src/fiscal/mod.py",
               "cst = '01'\ncsosn = '101'\n")
        result, details = _check_cst_csosn(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_fail_sem_cst(self, tmp_path):
        _write(tmp_path, "src/fiscal/mod.py", "x = 1\n")
        result, details = _check_cst_csosn(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "cst" in details.lower()


class TestCheckEcd:
    """C6: Registros ECD obrigatorios (0000, I001, I050, I200, I250, I990, 9001, 9999).

    Nota: _check_ecd nao tem caminho FAIL. Se o modulo nao existe ou faltam
    registros, retorna PASS_WITH_ISSUES. Os 3 cenarios testam PASS, lacuna
    com registros faltando, e modulo ausente.
    """

    def test_pass_com_todos_registros(self, tmp_path):
        _write(tmp_path, "src/contabilidade/ecd.py",
               "reg_0000 = True\nreg_I001 = True\nreg_I050 = True\n"
               "reg_I200 = True\nreg_I250 = True\nreg_I990 = True\n"
               "reg_9001 = True\nreg_9999 = True\n")
        result, details = _check_ecd(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_registros_faltando(self, tmp_path):
        _write(tmp_path, "src/contabilidade/ecd.py",
               "reg_0000 = True\nreg_I001 = True\n")
        result, details = _check_ecd(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "faltando" in details.lower()

    def test_pass_with_issues_modulo_ausente(self, tmp_path):
        _write(tmp_path, "src/outro.py", "x = 1\n")
        result, details = _check_ecd(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "ecd" in details.lower()


class TestCheckReconciliacao:
    """C7: Reconciliacao three-way com tolerancias e estados."""

    def test_pass_com_three_way_tolerancia_status(self, tmp_path):
        _write(tmp_path, "src/reconciliacao/motor.py",
               "pedido = True\nrecebimento = True\ntolerancia = 0.01\n"
               "matched = True\ndivergent = False\npending = True\n")
        result, details = _check_reconciliacao(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_tolerancia(self, tmp_path):
        _write(tmp_path, "src/reconciliacao/motor.py",
               "pedido = True\nrecebimento = True\n"
               "matched = True\ndivergent = False\npending = True\n")
        result, details = _check_reconciliacao(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "toler" in details.lower()

    def test_fail_sem_three_way(self, tmp_path):
        _write(tmp_path, "src/reconciliacao/motor.py", "x = 1\n")
        result, details = _check_reconciliacao(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "three-way" in details.lower() or "reconciliao" in details.lower()


class TestCheckTributos:
    """C8: Tributos (ICMS, IPI, PIS, COFINS) com Decimal e IBS/CBS."""

    def test_pass_com_tributos_decimal_ibs(self, tmp_path):
        _write(tmp_path, "src/fiscal/calculo.py",
               "from decimal import Decimal\n"
               "icms = Decimal('0.17')\nipi = Decimal('0.05')\n"
               "pis = Decimal('0.01')\ncofins = Decimal('0.02')\n"
               "ibs = Decimal('0.1')\ncbs = Decimal('0.1')\n")
        result, details = _check_tributos(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_ibs(self, tmp_path):
        _write(tmp_path, "src/fiscal/calculo.py",
               "from decimal import Decimal\n"
               "icms = Decimal('0.17')\nipi = Decimal('0.05')\n"
               "pis = Decimal('0.01')\ncofins = Decimal('0.02')\n")
        result, details = _check_tributos(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "ibs" in details.lower()

    def test_fail_tributos_insuficientes(self, tmp_path):
        _write(tmp_path, "src/fiscal/calculo.py",
               "icms = 0.17\n")
        result, details = _check_tributos(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "incompleto" in details.lower()


class TestCheckEstorno:
    """C9: Estorno cria novo lancamento e referencia original."""

    def test_pass_com_estorno_e_referencia(self, tmp_path):
        _write(tmp_path, "src/contabilidade/gerador.py",
               "def estornar(): pass\nestorno_id = 42\nlancamento_estorno = True\n")
        result, details = _check_estorno(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_referencia(self, tmp_path):
        _write(tmp_path, "src/contabilidade/gerador.py",
               "def estornar(): pass\n")
        result, details = _check_estorno(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "referncia" in details.lower() or "original" in details.lower()

    def test_fail_sem_estorno(self, tmp_path):
        _write(tmp_path, "src/contabilidade/gerador.py", "x = 1\n")
        result, details = _check_estorno(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "estorno" in details.lower()


class TestCheckRastreabilidade:
    """C10: Rastreabilidade com origem, protocolo e chave de acesso."""

    def test_pass_com_origem_protocolo_chave(self, tmp_path):
        _write(tmp_path, "src/persistencia/models.py",
               "origem = 'nfe'\nprotocolo = '123'\nchave_acesso = '44digitos'\n")
        result, details = _check_rastreabilidade(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_protocolo(self, tmp_path):
        _write(tmp_path, "src/persistencia/models.py",
               "origem = 'nfe'\nchave_acesso = '44digitos'\n")
        result, details = _check_rastreabilidade(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "protocolo" in details.lower()

    def test_fail_sem_origem_chave(self, tmp_path):
        _write(tmp_path, "src/persistencia/models.py", "x = 1\n")
        result, details = _check_rastreabilidade(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "rastreabilidade" in details.lower()


class TestCheckPrecisaoMonetaria:
    """C11: Precisao monetaria (Decimal, nao float)."""

    def test_pass_com_decimal_sem_float(self, tmp_path):
        _write(tmp_path, "src/mod.py",
               "from decimal import Decimal\nvalor_total = Decimal('10.00')\n")
        result, details = _check_precisao_monetaria(_ctx(tmp_path, has_decimal=True))
        assert result == CheckResult.PASS

    def test_pass_with_issues_com_float(self, tmp_path):
        _write(tmp_path, "src/mod.py",
               "valor_total = float(10.0)\n")
        result, details = _check_precisao_monetaria(_ctx(tmp_path, has_decimal=True))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "float" in details.lower()

    def test_fail_sem_decimal_no_contexto(self, tmp_path):
        _write(tmp_path, "src/mod.py", "x = 1\n")
        result, details = _check_precisao_monetaria(_ctx(tmp_path, has_decimal=False))
        assert result == CheckResult.FAIL
        assert "decimal" in details.lower()


class TestCheckPeriodoData:
    """C12: Validacao de periodo com data inicio/fim e maximo de 1 ano."""

    def test_pass_com_periodo_e_limite_ano(self, tmp_path):
        _write(tmp_path, "src/contabilidade/ecd.py",
               "data_inicio = '2026-01-01'\ndata_fim = '2026-12-31'\n"
               "# maximo 366 dias\n")
        result, details = _check_periodo_data(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_limite_ano(self, tmp_path):
        _write(tmp_path, "src/contabilidade/ecd.py",
               "data_inicio = '2026-01-01'\ndata_fim = '2026-12-31'\n")
        result, details = _check_periodo_data(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "ano" in details.lower() or "limite" in details.lower()

    def test_fail_sem_validacao_periodo(self, tmp_path):
        _write(tmp_path, "src/contabilidade/ecd.py", "x = 1\n")
        result, details = _check_periodo_data(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "período" in details.lower()


# =============================================================================
# legislativo.py - 8 checks
# =============================================================================


class TestCheckNfeChave:
    """L1: Chave NF-e (44 digitos, DV modulo 11, protocolo)."""

    def test_pass_com_44_modulo11_protocolo(self, tmp_path):
        _write(tmp_path, "src/fiscal/validador.py",
               "chave = 44\ndef modulo_11(): pass\nprotocolo = 15\n")
        result, details = _check_nfe_chave(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_protocolo(self, tmp_path):
        _write(tmp_path, "src/fiscal/validador.py",
               "chave = 44\ndef modulo_11(): pass\n")
        result, details = _check_nfe_chave(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "protocolo" in details.lower()

    def test_fail_sem_validador(self, tmp_path):
        _write(tmp_path, "src/outro.py", "x = 1\n")
        result, details = _check_nfe_chave(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "validador" in details.lower() or "chave" in details.lower()


class TestCheckEcdPrazo:
    """L2: Prazo ECD (ultimo dia util de junho) com periodo validado."""

    def test_pass_com_periodo_e_junho_no_skill(self, tmp_path):
        _write(tmp_path, "src/contabilidade/ecd.py",
               "data_inicio = '2026-01-01'\ndata_fim = '2026-12-31'\n")
        _write(tmp_path, ".devin/skills/legislativo-gate/SKILL.md",
               "# Prazo ECD: ultimo dia util de junho\n")
        result, details = _check_ecd_prazo(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_junho_no_skill(self, tmp_path):
        _write(tmp_path, "src/contabilidade/ecd.py",
               "data_inicio = '2026-01-01'\ndata_fim = '2026-12-31'\n")
        result, details = _check_ecd_prazo(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "junho" in details.lower()

    def test_fail_sem_periodo(self, tmp_path):
        _write(tmp_path, "src/contabilidade/ecd.py", "x = 1\n")
        result, details = _check_ecd_prazo(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "prazo" in details.lower() or "perodo" in details.lower()


class TestCheckReformaTributaria:
    """L3: IBS/CBS com vigencia e aliquota configuravel."""

    def test_pass_com_ibs_vigencia_config(self, tmp_path):
        _write(tmp_path, "src/fiscal/calculo.py",
               "ibs = True\ncbs = True\nvigencia = '2026'\naliquota = 0.1\nsettings\n")
        result, details = _check_reforma_tributaria(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_com_ibs_sem_vigencia(self, tmp_path):
        _write(tmp_path, "src/fiscal/calculo.py",
               "ibs = True\naliquota = 0.1\n")
        result, details = _check_reforma_tributaria(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "vigência" in details.lower()

    def test_fail_sem_ibs(self, tmp_path):
        _write(tmp_path, "src/fiscal/calculo.py", "icms = 0.17\n")
        result, details = _check_reforma_tributaria(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "ibs" in details.lower() or "cbs" in details.lower()


class TestCheckIcms:
    """L4: ICMS com base, aliquota e ST."""

    def test_pass_com_base_aliquota_st(self, tmp_path):
        _write(tmp_path, "src/fiscal/calculo.py",
               "base_calculo = 100.0\naliquota = 0.17\nst = True\nsubstituicao = True\n")
        result, details = _check_icms(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_st(self, tmp_path):
        _write(tmp_path, "src/fiscal/calculo.py",
               "base_calculo = 100.0\naliquota = 0.17\n")
        result, details = _check_icms(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "st" in details.lower()

    def test_fail_sem_base_aliquota(self, tmp_path):
        _write(tmp_path, "src/fiscal/calculo.py", "x = 1\n")
        result, details = _check_icms(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "icms" in details.lower()


class TestCheckManifestacao:
    """L5: Manifestacao do destinatario com ciencia, confirmacao e prazos."""

    def test_pass_com_ciencia_confirmacao_prazo(self, tmp_path):
        _write(tmp_path, "src/importador/manifestacao.py",
               "ciencia = True\nconfirmacao = True\nprazo = 10\n")
        result, details = _check_manifestacao(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_prazo(self, tmp_path):
        _write(tmp_path, "src/importador/manifestacao.py",
               "ciencia = True\nconfirmacao = True\n")
        result, details = _check_manifestacao(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "prazo" in details.lower()

    def test_fail_sem_ciencia_confirmacao(self, tmp_path):
        _write(tmp_path, "src/importador/manifestacao.py", "x = 1\n")
        result, details = _check_manifestacao(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "manifesta" in details.lower()


class TestCheckLgpd:
    """L6: LGPD (mascaramento de dados pessoais).

    Nota: _check_lgpd nao tem caminho FAIL. Os 3 cenarios testam PASS,
    PASS_WITH_ISSUES com CPF sem mascara, e PASS_WITH_ISSUES sem dados
    pessoais.
    """

    def test_pass_com_mascara_e_cpf(self, tmp_path):
        _write(tmp_path, "src/mod.py",
               "cpf = '12345678901'\ndef mascarar(): return '***.***.***-**'\n")
        result, details = _check_lgpd(_ctx(tmp_path))
        assert result == CheckResult.PASS
        assert "mascara" in details.lower()

    def test_pass_with_issues_cpf_sem_mascara(self, tmp_path):
        _write(tmp_path, "src/mod.py", "cpf = '12345678901'\n")
        result, details = _check_lgpd(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "mascara" in details.lower()

    def test_pass_with_issues_sem_dados_pessoais(self, tmp_path):
        _write(tmp_path, "src/mod.py", "x = 1\n")
        result, details = _check_lgpd(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "dados pessoais" in details.lower()


class TestCheckObrigacoes:
    """L7: Obrigacoes acessorias (apuracao mensal por periodo)."""

    def test_pass_com_apuracao_e_periodo(self, tmp_path):
        _write(tmp_path, "src/fiscal/apuracao.py",
               "def apurar(): pass\napuracao = True\nano = 2026\nmes = 1\n")
        result, details = _check_obrigacoes(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_periodo(self, tmp_path):
        _write(tmp_path, "src/fiscal/apuracao.py",
               "def apurar(): pass\napuracao = True\n")
        result, details = _check_obrigacoes(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "período" in details.lower()

    def test_fail_sem_apuracao(self, tmp_path):
        _write(tmp_path, "src/fiscal/apuracao.py", "x = 1\n")
        result, details = _check_obrigacoes(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "obriga" in details.lower() or "apura" in details.lower()


class TestCheckCadeiaEvidencia:
    """L8: Cadeia de evidencia (XML, eventos, protocolo)."""

    def test_pass_com_xml_evento_protocolo(self, tmp_path):
        _write(tmp_path, "src/persistencia/models.py",
               "xml = '<nfe>'\nevento = 'autorizado'\nprotocolo = '12345'\n")
        result, details = _check_cadeia_evidencia(_ctx(tmp_path))
        assert result == CheckResult.PASS

    def test_pass_with_issues_sem_evento(self, tmp_path):
        _write(tmp_path, "src/persistencia/models.py",
               "xml = '<nfe>'\nprotocolo = '12345'\n")
        result, details = _check_cadeia_evidencia(_ctx(tmp_path))
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "evento" in details.lower()

    def test_fail_sem_xml_protocolo(self, tmp_path):
        _write(tmp_path, "src/persistencia/models.py", "x = 1\n")
        result, details = _check_cadeia_evidencia(_ctx(tmp_path))
        assert result == CheckResult.FAIL
        assert "cadeia" in details.lower() or "evidncia" in details.lower()
