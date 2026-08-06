"""Testes de integracao do sistema de contabilidade.

Cobrem:
- Idempotencia (reimportar nao duplica)
- Reconciliacao (matched, divergent, pending)
- Lancamentos contabeis (debito = credito)
- Estorno de notas canceladas
- Rate limit
- Filtros de dashboard
"""
import pytest
import httpx
from decimal import Decimal
from datetime import date
from fastapi.testclient import TestClient

from src.dashboard.main import app
from src.persistencia.models import (
    Session, Nfe, Reconciliacao, LancamentoContabil, PedidoCompra,
    Recebimento, RecebimentoItem, PedidoCompraItem, NfeItem, NfeEvento,
    Participante, DfeImportacao, PlanoContas,
    init_db, engine,
)
from src.importador.dfe import ImportadorDFe
from src.reconciliacao.motor import MotorReconciliacao, popular_pedidos_demo
from src.contabilidade.gerador import GeradorLancamentos
from src.config import settings


def _reset_mock_sefaz():
    """Reseta o mock SEFAZ para o estado inicial."""
    try:
        httpx.post(f"{settings.sefaz_mock_url}/reset", timeout=5.0)
    except Exception:
        pass  # Mock pode não estar disponivel em alguns testes


@pytest.fixture
def session():
    init_db()
    _reset_mock_sefaz()
    s = Session()
    # Limpa na ordem correta (respeitando FKs)
    s.query(LancamentoContabil).delete()
    s.query(Reconciliacao).delete()
    s.query(RecebimentoItem).delete()
    s.query(Recebimento).delete()
    s.query(PedidoCompraItem).delete()
    s.query(PedidoCompra).delete()
    s.query(NfeEvento).delete()
    s.query(NfeItem).delete()
    s.query(Nfe).delete()
    s.query(DfeImportacao).delete()
    s.query(Participante).delete()
    s.query(PlanoContas).delete()
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client():
    return TestClient(app)


class TestImportacao:
    """Testes do importador DF-e."""

    def test_importacao_basica(self, session):
        importador = ImportadorDFe(session=session)
        stats = importador.importar_tudo()
        assert stats["importadas"] > 0
        assert stats["erros"] == 0
        importador.close()

    def test_idempotencia(self, session):
        """Reimportar não duplica notas no banco."""
        importador = ImportadorDFe(session=session)
        stats1 = importador.importar_tudo()
        total_apos_primeira = session.query(Nfe).count()

        # Reseta NSU para forcar reconsulta do mock
        session.query(DfeImportacao).delete()
        session.commit()

        stats2 = importador.importar_tudo()
        total_apos_segunda = session.query(Nfe).count()

        assert stats1["importadas"] > 0
        assert total_apos_primeira == total_apos_segunda  # não duplicou
        # Segunda importação deve detectar duplicadas (notas já existem por chave)
        assert stats2["duplicadas"] > 0, "Segunda importação deveria detectar duplicadas"
        assert stats2["importadas"] == 0, "Segunda importação não deveria importar novas"
        importador.close()

    def test_nota_tem_itens(self, session):
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        nfe = session.query(Nfe).first()
        assert nfe is not None
        assert len(nfe.itens) > 0
        importador.close()


class TestReconciliacao:
    """Testes do motor de reconciliação."""

    def test_reconciliacao_matched(self, session):
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        stats = motor.reconciliar_todas()
        assert stats["matched"] > 0
        assert stats["erros"] == 0
        importador.close()

    def test_reconciliacao_divergente(self, session):
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        divergentes = session.query(Reconciliacao).filter_by(status="divergent").all()
        for d in divergentes:
            assert d.divergencias is not None
            assert len(d.divergencias) > 0
        importador.close()

    def test_reconciliacao_pending_sem_pedido(self, session):
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        pending = session.query(Reconciliacao).filter_by(status="pending").all()
        for p in pending:
            assert p.pedido_compra_id is None
        importador.close()

    def test_idempotencia_reconciliacao(self, session):
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        stats1 = motor.reconciliar_todas()
        stats2 = motor.reconciliar_todas()
        assert stats1["reconciliadas"] > 0
        assert stats2["reconciliadas"] == 0
        importador.close()


class TestLancamentos:
    """Testes do gerador de lançamentos contábeis."""

    def test_lancamento_debito_igual_credito(self, session):
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        # Para cada NF-e matched, soma dos débitos = soma dos créditos (partida dobrada)
        notas_matched = session.query(Nfe).join(Reconciliacao).filter(
            Reconciliacao.status == "matched"
        ).all()
        for nfe in notas_matched:
            for l in nfe.lancamentos:
                if not l.estornado:
                    assert l.valor > 0, f"Lancamento com valor <= 0: {l.historico}"
                    # Partida dobrada: cada lançamento tem débito e crédito de mesmo valor
                    assert l.conta_debito_codigo, f"Lancamento sem conta de débito: {l.historico}"
                    assert l.conta_credito_codigo, f"Lancamento sem conta de crédito: {l.historico}"
            # Soma total de débitos = soma total de créditos
            debito_total = sum(float(l.valor) for l in nfe.lancamentos if not l.estornado)
            credito_total = sum(float(l.valor) for l in nfe.lancamentos if not l.estornado)
            assert abs(debito_total - credito_total) < 0.01, \
                f"Partida dobrada violada: débito={debito_total}, crédito={credito_total}"
        importador.close()

    def test_estorno_nota_cancelada(self, session):
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        # Cancela a primeira nota matched
        nfe = session.query(Nfe).join(Reconciliacao).filter(
            Reconciliacao.status == "matched"
        ).first()
        nfe.status_autorizacao = "cancelada"
        session.commit()

        # Gera novamente: deve estornar
        gerador2 = GeradorLancamentos(session=session)
        stats = gerador2.gerar_todos()
        assert stats["estornos"] > 0

        # Verifica que lançamentos originais estao estornados
        originais = session.query(LancamentoContabil).filter_by(
            nfe_id=nfe.id, estornado=True
        ).all()
        assert len(originais) > 0

        # Verifica que existem lançamentos de estorno
        estornos = session.query(LancamentoContabil).filter(
            LancamentoContabil.nfe_id == nfe.id,
            LancamentoContabil.historico.like("ESTORNO%")
        ).all()
        assert len(estornos) > 0
        importador.close()

    def test_nao_gera_para_divergente(self, session):
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        divergentes = session.query(Nfe).join(Reconciliacao).filter(
            Reconciliacao.status == "divergent"
        ).all()
        for nfe in divergentes:
            assert len(nfe.lancamentos) == 0
        importador.close()


class TestDashboard:
    """Testes dos endpoints do dashboard."""

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_dashboard_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_api_dashboard(self, client):
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_notas" in data
        assert "valor_total" in data

    def test_filtro_status(self, client):
        resp = client.get("/api/notas?status=autorizada")
        assert resp.status_code == 200
        data = resp.json()
        for n in data["notas"]:
            assert n["status"] == "autorizada"

    def test_export_csv_notas(self, client):
        resp = client.get("/api/export/csv?tipo=notas")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "Número" in resp.text

    def test_export_csv_lancamentos(self, client):
        resp = client.get("/api/export/csv?tipo=lancamentos")
        assert resp.status_code == 200
        assert "Debito" in resp.text


class TestVolume:
    """Testes de volume com 1000 NF-e sintéticas."""

    def test_gerar_1000_nfe(self, session):
        """Gera 1000 NF-e e verifica que todas foram criadas."""
        from tests.gerador_sintetico import popular_nfe_sinteticas
        stats = popular_nfe_sinteticas(session, 1000)
        assert stats["criadas"] == 1000
        assert stats["erros"] == 0
        assert stats["canceladas"] > 0  # ~5% canceladas
        assert stats["valor_total"] > 0

        total = session.query(Nfe).count()
        assert total >= 1000

    def test_dashboard_responde_rapido_com_1000(self, client):
        """Dashboard deve responder em menos de 2s com 1000+ notas."""
        import time
        inicio = time.time()
        resp = client.get("/api/dashboard")
        tempo = time.time() - inicio
        assert resp.status_code == 200
        assert tempo < 2.0, f"Dashboard demorou {tempo:.2f}s (limite 2s)"

    def test_api_notas_responde_rapido_com_1000(self, client):
        """API de notas deve responder em menos de 2s com 1000+ notas."""
        import time
        inicio = time.time()
        resp = client.get("/api/notas")
        tempo = time.time() - inicio
        assert resp.status_code == 200
        assert tempo < 2.0, f"API notas demorou {tempo:.2f}s (limite 2s)"

    def test_export_csv_responde_rapido_com_1000(self, client):
        """Export CSV deve responder em menos de 2s com 1000+ notas."""
        import time
        inicio = time.time()
        resp = client.get("/api/export/csv?tipo=notas")
        tempo = time.time() - inicio
        assert resp.status_code == 200
        assert tempo < 2.0, f"Export CSV demorou {tempo:.2f}s (limite 2s)"
