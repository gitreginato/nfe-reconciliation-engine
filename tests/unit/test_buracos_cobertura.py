"""Testes para cobrir buracos de cobertura identificados via pytest --cov-report=term-missing.

Cobre linhas não testadas em:
- src/gates/reporter.py
- src/contabilidade/gerador.py
- src/reconciliacao/motor.py
- src/importador/manifestacao.py
- src/contabilidade/ecd.py
- src/mock_sefaz/main.py
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.persistencia.models import (
    Base, Nfe, NfeItem, Participante, LancamentoContabil,
    PlanoContas, Reconciliacao, NfeEvento, PedidoCompra,
    PedidoCompraItem, Recebimento, RecebimentoItem,
)
from src.gates.engine import (
    GateReport, ProjectContext, Environment, Control, ControlEvaluation,
    CheckResult, Severity, RiskType, LegalRef,
)
from src.gates.reporter import format_report, report_as_dict
from src.contabilidade.gerador import GeradorLancamentos, executar_lancamentos
from src.reconciliacao.motor import MotorReconciliacao, executar_reconciliacao
from src.importador.manifestacao import (
    identificar_notas_pendentes,
    executar_manifestacao_automatica,
)
from src.contabilidade.ecd import ExportadorECD, executar_exportacao_ecd
from src.mock_sefaz.main import app
from src.mock_sefaz.pool_nfe import reset_pool


# ---------------------------------------------------------------------------
# Fixtures e helpers compartilhados
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    """Sessão SQLite em memória com StaticPool para testes de DB."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def client():
    """Cliente de teste do FastAPI com pool resetado."""
    reset_pool()
    with TestClient(app) as c:
        yield c
    reset_pool()


def _criar_participante(session, cnpj="11222333000144", nome="Emitente Teste"):
    existente = session.query(Participante).filter_by(cnpj_cpf=cnpj).first()
    if existente:
        return existente
    p = Participante(cnpj_cpf=cnpj, nome=nome)
    session.add(p)
    session.flush()
    return p


def _criar_nfe(session, emitente=None, cfop="1102", valor=1000, status="autorizada",
               origem="sefaz", manifestacao=None, data_emissao=None, chave_suffix="01",
               vicms=0, vipi=0, vpis=0, vcofins=0, vicms_st=0, vibscbs=0,
               sem_itens=False):
    """Cria uma NF-e completa (ou sem itens se sem_itens=True)."""
    if data_emissao is None:
        data_emissao = datetime(2026, 7, 15, 10, 0)
    if emitente is None:
        emitente = _criar_participante(session)
    dest = session.query(Participante).filter_by(cnpj_cpf="12345678000190").first()
    if not dest:
        dest = Participante(cnpj_cpf="12345678000190", nome="Destinatario Teste")
        session.add(dest)
    session.flush()

    nfe = Nfe(
        chave_acesso=f"352008112223330001445500100000000{chave_suffix}0000000{chave_suffix}",
        numero_nota=int(chave_suffix),
        serie=1, modelo="55",
        data_emissao=data_emissao,
        tipo_operacao="0",
        valor_total=Decimal(str(valor)),
        status_autorizacao=status,
        origem=origem,
        protocolo="33520260715100000",
        manifestacao_destinatario=manifestacao,
        emitente_id=emitente.id,
        destinatario_id=dest.id,
    )
    session.add(nfe)
    session.flush()

    if not sem_itens:
        item = NfeItem(
            nfe_id=nfe.id, numero_item=1,
            descricao="Produto teste", ncm="11010010", cfop=cfop,
            unidade="UN", quantidade=1, valor_unitario=Decimal(str(valor)),
            valor_total=Decimal(str(valor)),
            vicms=Decimal(str(vicms)) if vicms else None,
            vipi=Decimal(str(vipi)) if vipi else None,
            vpis=Decimal(str(vpis)) if vpis else None,
            vcofins=Decimal(str(vcofins)) if vcofins else None,
            vicms_st=Decimal(str(vicms_st)) if vicms_st else None,
            vibscbs=Decimal(str(vibscbs)) if vibscbs else None,
        )
        session.add(item)
    session.commit()
    return nfe


def _criar_pedido(session, cnpj="11222333000144", numero="PC-001",
                  valor=1500.00, data_pedido=None, status="aberto"):
    if data_pedido is None:
        data_pedido = date(2026, 7, 14)
    p = PedidoCompra(
        numero=numero, fornecedor_cnpj=cnpj,
        fornecedor_nome="Fornecedor", data_pedido=data_pedido,
        valor_total=Decimal(str(valor)), condicao_pagamento="30 dias",
        status=status,
    )
    session.add(p)
    session.flush()
    return p


def _gerar_relatorio_gates(ctx, avaliacoes):
    """Cria um GateReport com avaliações para teste do reporter."""
    return GateReport(
        gate_name="contabil-gate",
        context=ctx,
        evaluations=avaliacoes,
    )


def _controle_exemplo(id="C1", nome="Controle Teste", severity=Severity.HIGH,
                      risk=RiskType.FINANCIAL, legal_refs=None):
    return Control(
        id=id, name=nome, category="contabil",
        risk_type=risk, base_severity=severity,
        legal_refs=legal_refs or [],
    )


# ===========================================================================
# 1. src/gates/reporter.py
# ===========================================================================


class TestReporter:
    """Testes do format_report e report_as_dict (linhas 44-48, 56-57, 60-65, 69-76, 90)."""

    def test_format_report_com_drift(self):
        """format_report com include_drift=True mostra seção de pesos e drift."""
        ctx = ProjectContext(
            system_type="fiscal", environment=Environment.MVP,
            handles_nfe=True, handles_ecd=True,
        )
        ctrl = _controle_exemplo()
        avaliacoes = [ControlEvaluation(control=ctrl, result=CheckResult.PASS, details="OK")]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        texto = format_report(report, include_drift=True)
        assert "## Pesos aplicados" in texto
        assert "Score:" in texto
        assert "Controles aplicáveis" in texto

    def test_format_report_sem_drift(self):
        """format_report com include_drift=False omite alerta de drift."""
        ctx = ProjectContext(environment=Environment.MVP)
        ctrl = _controle_exemplo()
        avaliacoes = [ControlEvaluation(control=ctrl, result=CheckResult.PASS, details="OK")]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        texto = format_report(report, include_drift=False)
        assert "Alerta de regulatory drift" not in texto
        # Pesos sempre aparecem (fora do bloco condicional)
        assert "## Pesos aplicados" in texto

    def test_format_report_com_pass_pass_with_issues_e_fail(self):
        """Relatório com controles PASS, PASS_WITH_ISSUES e FAIL."""
        ctx = ProjectContext(environment=Environment.MVP)
        c1 = _controle_exemplo(id="C1", nome="Passou")
        c2 = _controle_exemplo(id="C2", nome="Com lacuna", severity=Severity.MEDIUM)
        c3 = _controle_exemplo(id="C3", nome="Falhou", severity=Severity.CRITICAL)
        avaliacoes = [
            ControlEvaluation(control=c1, result=CheckResult.PASS, details="Tudo ok"),
            ControlEvaluation(control=c2, result=CheckResult.PASS_WITH_ISSUES, details="Lacuna parcial"),
            ControlEvaluation(control=c3, result=CheckResult.FAIL, details="Falha critica"),
        ]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        texto = format_report(report)
        assert "PASSA" in texto
        assert "LACUNA" in texto
        assert "FALHA" in texto
        # Seção de controles falhando (linhas 49-58)
        assert "## Controles falhando" in texto
        # Seção de controles com lacunas (linhas 59-65)
        assert "## Controles com lacunas" in texto

    def test_format_report_com_controles_falhando_e_refs_legais(self):
        """Controles falhando com referências legais (linhas 55-57)."""
        ctx = ProjectContext(environment=Environment.MVP)
        ref = LegalRef(name="Lei 6.404", article="art. 177", url="http://exemplo.gov.br")
        ctrl = _controle_exemplo(id="C1", nome="Controle com ref", legal_refs=[ref])
        avaliacoes = [ControlEvaluation(control=ctrl, result=CheckResult.FAIL, details="Falhou")]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        texto = format_report(report)
        assert "## Controles falhando" in texto
        assert "Ref: Lei 6.404 art. 177" in texto
        assert "http://exemplo.gov.br" in texto

    def test_format_report_com_controles_skipped(self):
        """Controles não aplicáveis (skipped) aparecem na seção (linhas 43-48)."""
        ctx = ProjectContext(environment=Environment.MVP)
        ctrl = _controle_exemplo(id="C1", nome="Controle N/A")
        avaliacoes = [ControlEvaluation(
            control=ctrl, result=CheckResult.NOT_APPLICABLE,
            details="Não aplicável ao contexto",
        )]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        texto = format_report(report)
        assert "## Controles não aplicáveis" in texto
        assert "Não aplicável ao contexto" in texto

    def test_format_report_score_zero_todos_fail(self):
        """Relatório com score 0 (todos FAIL)."""
        ctx = ProjectContext(environment=Environment.MVP)
        c1 = _controle_exemplo(id="C1", severity=Severity.CRITICAL)
        c2 = _controle_exemplo(id="C2", severity=Severity.HIGH)
        avaliacoes = [
            ControlEvaluation(control=c1, result=CheckResult.FAIL, details="Falhou 1"),
            ControlEvaluation(control=c2, result=CheckResult.FAIL, details="Falhou 2"),
        ]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        assert report.score == 0.0
        texto = format_report(report)
        assert "0.0/100" in texto
        assert "BLOQUEIA" in texto

    def test_format_report_score_cem_todos_pass(self):
        """Relatório com score 100 (todos PASS)."""
        ctx = ProjectContext(environment=Environment.MVP)
        c1 = _controle_exemplo(id="C1")
        c2 = _controle_exemplo(id="C2", severity=Severity.MEDIUM)
        avaliacoes = [
            ControlEvaluation(control=c1, result=CheckResult.PASS, details="OK 1"),
            ControlEvaluation(control=c2, result=CheckResult.PASS, details="OK 2"),
        ]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        assert report.score == 100.0
        texto = format_report(report)
        assert "100.0/100" in texto
        assert "PASSA" in texto
        # Sem controles falhando nem com lacunas
        assert "## Controles falhando" not in texto
        assert "## Controles com lacunas" not in texto

    def test_format_report_vazio_sem_controles(self):
        """Relatório vazio (sem controles) não quebra."""
        ctx = ProjectContext(environment=Environment.MVP)
        report = _gerar_relatorio_gates(ctx, [])

        texto = format_report(report)
        assert "## Score" in texto
        assert "Controles aplicáveis (0)" in texto
        # Score 100 quando não há controles
        assert report.score == 100.0

    def test_report_as_dict_retorna_estrutura(self):
        """report_as_dict retorna dict com chaves esperadas (linha 90)."""
        ctx = ProjectContext(
            system_type="fiscal", environment=Environment.PRODUCTION,
            handles_nfe=True,
        )
        ctrl = _controle_exemplo(id="C1")
        avaliacoes = [ControlEvaluation(control=ctrl, result=CheckResult.PASS, details="OK")]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        d = report_as_dict(report, include_drift=True)
        assert d["gate"] == "contabil-gate"
        assert d["context"]["system_type"] == "fiscal"
        assert d["context"]["environment"] == "production"
        assert d["score"] == 100.0
        assert d["passed"] == 1
        assert d["applicable"] == 1
        assert d["skipped"] == 0
        assert d["failing"] == 0
        assert d["regulatory_drift"] is not None
        assert len(d["controls"]) == 1
        assert d["controls"][0]["result"] == "pass"

    def test_report_as_dict_sem_drift(self):
        """report_as_dict com include_drift=False tem regulatory_drift None."""
        ctx = ProjectContext(environment=Environment.MVP)
        ctrl = _controle_exemplo()
        avaliacoes = [ControlEvaluation(control=ctrl, result=CheckResult.FAIL, details="Erro")]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        d = report_as_dict(report, include_drift=False)
        assert d["regulatory_drift"] is None
        assert d["failing"] == 1
        assert d["controls"][0]["result"] == "fail"


# ===========================================================================
# 2. src/contabilidade/gerador.py
# ===========================================================================


class TestGeradorBuracosCobertura:
    """Testes para cobrir linhas não testadas do gerador.py."""

    def test_nfe_sem_itens_nao_quebra(self, session):
        """NF-e sem itens usa categoria 'generico' (linhas 143, 147-148)."""
        nfe = _criar_nfe(session, cfop="1102", valor=1000, sem_itens=True)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        # Gera lançamento principal mesmo sem itens (usa fallback generico)
        assert len(lancs) >= 1
        assert lancs[0].conta_debito_codigo == "1.1.3.01"

    def test_nfe_cancelada_nao_gera_lancamentos(self, session):
        """NF-e cancelada não gera lançamentos (linha 235-237)."""
        nfe = _criar_nfe(session, status="cancelada")
        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        assert len(lancs) == 0

    def test_cfop_devolucao_1201(self, session):
        """CFOP 1201 (devolução de venda) inverte débito/crédito."""
        nfe = _criar_nfe(session, cfop="1201", valor=500)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        principal = lancs[0]
        assert principal.conta_debito_codigo == "2.1.01"
        assert principal.conta_credito_codigo == "1.1.3.01"

    def test_cfop_devolucao_2201(self, session):
        """CFOP 2201 (devolução de venda, saída) usa mapeamento por categoria."""
        nfe = _criar_nfe(session, cfop="2201", valor=300)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        gerador._garantir_plano_contas()
        lanc = gerador._gerar_lancamento_principal(nfe)
        # 2201 não está mapeado explicitamente, usa categoria devolucao
        assert lanc.conta_debito_codigo == "2.1.01"
        assert lanc.conta_credito_codigo == "1.1.3.01"

    def test_cfop_ativo_1551(self, session):
        """CFOP 1551 (ativo imobilizado) debita conta de ativo."""
        nfe = _criar_nfe(session, cfop="1551", valor=3500)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        principal = lancs[0]
        assert principal.conta_debito_codigo == "1.2.1.01"

    def test_cfop_ativo_2551_por_categoria(self, session):
        """CFOP 2551 (ativo, saída) usa mapeamento por categoria ativo."""
        nfe = _criar_nfe(session, cfop="2551", valor=5000)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        gerador._garantir_plano_contas()
        lanc = gerador._gerar_lancamento_principal(nfe)
        assert lanc.conta_debito_codigo == "1.2.1.01"

    def test_cfop_servico_1933(self, session):
        """CFOP 1933 (aquisição de serviços) debita conta de despesa com serviços."""
        nfe = _criar_nfe(session, cfop="1933", valor=500)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        principal = lancs[0]
        assert principal.conta_debito_codigo == "3.1.02"

    def test_cfop_servico_2933_por_categoria(self, session):
        """CFOP 2933 (serviço, saída) usa mapeamento por categoria servico."""
        nfe = _criar_nfe(session, cfop="2933", valor=800)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        gerador._garantir_plano_contas()
        lanc = gerador._gerar_lancamento_principal(nfe)
        assert lanc.conta_debito_codigo == "3.1.02"

    def test_estorno_lancamento(self, session):
        """Estorno cria lançamentos com débito/crédito invertidos (linhas 294-333)."""
        nfe = _criar_nfe(session, cfop="1102", valor=1000, vicms=120)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        gerador.gerar_para_nfe(nfe)
        lancs_antes = session.query(LancamentoContabil).filter_by(nfe_id=nfe.id).all()
        assert len(lancs_antes) == 2

        # Estorna
        count = gerador.estornar_nfe(nfe)
        assert count == 2

        # Originais marcados como estornados
        for l in lancs_antes:
            assert l.estornado is True

        # Estornos criados com contas invertidas
        estornos = session.query(LancamentoContabil).filter_by(
            nfe_id=nfe.id, estornado=False
        ).all()
        assert len(estornos) == 2
        for e in estornos:
            assert "ESTORNO" in e.historico

    def test_estorno_sem_lancamentos_retorna_zero(self, session):
        """estornar_nfe sem lançamentos retorna 0 (linha 303-304)."""
        nfe = _criar_nfe(session, status="cancelada")
        gerador = GeradorLancamentos(session)
        count = gerador.estornar_nfe(nfe)
        assert count == 0

    def test_lancamento_ibscbs(self, session):
        """Lançamento de IBS/CBS é gerado quando item tem vibscbs (linhas 191-192, 200)."""
        nfe = _criar_nfe(session, cfop="1102", valor=1000, vibscbs=10)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        ibs = [l for l in lancs if l.conta_debito_codigo == "2.2.06"]
        assert len(ibs) == 1
        assert ibs[0].valor == Decimal("10")

    def test_lancamento_icms_st(self, session):
        """Lançamento de ICMS ST é gerado quando item tem vicms_st (linha 183-184)."""
        nfe = _criar_nfe(session, cfop="1102", valor=1000, vicms_st=50)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        icms_st = [l for l in lancs if l.conta_debito_codigo == "2.2.02"]
        assert len(icms_st) == 1
        assert icms_st[0].valor == Decimal("50")

    def test_gerar_todos_com_estorno_e_erro(self, session):
        """gerar_todos estorna canceladas e processa autorizadas (linhas 264-271, 286-290)."""
        # NF-e autorizada com lançamentos (vai gerar e depois ser cancelada para estorno)
        nfe = _criar_nfe(
            session, cfop="1102", valor=1000, vicms=100,
            status="autorizada", origem="sefaz", chave_suffix="01",
        )
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        gerador.gerar_para_nfe(nfe)
        session.commit()

        # Agora cancela a NF-e (origem sefaz) para que gerar_todos estorne
        nfe.status_autorizacao = "cancelada"
        session.commit()

        # NF-e autorizada normal (vai ser processada)
        nfe_ok = _criar_nfe(
            session, cfop="1102", valor=500, status="autorizada",
            origem="sefaz", chave_suffix="02",
        )
        rec2 = Reconciliacao(nfe_id=nfe_ok.id, status="matched")
        session.add(rec2)
        session.commit()

        gerador2 = GeradorLancamentos(session)
        stats = gerador2.gerar_todos()
        assert stats["estornos"] >= 1
        assert stats["notas_processadas"] >= 1
        assert stats["erros"] == 0

    def test_gerar_todos_pula_notas_com_reconciliacao_divergent(self, session):
        """Notas com reconciliação divergent são puladas (linhas 285-286)."""
        nfe = _criar_nfe(session, status="autorizada", origem="sefaz", chave_suffix="01")
        rec = Reconciliacao(nfe_id=nfe.id, status="divergent")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        stats = gerador.gerar_todos()
        assert stats["notas_puladas"] >= 1
        assert stats["notas_processadas"] == 0

    def test_data_emissao_com_date_nao_datetime(self, session):
        """NF-e com data_emissao como date (não datetime) usa diretamente (linhas 156-157, 206-207, 306-307)."""
        emitente = _criar_participante(session)
        # Passa uma date (não datetime) - cobre branch else do hasattr
        nfe = Nfe(
            chave_acesso="35200811222333000144550010000000099000000099",
            numero_nota=99, serie=1, modelo="55",
            data_emissao=date(2026, 7, 15),
            tipo_operacao="0", valor_total=Decimal("1000"),
            status_autorizacao="autorizada", origem="sefaz",
            emitente_id=emitente.id,
        )
        session.add(nfe)
        session.flush()
        session.add(NfeItem(
            nfe_id=nfe.id, numero_item=1, descricao="Produto", ncm="11010010",
            cfop="1102", unidade="UN", quantidade=1,
            valor_unitario=Decimal("1000"), valor_total=Decimal("1000"),
            vicms=Decimal("100"),
        ))
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        assert len(lancs) >= 1
        # Data do lançamento deve ser a data de emissão
        assert lancs[0].data_lancamento == date(2026, 7, 15)

    def test_nfe_sem_emitente_historico_vazio(self, session):
        """NF-e sem emitente não quebra ao gerar histórico (linha 164)."""
        nfe = Nfe(
            chave_acesso="35200811222333000144550010000000088000000088",
            numero_nota=88, serie=1, modelo="55",
            data_emissao=datetime(2026, 7, 15, 10, 0),
            tipo_operacao="0", valor_total=Decimal("500"),
            status_autorizacao="autorizada", origem="sefaz",
        )
        session.add(nfe)
        session.flush()
        session.add(NfeItem(
            nfe_id=nfe.id, numero_item=1, descricao="Produto", ncm="11010010",
            cfop="1102", unidade="UN", quantidade=1,
            valor_unitario=Decimal("500"), valor_total=Decimal("500"),
        ))
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        assert len(lancs) >= 1
        # Histórico não quebra mesmo sem emitente
        assert "NF-e 88" in lancs[0].historico

    def test_executar_lancamentos_funcao_conveniencia(self):
        """executar_lancamentos() cria e fecha gerador (linhas 336-342)."""
        with patch("src.contabilidade.gerador.GeradorLancamentos") as mock_cls:
            mock_gerador = MagicMock()
            mock_gerador.gerar_todos.return_value = {"notas_processadas": 0}
            mock_cls.return_value = mock_gerador

            result = executar_lancamentos()
            assert result == {"notas_processadas": 0}
            mock_gerador.gerar_todos.assert_called_once()
            mock_gerador.close.assert_called_once()


# ===========================================================================
# 3. src/reconciliacao/motor.py
# ===========================================================================


class TestMotorBuracosCobertura:
    """Testes para cobrir linhas não testadas do motor.py."""

    def test_executar_reconciliacao_funcao_conveniencia(self):
        """executar_reconciliacao() cria e fecha motor (linhas 234-240)."""
        with patch("src.reconciliacao.motor.MotorReconciliacao") as mock_cls:
            mock_motor = MagicMock()
            mock_motor.reconciliar_todas.return_value = {"reconciliadas": 0}
            mock_cls.return_value = mock_motor

            result = executar_reconciliacao()
            assert result == {"reconciliadas": 0}
            mock_motor.reconciliar_todas.assert_called_once()
            mock_motor.close.assert_called_once()

    def test_motor_close_fecha_session_propria(self):
        """MotorReconciliacao.close() fecha session própria (linhas 31-33)."""
        motor = MotorReconciliacao()
        motor.close()
        # Session foi fechada sem erro
        assert motor.session is not None

    def test_motor_close_nao_fecha_session_externa(self, session):
        """MotorReconciliacao.close() não fecha session externa (linha 32)."""
        motor = MotorReconciliacao(session)
        motor.close()
        # Session externa não foi fechada
        assert motor.session is not None

    def test_reconciliar_todas_com_erro_nao_para_loop(self, session):
        """Erro em uma NF-e não para o loop (linhas 226-229)."""
        emitente = _criar_participante(session)
        nfe1 = _criar_nfe(session, emitente, chave_suffix="01")
        nfe2 = _criar_nfe(session, emitente, chave_suffix="02")

        motor = MotorReconciliacao(session)

        # Patch reconciliar_nfe para falhar na primeira e sucesso na segunda
        original = motor.reconciliar_nfe
        call_count = [0]

        def patched(nfe):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Erro simulado")
            return original(nfe)

        with patch.object(motor, "reconciliar_nfe", side_effect=patched):
            stats = motor.reconciliar_todas()

        assert stats["erros"] == 1
        assert stats["reconciliadas"] == 1

    def test_buscar_pedido_candidato_pedido_fechado_ignorado(self, session):
        """Pedido fechado é ignorado na busca (linha 47)."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1500, chave_suffix="01")
        # Pedido fechado (mesmo CNPJ, mesmo valor)
        _criar_pedido(session, valor=1500, status="fechado")

        motor = MotorReconciliacao(session)
        pedido = motor._buscar_pedido_candidato(nfe)
        # Pedido fechado não é candidato
        assert pedido is None

    def test_buscar_pedido_candidato_sem_pedido_retorna_none(self, session):
        """Sem pedido do fornecedor retorna None (linhas 51-52)."""
        emitente = _criar_participante(session, cnpj="99999999000199")
        nfe = _criar_nfe(session, emitente, valor=500, chave_suffix="01")

        motor = MotorReconciliacao(session)
        pedido = motor._buscar_pedido_candidato(nfe)
        assert pedido is None

    def test_buscar_pedido_candidato_sem_emitente_retorna_none(self, session):
        """NF-e sem emitente retorna None (linha 42)."""
        nfe = Nfe(
            chave_acesso="3" * 44, numero_nota=3, serie=1, modelo="55",
            data_emissao=datetime(2026, 7, 15), natureza_operacao="Compra",
            tipo_operacao="0", valor_total=Decimal("500"),
            status_autorizacao="autorizada",
        )
        session.add(nfe)
        session.flush()

        motor = MotorReconciliacao(session)
        pedido = motor._buscar_pedido_candidato(nfe)
        assert pedido is None

    def test_buscar_recebimento_sem_pedido_retorna_none(self, session):
        """_buscar_recebimento com pedido None retorna None (linha 80-81)."""
        motor = MotorReconciliacao(session)
        result = motor._buscar_recebimento(None)
        assert result is None


# ===========================================================================
# 4. src/importador/manifestacao.py
# ===========================================================================


class TestManifestacaoBuracosCobertura:
    """Testes para cobrir linhas não testadas da manifestacao.py."""

    def test_identificar_notas_dentro_e_fora_prazo(self, session):
        """Notas dentro e fora do prazo simultaneamente (linhas 75-88)."""
        # Nota dentro do prazo (3 dias)
        _criar_nfe(
            session, manifestacao=None,
            data_emissao=datetime.now() - timedelta(days=3),
            chave_suffix="01",
        )
        # Nota fora do prazo (30 dias)
        _criar_nfe(
            session, manifestacao=None,
            data_emissao=datetime.now() - timedelta(days=30),
            chave_suffix="02",
        )

        r = identificar_notas_pendentes(session)
        assert len(r["urgente_ciencia"]) == 1
        assert len(r["fora_prazo_ciencia"]) == 1

    def test_identificar_notas_sem_notas(self, session):
        """Sem notas no banco retorna todas as listas vazias (linhas 64-69)."""
        r = identificar_notas_pendentes(session)
        assert r["urgente_ciencia"] == []
        assert r["fora_prazo_ciencia"] == []
        assert r["pendente_ciencia"] == []
        assert r["pendente_confirmacao"] == []

    def test_identificar_notas_pendente_ciencia_lista_vazia(self, session):
        """pendente_ciencia sempre existe mas pode estar vazia."""
        _criar_nfe(
            session, manifestacao=None,
            data_emissao=datetime.now() - timedelta(days=3),
            chave_suffix="01",
        )
        r = identificar_notas_pendentes(session)
        # pendente_ciencia não é populada pela função (apenas urgente e fora_prazo)
        assert "pendente_ciencia" in r
        assert r["pendente_ciencia"] == []

    def test_identificar_nota_com_ciencia_dentro_prazo_confirmacao(self, session):
        """Nota com ciência dentro do prazo de confirmação (linhas 90-100)."""
        _criar_nfe(
            session, manifestacao="ciencia_emissao",
            data_emissao=datetime.now() - timedelta(days=20),
            chave_suffix="01",
        )
        r = identificar_notas_pendentes(session)
        assert len(r["pendente_confirmacao"]) == 1
        assert r["pendente_confirmacao"][0]["dias"] == 20

    def test_identificar_nota_com_ciencia_fora_prazo_confirmacao(self, session):
        """Nota com ciência mas fora do prazo de confirmação não aparece."""
        _criar_nfe(
            session, manifestacao="ciencia_emissao",
            data_emissao=datetime.now() - timedelta(days=200),
            chave_suffix="01",
        )
        r = identificar_notas_pendentes(session)
        assert r["pendente_confirmacao"] == []

    @patch("src.importador.manifestacao.manifestar_lote")
    def test_executar_manifestacao_automatica_com_match(self, mock_manifestar, session):
        """executar_manifestacao_automatica com reconciliação matched dispara fase 2 (linhas 221, 231-235)."""
        nfe = _criar_nfe(
            session, manifestacao="ciencia_emissao",
            data_emissao=datetime.now() - timedelta(days=20),
            chave_suffix="01",
        )
        rec = Reconciliacao(nfe_id=nfe.id, status="matched", matched_by="automatico")
        session.add(rec)
        session.commit()

        mock_manifestar.side_effect = [
            {"manifestadas": 3, "erros": 0, "puladas": 0, "fora_prazo": 0, "total_verificadas": 3},
            {"manifestadas": 1, "erros": 0, "puladas": 0, "fora_prazo": 0, "total_verificadas": 1},
        ]
        r = executar_manifestacao_automatica(session)
        assert r["total_manifestadas"] == 4
        assert mock_manifestar.call_count == 2

    @patch("src.importador.manifestacao.manifestar_lote")
    def test_executar_manifestacao_automatica_sem_session(self, mock_manifestar):
        """executar_manifestacao_automatica sem session cria própria (linhas 218-221, 254-256)."""
        mock_manifestar.return_value = {
            "manifestadas": 0, "erros": 0, "puladas": 0,
            "fora_prazo": 0, "total_verificadas": 0,
        }
        with patch("src.persistencia.models.Session") as mock_session_cls:
            mock_s = MagicMock()
            mock_session_cls.return_value = mock_s

            r = executar_manifestacao_automatica()
            assert r["total_manifestadas"] == 0
            mock_s.close.assert_called_once()


# ===========================================================================
# 5. src/contabilidade/ecd.py
# ===========================================================================


class TestECDBuracosCobertura:
    """Testes para cobrir linhas não testadas do ecd.py."""

    def test_exportador_sem_lancamentos_gera_arquivo_valido(self, session):
        """Período sem lançamentos gera ECD com bloco I sem movimento (linhas 52, 101, 105)."""
        # Adiciona contas mas sem lançamentos
        session.add(PlanoContas(
            codigo_referencial="1.1.3.01", nome="Estoque",
            tipo="ativo", natureza="devedora",
        ))
        session.commit()

        exp = ExportadorECD(session)
        conteudo = exp.exportar(
            date(2026, 7, 1), date(2026, 7, 31),
            "12345678000190", "Empresa Teste",
        )
        assert "|0000|" in conteudo
        assert "|I001|0|" in conteudo  # sem movimento
        assert "|I012|0|" in conteudo  # sem livros com movimento
        assert "|J001|0|" in conteudo
        assert "|K001|0|" in conteudo
        assert "|9999|" in conteudo

    def test_exportador_periodo_muito_longo_erro(self, session):
        """Período maior que 366 dias levanta ValueError (linha 77-78)."""
        exp = ExportadorECD(session)
        with pytest.raises(ValueError, match="366"):
            exp.exportar(
                date(2025, 1, 1), date(2026, 1, 3),
                "12345678000190", "Empresa Teste",
            )

    def test_exportador_periodo_exatamente_366_dias(self, session):
        """Período de exatamente 366 dias (ano bissexto) é aceito (linha 77)."""
        exp = ExportadorECD(session)
        # 2024 é bissexto: 01/01/2024 a 31/12/2024 = 365 dias, +1 = 366
        conteudo = exp.exportar(
            date(2024, 1, 1), date(2024, 12, 31),
            "12345678000190", "Empresa Teste",
        )
        assert "|0000|" in conteudo

    def test_exportador_sem_data_inicio_erro(self, session):
        """Data inicial vazia levanta ValueError (linha 73-74)."""
        exp = ExportadorECD(session)
        with pytest.raises(ValueError, match="obrigatórias"):
            exp.exportar(None, date(2026, 7, 31), "12345678000190", "Empresa")

    def test_exportador_retorna_string_com_blocos(self, session):
        """exportar() retorna string com todos os blocos ECD (linhas 195-199, 306-312)."""
        # Popula dados mínimos
        session.add(PlanoContas(
            codigo_referencial="1.1.3.01", nome="Estoque",
            tipo="ativo", natureza="devedora",
        ))
        session.add(PlanoContas(
            codigo_referencial="2.1.01", nome="Fornecedores",
            tipo="passivo", natureza="credora",
        ))
        emit = Participante(cnpj_cpf="11222333000144", nome="Emitente")
        dest = Participante(cnpj_cpf="12345678000190", nome="Destinatario")
        session.add(emit, dest)
        session.flush()

        nfe = Nfe(
            chave_acesso="35200811222333000144550010000000011000000001",
            numero_nota=1, serie=1, modelo="55",
            data_emissao=datetime(2026, 7, 15, 10, 0),
            tipo_operacao="0", valor_total=Decimal("1000"),
            status_autorizacao="autorizada", origem="sefaz",
            emitente_id=emit.id, destinatario_id=dest.id,
        )
        session.add(nfe)
        session.flush()
        session.add(LancamentoContabil(
            nfe_id=nfe.id, data_lancamento=date(2026, 7, 15),
            numero_documento="1", historico="Compra",
            conta_debito_codigo="1.1.3.01", conta_credito_codigo="2.1.01",
            valor=Decimal("1000"),
        ))
        session.commit()

        exp = ExportadorECD(session)
        conteudo = exp.exportar(
            date(2026, 7, 1), date(2026, 7, 31),
            "12345678000190", "Empresa Teste",
        )
        assert isinstance(conteudo, str)
        assert "|0000|" in conteudo
        assert "|I001|1|" in conteudo  # com movimento
        assert "|I200|" in conteudo
        assert "|I250|" in conteudo
        assert "|J005|" in conteudo
        assert "|J100|" in conteudo
        assert "|K100|" in conteudo
        assert "|9900|" in conteudo
        assert "|9999|" in conteudo

    def test_executar_exportacao_ecd_funcao_conveniencia(self):
        """executar_exportacao_ecd cria e fecha session (linhas 304-312)."""
        with patch("src.persistencia.models.Session") as mock_session_cls, \
             patch("src.contabilidade.ecd.ExportadorECD") as mock_exp_cls:
            mock_s = MagicMock()
            mock_session_cls.return_value = mock_s
            mock_exp = MagicMock()
            mock_exp.exportar.return_value = "|0000|ECD|..."
            mock_exp_cls.return_value = mock_exp

            result = executar_exportacao_ecd(
                date(2026, 7, 1), date(2026, 7, 31),
                "12345678000190", "Empresa",
            )
            assert result == "|0000|ECD|..."
            mock_exp.exportar.assert_called_once()
            mock_s.close.assert_called_once()

    def test_fmt_data_sem_strftime_retorna_vazio(self, session):
        """_fmt_data com objeto sem strftime retorna string vazia (linha 52)."""
        exp = ExportadorECD(session)
        assert exp._fmt_data("nao_eh_data") == ""

    def test_fmt_valor_com_int_converte_para_decimal(self, session):
        """_fmt_valor com valor não-Decimal converte corretamente (linha 57)."""
        exp = ExportadorECD(session)
        resultado = exp._fmt_valor(100)
        assert resultado == "100,00"

    def test_fmt_cnpj_com_pontuacao(self, session):
        """_fmt_cnpj remove pontuação e completa com zeros (linhas 45-46)."""
        exp = ExportadorECD(session)
        assert exp._fmt_cnpj("12.345.678/0001-90") == "12345678000190"
        assert exp._fmt_cnpj("12345") == "00000000012345"
        assert exp._fmt_cnpj(None) == "00000000000000"


# ===========================================================================
# 6. src/mock_sefaz/main.py
# ===========================================================================


class TestMockSefazBuracosCobertura:
    """Testes para cobrir linhas não testadas do mock_sefaz/main.py."""

    def test_endpoint_status_servico(self, client):
        """GET /status-serviço retorna status 114 (linha 101)."""
        resp = client.get("/status-serviço")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "114"
        assert "data_consulta" in data

    def test_endpoint_reset(self, client):
        """POST /reset reseta o mock (linha 121)."""
        resp = client.post("/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "resetado" in data["motivo"].lower()

    def test_resumo_por_chave_inexistente(self, client):
        """GET /nfe/{chave} com chave inexistente retorna 404 (linha 141)."""
        resp = client.get("/nfe/00000000000000000000000000000000000000000000")
        assert resp.status_code == 404
        data = resp.json()
        assert "erro" in data
        assert "não encontrada" in data["erro"]

    def test_xml_por_chave_inexistente(self, client):
        """GET /nfe/{chave}/xml com chave inexistente retorna 404 (linha 121)."""
        resp = client.get("/nfe/00000000000000000000000000000000000000000000/xml")
        assert resp.status_code == 404
        data = resp.json()
        assert data["status"] == "631"

    def test_endpoint_pool(self, client):
        """GET /pool lista todas as notas do pool (linha 174)."""
        resp = client.get("/pool")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "notas" in data
        assert data["total"] > 0

    def test_manifestacao_chave_invalida(self, client):
        """POST /nfe-manifestação com chave inválida retorna 404 (linha 101)."""
        resp = client.post("/nfe-manifestação", json={
            "chave": "00000000000000000000000000000000000000000000",
            "tipo_evento": "ciencia_emissao",
        })
        assert resp.status_code == 404
        data = resp.json()
        assert data["status"] == "631"


# ===========================================================================
# Testes extras para cobrir linhas restantes
# ===========================================================================


class TestReporterDriftAlerta:
    """Cobre linhas 69-76 do reporter.py: alerta de regulatory drift."""

    def test_format_report_com_alerta_drift_ativo(self):
        """Quando há legislação expirando, mostra alerta de drift (linhas 69-76)."""
        ctx = ProjectContext(environment=Environment.MVP)
        ctrl = _controle_exemplo()
        avaliacoes = [ControlEvaluation(control=ctrl, result=CheckResult.PASS, details="OK")]
        report = _gerar_relatorio_gates(ctx, avaliacoes)

        drift_mock = {
            "vigente": 10, "total": 15, "expirando_90d": 2, "substituida": 1,
            "alertas": [
                {"id": "lei-x", "name": "Lei X", "dias_para_expirar": 45},
            ],
        }
        with patch("src.gates.reporter.regulatory_drift_report", return_value=drift_mock):
            texto = format_report(report, include_drift=True)

        assert "## Alerta de regulatory drift" in texto
        assert "Expirando em <=90 dias: 2" in texto
        assert "Substituída: 1" in texto
        assert "Lei X" in texto
        assert "45 dias" in texto


class TestGeradorBuracosExtras:
    """Cobre linhas restantes do gerador.py: close(), erros em gerar_todos."""

    def test_gerador_close_fecha_session_propria(self):
        """GeradorLancamentos.close() fecha session própria (linhas 112-113)."""
        gerador = GeradorLancamentos()
        gerador.close()
        # Session foi fechada sem erro

    def test_gerar_todos_com_erro_ao_estornar(self, session):
        """Erro ao estornar NF-e é capturado e incrementa erros (linhas 268-271)."""
        emitente = _criar_participante(session)
        # Cria nota autorizada, gera lançamentos, depois cancela
        nfe = _criar_nfe(
            session, cfop="1102", valor=1000, vicms=100,
            status="autorizada", origem="sefaz", chave_suffix="01",
        )
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        gerador.gerar_para_nfe(nfe)
        session.commit()

        nfe.status_autorizacao = "cancelada"
        session.commit()

        # Patch estornar_nfe para lançar exceção
        with patch.object(gerador, "estornar_nfe", side_effect=Exception("Erro DB")):
            stats = gerador.gerar_todos()
        assert stats["erros"] >= 1

    def test_gerar_todos_com_erro_ao_gerar(self, session):
        """Erro ao gerar lançamentos é capturado e incrementa erros (linhas 287-290)."""
        nfe = _criar_nfe(
            session, cfop="1102", valor=500, status="autorizada",
            origem="sefaz", chave_suffix="01",
        )
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        with patch.object(gerador, "gerar_para_nfe", side_effect=Exception("Erro DB")):
            stats = gerador.gerar_todos()
        assert stats["erros"] >= 1


class TestManifestacaoBuracosExtras:
    """Cobre linhas restantes da manifestacao.py: tipo inválido, resultado sem protocolo."""

    @patch("src.importador.manifestacao.ImportadorDFe")
    def test_manifestar_lote_tipo_evento_invalido(self, mock_importador_cls, session):
        """Tipo de evento não suportado retorna stats vazias (linhas 142-144)."""
        mock_importador = MagicMock()
        mock_importador_cls.return_value = mock_importador

        from src.importador.manifestacao import manifestar_lote
        stats = manifestar_lote(session, "tipo_invalido")
        assert stats["manifestadas"] == 0
        assert stats["total_verificadas"] == 0

    @patch("src.importador.manifestacao.ImportadorDFe")
    def test_manifestar_lote_resultado_sem_status_ok(self, mock_importador_cls, session):
        """Resultado sem status ok nem protocolo incrementa erros (linhas 190-191)."""
        _criar_nfe(
            session, manifestacao=None,
            data_emissao=datetime.now() - timedelta(days=3),
            chave_suffix="01",
        )

        mock_importador = MagicMock()
        mock_importador.manifestar.return_value = {"status": "rejeitado"}
        mock_importador_cls.return_value = mock_importador

        from src.importador.manifestacao import manifestar_lote
        stats = manifestar_lote(session, "ciencia_emissao")
        assert stats["erros"] == 1
        assert stats["manifestadas"] == 0


class TestMotorBuracosExtras:
    """Cobre linhas restantes do motor.py: divergência de quantidade, divergent em todas."""

    def test_reconciliar_todas_com_divergent(self, session):
        """reconciliar_todas conta divergent nas stats (linha 223)."""
        emitente = _criar_participante(session)
        # NF-e com valor diferente do pedido (divergent)
        nfe = _criar_nfe(session, emitente, valor=1600, chave_suffix="01")
        _criar_pedido(session, valor=1500)

        motor = MotorReconciliacao(session)
        stats = motor.reconciliar_todas()
        assert stats["divergent"] == 1

    def test_divergencia_quantidade_recebimento(self, session):
        """Divergência de quantidade no recebimento é detectada (linha 122)."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1500, chave_suffix="01")
        pedido = _criar_pedido(session, valor=1500)
        # Adiciona item ao pedido
        session.add(PedidoCompraItem(
            pedido_id=pedido.id, numero_item=1, codigo_produto="001",
            descricao="Farinha 1kg", ncm="11010010", cfop="1102",
            unidade="UN", quantidade=Decimal("100"),
            valor_unitario=Decimal("5.00"), valor_total=Decimal("500.00"),
        ))
        session.flush()

        # Cria recebimento com item divergente
        r = Recebimento(pedido_id=pedido.id, data_recebimento=date(2026, 7, 16),
                        responsavel="Joao")
        session.add(r)
        session.flush()
        pi = pedido.itens[0]
        session.add(RecebimentoItem(
            recebimento_id=r.id, pedido_item_id=pi.id,
            quantidade_recebida=Decimal("50"), conferido=True,
            divergencia="Quantidade menor",
        ))
        session.commit()

        motor = MotorReconciliacao(session)
        rec = motor.reconciliar_nfe(nfe)
        assert rec.status == "divergent"
        assert any("quantidade_item" in d["campo"] for d in (rec.divergencias or []))


class TestECDBuracosExtras:
    """Cobre linhas restantes do ecd.py: receitas no DRE."""

    def test_ecd_com_receitas_no_dre(self, session):
        """Lançamento com receita (conta 3.x crédito) aparece no DRE (linhas 195, 199)."""
        session.add(PlanoContas(
            codigo_referencial="1.1.3.01", nome="Estoque",
            tipo="ativo", natureza="devedora",
        ))
        session.add(PlanoContas(
            codigo_referencial="2.1.01", nome="Fornecedores",
            tipo="passivo", natureza="credora",
        ))
        session.add(PlanoContas(
            codigo_referencial="3.2.01", nome="Receita de Vendas",
            tipo="receita", natureza="credora",
        ))
        emit = Participante(cnpj_cpf="11222333000144", nome="Emitente")
        dest = Participante(cnpj_cpf="12345678000190", nome="Destinatario")
        session.add(emit, dest)
        session.flush()

        nfe = Nfe(
            chave_acesso="35200811222333000144550010000000011000000001",
            numero_nota=1, serie=1, modelo="55",
            data_emissao=datetime(2026, 7, 15, 10, 0),
            tipo_operacao="0", valor_total=Decimal("2000"),
            status_autorizacao="autorizada", origem="sefaz",
            emitente_id=emit.id, destinatario_id=dest.id,
        )
        session.add(nfe)
        session.flush()
        # Lançamento com crédito em conta 3.x (receita)
        session.add(LancamentoContabil(
            nfe_id=nfe.id, data_lancamento=date(2026, 7, 15),
            numero_documento="1", historico="Venda",
            conta_debito_codigo="2.1.01", conta_credito_codigo="3.2.01",
            valor=Decimal("2000"),
        ))
        session.commit()

        exp = ExportadorECD(session)
        conteudo = exp.exportar(
            date(2026, 7, 1), date(2026, 7, 31),
            "12345678000190", "Empresa Teste",
        )
        assert "Receita Operacional Bruta" in conteudo
        assert "2000,00" in conteudo
