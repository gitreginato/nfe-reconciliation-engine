"""Testes da manifestação do destinatário automatizada em lote."""
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistencia.models import Base, Nfe, NfeItem, Participante, NfeEvento, Reconciliacao
from src.importador.manifestacao import (
    identificar_notas_pendentes,
    manifestar_lote,
    executar_manifestacao_automatica,
    PRAZO_CIENCIA_EMISSAO,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _criar_nfe(session, manifestacao=None, data_emissao=None, chave_suffix="01",
               status="autorizada", origem="sefaz"):
    """Cria uma NF-e para teste de manifestação."""
    if data_emissao is None:
        data_emissao = datetime.now() - timedelta(days=5)

    emit = session.query(Participante).filter_by(cnpj_cpf="11222333000144").first()
    if not emit:
        emit = Participante(cnpj_cpf="11222333000144", nome="Emitente")
        session.add(emit)
    dest = session.query(Participante).filter_by(cnpj_cpf="12345678000190").first()
    if not dest:
        dest = Participante(cnpj_cpf="12345678000190", nome="Destinatario")
        session.add(dest)
    session.flush()

    nfe = Nfe(
        chave_acesso=f"352008112223330001445500100000000{chave_suffix}0000000{chave_suffix}",
        numero_nota=int(chave_suffix),
        serie=1, modelo="55",
        data_emissao=data_emissao,
        tipo_operacao="0",
        valor_total=Decimal("1000.00"),
        status_autorizacao=status,
        origem=origem,
        manifestacao_destinatario=manifestacao,
        emitente_id=emit.id,
        destinatario_id=dest.id,
    )
    session.add(nfe)
    session.commit()
    return nfe


class TestIdentificarNotasPendentes:
    def test_sem_notas(self, session):
        r = identificar_notas_pendentes(session)
        assert r["urgente_ciencia"] == []
        assert r["fora_prazo_ciencia"] == []
        assert r["pendente_confirmacao"] == []

    def test_nota_recente_sem_manifestacao(self, session):
        _criar_nfe(session, manifestacao=None, data_emissao=datetime.now() - timedelta(days=3))
        r = identificar_notas_pendentes(session)
        assert len(r["urgente_ciencia"]) == 1
        assert r["fora_prazo_ciencia"] == []

    def test_nota_antiga_sem_manifestacao(self, session):
        _criar_nfe(session, manifestacao=None, data_emissao=datetime.now() - timedelta(days=30))
        r = identificar_notas_pendentes(session)
        assert r["urgente_ciencia"] == []
        assert len(r["fora_prazo_ciencia"]) == 1

    def test_nota_com_ciencia_pendente_confirmacao(self, session):
        _criar_nfe(session, manifestacao="ciencia_emissao", data_emissao=datetime.now() - timedelta(days=20))
        r = identificar_notas_pendentes(session)
        assert len(r["pendente_confirmacao"]) == 1

    def test_nota_cancelada_nao_conta(self, session):
        _criar_nfe(session, manifestacao=None, status="cancelada")
        r = identificar_notas_pendentes(session)
        assert r["urgente_ciencia"] == []

    def test_nota_sintetica_nao_conta(self, session):
        _criar_nfe(session, manifestacao=None, origem="sintetica")
        r = identificar_notas_pendentes(session)
        assert r["urgente_ciencia"] == []


class TestManifestarLote:
    @patch("src.importador.manifestacao.ImportadorDFe")
    def test_manifestar_ciencia_emissao(self, mock_importador_cls, session):
        _criar_nfe(session, manifestacao=None, data_emissao=datetime.now() - timedelta(days=3),
                   chave_suffix="01")

        # Mock do importador
        mock_importador = MagicMock()
        mock_importador.manifestar.return_value = {"status": "ok", "protocolo": "123456789012345"}
        mock_importador.close = MagicMock()
        mock_importador_cls.return_value = mock_importador

        stats = manifestar_lote(session, "ciencia_emissao")
        assert stats["manifestadas"] == 1
        assert stats["erros"] == 0

        # Verifica que a NF-e foi atualizada
        nfe = session.query(Nfe).first()
        assert nfe.manifestacao_destinatario == "ciencia_emissao"

        # Verifica que o evento foi registrado
        eventos = session.query(NfeEvento).filter_by(nfe_id=nfe.id).all()
        assert len(eventos) == 1
        assert eventos[0].tipo_evento == "ciencia_emissao"

    @patch("src.importador.manifestacao.ImportadorDFe")
    def test_manifestar_fora_prazo(self, mock_importador_cls, session):
        _criar_nfe(session, manifestacao=None, data_emissao=datetime.now() - timedelta(days=30),
                   chave_suffix="01")

        mock_importador = MagicMock()
        mock_importador_cls.return_value = mock_importador

        stats = manifestar_lote(session, "ciencia_emissao")
        assert stats["manifestadas"] == 0
        assert stats["fora_prazo"] == 1

    @patch("src.importador.manifestacao.ImportadorDFe")
    def test_manifestar_sem_notas(self, mock_importador_cls, session):
        mock_importador = MagicMock()
        mock_importador_cls.return_value = mock_importador

        stats = manifestar_lote(session, "ciencia_emissao")
        assert stats["manifestadas"] == 0
        assert stats["total_verificadas"] == 0

    @patch("src.importador.manifestacao.ImportadorDFe")
    def test_manifestar_erro(self, mock_importador_cls, session):
        _criar_nfe(session, manifestacao=None, data_emissao=datetime.now() - timedelta(days=3),
                   chave_suffix="01")

        mock_importador = MagicMock()
        mock_importador.manifestar.side_effect = Exception("Erro de rede")
        mock_importador_cls.return_value = mock_importador

        stats = manifestar_lote(session, "ciencia_emissao")
        assert stats["erros"] == 1
        assert stats["manifestadas"] == 0


class TestExecutarManifestacaoAutomatica:
    @patch("src.importador.manifestacao.manifestar_lote")
    def test_executa_duas_fases(self, mock_manifestar, session):
        # Cria nota com ciência e reconciliação matched para disparar fase 2
        nfe = _criar_nfe(session, manifestacao="ciencia_emissao",
                         data_emissao=datetime.now() - timedelta(days=20),
                         chave_suffix="01")
        rec = Reconciliacao(nfe_id=nfe.id, status="matched", matched_by="automatico")
        session.add(rec)
        session.commit()

        mock_manifestar.side_effect = [
            {"manifestadas": 5, "erros": 0, "puladas": 0, "fora_prazo": 0, "total_verificadas": 5},
            {"manifestadas": 2, "erros": 0, "puladas": 0, "fora_prazo": 0, "total_verificadas": 2},
        ]
        r = executar_manifestacao_automatica(session)
        assert r["total_manifestadas"] == 7
        assert mock_manifestar.call_count == 2

    @patch("src.importador.manifestacao.manifestar_lote")
    def test_executa_somente_ciencia_sem_match(self, mock_manifestar, session):
        """Sem reconciliação matched, só executa fase de ciência."""
        mock_manifestar.return_value = {"manifestadas": 3, "erros": 0, "puladas": 0,
                                        "fora_prazo": 0, "total_verificadas": 3}
        r = executar_manifestacao_automatica(session)
        assert r["total_manifestadas"] == 3
        assert mock_manifestar.call_count == 1
