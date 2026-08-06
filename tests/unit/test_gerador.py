"""Testes do gerador de lançamentos contábeis."""
from datetime import datetime, date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistencia.models import (
    Base, Nfe, NfeItem, Participante, LancamentoContabil,
    PlanoContas, Reconciliacao,
)
from src.contabilidade.gerador import GeradorLancamentos, MAPEAMENTO_CFOP, MAPEAMENTO_CATEGORIA
from src.fiscal.validadores import CFOPS_VALIDOS, categoria_contabil_cfop


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _criar_nfe(session, cfop="1102", valor=1000, status="autorizada",
               manifestacao="ciencia_emissao", chave_suffix="01",
               vicms=0, vipi=0, vpis=0, vcofins=0, vicms_st=0, vibscbs=0):
    """Cria uma NF-e completa com item e participante."""
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
        data_emissao=datetime(2026, 7, 15, 10, 0),
        tipo_operacao="0",
        valor_total=Decimal(str(valor)),
        status_autorizacao=status,
        origem="sefaz",
        protocolo="33520260715100000",
        manifestacao_destinatario=manifestacao,
        emitente_id=emit.id,
        destinatario_id=dest.id,
    )
    session.add(nfe)
    session.flush()

    item = NfeItem(
        nfe_id=nfe.id, numero_item=1,
        descricao="Produto teste", ncm="11010010", cfop=cfop,
        unidade="UN", quantidade=1, valor_unitario=Decimal(str(valor)),
        valor_total=Decimal(str(valor)),
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


class TestGeradorLancamentos:
    def test_gerar_lancamento_principal_cfop_1102(self, session):
        nfe = _criar_nfe(session, cfop="1102", valor=1000)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched", matched_by="automatico")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        assert len(lancs) >= 1
        # Lançamento principal: débito estoque, crédito fornecedores
        principal = lancs[0]
        assert principal.conta_debito_codigo == "1.1.3.01"
        assert principal.conta_credito_codigo == "2.1.01"
        assert principal.valor == Decimal("1000")

    def test_gerar_lancamento_ativo_imobilizado(self, session):
        nfe = _criar_nfe(session, cfop="1551", valor=3500)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        principal = lancs[0]
        assert principal.conta_debito_codigo == "1.2.1.01"

    def test_gerar_lancamento_servico(self, session):
        nfe = _criar_nfe(session, cfop="1933", valor=500)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        principal = lancs[0]
        assert principal.conta_debito_codigo == "3.1.02"

    def test_gerar_lancamento_impostos(self, session):
        nfe = _criar_nfe(session, cfop="1102", valor=1000, vicms=120, vipi=50,
                         vpis=6.5, vcofins=30)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        # 1 principal + 4 impostos (icms, ipi, pis, cofins)
        assert len(lancs) == 5

        # Verifica impostos
        impostos = [l for l in lancs if l.conta_debito_codigo.startswith("2.2")]
        assert len(impostos) == 4
        valores = {l.conta_debito_codigo: l.valor for l in impostos}
        assert valores["2.2.01"] == Decimal("120")  # ICMS
        assert valores["2.2.03"] == Decimal("50")   # IPI
        assert valores["2.2.04"] == Decimal("6.5")  # PIS
        assert valores["2.2.05"] == Decimal("30")   # COFINS

    def test_gerar_lancamento_ibscbs(self, session):
        nfe = _criar_nfe(session, cfop="1102", valor=1000, vibscbs=10)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        ibs = [l for l in lancs if l.conta_debito_codigo == "2.2.06"]
        assert len(ibs) == 1
        assert ibs[0].valor == Decimal("10")

    def test_nao_gerar_para_nota_cancelada(self, session):
        nfe = _criar_nfe(session, status="cancelada")
        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        assert len(lancs) == 0

    def test_nao_gerar_para_reconciliacao_divergent(self, session):
        nfe = _criar_nfe(session)
        rec = Reconciliacao(nfe_id=nfe.id, status="divergent")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        assert len(lancs) == 0

    def test_nao_gerar_duplicado(self, session):
        nfe = _criar_nfe(session, cfop="1102", valor=1000)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs1 = gerador.gerar_para_nfe(nfe)
        assert len(lancs1) >= 1

        # Segunda chamada não deve gerar duplicados
        lancs2 = gerador.gerar_para_nfe(nfe)
        assert len(lancs2) == 0

    def test_estornar_nfe_cancelada(self, session):
        nfe = _criar_nfe(session, cfop="1102", valor=1000, vicms=120)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        # Gera lançamentos
        gerador.gerar_para_nfe(nfe)
        lancs_antes = session.query(LancamentoContabil).filter_by(nfe_id=nfe.id).all()
        assert len(lancs_antes) == 2  # principal + ICMS

        # Estorna
        nfe.status_autorizacao = "cancelada"
        session.commit()
        count = gerador.estornar_nfe(nfe)
        assert count == 2

        # Verifica estornos
        estornos = session.query(LancamentoContabil).filter_by(
            nfe_id=nfe.id, estornado=False
        ).all()
        # Os estornos têm débito/crédito invertidos
        for e in estornos:
            assert "ESTORNO" in e.historico

    def test_gerar_todos(self, session):
        nfe1 = _criar_nfe(session, cfop="1102", valor=1000, chave_suffix="01")
        nfe2 = _criar_nfe(session, cfop="1551", valor=500, chave_suffix="02")
        for n in [nfe1, nfe2]:
            rec = Reconciliacao(nfe_id=n.id, status="matched")
            session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        stats = gerador.gerar_todos()
        assert stats["notas_processadas"] == 2
        assert stats["lancamentos_gerados"] >= 2
        assert stats["erros"] == 0

    def test_data_lancamento_usa_data_emissao(self, session):
        nfe = _criar_nfe(session, cfop="1102", valor=1000)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        # Data do lançamento deve ser a data de emissão da NF-e
        assert lancs[0].data_lancamento == date(2026, 7, 15)

    def test_cfop_nao_mapeado_usa_default(self, session):
        nfe = _criar_nfe(session, cfop="1949", valor=1000)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        # CFOP 1949 não está no mapeamento, usa default
        principal = lancs[0]
        assert principal.conta_debito_codigo == MAPEAMENTO_CFOP["_default"]["débito"]

    def test_historico_contem_numero_e_emitente(self, session):
        nfe = _criar_nfe(session, cfop="1102", valor=1000)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        hist = lancs[0].historico
        assert "1" in hist  # número da nota
        assert "Emitente Teste" in hist

    def test_plano_contas_criado_automaticamente(self, session):
        nfe = _criar_nfe(session, cfop="1102", valor=1000)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        # Antes: sem contas
        assert session.query(PlanoContas).count() == 0

        gerador = GeradorLancamentos(session)
        gerador.gerar_para_nfe(nfe)

        # Depois: contas criadas
        assert session.query(PlanoContas).count() > 0
        assert session.query(PlanoContas).filter_by(codigo_referencial="1.1.3.01").first()
        assert session.query(PlanoContas).filter_by(codigo_referencial="2.1.01").first()

    def test_devolucao_inverte_debito_credito(self, session):
        nfe = _criar_nfe(session, cfop="1201", valor=500)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()

        gerador = GeradorLancamentos(session)
        lancs = gerador.gerar_para_nfe(nfe)
        principal = lancs[0]
        # Devolução: débito fornecedores, crédito estoque (invertido)
        assert principal.conta_debito_codigo == "2.1.01"
        assert principal.conta_credito_codigo == "1.1.3.01"

    def test_cfop_nao_mapeado_usa_categoria_estoque(self, session):
        """CFOP válido mas não explicitamente mapeado usa categoria contábil."""
        # 1117 = compra para industrialização por conta de terceiros (não mapeado explicitamente)
        nfe = _criar_nfe(session, cfop="1117", valor=800)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()
        gerador = GeradorLancamentos(session)
        gerador._garantir_plano_contas()
        lanc = gerador._gerar_lancamento_principal(nfe)
        # Categoria estoque: débito 1.1.3.01, crédito 2.1.01
        assert lanc.conta_debito_codigo == "1.1.3.01"
        assert lanc.conta_credito_codigo == "2.1.01"

    def test_cfop_nao_mapeado_usa_categoria_ativo(self, session):
        """CFOP de ativo não mapeado explicitamente usa categoria ativo."""
        # 1552 = compra de bem para ativo imobilizado (não mapeado)
        nfe = _criar_nfe(session, cfop="1552", valor=5000)
        rec = Reconciliacao(nfe_id=nfe.id, status="matched")
        session.add(rec)
        session.commit()
        gerador = GeradorLancamentos(session)
        gerador._garantir_plano_contas()
        lanc = gerador._gerar_lancamento_principal(nfe)
        # Categoria ativo: débito 1.2.1.01
        assert lanc.conta_debito_codigo == "1.2.1.01"

    def test_todos_cfops_oficiais_tem_mapeamento(self):
        """Todos os 369 CFOPs oficiais têm mapeamento (explícito ou por categoria)."""
        mapeados = set(MAPEAMENTO_CFOP.keys()) - {"_default"}
        for cfop in CFOPS_VALIDOS:
            if cfop in mapeados:
                continue
            # Não mapeado explicitamente: deve ter categoria com mapeamento
            cat = categoria_contabil_cfop(cfop)
            assert cat in MAPEAMENTO_CATEGORIA, f"CFOP {cfop}: categoria '{cat}' sem mapeamento"
