"""Motor de reconciliacao - three-way matching.

Compara NF-e com pedido de compra e recebimento.
Detecta divergencias de preco, quantidade e data.
Tolerancias configuraveis via settings.
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.persistencia.models import (
    Nfe, PedidoCompra, Recebimento, Reconciliacao, Session as SessionClass,
)

logger = logging.getLogger(__name__)


class MotorReconciliacao:
    """Faz matching entre NF-e, pedido de compra e recebimento."""

    def __init__(self, session: Session | None = None):
        self.session = session or SessionClass()
        self._own_session = session is None
        self.tol_preco = Decimal(str(settings.tolerancia_preco_percent))
        self.tol_qtd = Decimal(str(settings.tolerancia_qtd_percent))
        self.tol_data = settings.tolerancia_data_dias

    def close(self):
        if self._own_session:
            self.session.close()

    def _buscar_pedido_candidato(self, nfe: Nfe) -> PedidoCompra | None:
        """Busca pedido de compra com mesmo CNPJ do emitente.

        Usa score composto: valor total + proximidade de data + contagem de itens.
        Quanto menor o score, melhor o match.
        """
        if not nfe.emitente:
            return None

        pedidos = self.session.query(PedidoCompra).filter(
            and_(
                PedidoCompra.fornecedor_cnpj == nfe.emitente.cnpj_cpf,
                PedidoCompra.status != "fechado",
            )
        ).all()

        if not pedidos:
            return None

        valor_nfe = Decimal(str(nfe.valor_total))
        data_nfe = nfe.data_emissao.date() if hasattr(nfe.data_emissao, 'date') else nfe.data_emissao
        num_itens_nfe = len(nfe.itens)

        melhor = None
        menor_score = None
        for p in pedidos:
            # Score de valor (peso 1000: diferença absoluta em reais)
            diff_valor = abs(Decimal(str(p.valor_total)) - valor_nfe)

            # Score de data (peso 1: dias de diferença)
            diff_dias = abs((data_nfe - p.data_pedido).days) if p.data_pedido else 999

            # Score de itens (peso 100: diferença na quantidade de itens)
            diff_itens = abs(len(p.itens) - num_itens_nfe) * 100

            # Score composto: valor tem peso maior, depois itens, depois data
            score = float(diff_valor) + diff_itens + diff_dias * 0.5

            if menor_score is None or score < menor_score:
                menor_score = score
                melhor = p
        return melhor

    def _buscar_recebimento(self, pedido: PedidoCompra) -> Recebimento | None:
        """Busca recebimento vinculado ao pedido."""
        if not pedido:
            return None
        return self.session.query(Recebimento).filter_by(pedido_id=pedido.id).first()

    def _calcular_divergencias(
        self, nfe: Nfe, pedido: PedidoCompra, recebimento: Recebimento | None
    ) -> list[dict]:
        """Calcula divergências entre NF-e, pedido e recebimento."""
        divergencias = []
        valor_nfe = Decimal(str(nfe.valor_total))
        valor_pedido = Decimal(str(pedido.valor_total))

        # Divergência de valor
        if valor_pedido > 0:
            diff_percent = abs(valor_nfe - valor_pedido) / valor_pedido * 100
            if diff_percent > self.tol_preco:
                divergencias.append({
                    "campo": "valor_total",
                    "esperado": float(valor_pedido),
                    "encontrado": float(valor_nfe),
                    "diferenca": float(valor_nfe - valor_pedido),
                    "diferenca_percent": float(diff_percent),
                    "tolerancia_percent": float(self.tol_preco),
                })

        # Divergência de data
        if nfe.data_emissao and pedido.data_pedido:
            data_nfe = nfe.data_emissao.date() if hasattr(nfe.data_emissao, 'date') else nfe.data_emissao
            diff_dias = abs((data_nfe - pedido.data_pedido).days)
            if diff_dias > self.tol_data:
                divergencias.append({
                    "campo": "data",
                    "esperado": pedido.data_pedido.isoformat(),
                    "encontrado": data_nfe.isoformat(),
                    "diferenca_dias": diff_dias,
                    "tolerancia_dias": self.tol_data,
                })

        # Divergência de quantidade (se tem recebimento)
        if recebimento and recebimento.itens:
            for ri in recebimento.itens:
                if ri.pedido_item and ri.divergencia:
                    divergencias.append({
                        "campo": f"quantidade_item_{ri.pedido_item.numero_item}",
                        "esperado": float(ri.pedido_item.quantidade),
                        "encontrado": float(ri.quantidade_recebida),
                        "diferenca": ri.divergencia,
                    })

        # Divergência por item (preço unitario)
        # Guarda de tamanho: se pedido tem muitos itens, usa dict indexado por codigo
        pedido_itens_by_codigo = {}
        if pedido.itens and len(pedido.itens) > 100:
            for pi in pedido.itens:
                if pi.codigo_produto:
                    pedido_itens_by_codigo[pi.codigo_produto] = pi
        for item in nfe.itens:
            pedido_item = None
            if pedido_itens_by_codigo:
                pedido_item = pedido_itens_by_codigo.get(item.codigo_produto)
            elif pedido.itens:
                for pi in pedido.itens:
                    if pi.codigo_produto and pi.codigo_produto == item.codigo_produto:
                        pedido_item = pi
                        break
            if pedido_item and pedido_item.valor_unitario > 0:
                diff = abs(Decimal(str(item.valor_unitario)) - Decimal(str(pedido_item.valor_unitario)))
                diff_pct = diff / Decimal(str(pedido_item.valor_unitario)) * 100
                if diff_pct > self.tol_preco:
                    divergencias.append({
                        "campo": f"preco_unitario_item_{item.numero_item}",
                        "esperado": float(pedido_item.valor_unitario),
                        "encontrado": float(item.valor_unitario),
                        "diferenca": float(diff),
                        "diferenca_percent": float(diff_pct),
                    })

        return divergencias

    def reconciliar_nfe(self, nfe: Nfe) -> Reconciliacao:
        """Reconcilia uma NF-e específica."""
        # Verifica se já existe reconciliação
        rec_existente = self.session.query(Reconciliacao).filter_by(nfe_id=nfe.id).first()
        if rec_existente:
            return rec_existente

        pedido = self._buscar_pedido_candidato(nfe)
        recebimento = self._buscar_recebimento(pedido) if pedido else None

        if not pedido:
            # Sem pedido vinculado: pending
            rec = Reconciliacao(
                nfe_id=nfe.id,
                status="pending",
                tipo_match=None,
                divergencias=None,
                data_match=datetime.now(),
                matched_by="automatico",
            )
        else:
            divergencias = self._calcular_divergencias(nfe, pedido, recebimento)
            if divergencias:
                status = "divergent"
                tipo_match = "three_way" if recebimento else "two_way"
            else:
                status = "matched"
                tipo_match = "three_way" if recebimento else "two_way"

            rec = Reconciliacao(
                nfe_id=nfe.id,
                pedido_compra_id=pedido.id,
                recebimento_id=recebimento.id if recebimento else None,
                status=status,
                tipo_match=tipo_match,
                divergencias=divergencias if divergencias else None,
                tolerancia_percentual=self.tol_preco,
                data_match=datetime.now(),
                matched_by="automatico",
            )

            # Marca pedido como fechado quando matched (não será reusado)
            if status == "matched":
                pedido.status = "fechado"

        self.session.add(rec)
        self.session.commit()
        logger.info(f"NF-e {nfe.chave_acesso[:20]}...: reconciliação {rec.status} ({rec.tipo_match or 'sem_pedido'})")
        return rec

    def reconciliar_todas(self) -> dict:
        """Reconcilia todas as NF-e que ainda não tem reconciliação.

        Processa ordenado por (CNPJ do emitente, valor_total) para maximizar
        matches: notas do mesmo fornecedor são processadas juntas, em ordem
        de valor, facilitando o matching com pedidos do mesmo fornecedor.
        """
        stats = {"reconciliadas": 0, "matched": 0, "divergent": 0, "pending": 0, "erros": 0}

        notas = self.session.query(Nfe).filter(
            ~Nfe.reconciliacoes.any()
        ).order_by(
            Nfe.emitente_id, Nfe.valor_total
        ).all()

        for nfe in notas:
            try:
                rec = self.reconciliar_nfe(nfe)
                stats["reconciliadas"] += 1
                if rec.status == "matched":
                    stats["matched"] += 1
                elif rec.status == "divergent":
                    stats["divergent"] += 1
                elif rec.status == "pending":
                    stats["pending"] += 1
            except (SQLAlchemyError, ValueError, RuntimeError) as e:
                self.session.rollback()
                logger.error(f"Erro ao reconciliar NF-e {nfe.chave_acesso[:20]}...: {e}")
                stats["erros"] += 1

        return stats


def executar_reconciliacao() -> dict:
    """Função de conveniência para executar reconciliação (chamada pela API)."""
    motor = MotorReconciliacao()
    try:
        return motor.reconciliar_todas()
    finally:
        motor.close()


def popular_pedidos_demo(session: Session | None = None):
    """Cria pedidos de compra de demonstracao que casam com as notas do mock.

    Cenarios:
    - Pedido que casa exato com nota 1 (matched)
    - Pedido com divergencia de preco para nota 5 (divergent)
    - Pedido com divergencia de quantidade para nota 6 (divergent)
    - Sem pedido para nota 4 (pending)
    """
    session = session or SessionClass()
    from src.persistencia.models import PedidoCompra, PedidoCompraItem, Recebimento, RecebimentoItem

    pedidos_existentes = session.query(PedidoCompra).count()
    if pedidos_existentes > 0:
        return {"criados": 0, "motivo": "já existem pedidos"}

    from datetime import date as date_type

    # Pedido 1: casa exato com NF-e 1 (Distribuidora Alimentos, R$ 1500)
    p1 = PedidoCompra(
        numero="PC-001",
        fornecedor_cnpj="11222333000144",
        fornecedor_nome="Distribuidora Alimentos SP Ltda",
        data_pedido=date_type(2026, 7, 14),
        valor_total=Decimal("1500.00"),
        condicao_pagamento="30 dias",
    )
    session.add(p1)
    session.flush()
    session.add(PedidoCompraItem(
        pedido_id=p1.id, numero_item=1, codigo_produto="001",
        descricao="Farinha de trigo 1kg", ncm="11010010", cfop="1102",
        unidade="UN", quantidade=100, valor_unitario=5.00, valor_total=500.00,
    ))
    session.add(PedidoCompraItem(
        pedido_id=p1.id, numero_item=2, codigo_produto="002",
        descricao="Açúcar cristal 1kg", ncm="17019900", cfop="1102",
        unidade="UN", quantidade=100, valor_unitario=4.00, valor_total=400.00,
    ))
    session.add(PedidoCompraItem(
        pedido_id=p1.id, numero_item=3, codigo_produto="003",
        descricao="Óleo de soja 1L", ncm="15121911", cfop="1102",
        unidade="UN", quantidade=100, valor_unitario=6.00, valor_total=600.00,
    ))

    # Recebimento do pedido 1 (three-way match)
    r1 = Recebimento(
        pedido_id=p1.id,
        data_recebimento=date_type(2026, 7, 16),
        responsavel="Joao Silva",
    )
    session.add(r1)
    session.flush()
    for pi in p1.itens:
        session.add(RecebimentoItem(
            recebimento_id=r1.id, pedido_item_id=pi.id,
            quantidade_recebida=pi.quantidade, conferido=True,
        ))

    # Pedido 2: divergência de preço para NF-e 5 (Distribuidora, R$ 1250 vs pedido R$ 1000)
    p2 = PedidoCompra(
        numero="PC-005",
        fornecedor_cnpj="11222333000144",
        fornecedor_nome="Distribuidora Alimentos SP Ltda",
        data_pedido=date_type(2026, 7, 18),
        valor_total=Decimal("1000.00"),
        condicao_pagamento="30 dias",
    )
    session.add(p2)
    session.flush()
    session.add(PedidoCompraItem(
        pedido_id=p2.id, numero_item=1, codigo_produto="001",
        descricao="Farinha de trigo 1kg", ncm="11010010", cfop="1102",
        unidade="UN", quantidade=100, valor_unitario=5.00, valor_total=500.00,
    ))
    session.add(PedidoCompraItem(
        pedido_id=p2.id, numero_item=2, codigo_produto="002",
        descricao="Açúcar cristal 1kg", ncm="17019900", cfop="1102",
        unidade="UN", quantidade=100, valor_unitario=4.00, valor_total=400.00,
    ))
    session.add(PedidoCompraItem(
        pedido_id=p2.id, numero_item=3, codigo_produto="003",
        descricao="Óleo de soja 1L", ncm="15121911", cfop="1102",
        unidade="UN", quantidade=100, valor_unitario=1.00, valor_total=100.00,
    ))

    # Pedido 3: divergência de quantidade para NF-e 6 (Distribuidora, 150 vs 100)
    p3 = PedidoCompra(
        numero="PC-006",
        fornecedor_cnpj="11222333000144",
        fornecedor_nome="Distribuidora Alimentos SP Ltda",
        data_pedido=date_type(2026, 7, 19),
        valor_total=Decimal("1000.00"),
        condicao_pagamento="30 dias",
    )
    session.add(p3)
    session.flush()
    session.add(PedidoCompraItem(
        pedido_id=p3.id, numero_item=1, codigo_produto="001",
        descricao="Farinha de trigo 1kg", ncm="11010010", cfop="1102",
        unidade="UN", quantidade=100, valor_unitario=5.00, valor_total=500.00,
    ))

    # Pedido 4: casa com NF-e 3 (Móveis, ativo imobilizado, R$ 3500)
    p4 = PedidoCompra(
        numero="PC-003",
        fornecedor_cnpj="44555666000177",
        fornecedor_nome="Móveis Industrializados do Brasil SA",
        data_pedido=date_type(2026, 7, 16),
        valor_total=Decimal("3500.00"),
        condicao_pagamento="a vista",
    )
    session.add(p4)
    session.flush()
    session.add(PedidoCompraItem(
        pedido_id=p4.id, numero_item=1, codigo_produto="MESA01",
        descricao="Mesa de escritório 1.20m", ncm="94033000", cfop="1551",
        unidade="UN", quantidade=5, valor_unitario=350.00, valor_total=1750.00,
    ))
    session.add(PedidoCompraItem(
        pedido_id=p4.id, numero_item=2, codigo_produto="CAD01",
        descricao="Cadeira giratória executiva", ncm="94013090", cfop="1551",
        unidade="UN", quantidade=10, valor_unitario=175.00, valor_total=1750.00,
    ))

    # Pedido 5: casa com NF-e 9 (Limpeza, R$ 450)
    p5 = PedidoCompra(
        numero="PC-009",
        fornecedor_cnpj="22333444000155",
        fornecedor_nome="Limpeza Total Produtos de Higiene Ltda",
        data_pedido=date_type(2026, 7, 22),
        valor_total=Decimal("450.00"),
        condicao_pagamento="15 dias",
    )
    session.add(p5)
    session.flush()
    session.add(PedidoCompraItem(
        pedido_id=p5.id, numero_item=1, codigo_produto="SABAO",
        descricao="Sabão em pó 1kg", ncm="34022020", cfop="1102",
        unidade="UN", quantidade=30, valor_unitario=15.00, valor_total=450.00,
    ))

    # Pedido 6: divergência alta para NF-e 10 (TechInfo, R$ 4200 vs pedido R$ 3000)
    p6 = PedidoCompra(
        numero="PC-010",
        fornecedor_cnpj="55666777000188",
        fornecedor_nome="TechInfo Equipamentos Eletrônicos Ltda",
        data_pedido=date_type(2026, 7, 22),
        valor_total=Decimal("3000.00"),
        condicao_pagamento="a vista",
    )
    session.add(p6)
    session.flush()
    session.add(PedidoCompraItem(
        pedido_id=p6.id, numero_item=1, codigo_produto="NOTE-DELL",
        descricao="Notebook Dell Inspiron 15", ncm="84713012", cfop="1102",
        unidade="UN", quantidade=3, valor_unitario=1000.00, valor_total=3000.00,
    ))

    session.commit()
    return {"criados": 6, "pedidos": ["PC-001", "PC-003", "PC-005", "PC-006", "PC-009", "PC-010"]}
