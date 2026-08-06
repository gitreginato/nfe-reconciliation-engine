"""Testes unitários do dashboard (FastAPI endpoints)."""
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.persistencia.models import (
    Base, Nfe, NfeItem, Participante, Reconciliacao, LancamentoContabil,
    PlanoContas, PedidoCompra,
)


@pytest.fixture
def client(monkeypatch):
    """Cria cliente de teste com banco em memória."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    # Popula dados de teste
    s = TestSession()
    emitente = Participante(cnpj_cpf="11222333000144", nome="Distribuidora Alimentos SP Ltda")
    s.add(emitente)
    s.flush()
    nfe = Nfe(
        chave_acesso="1" * 44, numero_nota=1, serie=1, modelo="55",
        data_emissao=datetime(2026, 7, 15), natureza_operacao="Compra",
        tipo_operacao="0", valor_total=Decimal("1500.00"),
        status_autorizacao="autorizado", emitente_id=emitente.id,
    )
    s.add(nfe)
    s.flush()
    s.add(NfeItem(
        nfe_id=nfe.id, numero_item=1, codigo_produto="001",
        descricao="Farinha de trigo 1kg", ncm="11010010", cfop="1102",
        valor_total=Decimal("1500.00"), valor_unitario=Decimal("15.00"),
        quantidade=Decimal("100"), unidade="UN",
    ))
    s.commit()
    s.close()

    # Override da dependência get_session do FastAPI
    def _get_test_session():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    from src.dashboard import main as dashboard_main
    dashboard_main.app.dependency_overrides[dashboard_main.get_session] = _get_test_session

    client = TestClient(dashboard_main.app)
    yield client

    # Cleanup
    dashboard_main.app.dependency_overrides.clear()


class TestDashboardHTML:
    """Testa endpoints HTML do dashboard."""

    def test_home_retorna_200(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_home_contem_titulo(self, client):
        r = client.get("/")
        assert "Contabilidade" in r.text or "NF-e" in r.text

    def test_home_contem_tabela_notas(self, client):
        r = client.get("/")
        assert "<table" in r.text
        assert "11222333000144" in r.text or "Distribuidora" in r.text

    def test_nota_detalhe_retorna_200(self, client):
        r = client.get(f"/notas/{'1' * 44}")
        assert r.status_code == 200

    def test_nota_detalhe_nao_encontrada(self, client):
        r = client.get(f"/notas/{'9' * 44}")
        assert r.status_code == 404

    def test_crossover_retorna_200(self, client):
        r = client.get("/crossover")
        assert r.status_code == 200


class TestDashboardAPI:
    """Testa endpoints JSON do dashboard."""

    def test_api_dashboard_retorna_200(self, client):
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "total_notas" in data
        assert data["total_notas"] >= 1

    def test_api_notas_retorna_200(self, client):
        r = client.get("/api/notas")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "notas" in data
        assert data["total"] >= 1

    def test_api_nota_detalhe_retorna_200(self, client):
        r = client.get(f"/api/notas/{'1' * 44}")
        assert r.status_code == 200
        data = r.json()
        assert data["chave"] == "1" * 44
        assert "itens" in data

    def test_api_nota_detalhe_nao_encontrada(self, client):
        r = client.get(f"/api/notas/{'9' * 44}")
        assert r.status_code == 404

    def test_api_lancamentos_retorna_200(self, client):
        r = client.get("/api/lancamentos")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data

    def test_api_reconciliacoes_retorna_200(self, client):
        r = client.get("/api/reconciliacoes")
        assert r.status_code == 200
        data = r.json()
        assert "reconciliacoes" in data

    def test_api_notas_com_filtro_status(self, client):
        r = client.get("/api/notas?status=autorizado")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1

    def test_api_notas_com_filtro_cnpj(self, client):
        r = client.get("/api/notas?emitente_cnpj=11222333000144")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1

    def test_api_notas_com_data_inicio(self, client):
        r = client.get("/api/notas?data_inicio=2026-07-01")
        assert r.status_code == 200

    def test_api_notas_com_data_invalida(self, client):
        """Data inválida é ignorada (não filtra, não quebra)."""
        r = client.get("/api/notas?data_inicio=invalida")
        assert r.status_code == 200

    def test_api_notas_paginacao(self, client):
        r = client.get("/api/notas?page=1&page_size=10")
        assert r.status_code == 200
        data = r.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_api_export_csv_notas(self, client):
        r = client.get("/api/export/csv?tipo=notas")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "Número" in r.text

    def test_api_export_csv_reconciliacoes(self, client):
        r = client.get("/api/export/csv?tipo=reconciliacoes")
        assert r.status_code == 200
        assert "ID" in r.text

    def test_api_export_csv_lancamentos(self, client):
        r = client.get("/api/export/csv?tipo=lancamentos")
        assert r.status_code == 200
        assert "ID" in r.text

    def test_api_export_csv_tipo_invalido(self, client):
        r = client.get("/api/export/csv?tipo=invalido")
        assert r.status_code == 400

    def test_api_export_ecd_periodo_valido(self, client):
        r = client.get("/api/export/ecd?data_inicio=2026-01-01&data_fim=2026-07-31")
        assert r.status_code == 200

    def test_api_export_ecd_data_invalida(self, client):
        r = client.get("/api/export/ecd?data_inicio=xxx&data_fim=yyy")
        assert r.status_code == 400

    def test_api_export_ecd_fim_anterior_inicio(self, client):
        r = client.get("/api/export/ecd?data_inicio=2026-07-31&data_fim=2026-01-01")
        assert r.status_code == 400

    def test_api_export_ecd_periodo_maior_1_ano(self, client):
        r = client.get("/api/export/ecd?data_inicio=2025-01-01&data_fim=2026-12-31")
        assert r.status_code == 400

    def test_api_resolver_divergencia_nao_encontrada(self, client):
        r = client.post("/api/reconciliacoes/9999/resolver?justificativa=teste+de+resolucao&resolvido_por=Joao")
        assert r.status_code == 404

    def test_api_resolver_divergencia_justificativa_curta(self, client):
        """Justificativa com menos de 10 chars rejeitada."""
        r = client.post("/api/reconciliacoes/1/resolver?justificativa=curta&resolvido_por=Joao")
        assert r.status_code == 422

    def test_api_crossover_retorna_200(self, client):
        r = client.get(f"/api/crossover/{'1' * 44}")
        assert r.status_code == 200
        data = r.json()
        assert "nfe" in data

    def test_api_crossover_nao_encontrada(self, client):
        r = client.get(f"/api/crossover/{'9' * 44}")
        assert r.status_code == 404

    def test_api_crossover_chave_invalida(self, client):
        r = client.get("/api/crossover/abc")
        assert r.status_code == 400

    def test_api_apuracao_mensal(self, client):
        r = client.get("/api/apuracao/2026/7")
        assert r.status_code == 200

    def test_api_apuracao_mes_invalido(self, client):
        r = client.get("/api/apuracao/2026/13")
        assert r.status_code == 422

    def test_api_manifestacao_pendentes(self, client):
        r = client.get("/api/manifestacao/pendentes")
        assert r.status_code == 200

    def test_crossover_html_nota_encontrada(self, client):
        r = client.get(f"/crossover/{'1' * 44}")
        assert r.status_code == 200

    def test_crossover_html_chave_invalida(self, client):
        r = client.get("/crossover/abc")
        assert r.status_code == 400

    def test_crossover_html_nao_encontrada(self, client):
        r = client.get(f"/crossover/{'9' * 44}")
        assert r.status_code == 404

    def test_nota_detalhe_chave_invalida(self, client):
        r = client.get("/notas/abc")
        assert r.status_code == 400

    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_api_notas_com_data_fim(self, client):
        r = client.get("/api/notas?data_fim=2026-12-31")
        assert r.status_code == 200

    def test_api_notas_com_data_fim_invalida(self, client):
        r = client.get("/api/notas?data_fim=invalida")
        assert r.status_code == 200

    @patch("src.dashboard.main.executar_reconciliacao")
    def test_api_executar_reconciliacao(self, mock_rec, client):
        mock_rec.return_value = {"matched": 1, "pending": 0}
        r = client.post("/api/reconciliacao/executar")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @patch("src.dashboard.main.executar_reconciliacao")
    def test_api_executar_reconciliacao_erro(self, mock_rec, client):
        mock_rec.side_effect = RuntimeError("falha")
        r = client.post("/api/reconciliacao/executar")
        assert r.status_code == 500

    @patch("src.dashboard.main.popular_pedidos_demo")
    def test_api_popular_pedidos(self, mock_pop, client):
        mock_pop.return_value = {"criados": 6}
        r = client.post("/api/reconciliacao/popular-pedidos")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @patch("src.dashboard.main.popular_pedidos_demo")
    def test_api_popular_pedidos_erro(self, mock_pop, client):
        mock_pop.side_effect = RuntimeError("falha")
        r = client.post("/api/reconciliacao/popular-pedidos")
        assert r.status_code == 500

    @patch("src.dashboard.main.executar_lancamentos")
    def test_api_executar_lancamentos(self, mock_lan, client):
        mock_lan.return_value = {"gerados": 5}
        r = client.post("/api/lancamentos/executar")
        assert r.status_code == 200

    @patch("src.dashboard.main.executar_lancamentos")
    def test_api_executar_lancamentos_erro(self, mock_lan, client):
        mock_lan.side_effect = RuntimeError("falha")
        r = client.post("/api/lancamentos/executar")
        assert r.status_code == 500

    @patch("src.dashboard.main.executar_importacao")
    def test_api_executar_importacao(self, mock_imp, client):
        mock_imp.return_value = {"importadas": 3}
        r = client.post("/api/importacao/executar")
        assert r.status_code == 200

    @patch("src.dashboard.main.executar_importacao")
    def test_api_executar_importacao_erro(self, mock_imp, client):
        mock_imp.side_effect = RuntimeError("falha")
        r = client.post("/api/importacao/executar")
        assert r.status_code == 500

    @patch("src.dashboard.main.gerar_pedidos_para_notas")
    def test_api_gerar_pedidos(self, mock_gen, client):
        mock_gen.return_value = {"gerados": 2}
        r = client.post("/api/pedidos/gerar")
        assert r.status_code == 200

    @patch("src.dashboard.main.gerar_pedidos_para_notas")
    def test_api_gerar_pedidos_erro(self, mock_gen, client):
        mock_gen.side_effect = RuntimeError("falha")
        r = client.post("/api/pedidos/gerar")
        assert r.status_code == 500

    @patch("src.dashboard.main.executar_manifestacao_automatica")
    def test_api_manifestacao_lote(self, mock_man, client):
        mock_man.return_value = {"manifestadas": 5}
        r = client.post("/api/manifestacao/executar")
        assert r.status_code == 200

    @patch("src.dashboard.main.executar_manifestacao_automatica")
    def test_api_manifestacao_lote_erro(self, mock_man, client):
        mock_man.side_effect = RuntimeError("falha")
        r = client.post("/api/manifestacao/executar")
        assert r.status_code == 500

    @patch("src.dashboard.main.popular_nfe_sinteticas")
    def test_api_gerar_1000(self, mock_gen, client):
        mock_gen.return_value = {"geradas": 1000}
        r = client.post("/api/teste/gerar-1000")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestDashboardHelpers:
    """Testa funções helper do dashboard."""

    def test_fmt_money_decimal(self):
        from src.dashboard.main import _fmt_money
        from decimal import Decimal
        assert _fmt_money(Decimal("1234.56")) == "R$ 1,234.56"

    def test_fmt_money_zero(self):
        from src.dashboard.main import _fmt_money
        assert _fmt_money(None) == "R$ 0,00"
        assert _fmt_money(0) == "R$ 0,00"

    def test_fmt_money_float(self):
        from src.dashboard.main import _fmt_money
        assert _fmt_money(1234.56) == "R$ 1,234.56"

    def test_to_float_decimal_quantizado(self):
        from src.dashboard.main import _to_float
        from decimal import Decimal
        # Decimal com mais de 2 casas deve ser quantizado
        v = _to_float(Decimal("123.456"))
        assert v == 123.46

    def test_to_float_none(self):
        from src.dashboard.main import _to_float
        assert _to_float(None) == 0.0

    def test_to_float_int(self):
        from src.dashboard.main import _to_float
        assert _to_float(42) == 42.0

    def test_esc_string(self):
        from src.dashboard.main import _esc
        assert _esc("<script>") == "&lt;script&gt;"

    def test_esc_none(self):
        from src.dashboard.main import _esc
        assert _esc(None) == "-"

    def test_fmt_date(self):
        from src.dashboard.main import _fmt_date
        d = date(2026, 7, 15)
        assert _fmt_date(d) == "15/07/2026"

    def test_fmt_date_none(self):
        from src.dashboard.main import _fmt_date
        assert _fmt_date(None) == "-"

    def test_status_badge(self):
        from src.dashboard.main import _badge
        html = _badge("matched")
        assert "badge" in html
        assert "matched" in html

    def test_status_badge_unknown(self):
        from src.dashboard.main import _badge
        html = _badge("unknown")
        assert "badge" in html
