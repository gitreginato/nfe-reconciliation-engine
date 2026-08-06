"""Testes unitários do mock SEFAZ, pool de NF-e e gerador de pedidos.

Cobre:
- MockSEFAZ (FastAPI app): gera NF-e válida com 44 dígitos, múltiplas NF-e
- pool_nfe: gera pool de notas para teste
- gerador_pedidos: gera pedidos a partir de notas existentes, não duplica
"""
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.mock_sefaz.main import app, _gerar_xml_nfe
from src.mock_sefaz.pool_nfe import (
    POOL_NFE, get_nfe_by_chave, get_nfe_by_nsu,
    get_notas_apartir_nsu, manifestar_nfe, reset_pool,
)
from src.persistencia.models import (
    Base, Nfe, NfeItem, Participante, PedidoCompra, Reconciliacao,
)
from src.reconciliacao.gerador_pedidos import gerar_pedidos_para_notas


@pytest.fixture
def client():
    """Cliente de teste do FastAPI com pool resetado antes de cada teste."""
    reset_pool()
    with TestClient(app) as c:
        yield c
    reset_pool()


@pytest.fixture
def session():
    """Sessão SQLite em memória para testes do gerador de pedidos."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _criar_nfe_completa(session, chave, emitente, numero=1, valor=1500.00):
    """Cria uma NF-e autorizada de origem sefaz com itens para o gerador."""
    nfe = Nfe(
        chave_acesso=chave,
        numero_nota=numero,
        serie=1,
        modelo="55",
        data_emissao=datetime(2026, 7, 15, 10, 0, 0),
        natureza_operacao="Compra de mercadorias",
        tipo_operacao="0",
        valor_total=Decimal(str(valor)),
        valor_produtos=Decimal(str(valor)),
        status_autorizacao="autorizada",
        origem="sefaz",
        emitente_id=emitente.id,
        destinatario_id=emitente.id,
    )
    session.add(nfe)
    session.flush()
    session.add(NfeItem(
        nfe_id=nfe.id, numero_item=1, codigo_produto="001",
        descricao="Farinha 1kg", ncm="11010010", cfop="1102", unidade="UN",
        quantidade=Decimal("100"), valor_unitario=Decimal("5.00"),
        valor_total=Decimal(str(valor)),
    ))
    session.commit()
    return nfe


class TestMockSEFAZ:
    """Testes do servidor mock SEFAZ via FastAPI TestClient."""

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "mock-sefaz"

    def test_gera_nfe_valida_com_44_digitos(self, client):
        """A distribuição retorna documentos com chave de 44 dígitos."""
        resp = client.post("/nfe-distribuicao", json={"ultimo_nsu": 0, "cnpj": "12345678000190"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "138"
        documentos = data["documentos"]
        assert len(documentos) > 0
        for doc in documentos:
            assert len(doc["chave"]) == 44, f"Chave {doc['chave']} não tem 44 dígitos"
            assert doc["chave"].isdigit(), f"Chave {doc['chave']} não é numérica"

    def test_gera_multiplas_nfe(self, client):
        """A distribuição retorna múltiplas NF-e a partir do NSU 0."""
        resp = client.post("/nfe-distribuicao", json={"ultimo_nsu": 0, "cnpj": "12345678000190"})
        documentos = resp.json()["documentos"]
        assert len(documentos) > 1, "Deveria retornar múltiplas NF-e"
        # NSUs devem ser únicos e crescentes
        nsus = [d["nsu"] for d in documentos]
        assert len(set(nsus)) == len(nsus), "NSUs duplicados"
        assert nsus == sorted(nsus), "NSUs não estão em ordem crescente"

    def test_distribuicao_sem_documentos(self, client):
        """NSU muito alto retorna sem documentos."""
        resp = client.post("/nfe-distribuicao", json={"ultimo_nsu": 99999, "cnpj": "12345678000190"})
        data = resp.json()
        assert data["status"] == "0"
        assert data["documentos"] == []

    def test_manifestacao_libera_xml(self, client):
        """Após manifestar, o XML da nota fica disponível."""
        primeira = POOL_NFE[0]
        chave = primeira["chave"]

        # Antes de manifestar: XML bloqueado (403)
        resp = client.get(f"/nfe/{chave}/xml")
        assert resp.status_code == 403

        # Manifestar
        resp = client.post("/nfe-manifestação", json={"chave": chave, "tipo_evento": "ciencia_emissao"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "135"

        # Depois de manifestar: XML disponível
        resp = client.get(f"/nfe/{chave}/xml")
        assert resp.status_code == 200
        assert "xml" in resp.headers.get("content-type", "").lower() or "<NFe" in resp.text
        assert "<NFe" in resp.text

    def test_resumo_nfe_por_chave(self, client):
        """GET /nfe/{chave} retorna o resumo completo da nota."""
        chave = POOL_NFE[0]["chave"]
        resp = client.get(f"/nfe/{chave}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chave"] == chave
        assert len(data["chave"]) == 44
        assert "itens" in data
        assert len(data["itens"]) > 0

    def test_status_servico(self, client):
        resp = client.get("/status-serviço")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "114"

    def test_gerar_xml_nfe_tem_estrutura_valida(self):
        """_gerar_xml_nfe produz XML com infNFe e a chave correta."""
        nota = POOL_NFE[0]
        xml = _gerar_xml_nfe(nota)
        assert "<?xml" in xml
        assert "<NFe" in xml
        assert "<infNFe" in xml
        assert f"NFe{nota['chave']}" in xml
        assert "<det" in xml
        assert "<prod>" in xml

    def test_reset_endpoint(self, client):
        """POST /reset marca todas as notas como não manifestadas."""
        chave = POOL_NFE[0]["chave"]
        manifestar_nfe(chave)
        assert get_nfe_by_chave(chave)["manifestada"] is True

        resp = client.post("/reset")
        assert resp.status_code == 200
        assert get_nfe_by_chave(chave)["manifestada"] is False


class TestPoolNFE:
    """Testes do pool de NF-e de exemplo."""

    def test_pool_tem_notas(self):
        assert len(POOL_NFE) > 0

    def test_todas_chaves_tem_44_digitos(self):
        for nota in POOL_NFE:
            assert len(nota["chave"]) == 44, f"Chave {nota['chave']} inválida"
            assert nota["chave"].isdigit()

    def test_get_nfe_by_chave_existente(self):
        nota = POOL_NFE[0]
        encontrada = get_nfe_by_chave(nota["chave"])
        assert encontrada is not None
        assert encontrada["nsu"] == nota["nsu"]

    def test_get_nfe_by_chave_inexistente(self):
        assert get_nfe_by_chave("00000000000000000000000000000000000000000000") is None

    def test_get_nfe_by_nsu(self):
        nota = POOL_NFE[0]
        assert get_nfe_by_nsu(nota["nsu"])["chave"] == nota["chave"]
        assert get_nfe_by_nsu(999999) is None

    def test_get_notas_apartir_nsu(self):
        """Retorna apenas notas com NSU maior que o informado."""
        todas = get_notas_apartir_nsu(0)
        assert len(todas) == len(POOL_NFE)
        assert all(n["nsu"] > 0 for n in todas)

        algumas = get_notas_apartir_nsu(5)
        assert all(n["nsu"] > 5 for n in algumas)
        assert len(algumas) < len(POOL_NFE)

    def test_get_notas_apartir_nsu_respeita_limite(self):
        notas = get_notas_apartir_nsu(0, limite=3)
        assert len(notas) == 3

    def test_manifestar_nfe(self):
        reset_pool()
        nota = POOL_NFE[0]
        assert nota["manifestada"] is False
        assert manifestar_nfe(nota["chave"]) is True
        assert nota["manifestada"] is True
        assert manifestar_nfe("chave_inexistente") is False

    def test_reset_pool(self):
        manifestar_nfe(POOL_NFE[0]["chave"])
        reset_pool()
        for nota in POOL_NFE:
            assert nota["manifestada"] is False


class TestGeradorPedidos:
    """Testes do gerador de pedidos de compra."""

    def test_gera_pedidos_a_partir_de_notas(self, session):
        """Gera pedidos para NF-e autorizadas de origem sefaz."""
        emitente = Participante(cnpj_cpf="11222333000144", nome="Distribuidora SP")
        session.add(emitente)
        session.flush()

        _criar_nfe_completa(session, "35200811222333000144550010000000011000000001", emitente, 1, 1500.00)
        _criar_nfe_completa(session, "35200811222333000144550010000000021000000008", emitente, 2, 800.00)
        session.commit()

        stats = gerar_pedidos_para_notas(session=session)

        assert stats["notas_verificadas"] == 2
        assert stats["pedidos_criados"] >= 1
        # Pelo menos um pedido foi criado no banco
        pedidos = session.query(PedidoCompra).all()
        assert len(pedidos) >= 1

    def test_nao_duplica_pedidos_existentes(self, session):
        """Notas já reconciliadas (com pedido vinculado) não geram novo pedido.

        A dedup do gerador baseia-se em Reconciliacao com pedido_compra_id,
        não em PedidoCompra isolado. Simulamos uma reconciliação existente.
        """
        emitente = Participante(cnpj_cpf="11222333000144", nome="Distribuidora SP")
        session.add(emitente)
        session.flush()
        nfe = _criar_nfe_completa(
            session, "35200811222333000144550010000000011000000001", emitente, 1, 1500.00
        )
        session.commit()

        # Primeira execução cria pedidos
        stats1 = gerar_pedidos_para_notas(session=session)
        assert stats1["pedidos_criados"] >= 1

        # Simula reconciliação vinculando a nota a um pedido existente
        pedido = session.query(PedidoCompra).first()
        session.add(Reconciliacao(
            nfe_id=nfe.id, pedido_compra_id=pedido.id,
            status="matched", tipo_match="three_way",
        ))
        session.commit()

        total_pedidos_antes = session.query(PedidoCompra).count()
        stats2 = gerar_pedidos_para_notas(session=session)
        total_pedidos_depois = session.query(PedidoCompra).count()

        # Segunda execução não cria novos pedidos para a nota reconciliada
        assert stats2["pedidos_criados"] == 0
        assert stats2["pedidos_existentes"] >= 1
        assert total_pedidos_depois == total_pedidos_antes

    def test_stats_retorna_estrutura_esperada(self, session):
        emitente = Participante(cnpj_cpf="11222333000144", nome="Distribuidora SP")
        session.add(emitente)
        session.flush()
        _criar_nfe_completa(session, "35200811222333000144550010000000011000000001", emitente, 1, 1500.00)
        session.commit()

        stats = gerar_pedidos_para_notas(session=session)
        for chave in ("notas_verificadas", "pedidos_criados", "recebimentos_criados",
                      "itens_criados", "sem_pedido", "pedidos_existentes"):
            assert chave in stats
