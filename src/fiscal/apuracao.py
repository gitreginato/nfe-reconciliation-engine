"""Apuração mensal de impostos.

Fecha o período (mês/ano) e calcula o total a recolher por imposto,
considerando:
- Créditos: impostos recuperáveis das entradas (compras)
- Débitos: impostos gerados nas saídas (vendas)
- Saldo: débitos - créditos (se positivo, a recolher; se negativo, a compensar)

Baseado em:
- LC 87/1991 (Lei Kandir) para ICMS
- Lei 10.637/02 (PIS) e Lei 10.833/03 (COFINS)
- RIPI (Decreto 7.212/2010) para IPI
- IN RFB 2.003/2021 para prazos de ECD

A apuração é determinística: lê os tributos persistidos nas NF-e do período
e soma. Não inventa valores nem consulta fontes externas.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from src.persistencia.models import Nfe, NfeItem

logger = logging.getLogger(__name__)


@dataclass
class ApuracaoImposto:
    """Resultado da apuração de um imposto em um período."""
    imposto: str
    creditos: Decimal = Decimal("0")
    debitos: Decimal = Decimal("0")
    saldo_a_recolher: Decimal = Decimal("0")
    saldo_a_compensar: Decimal = Decimal("0")
    notas_entrada: int = 0
    notas_saida: int = 0
    valor_contabil_entradas: Decimal = Decimal("0")
    valor_contabil_saidas: Decimal("0") = Decimal("0")

    def calcular_saldo(self):
        """Calcula o saldo final (débitos - créditos)."""
        diff = self.debitos - self.creditos
        if diff > 0:
            self.saldo_a_recolher = diff
            self.saldo_a_compensar = Decimal("0")
        else:
            self.saldo_a_recolher = Decimal("0")
            self.saldo_a_compensar = abs(diff)


@dataclass
class ApuracaoMensal:
    """Resultado da apuração mensal completa."""
    periodo: str  # YYYY-MM
    data_inicio: date
    data_fim: date
    icms: ApuracaoImposto = None
    icms_st: ApuracaoImposto = None
    ipi: ApuracaoImposto = None
    pis: ApuracaoImposto = None
    cofins: ApuracaoImposto = None
    ibs_cbs: ApuracaoImposto = None
    total_a_recolher: Decimal = Decimal("0")
    alertas: list[str] = field(default_factory=list)


def _soma_tributo_entradas(
    session: Session, campo: str, data_inicio: date, data_fim: date
) -> tuple[Decimal, int, Decimal]:
    """Soma um tributo das notas de entrada (tipo_operacao='0') no período.

    Returns:
        (soma_tributo, num_notas, valor_contabil)
    """
    q = session.query(
        func.coalesce(func.sum(getattr(NfeItem, campo)), 0),
        func.count(func.distinct(NfeItem.nfe_id)),
    ).join(Nfe).filter(
        Nfe.tipo_operacao == "0",
        Nfe.status_autorizacao.in_(["autorizada", "sintética"]),
        Nfe.data_emissao >= data_inicio,
        Nfe.data_emissao < data_fim + timedelta(days=1),
    )
    soma, num_notas = q.first()
    # Valor contábil
    v = session.query(
        func.coalesce(func.sum(Nfe.valor_total), 0)
    ).filter(
        Nfe.tipo_operacao == "0",
        Nfe.status_autorizacao.in_(["autorizada", "sintética"]),
        Nfe.data_emissao >= data_inicio,
        Nfe.data_emissao < data_fim + timedelta(days=1),
    ).scalar()
    return Decimal(str(soma)), int(num_notas), Decimal(str(v))


def _soma_tributo_saidas(
    session: Session, campo: str, data_inicio: date, data_fim: date
) -> tuple[Decimal, int, Decimal]:
    """Soma um tributo das notas de saída (tipo_operacao='1') no período."""
    q = session.query(
        func.coalesce(func.sum(getattr(NfeItem, campo)), 0),
        func.count(func.distinct(NfeItem.nfe_id)),
    ).join(Nfe).filter(
        Nfe.tipo_operacao == "1",
        Nfe.status_autorizacao.in_(["autorizada", "sintética"]),
        Nfe.data_emissao >= data_inicio,
        Nfe.data_emissao < data_fim + timedelta(days=1),
    )
    soma, num_notas = q.first()
    v = session.query(
        func.coalesce(func.sum(Nfe.valor_total), 0)
    ).filter(
        Nfe.tipo_operacao == "1",
        Nfe.status_autorizacao.in_(["autorizada", "sintética"]),
        Nfe.data_emissao >= data_inicio,
        Nfe.data_emissao < data_fim + timedelta(days=1),
    ).scalar()
    return Decimal(str(soma)), int(num_notas), Decimal(str(v))


def apurar_mes(session: Session, ano: int, mes: int) -> ApuracaoMensal:
    """Apura todos os impostos de um mês específico.

    Args:
        session: Sessão do banco
        ano: Ano (ex.: 2026)
        mes: Mês (1-12)

    Returns:
        ApuracaoMensal com créditos, débitos e saldos por imposto
    """
    if mes < 1 or mes > 12:
        raise ValueError("Mês deve estar entre 1 e 12")
    if ano < 2000 or ano > 2100:
        raise ValueError("Ano inválido")

    data_inicio = date(ano, mes, 1)
    # Último dia do mês
    if mes == 12:
        data_fim = date(ano, 12, 31)
    else:
        data_fim = date(ano, mes + 1, 1) - timedelta(days=1)

    periodo = f"{ano:04d}-{mes:02d}"
    resultado = ApuracaoMensal(
        periodo=periodo, data_inicio=data_inicio, data_fim=data_fim
    )
    alertas = []

    # ICMS
    cred_icms, n_ent, v_ent = _soma_tributo_entradas(session, "vicms", data_inicio, data_fim)
    deb_icms, n_sai, v_sai = _soma_tributo_saidas(session, "vicms", data_inicio, data_fim)
    icms = ApuracaoImposto(imposto="ICMS")
    icms.creditos = cred_icms
    icms.debitos = deb_icms
    icms.notas_entrada = n_ent
    icms.notas_saida = n_sai
    icms.valor_contabil_entradas = v_ent
    icms.valor_contabil_saidas = v_sai
    icms.calcular_saldo()
    resultado.icms = icms

    # ICMS-ST
    cred_st, _, _ = _soma_tributo_entradas(session, "vicms_st", data_inicio, data_fim)
    deb_st, _, _ = _soma_tributo_saidas(session, "vicms_st", data_inicio, data_fim)
    st = ApuracaoImposto(imposto="ICMS-ST")
    st.creditos = cred_st
    st.debitos = deb_st
    st.calcular_saldo()
    resultado.icms_st = st

    # IPI
    cred_ipi, _, _ = _soma_tributo_entradas(session, "vipi", data_inicio, data_fim)
    deb_ipi, _, _ = _soma_tributo_saidas(session, "vipi", data_inicio, data_fim)
    ipi = ApuracaoImposto(imposto="IPI")
    ipi.creditos = cred_ipi
    ipi.debitos = deb_ipi
    ipi.calcular_saldo()
    resultado.ipi = ipi

    # PIS
    cred_pis, _, _ = _soma_tributo_entradas(session, "vpis", data_inicio, data_fim)
    deb_pis, _, _ = _soma_tributo_saidas(session, "vpis", data_inicio, data_fim)
    pis = ApuracaoImposto(imposto="PIS")
    pis.creditos = cred_pis
    pis.debitos = deb_pis
    pis.calcular_saldo()
    resultado.pis = pis

    # COFINS
    cred_cofins, _, _ = _soma_tributo_entradas(session, "vcofins", data_inicio, data_fim)
    deb_cofins, _, _ = _soma_tributo_saidas(session, "vcofins", data_inicio, data_fim)
    cofins = ApuracaoImposto(imposto="COFINS")
    cofins.creditos = cred_cofins
    cofins.debitos = deb_cofins
    cofins.calcular_saldo()
    resultado.cofins = cofins

    # IBS/CBS
    cred_ibs, _, _ = _soma_tributo_entradas(session, "vibscbs", data_inicio, data_fim)
    deb_ibs, _, _ = _soma_tributo_saidas(session, "vibscbs", data_inicio, data_fim)
    ibs = ApuracaoImposto(imposto="IBS/CBS")
    ibs.creditos = cred_ibs
    ibs.debitos = deb_ibs
    ibs.calcular_saldo()
    resultado.ibs_cbs = ibs
    if cred_ibs > 0 or deb_ibs > 0:
        alertas.append(
            "IBS/CBS em fase educativa em 2026: valores calculados mas sem recolhimento"
        )

    # Total a recolher
    resultado.total_a_recolher = (
        icms.saldo_a_recolher + st.saldo_a_recolher + ipi.saldo_a_recolher +
        pis.saldo_a_recolher + cofins.saldo_a_recolher + ibs.saldo_a_recolher
    )

    resultado.alertas = alertas
    logger.info(
        "Apuração %s: ICMS a recolher=%s, IPI=%s, PIS=%s, COFINS=%s, total=%s",
        periodo, icms.saldo_a_recolher, ipi.saldo_a_recolher,
        pis.saldo_a_recolher, cofins.saldo_a_recolher, resultado.total_a_recolher,
    )
    return resultado


def apurar_mes_dict(session: Session, ano: int, mes: int) -> dict:
    """Apura e retorna como dict (para API JSON)."""
    r = apurar_mes(session, ano, mes)

    def imp_dict(imp: Optional[ApuracaoImposto]) -> dict:
        if imp is None:
            return None
        return {
            "creditos": float(imp.creditos),
            "debitos": float(imp.debitos),
            "saldo_a_recolher": float(imp.saldo_a_recolher),
            "saldo_a_compensar": float(imp.saldo_a_compensar),
            "notas_entrada": imp.notas_entrada,
            "notas_saida": imp.notas_saida,
            "valor_contabil_entradas": float(imp.valor_contabil_entradas),
            "valor_contabil_saidas": float(imp.valor_contabil_saidas),
        }

    return {
        "periodo": r.periodo,
        "data_inicio": r.data_inicio.isoformat(),
        "data_fim": r.data_fim.isoformat(),
        "icms": imp_dict(r.icms),
        "icms_st": imp_dict(r.icms_st),
        "ipi": imp_dict(r.ipi),
        "pis": imp_dict(r.pis),
        "cofins": imp_dict(r.cofins),
        "ibs_cbs": imp_dict(r.ibs_cbs),
        "total_a_recolher": float(r.total_a_recolher),
        "alertas": r.alertas,
    }
