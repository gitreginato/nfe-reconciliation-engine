"""Testes unitários do motor de reconciliação (three-way matching)."""
from datetime import datetime, date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistencia.models import (
    Base, Nfe, NfeItem, Participante, PedidoCompra, PedidoCompraItem,
    Recebimento, RecebimentoItem, Reconciliacao,
)
from src.reconciliacao.motor import MotorReconciliacao, popular_pedidos_demo


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _criar_participante(session, cnpj="11222333000144", nome="Distribuidora Alimentos SP Ltda"):
    p = Participante(cnpj_cpf=cnpj, nome=nome)
    session.add(p)
    session.flush()
    return p


def _criar_nfe(session, emitente, valor=1500.00, data_emissao=None, itens=None, chave=None):
    if data_emissao is None:
        data_emissao = datetime(2026, 7, 15)
    if chave is None:
        chave = f"{'1' * 43}{datetime.now().microsecond % 10}"
    nfe = Nfe(
        chave_acesso=chave,
        numero_nota=int(chave[-6:]) if chave else 1,
        serie=1, modelo="55",
        data_emissao=data_emissao,
        natureza_operacao="Compra",
        tipo_operacao="0",
        valor_total=Decimal(str(valor)),
        status_autorizacao="autorizado",
        emitente_id=emitente.id,
    )
    session.add(nfe)
    session.flush()
    if itens is None:
        itens = [
            {"numero_item": 1, "codigo_produto": "001", "descricao": "Farinha 1kg",
             "ncm": "11010010", "cfop": "1102", "valor_total": Decimal("500.00"),
             "valor_unitario": Decimal("5.00"), "quantidade": Decimal("100"), "unidade": "UN"},
            {"numero_item": 2, "codigo_produto": "002", "descricao": "Acucar 1kg",
             "ncm": "17019900", "cfop": "1102", "valor_total": Decimal("400.00"),
             "valor_unitario": Decimal("4.00"), "quantidade": Decimal("100"), "unidade": "UN"},
            {"numero_item": 3, "codigo_produto": "003", "descricao": "Oleo 1L",
             "ncm": "15121911", "cfop": "1102", "valor_total": Decimal("600.00"),
             "valor_unitario": Decimal("6.00"), "quantidade": Decimal("100"), "unidade": "UN"},
        ]
    for item_data in itens:
        session.add(NfeItem(nfe_id=nfe.id, **item_data))
    session.flush()
    return nfe


def _criar_pedido(session, cnpj="11222333000144", numero="PC-001",
                  valor=1500.00, data_pedido=None, itens=None):
    if data_pedido is None:
        data_pedido = date(2026, 7, 14)
    p = PedidoCompra(
        numero=numero, fornecedor_cnpj=cnpj,
        fornecedor_nome="Fornecedor", data_pedido=data_pedido,
        valor_total=Decimal(str(valor)), condicao_pagamento="30 dias",
    )
    session.add(p)
    session.flush()
    if itens is None:
        itens = [
            {"numero_item": 1, "codigo_produto": "001", "descricao": "Farinha 1kg",
             "ncm": "11010010", "cfop": "1102", "unidade": "UN",
             "quantidade": Decimal("100"), "valor_unitario": Decimal("5.00"),
             "valor_total": Decimal("500.00")},
            {"numero_item": 2, "codigo_produto": "002", "descricao": "Acucar 1kg",
             "ncm": "17019900", "cfop": "1102", "unidade": "UN",
             "quantidade": Decimal("100"), "valor_unitario": Decimal("4.00"),
             "valor_total": Decimal("400.00")},
            {"numero_item": 3, "codigo_produto": "003", "descricao": "Oleo 1L",
             "ncm": "15121911", "cfop": "1102", "unidade": "UN",
             "quantidade": Decimal("100"), "valor_unitario": Decimal("6.00"),
             "valor_total": Decimal("600.00")},
        ]
    for item_data in itens:
        session.add(PedidoCompraItem(pedido_id=p.id, **item_data))
    session.flush()
    return p


def _criar_recebimento(session, pedido, conferido=True, quantidades=None):
    r = Recebimento(pedido_id=pedido.id, data_recebimento=date(2026, 7, 16),
                    responsavel="Joao Silva")
    session.add(r)
    session.flush()
    for pi in pedido.itens:
        qtd = quantidades.get(pi.numero_item, pi.quantidade) if quantidades else pi.quantidade
        session.add(RecebimentoItem(
            recebimento_id=r.id, pedido_item_id=pi.id,
            quantidade_recebida=qtd, conferido=conferido,
        ))
    session.flush()
    return r


class TestMotorReconciliacao:
    """Testes do motor de reconciliação three-way matching."""

    def test_match_perfeito_three_way(self, session):
        """NF-e com pedido e recebimento idênticos: matched three_way."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1500.00)
        pedido = _criar_pedido(session, valor=1500.00)
        _criar_recebimento(session, pedido)

        motor = MotorReconciliacao(session)
        rec = motor.reconciliar_nfe(nfe)

        assert rec.status == "matched"
        assert rec.tipo_match == "three_way"
        assert rec.pedido_compra_id == pedido.id
        assert rec.divergencias is None

    def test_match_perfeito_two_way(self, session):
        """NF-e com pedido mas sem recebimento: matched two_way."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1500.00)
        pedido = _criar_pedido(session, valor=1500.00)
        # Sem recebimento

        motor = MotorReconciliacao(session)
        rec = motor.reconciliar_nfe(nfe)

        assert rec.status == "matched"
        assert rec.tipo_match == "two_way"

    def test_sem_pedido_pending(self, session):
        """NF-e sem pedido vinculado: pending."""
        emitente = _criar_participante(session, cnpj="99999999000199")
        nfe = _criar_nfe(session, emitente, valor=500.00)

        motor = MotorReconciliacao(session)
        rec = motor.reconciliar_nfe(nfe)

        assert rec.status == "pending"
        assert rec.tipo_match is None

    def test_divergencia_preco(self, session):
        """NF-e com valor diferente do pedido (acima da tolerância): divergent."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1600.00)
        pedido = _criar_pedido(session, valor=1500.00)

        motor = MotorReconciliacao(session)
        rec = motor.reconciliar_nfe(nfe)

        assert rec.status == "divergent"
        assert rec.divergencias is not None
        assert any(d["campo"] == "valor_total" for d in rec.divergencias)

    def test_divergencia_dentro_tolerancia(self, session):
        """Diferença de 1% (dentro da tolerância de 2%): matched."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1515.00)
        pedido = _criar_pedido(session, valor=1500.00)

        motor = MotorReconciliacao(session)
        rec = motor.reconciliar_nfe(nfe)

        assert rec.status == "matched"

    def test_divergencia_data(self, session):
        """Diferença de data maior que tolerância: divergent."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1500.00,
                         data_emissao=datetime(2026, 8, 10))
        pedido = _criar_pedido(session, valor=1500.00,
                               data_pedido=date(2026, 7, 14))

        motor = MotorReconciliacao(session)
        rec = motor.reconciliar_nfe(nfe)

        assert rec.status == "divergent"
        assert any(d["campo"] == "data" for d in rec.divergencias)

    def test_divergencia_preco_unitario_item(self, session):
        """Preço unitário de item divergente: divergent."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1500.00, itens=[
            {"numero_item": 1, "codigo_produto": "001", "descricao": "Farinha 1kg",
             "ncm": "11010010", "cfop": "1102", "valor_total": Decimal("600.00"),
             "valor_unitario": Decimal("6.00"), "quantidade": Decimal("100"), "unidade": "UN"},
            {"numero_item": 2, "codigo_produto": "002", "descricao": "Acucar 1kg",
             "ncm": "17019900", "cfop": "1102", "valor_total": Decimal("400.00"),
             "valor_unitario": Decimal("4.00"), "quantidade": Decimal("100"), "unidade": "UN"},
            {"numero_item": 3, "codigo_produto": "003", "descricao": "Oleo 1L",
             "ncm": "15121911", "cfop": "1102", "valor_total": Decimal("500.00"),
             "valor_unitario": Decimal("5.00"), "quantidade": Decimal("100"), "unidade": "UN"},
        ])
        pedido = _criar_pedido(session, valor=1500.00)

        motor = MotorReconciliacao(session)
        rec = motor.reconciliar_nfe(nfe)

        assert rec.status == "divergent"
        assert any("preco_unitario" in d["campo"] for d in rec.divergencias)

    def test_pedido_marcado_fechado_ao_match(self, session):
        """Pedido é marcado como 'fechado' quando reconciliado com matched."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1500.00)
        pedido = _criar_pedido(session, valor=1500.00)

        motor = MotorReconciliacao(session)
        motor.reconciliar_nfe(nfe)

        assert pedido.status == "fechado"

    def test_nao_reconcilia_duplicada(self, session):
        """Reconciliar mesma NF-e duas vezes não cria duplicata."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1500.00)
        pedido = _criar_pedido(session, valor=1500.00)

        motor = MotorReconciliacao(session)
        rec1 = motor.reconciliar_nfe(nfe)
        rec2 = motor.reconciliar_nfe(nfe)

        assert rec1.id == rec2.id
        assert session.query(Reconciliacao).filter_by(nfe_id=nfe.id).count() == 1

    def test_reconciliar_todas(self, session):
        """reconciliar_todas processa todas as NF-e sem reconciliação."""
        emitente = _criar_participante(session)
        nfe1 = _criar_nfe(session, emitente, valor=1500.00, chave="1" * 43 + "1")
        nfe2 = _criar_nfe(session, emitente, valor=2000.00, chave="1" * 43 + "2")
        _criar_pedido(session, valor=1500.00, numero="PC-001")
        _criar_pedido(session, valor=2000.00, numero="PC-002")

        motor = MotorReconciliacao(session)
        stats = motor.reconciliar_todas()

        assert stats["reconciliadas"] == 2
        assert stats["matched"] == 2

    def test_reconciliar_todas_com_pending(self, session):
        """NF-e sem pedido fica pending nas stats."""
        emitente1 = _criar_participante(session, cnpj="11111111000111")
        emitente2 = _criar_participante(session, cnpj="22222222000222")
        nfe1 = _criar_nfe(session, emitente1, valor=1500.00, chave="1" * 43 + "1")
        nfe2 = _criar_nfe(session, emitente2, valor=500.00, chave="2" * 43 + "2")
        pedido = _criar_pedido(session, cnpj="11111111000111", valor=1500.00)

        motor = MotorReconciliacao(session)
        stats = motor.reconciliar_todas()

        assert stats["matched"] == 1
        assert stats["pending"] == 1

    def test_busca_pedido_melhor_match(self, session):
        """Quando há múltiplos pedidos do mesmo fornecedor, escolhe o mais próximo."""
        emitente = _criar_participante(session)
        nfe = _criar_nfe(session, emitente, valor=1500.00)
        # Pedido distante (valor diferente)
        _criar_pedido(session, valor=3000.00, numero="PC-DISTANTE")
        # Pedido próximo (valor igual)
        pedido_proximo = _criar_pedido(session, valor=1500.00, numero="PC-PROXIMO")

        motor = MotorReconciliacao(session)
        pedido = motor._buscar_pedido_candidato(nfe)

        assert pedido is not None
        assert pedido.id == pedido_proximo.id

    def test_sem_emitente_retorna_pending(self, session):
        """NF-e sem emitente: pending (não quebra)."""
        nfe = Nfe(
            chave_acesso="3" * 44, numero_nota=3, serie=1, modelo="55",
            data_emissao=datetime(2026, 7, 15), natureza_operacao="Compra",
            tipo_operacao="0",
            valor_total=Decimal("500.00"), status_autorizacao="autorizado",
        )
        session.add(nfe)
        session.flush()

        motor = MotorReconciliacao(session)
        rec = motor.reconciliar_nfe(nfe)

        assert rec.status == "pending"


class TestPopularPedidosDemo:
    """Testa criação de pedidos de demonstração."""

    def test_popular_pedidos_cria_6(self, session):
        """popular_pedidos_demo cria 6 pedidos de demo."""
        result = popular_pedidos_demo(session)
        assert result["criados"] == 6

    def test_popular_pedidos_nao_duplica(self, session):
        """popular_pedidos_demo não cria pedidos duplicados."""
        popular_pedidos_demo(session)
        result = popular_pedidos_demo(session)
        assert result["criados"] == 0
