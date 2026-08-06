"""Gerador de lancamentos contabeis a partir de NF-e reconciliadas.

Mapeia CFOPs para contas do plano de contas e gera lancamentos
de estoque, ICMS, IPI, IBS/CBS e fornecedor.
"""
from datetime import datetime, date
from decimal import Decimal
import logging
from sqlalchemy.orm import Session

from src.persistencia.models import (
    Nfe, Reconciliacao, LancamentoContabil, PlanoContas,
    Session as SessionClass,
)
from src.fiscal.validadores import categoria_contabil_cfop

logger = logging.getLogger(__name__)

# Tabela de CFOPs para contas contábeis (codigo_referencial do plano_contas)
# Categorias: estoque, ativo, consumo, servico, devolucao, venda
MAPEAMENTO_CFOP = {
    # --- Entrada: compras para comercialização (estoque) ---
    "1101": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Compra para comercialização"},
    "1102": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Compra de mercadorias para revenda"},
    "1111": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Compra para industrialização"},
    "1113": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Compra para uso e consumo"},
    "1116": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Compra para industrialização sem NF-e"},
    "1403": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Compra para comercialização por conta de terceiros"},
    # --- Entrada: compras para ativo imobilizado ---
    "1551": {"débito": "1.2.1.01", "crédito": "2.1.01", "descricao": "Compra de ativo imobilizado"},
    "1554": {"débito": "1.2.1.01", "crédito": "2.1.01", "descricao": "Compra de ativo imobilizado por conta de terceiros"},
    "1556": {"débito": "1.2.1.01", "crédito": "2.1.01", "descricao": "Compra de ativo imobilizado para uso"},
    # --- Entrada: compras de consumo ---
    "1103": {"débito": "3.1.01", "crédito": "2.1.01", "descricao": "Compra de material de consumo"},
    "1106": {"débito": "3.1.01", "crédito": "2.1.01", "descricao": "Compra de material de uso e consumo"},
    # --- Entrada: serviços (ISS) ---
    "1933": {"débito": "3.1.02", "crédito": "2.1.01", "descricao": "Aquisição de serviços"},
    "1934": {"débito": "3.1.02", "crédito": "2.1.01", "descricao": "Aquisição de serviços"},
    "1935": {"débito": "3.1.02", "crédito": "2.1.01", "descricao": "Aquisição de serviços"},
    # --- Entrada: energia elétrica ---
    "1252": {"débito": "3.1.02", "crédito": "2.1.01", "descricao": "Aquisição de energia elétrica"},
    "1253": {"débito": "3.1.02", "crédito": "2.1.01", "descricao": "Aquisição de energia elétrica por conta de terceiros"},
    # --- Entrada: combustível ---
    "1303": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Aquisição de combustível"},
    # --- Entrada: devoluções de venda (estorno) ---
    "1201": {"débito": "2.1.01", "crédito": "1.1.3.01", "descricao": "Devolução de venda de mercadoria"},
    "1202": {"débito": "2.1.01", "crédito": "1.1.3.01", "descricao": "Devolução de venda de mercadoria"},
    "1410": {"débito": "2.1.01", "crédito": "1.1.3.01", "descricao": "Devolução de venda de produção"},
    "1411": {"débito": "2.1.01", "crédito": "1.1.3.01", "descricao": "Devolução de venda de mercadoria de terceiros"},
    "1503": {"débito": "2.1.01", "crédito": "1.2.1.01", "descricao": "Devolução de venda de bem do ativo imobilizado"},
    "1505": {"débito": "2.1.01", "crédito": "1.2.1.01", "descricao": "Devolução de venda de bem do ativo imobilizado"},
    # --- Entrada: outras ---
    "1903": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Entrada de mercadoria de terceiros"},
    "1949": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Outra entrada de mercadoria"},
    # --- Saída: vendas de mercadorias (estoque) ---
    "5101": {"débito": "2.1.01", "crédito": "3.2.01", "descricao": "Venda de produção do estabelecimento"},
    "5102": {"débito": "2.1.01", "crédito": "3.2.01", "descricao": "Venda de mercadoria adquirida de terceiros"},
    "5103": {"débito": "2.1.01", "crédito": "3.2.01", "descricao": "Venda de produção"},
    "5104": {"débito": "2.1.01", "crédito": "3.2.01", "descricao": "Venda de mercadoria"},
    "5111": {"débito": "2.1.01", "crédito": "3.2.01", "descricao": "Venda de produção"},
    "5112": {"débito": "2.1.01", "crédito": "3.2.01", "descricao": "Venda de mercadoria"},
    "5405": {"débito": "2.1.01", "crédito": "3.2.01", "descricao": "Venda de mercadoria"},
    # --- Saída: vendas de ativo imobilizado ---
    "5501": {"débito": "2.1.01", "crédito": "1.2.1.01", "descricao": "Venda de bem do ativo imobilizado"},
    "5502": {"débito": "2.1.01", "crédito": "1.2.1.01", "descricao": "Venda de bem do ativo imobilizado"},
    "5551": {"débito": "2.1.01", "crédito": "1.2.1.01", "descricao": "Venda de bem do ativo imobilizado"},
    # --- Saída: devoluções de compra (estorno) ---
    "5201": {"débito": "2.1.01", "crédito": "1.1.3.01", "descricao": "Devolução de compra de mercadoria"},
    "5202": {"débito": "2.1.01", "crédito": "1.1.3.01", "descricao": "Devolução de compra de mercadoria"},
    "5251": {"débito": "2.1.01", "crédito": "1.2.1.01", "descricao": "Devolução de compra de ativo imobilizado"},
    "5252": {"débito": "2.1.01", "crédito": "1.2.1.01", "descricao": "Devolução de compra de ativo imobilizado"},
    # --- Saída: serviços ---
    "5933": {"débito": "2.1.01", "crédito": "3.2.02", "descricao": "Prestação de serviço"},
    "5934": {"débito": "2.1.01", "crédito": "3.2.02", "descricao": "Prestação de serviço"},
    "5935": {"débito": "2.1.01", "crédito": "3.2.02", "descricao": "Prestação de serviço"},
    # --- Saída: outras ---
    "5949": {"débito": "2.1.01", "crédito": "3.2.01", "descricao": "Outra saída de mercadoria"},
    # --- Default ---
    "_default": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Compra genérica"},
}

# Mapeamento por categoria contábil (fallback para CFOPs não explicitamente mapeados).
# Cobre todos os 369 CFOPs oficiais via categoria_contabil_cfop().
MAPEAMENTO_CATEGORIA = {
    "estoque": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Mercadorias para comercialização"},
    "ativo": {"débito": "1.2.1.01", "crédito": "2.1.01", "descricao": "Aquisição de ativo imobilizado"},
    "consumo": {"débito": "3.1.01", "crédito": "2.1.01", "descricao": "Material de uso e consumo"},
    "servico": {"débito": "3.1.02", "crédito": "2.1.01", "descricao": "Aquisição de serviços"},
    "devolucao": {"débito": "2.1.01", "crédito": "1.1.3.01", "descricao": "Devolução de mercadoria"},
    "generico": {"débito": "1.1.3.01", "crédito": "2.1.01", "descricao": "Operação genérica"},
}

# Contas de impostos
CONTAS_IMPOSTOS = {
    "icms": "2.2.01",
    "icms_st": "2.2.02",
    "ipi": "2.2.03",
    "pis": "2.2.04",
    "cofins": "2.2.05",
    "ibscbs": "2.2.06",
}


class GeradorLancamentos:
    """Gera lançamentos contábeis a partir de NF-e reconciliadas."""

    def __init__(self, session: Session | None = None):
        self.session = session or SessionClass()
        self._own_session = session is None

    def close(self):
        if self._own_session:
            self.session.close()

    def _garantir_plano_contas(self):
        """Cria contas do plano de contas se não existirem."""
        contas = [
            ("1.1.3.01", "Estoque de Mercadorias", "ativo", "1.1.3", "devedora"),
            ("1.2.1.01", "Ativo Imobilizado", "ativo", "1.2.1", "devedora"),
            ("2.1.01", "Fornecedores", "passivo", "2.1", "credora"),
            ("2.2.01", "ICMS a Recuperar", "ativo", "2.2", "devedora"),
            ("2.2.02", "ICMS ST a Recuperar", "ativo", "2.2", "devedora"),
            ("2.2.03", "IPI a Recuperar", "ativo", "2.2", "devedora"),
            ("2.2.04", "PIS a Recuperar", "ativo", "2.2", "devedora"),
            ("2.2.05", "COFINS a Recuperar", "ativo", "2.2", "devedora"),
            ("2.2.06", "IBS/CBS a Recuperar", "ativo", "2.2", "devedora"),
            ("3.1.01", "Material de Consumo", "despesa", "3.1", "devedora"),
            ("3.1.02", "Despesas com Servicos", "despesa", "3.1", "devedora"),
            ("3.2.01", "Receita de Vendas", "receita", "3.2", "credora"),
            ("3.2.02", "Receita de Servicos", "receita", "3.2", "credora"),
        ]
        for codigo, nome, tipo, pai, natureza in contas:
            existente = self.session.query(PlanoContas).filter_by(codigo_referencial=codigo).first()
            if not existente:
                self.session.add(PlanoContas(
                    codigo_referencial=codigo, nome=nome, tipo=tipo,
                    conta_pai=pai, natureza=natureza,
                ))
        self.session.commit()

    def _gerar_lancamento_principal(self, nfe: Nfe) -> LancamentoContabil:
        """Gera o lançamento principal (débito estoque/ativo, crédito fornecedor)."""
        cfop = nfe.itens[0].cfop if nfe.itens else None
        mapeamento = MAPEAMENTO_CFOP.get(cfop)
        if not mapeamento:
            # Fallback por categoria contábil (cobre todos os 369 CFOPs oficiais)
            categoria = categoria_contabil_cfop(cfop) if cfop else "generico"
            mapeamento = MAPEAMENTO_CATEGORIA.get(categoria, MAPEAMENTO_CFOP["_default"])
            logger.info(
                f"CFOP {cfop} não mapeado explicitamente, usando categoria '{categoria}' "
                f"para NF-e {nfe.chave_acesso[:20]}..."
            )

        # Usa a data de emissão da NF-e, não a data atual
        if nfe.data_emissao:
            data_lanc = nfe.data_emissao.date() if hasattr(nfe.data_emissao, 'date') else nfe.data_emissao
        else:
            data_lanc = date.today()

        return LancamentoContabil(
            nfe_id=nfe.id,
            data_lancamento=data_lanc,
            numero_documento=str(nfe.numero_nota),
            historico=f"{mapeamento['descricao']} - NF-e {nfe.numero_nota} - {nfe.emitente.nome if nfe.emitente else ''}",
            conta_debito_codigo=mapeamento["débito"],
            conta_credito_codigo=mapeamento["crédito"],
            valor=Decimal(str(nfe.valor_total)),
        )

    def _gerar_lancamentos_impostos(self, nfe: Nfe) -> list[LancamentoContabil]:
        """Gera lançamentos de recuperação de impostos por item."""
        lancamentos = []
        total_icms = Decimal("0")
        total_icms_st = Decimal("0")
        total_ipi = Decimal("0")
        total_pis = Decimal("0")
        total_cofins = Decimal("0")
        total_ibscbs = Decimal("0")

        for item in nfe.itens:
            if item.vicms:
                total_icms += Decimal(str(item.vicms))
            if item.vicms_st:
                total_icms_st += Decimal(str(item.vicms_st))
            if item.vipi:
                total_ipi += Decimal(str(item.vipi))
            if item.vpis:
                total_pis += Decimal(str(item.vpis))
            if item.vcofins:
                total_cofins += Decimal(str(item.vcofins))
            if item.vibscbs:
                total_ibscbs += Decimal(str(item.vibscbs))

        impostos = [
            ("icms", total_icms, "ICMS a Recuperar"),
            ("icms_st", total_icms_st, "ICMS ST a Recuperar"),
            ("ipi", total_ipi, "IPI a Recuperar"),
            ("pis", total_pis, "PIS a Recuperar"),
            ("cofins", total_cofins, "COFINS a Recuperar"),
            ("ibscbs", total_ibscbs, "IBS/CBS a Recuperar"),
        ]

        for nome, valor, descricao in impostos:
            if valor > 0:
                if nfe.data_emissao:
                    data_lanc = nfe.data_emissao.date() if hasattr(nfe.data_emissao, 'date') else nfe.data_emissao
                else:
                    data_lanc = date.today()
                lancamentos.append(LancamentoContabil(
                    nfe_id=nfe.id,
                    data_lancamento=data_lanc,
                    numero_documento=str(nfe.numero_nota),
                    historico=f"{descricao} - NF-e {nfe.numero_nota}",
                    conta_debito_codigo=CONTAS_IMPOSTOS[nome],
                    conta_credito_codigo="2.1.01",  # Fornecedores
                    valor=valor,
                ))

        return lancamentos

    def gerar_para_nfe(self, nfe: Nfe) -> list[LancamentoContabil]:
        """Gera todos os lançamentos contábeis para uma NF-e."""
        # Verifica se já tem lançamentos
        existentes = self.session.query(LancamentoContabil).filter_by(nfe_id=nfe.id).count()
        if existentes > 0:
            logger.info(f"NF-e {nfe.chave_acesso[:20]}... já tem {existentes} lançamentos, pulando")
            return []

        # Verifica se a reconciliação está matched
        rec = self.session.query(Reconciliacao).filter_by(nfe_id=nfe.id).first()
        if rec and rec.status != "matched":
            logger.info(f"NF-e {nfe.chave_acesso[:20]}... reconciliação {rec.status}, não gera lançamento")
            return []

        if nfe.status_autorizacao == "cancelada":
            logger.info(f"NF-e {nfe.chave_acesso[:20]}... cancelada, não gera lançamento")
            return []

        self._garantir_plano_contas()

        lancamentos = []
        lanc_principal = self._gerar_lancamento_principal(nfe)
        self.session.add(lanc_principal)
        lancamentos.append(lanc_principal)

        lanc_impostos = self._gerar_lancamentos_impostos(nfe)
        for l in lanc_impostos:
            self.session.add(l)
            lancamentos.append(l)

        self.session.commit()
        logger.info(f"NF-e {nfe.chave_acesso[:20]}...: {len(lancamentos)} lançamentos gerados")
        return lancamentos

    def gerar_todos(self) -> dict:
        """Gera lançamentos para todas as NF-e reconciliadas como matched."""
        stats = {"notas_processadas": 0, "lancamentos_gerados": 0, "notas_puladas": 0, "estornos": 0, "erros": 0}

        # Primeiro: estorna lançamentos de notas canceladas (apenas notas da SEFAZ)
        canceladas = self.session.query(Nfe).filter(
            Nfe.status_autorizacao == "cancelada",
            Nfe.origem == "sefaz",
        ).all()
        for nfe in canceladas:
            try:
                estornos = self.estornar_nfe(nfe)
                stats["estornos"] += estornos
            except Exception as e:
                self.session.rollback()
                logger.error(f"Erro ao estornar NF-e {nfe.chave_acesso[:20]}...: {e}")
                stats["erros"] += 1

        # Depois: gera lançamentos para notas autorizadas (SEFAZ) e sintéticas matched
        # Notas sintéticas têm status "sintética" mas podem ter reconciliação matched
        notas = self.session.query(Nfe).filter(
            Nfe.status_autorizacao.in_(["autorizada", "sintética"]),
        ).all()

        for nfe in notas:
            try:
                lancs = self.gerar_para_nfe(nfe)
                if lancs:
                    stats["notas_processadas"] += 1
                    stats["lancamentos_gerados"] += len(lancs)
                else:
                    stats["notas_puladas"] += 1
            except Exception as e:
                self.session.rollback()
                logger.error(f"Erro ao gerar lançamentos para NF-e {nfe.chave_acesso[:20]}...: {e}")
                stats["erros"] += 1

        return stats

    def estornar_nfe(self, nfe: Nfe) -> int:
        """Estorna todos os lancamentos contabeis de uma NF-e cancelada.

        Cria lancamentos de estorno com debito/credito invertidos.
        """
        lancamentos = self.session.query(LancamentoContabil).filter_by(
            nfe_id=nfe.id, estornado=False
        ).all()

        if not lancamentos:
            return 0

        if nfe.data_emissao:
            data_estorno = nfe.data_emissao.date() if hasattr(nfe.data_emissao, 'date') else nfe.data_emissao
        else:
            data_estorno = date.today()

        count = 0
        for lanc in lancamentos:
            # Marca original como estornado
            lanc.estornado = True

            # Cria lançamento de estorno (débito/crédito invertidos)
            estorno = LancamentoContabil(
                nfe_id=nfe.id,
                data_lancamento=data_estorno,
                numero_documento=str(nfe.numero_nota),
                historico=f"ESTORNO - {lanc.historico}",
                conta_debito_codigo=lanc.conta_credito_codigo,
                conta_credito_codigo=lanc.conta_debito_codigo,
                valor=lanc.valor,
                estornado=False,
                lancamento_estorno_id=lanc.id,
            )
            self.session.add(estorno)
            count += 1

        self.session.commit()
        logger.info(f"NF-e {nfe.chave_acesso[:20]}...: {count} lançamentos estornados")
        return count


def executar_lancamentos() -> dict:
    """Função de conveniência para gerar lançamentos (chamada pela API)."""
    gerador = GeradorLancamentos()
    try:
        return gerador.gerar_todos()
    finally:
        gerador.close()
