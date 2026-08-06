"""Testes da apuração mensal de impostos."""
from datetime import datetime
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistencia.models import Base, Nfe, NfeItem, Participante
from src.fiscal.apuracao import apurar_mes, apurar_mes_dict


@pytest.fixture
def session():
    """Sessão em memória para testes."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _criar_nfe(session, tipo_op, valor_total, vicms=0, vipi=0, vpis=0, vcofins=0,
               vicms_st=0, vibscbs=0, data="2026-07-15T10:00:00", chave_suffix="01"):
    """Cria uma NF-e com um item para teste de apuração."""
    emit = session.query(Participante).filter_by(cnpj_cpf="11222333000144").first()
    if not emit:
        emit = Participante(cnpj_cpf="11222333000144", nome="Emitente Teste")
        session.add(emit)
    dest = session.query(Participante).filter_by(cnpj_cpf="12345678000190").first()
    if not dest:
        dest = Participante(cnpj_cpf="12345678000190", nome="Destinatario Teste")
        session.add(dest)
    session.flush()

    nfe = Nfe(
        chave_acesso=f"352008112223330001445500100000000{chave_suffix}0000000{chave_suffix}",
        numero_nota=int(chave_suffix),
        serie=1, modelo="55",
        data_emissao=datetime.fromisoformat(data),
        tipo_operacao=tipo_op,
        valor_total=Decimal(str(valor_total)),
        status_autorizacao="autorizada",
        origem="sefaz",
        emitente_id=emit.id,
        destinatario_id=dest.id,
    )
    session.add(nfe)
    session.flush()

    item = NfeItem(
        nfe_id=nfe.id, numero_item=1,
        descricao="Produto teste", ncm="11010010", cfop="1102" if tipo_op == "0" else "5102",
        unidade="UN", quantidade=1, valor_unitario=Decimal(str(valor_total)),
        valor_total=Decimal(str(valor_total)),
        vicms=Decimal(str(vicms)) if vicms else None,
        vipi=Decimal(str(vipi)) if vipi else None,
        vpis=Decimal(str(vpis)) if vpis else None,
        vcofins=Decimal(str(vcofins)) if vcofins else None,
        vicms_st=Decimal(str(vicms_st)) if vicms_st else None,
        vibscbs=Decimal(str(vibscbs)) if vibscbs else None,
    )
    session.add(item)
    session.commit()
    return nfe


class TestApuracaoMensal:
    def test_apuracao_sem_notas(self, session):
        r = apurar_mes(session, 2026, 7)
        assert r.icms.creditos == Decimal("0")
        assert r.icms.debitos == Decimal("0")
        assert r.icms.saldo_a_recolher == Decimal("0")
        assert r.total_a_recolher == Decimal("0")

    def test_apuracao_somente_entradas(self, session):
        _criar_nfe(session, "0", 1000, vicms=120, vipi=50, vpis=6.5, vcofins=30)
        r = apurar_mes(session, 2026, 7)
        # Entradas geram crédito (a recuperar)
        assert r.icms.creditos == Decimal("120")
        assert r.icms.debitos == Decimal("0")
        assert r.icms.saldo_a_compensar == Decimal("120")
        assert r.icms.saldo_a_recolher == Decimal("0")
        assert r.ipi.creditos == Decimal("50")
        assert r.pis.creditos == Decimal("6.5")
        assert r.cofins.creditos == Decimal("30")

    def test_apuracao_somente_saidas(self, session):
        _criar_nfe(session, "1", 1000, vicms=180, vpis=6.5, vcofins=30)
        r = apurar_mes(session, 2026, 7)
        # Saídas geram débito (a recolher)
        assert r.icms.debitos == Decimal("180")
        assert r.icms.creditos == Decimal("0")
        assert r.icms.saldo_a_recolher == Decimal("180")

    def test_apuracao_com_entradas_e_saidas(self, session):
        _criar_nfe(session, "0", 1000, vicms=120, chave_suffix="01")
        _criar_nfe(session, "1", 2000, vicms=360, chave_suffix="02")
        r = apurar_mes(session, 2026, 7)
        assert r.icms.creditos == Decimal("120")
        assert r.icms.debitos == Decimal("360")
        assert r.icms.saldo_a_recolher == Decimal("240")

    def test_apuracao_credito_maior_que_debito(self, session):
        _criar_nfe(session, "0", 2000, vicms=240, chave_suffix="01")
        _criar_nfe(session, "1", 1000, vicms=180, chave_suffix="02")
        r = apurar_mes(session, 2026, 7)
        assert r.icms.saldo_a_recolher == Decimal("0")
        assert r.icms.saldo_a_compensar == Decimal("60")

    def test_apuracao_nota_cancelada_nao_conta(self, session):
        nfe = _criar_nfe(session, "0", 1000, vicms=120)
        nfe.status_autorizacao = "cancelada"
        session.commit()
        r = apurar_mes(session, 2026, 7)
        assert r.icms.creditos == Decimal("0")

    def test_apuracao_periodo_diferente(self, session):
        _criar_nfe(session, "0", 1000, vicms=120, data="2026-06-15T10:00:00")
        r = apurar_mes(session, 2026, 7)
        assert r.icms.creditos == Decimal("0")

    def test_apuracao_dict(self, session):
        _criar_nfe(session, "0", 1000, vicms=120, vpis=6.5)
        d = apurar_mes_dict(session, 2026, 7)
        assert d["periodo"] == "2026-07"
        assert d["icms"]["creditos"] == 120.0
        assert d["pis"]["creditos"] == 6.5
        assert "alertas" in d

    def test_apuracao_mes_invalido(self, session):
        with pytest.raises(ValueError):
            apurar_mes(session, 2026, 13)

    def test_apuracao_ano_invalido(self, session):
        with pytest.raises(ValueError):
            apurar_mes(session, 1999, 7)

    def test_apuracao_ibscbs_com_alerta(self, session):
        _criar_nfe(session, "0", 1000, vibscbs=10)
        r = apurar_mes(session, 2026, 7)
        assert r.ibs_cbs.creditos == Decimal("10")
        assert any("fase educativa" in a for a in r.alertas)
