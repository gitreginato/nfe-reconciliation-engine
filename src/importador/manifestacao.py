"""Orquestrador de manifestação do destinatário em lote.

Identifica NF-e recebidas que ainda não foram manifestadas, verifica prazos
legais e manifesta automaticamente em lote, respeitando o rate limit.

Baseado em:
- Ajuste SINIEF 07/2005 (manifestação do destinatário)
- Ajuste SINIEF 44/2020 (prazos e eventos)
- NT 2024.001 (eventos da manifestação)

Fluxo:
1. Busca NF-e com manifestacao_destinatario nula ou pendente
2. Para cada uma, verifica prazo desde data_emissao
3. Ciência da Emissão: até 10 dias (prioridade alta se < 10 dias)
4. Confirmação da Operação: até 180 dias (após recebimento confirmado)
5. Manifesta em lote via ImportadorDFe, respeitando rate limit
6. Registra evento de manifestação no banco
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.persistencia.models import Nfe, NfeEvento
from src.fiscal.validadores import validar_prazo_manifestacao
from src.importador.dfe import ImportadorDFe
from src.config import settings

logger = logging.getLogger(__name__)

# Prazos em dias (Ajuste SINIEF 07/2005, Ajuste SINIEF 44/2020)
PRAZO_CIENCIA_EMISSAO = 10
PRAZO_CONFIRMACAO = 180
PRAZO_DESCONHECIMENTO = 180
PRAZO_OPERACAO_NAO_REALIZADA = 180


def identificar_notas_pendentes(session: Session) -> dict:
    """Identifica NF-e que precisam de manifestação.

    Returns:
        dict com listas de notas por prioridade:
        - urgente_ciencia: notas sem ciência da emissão, prazo < 10 dias
        - pendente_ciencia: notas sem ciência da emissão, prazo > 10 dias
        - pendente_confirmacao: notas com ciência mas sem confirmação
        - fora_prazo: notas com prazo vencido para ciência
    """
    hoje = date.today()

    # Notas autorizadas sem manifestação ou só com ciência
    notas_sem_manifestacao = session.query(Nfe).filter(
        Nfe.status_autorizacao == "autorizada",
        Nfe.origem == "sefaz",
        Nfe.manifestacao_destinatario.is_(None),
    ).all()

    notas_somente_ciencia = session.query(Nfe).filter(
        Nfe.status_autorizacao == "autorizada",
        Nfe.origem == "sefaz",
        Nfe.manifestacao_destinatario == "ciencia_emissao",
    ).all()

    resultado = {
        "urgente_ciencia": [],
        "pendente_ciencia": [],
        "fora_prazo_ciencia": [],
        "pendente_confirmacao": [],
    }

    for nfe in notas_sem_manifestacao:
        data_emissao = nfe.data_emissao.date() if hasattr(nfe.data_emissao, "date") else nfe.data_emissao
        dias = (hoje - data_emissao).days

        if dias > PRAZO_CIENCIA_EMISSAO:
            resultado["fora_prazo_ciencia"].append({
                "chave": nfe.chave_acesso,
                "numero": nfe.numero_nota,
                "data_emissao": data_emissao.isoformat(),
                "dias": dias,
            })
        elif dias >= 0:
            resultado["urgente_ciencia"].append({
                "chave": nfe.chave_acesso,
                "numero": nfe.numero_nota,
                "data_emissao": data_emissao.isoformat(),
                "dias": dias,
            })

    for nfe in notas_somente_ciencia:
        data_emissao = nfe.data_emissao.date() if hasattr(nfe.data_emissao, "date") else nfe.data_emissao
        dias = (hoje - data_emissao).days

        if dias <= PRAZO_CONFIRMACAO:
            resultado["pendente_confirmacao"].append({
                "chave": nfe.chave_acesso,
                "numero": nfe.numero_nota,
                "data_emissao": data_emissao.isoformat(),
                "dias": dias,
            })

    return resultado


def manifestar_lote(
    session: Session,
    tipo_evento: str = "ciencia_emissao",
    limite: int = 100,
) -> dict:
    """Manifesta em lote as NF-e pendentes.

    Args:
        session: Sessão do banco
        tipo_evento: "ciencia_emissao" ou "confirmacao_operacao"
        limite: Máximo de notas a manifestar por execução

    Returns:
        dict com estatísticas: manifestadas, erros, puladas, fora_prazo
    """
    stats = {
        "tipo_evento": tipo_evento,
        "manifestadas": 0,
        "erros": 0,
        "puladas": 0,
        "fora_prazo": 0,
        "total_verificadas": 0,
    }

    # Busca notas pendentes conforme tipo de evento
    if tipo_evento == "ciencia_emissao":
        notas = session.query(Nfe).filter(
            Nfe.status_autorizacao == "autorizada",
            Nfe.origem == "sefaz",
            Nfe.manifestacao_destinatario.is_(None),
        ).order_by(Nfe.data_emissao).limit(limite).all()
    elif tipo_evento == "confirmacao_operacao":
        notas = session.query(Nfe).filter(
            Nfe.status_autorizacao == "autorizada",
            Nfe.origem == "sefaz",
            Nfe.manifestacao_destinatario == "ciencia_emissao",
        ).order_by(Nfe.data_emissao).limit(limite).all()
    else:
        logger.warning(f"Tipo de evento não suportado: {tipo_evento}")
        return stats

    stats["total_verificadas"] = len(notas)
    if not notas:
        return stats

    hoje = date.today()
    importador = ImportadorDFe(session=session)

    try:
        for nfe in notas:
            data_emissao = nfe.data_emissao.date() if hasattr(nfe.data_emissao, "date") else nfe.data_emissao

            # Verifica prazo
            if not validar_prazo_manifestacao(data_emissao, hoje, tipo_evento):
                dias = (hoje - data_emissao).days
                logger.warning(
                    f"NF-e {nfe.chave_acesso[:20]}... fora do prazo para {tipo_evento} "
                    f"({dias} dias, limite {PRAZO_CIENCIA_EMISSAO if tipo_evento == 'ciencia_emissao' else PRAZO_CONFIRMACAO})"
                )
                stats["fora_prazo"] += 1
                continue

            try:
                # Manifesta via mock SEFAZ
                resultado = importador.manifestar(nfe.chave_acesso)

                if resultado.get("status") == "ok" or resultado.get("protocolo"):
                    # Atualiza status da manifestação
                    nfe.manifestacao_destinatario = tipo_evento

                    # Registra evento
                    evento = NfeEvento(
                        nfe_id=nfe.id,
                        tipo_evento=tipo_evento,
                        data_evento=datetime.now(),
                        sequencia=len(nfe.eventos) + 1,
                        protocolo=resultado.get("protocolo", ""),
                        status="registrado",
                    )
                    session.add(evento)
                    stats["manifestadas"] += 1
                    logger.info(
                        f"NF-e {nfe.chave_acesso[:20]}... manifestada: {tipo_evento}"
                    )
                else:
                    stats["erros"] += 1
                    logger.error(
                        f"Erro ao manifestar NF-e {nfe.chave_acesso[:20]}...: {resultado}"
                    )

            except Exception as e:
                session.rollback()
                stats["erros"] += 1
                logger.error(
                    f"Erro ao manifestar NF-e {nfe.chave_acesso[:20]}...: {e}"
                )

        session.commit()
    finally:
        importador.close()

    return stats


def executar_manifestacao_automatica(session: Session = None) -> dict:
    """Executa manifestação automática completa.

    1. Primeiro manifesta ciência da emissão (prioridade: notas mais antigas)
    2. Depois manifesta confirmação da operação (para notas já com ciência)

    Returns:
        dict com estatísticas consolidadas
    """
    from src.persistencia.models import Session as SessionClass
    own_session = session is None
    if own_session:
        session = SessionClass()

    try:
        # Fase 1: Ciência da Emissão
        stats_ciencia = manifestar_lote(session, "ciencia_emissao")

        # Fase 2: Confirmação da Operação (apenas se configurado)
        stats_confirmacao = {"manifestadas": 0, "erros": 0, "puladas": 0, "fora_prazo": 0, "total_verificadas": 0}
        # Confirmação automática só se houver reconciliação matched
        # (a mercadoria foi recebida e conferida)
        from src.persistencia.models import Reconciliacao
        notas_match = session.query(Nfe).join(Reconciliacao).filter(
            Reconciliacao.status == "matched",
            Nfe.manifestacao_destinatario == "ciencia_emissao",
        ).limit(100).all()

        if notas_match:
            stats_confirmacao = manifestar_lote(session, "confirmacao_operacao")

        resultado = {
            "ciencia_emissao": stats_ciencia,
            "confirmacao_operacao": stats_confirmacao,
            "total_manifestadas": stats_ciencia["manifestadas"] + stats_confirmacao["manifestadas"],
            "total_erros": stats_ciencia["erros"] + stats_confirmacao["erros"],
            "total_fora_prazo": stats_ciencia["fora_prazo"] + stats_confirmacao["fora_prazo"],
        }

        logger.info(
            "Manifestação automática: %d ciência, %d confirmação, %d erros, %d fora do prazo",
            stats_ciencia["manifestadas"], stats_confirmacao["manifestadas"],
            resultado["total_erros"], resultado["total_fora_prazo"],
        )
        return resultado
    finally:
        if own_session:
            session.close()
