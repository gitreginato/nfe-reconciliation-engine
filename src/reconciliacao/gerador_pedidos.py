"""Gerador de pedidos de compra que simulam o sistema de compras da empresa.

Cria pedidos para todas as NF-e do mock SEFAZ, com recebimento (three-way
matching). Cenários realistas:
- 60% dos pedidos casam exato com a nota (matched)
- 20% têm divergência de preço (divergent)
- 10% têm divergência de quantidade (divergent)
- 10% sem recebimento (pending, nota chegou mas pedido não foi fechado)

Também cria pedidos para parte das notas sintéticas (10%) para dar volume.
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from src.persistencia.models import (
    Nfe, PedidoCompra, PedidoCompraItem, Recebimento, RecebimentoItem,
    Reconciliacao, Session as SessionClass,
)


def _ja_tem_pedido(nfe: Nfe, session: Session) -> bool:
    """Verifica se já existe pedido que casa com esta NF-e."""
    # Se a NF-e já tem reconciliação matched, já tem pedido
    rec = session.query(Reconciliacao).filter_by(nfe_id=nfe.id).first()
    if rec and rec.pedido_compra_id:
        return True
    return False


def gerar_pedidos_para_notas(session: Session = None, limite: int = 200) -> dict:
    """Gera pedidos de compra para NF-e existentes no banco.

    Args:
        session: Sessão do banco (cria se não fornecida)
        limite: Máximo de notas a processar

    Returns:
        dict com estatísticas: pedidos_criados, recebimentos_criados, matched_esperado
    """
    own_session = session is None
    if own_session:
        session = SessionClass()

    try:
        # Busca notas autorizadas (do mock SEFAZ) sem pedido vinculado
        notas = session.query(Nfe).filter(
            Nfe.status_autorizacao == "autorizada",
            Nfe.origem == "sefaz",
        ).order_by(Nfe.data_emissao).all()

        # Também busca notas sintéticas não-canceladas (todas)
        notas_sint = session.query(Nfe).filter(
            Nfe.status_autorizacao == "sintética",
            Nfe.origem == "sintética",
        ).order_by(Nfe.data_emissao).all()

        todas_notas = notas + notas_sint
        stats = {
            "notas_verificadas": len(todas_notas),
            "pedidos_criados": 0,
            "recebimentos_criados": 0,
            "itens_criados": 0,
            "sem_pedido": 0,
            "pedidos_existentes": 0,
        }

        random.seed(42)  # determinístico para reprodução
        contador_pc = session.query(PedidoCompra).count() + 100

        for nfe in todas_notas:
            if _ja_tem_pedido(nfe, session):
                stats["pedidos_existentes"] += 1
                continue

            # 10% das notas ficam sem pedido (pending)
            if random.random() < 0.10:
                stats["sem_pedido"] += 1
                continue

            # Cria pedido baseado nos itens da NF-e
            emitente = nfe.emitente
            if not emitente:
                continue

            contador_pc += 1
            num_pedido = f"PC-{contador_pc:05d}"

            # Cenário: 70% casam exato, 20% divergência de preço, 10% divergência de qtd
            cenario = random.random()
            fator_preco = 1.0
            fator_qtd = 1.0

            if cenario < 0.70:
                # Matched: valores exatos
                pass
            elif cenario < 0.90:
                # Divergência de preço: pedido 10-15% mais barato
                fator_preco = random.uniform(0.85, 0.90)
            else:
                # Divergência de quantidade: pedido pede 20% a mais
                fator_qtd = random.uniform(1.15, 1.25)

            # Data do pedido: 1-5 dias antes da emissão da nota
            data_emissao = nfe.data_emissao.date() if hasattr(nfe.data_emissao, 'date') else nfe.data_emissao
            data_pedido = data_emissao - timedelta(days=random.randint(1, 5))

            # Calcula valor total do pedido
            valor_total_pedido = Decimal("0")
            itens_pedido = []

            for item_nfe in nfe.itens:
                qtd_pedida = Decimal(str(item_nfe.quantidade)) * Decimal(str(fator_qtd))
                qtd_pedida = Decimal(str(round(qtd_pedida, 4)))
                vunit_pedido = Decimal(str(item_nfe.valor_unitario)) * Decimal(str(fator_preco))
                vunit_pedido = Decimal(str(round(vunit_pedido, 4)))
                vtotal_item = (qtd_pedida * vunit_pedido).quantize(Decimal("0.01"))
                valor_total_pedido += vtotal_item

                itens_pedido.append({
                    "numero_item": item_nfe.numero_item,
                    "codigo_produto": f"PRD-{item_nfe.ncm}-{item_nfe.numero_item}",
                    "descricao": item_nfe.descricao,
                    "ncm": item_nfe.ncm,
                    "cfop": item_nfe.cfop,
                    "unidade": item_nfe.unidade or "UN",
                    "quantidade": qtd_pedida,
                    "valor_unitario": vunit_pedido,
                    "valor_total": vtotal_item,
                })

            valor_total_pedido = valor_total_pedido.quantize(Decimal("0.01"))

            # Condições de pagamento realistas
            condicoes = ["30 dias", "30/60 dias", "15 dias", "a vista", "30/60/90 dias"]
            condicao = random.choice(condicoes)

            pedido = PedidoCompra(
                numero=num_pedido,
                fornecedor_cnpj=emitente.cnpj_cpf,
                fornecedor_nome=emitente.nome,
                data_pedido=data_pedido,
                valor_total=valor_total_pedido,
                condicao_pagamento=condicao,
                status="aberto",
            )
            session.add(pedido)
            session.flush()
            stats["pedidos_criados"] += 1

            # Cria itens do pedido
            for ip in itens_pedido:
                session.add(PedidoCompraItem(
                    pedido_id=pedido.id,
                    numero_item=ip["numero_item"],
                    codigo_produto=ip["codigo_produto"],
                    descricao=ip["descricao"],
                    ncm=ip["ncm"],
                    cfop=ip["cfop"],
                    unidade=ip["unidade"],
                    quantidade=ip["quantidade"],
                    valor_unitario=ip["valor_unitario"],
                    valor_total=ip["valor_total"],
                ))
                stats["itens_criados"] += 1

            # 80% dos pedidos têm recebimento (three-way matching completo)
            if random.random() < 0.80:
                data_rec = data_emissao + timedelta(days=random.randint(0, 3))
                responsaveis = ["Joao Silva", "Maria Santos", "Pedro Oliveira",
                                "Ana Costa", "Carlos Pereira"]
                recebimento = Recebimento(
                    pedido_id=pedido.id,
                    data_recebimento=data_rec,
                    responsavel=random.choice(responsaveis),
                )
                session.add(recebimento)
                session.flush()
                stats["recebimentos_criados"] += 1

                # Itens do recebimento: quantidade recebida = quantidade do pedido
                for pi in pedido.itens:
                    session.add(RecebimentoItem(
                        recebimento_id=recebimento.id,
                        pedido_item_id=pi.id,
                        quantidade_recebida=pi.quantidade,
                        conferido=True,
                    ))

        session.commit()
        return stats
    finally:
        if own_session:
            session.close()
