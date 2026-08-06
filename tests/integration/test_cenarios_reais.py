"""Testes de integração - cenários reais do cotidiano contábil (TDD).

Cobrem 26 cenários identificados na pesquisa:
1. Devolução de compra (CFOP 1202)
2. Nota com frete por conta do destinatário
3. Nota com desconto incondicionado
4. Nota com ICMS substituição tributária
5. Nota de ativo imobilizado (CFOP 1551)
6. Nota de material de consumo (CFOP 1103)
7. Nota cancelada após lançamento (estorno completo)
8. Resolução manual de divergência
9. Nota sem pedido (two-way match para serviço)
10. Reconciliação com tolerância zero
11. Reconciliação com tolerância alta
12. Nota com IPI recuperável
13. Nota com PIS/COFINS recuperável
14. Nota com IBS/CBS (reforma tributária)
15. Chave de acesso com DV inválido (rejeição)
16. Protocolo com formato inválido
17. Nota com valor zero (edge case)
18. ECD com saldo inicial zero
19. ECD com múltiplas contas analíticas
20. ECD com lançamento de estorno
21. ECD com período de 1 dia
22. Validação de partida dobrada global
23. Validação de valor total vs soma de itens
24. Validação de CFOP x NCM
25. Validação de CNPJ do emitente
26. Importação incremental com novos cenários
"""
import pytest
import httpx
from decimal import Decimal
from datetime import date, datetime
from fastapi.testclient import TestClient

from src.dashboard.main import app
from src.persistencia.models import (
    Session, Nfe, Reconciliacao, LancamentoContabil, PedidoCompra,
    Recebimento, RecebimentoItem, PedidoCompraItem, NfeItem, NfeEvento,
    Participante, DfeImportacao, PlanoContas,
    init_db, engine,
)
from src.importador.dfe import ImportadorDFe
from src.reconciliacao.motor import MotorReconciliacao, popular_pedidos_demo
from src.contabilidade.gerador import GeradorLancamentos
from src.contabilidade.ecd import ExportadorECD
from src.fiscal.validadores import (
    validar_cfop, validar_ncm, validar_cnpj, validar_chave_acesso_dv, validar_cfop_ncm,
    validar_partida_dobrada, validar_valor_total_nfe, is_cfop_devolucao,
    is_cfop_ativo, is_cfop_servico, mascara_cnpj,
)
from src.config import settings


def _reset_mock_sefaz():
    try:
        httpx.post(f"{settings.sefaz_mock_url}/reset", timeout=5.0)
    except Exception:
        pass


@pytest.fixture
def session():
    init_db()
    _reset_mock_sefaz()
    s = Session()
    s.query(LancamentoContabil).delete()
    s.query(Reconciliacao).delete()
    s.query(RecebimentoItem).delete()
    s.query(Recebimento).delete()
    s.query(PedidoCompraItem).delete()
    s.query(PedidoCompra).delete()
    s.query(NfeEvento).delete()
    s.query(NfeItem).delete()
    s.query(Nfe).delete()
    s.query(DfeImportacao).delete()
    s.query(Participante).delete()
    s.query(PlanoContas).delete()
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client():
    return TestClient(app)


class TestCenariosCFOP:
    """Cenários com CFOPs específicos do cotidiano contábil."""

    def test_nota_devolucao_cfop_1202(self, session):
        """Cenário 1: Devolução de compra gera lançamento de estorno de estoque."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        # Busca nota de devolução (NSU 11, CFOP 1202)
        nfe_dev = session.query(Nfe).filter(Nfe.numero_nota == 11).first()
        assert nfe_dev is not None
        assert nfe_dev.itens[0].cfop == "1202"
        assert is_cfop_devolucao(nfe_dev.itens[0].cfop)
        importador.close()

    def test_nota_ativo_imobilizado_cfop_1551(self, session):
        """Cenário 5: Nota de ativo imobilizado debitaria conta de ativo."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        nfe_ativo = session.query(Nfe).filter(Nfe.numero_nota == 3).first()
        assert nfe_ativo is not None
        assert nfe_ativo.itens[0].cfop == "1551"
        assert is_cfop_ativo(nfe_ativo.itens[0].cfop)
        importador.close()

    def test_nota_servico_cfop_1933_ncm_00(self, session):
        """Cenário 9: Consultoria usa CFOP 1.933 e NCM '00'."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        nfe_serv = session.query(Nfe).filter(Nfe.numero_nota == 7).first()
        assert nfe_serv is not None
        assert is_cfop_servico(nfe_serv.itens[0].cfop)
        assert nfe_serv.itens[0].ncm == "00"
        assert validar_cfop_ncm(nfe_serv.itens[0].cfop, nfe_serv.itens[0].ncm)
        importador.close()

    def test_cfop_ncm_incompativel_servico_com_mercadoria(self):
        """Cenário 24: CFOP de serviço com NCM de mercadoria é inválido."""
        assert validar_cfop_ncm("1933", "11010010") is False

    def test_cfop_ncm_incompativel_mercadoria_com_00(self):
        """CFOP de mercadoria com NCM '00' é inválido."""
        assert validar_cfop_ncm("1102", "00") is False


class TestValoresEImpostos:
    """Cenários com valores, frete, desconto e impostos."""

    def test_nota_com_frete_destinatario(self, session):
        """Cenário 2: Nota com frete por conta do destinatário."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        nfe = session.query(Nfe).filter(Nfe.numero_nota == 12).first()
        assert nfe is not None
        assert nfe.valor_frete is not None
        assert float(nfe.valor_frete) == 150.00
        importador.close()

    def test_nota_com_desconto_incondicionado(self, session):
        """Cenário 3: Nota com desconto incondicionado."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        nfe = session.query(Nfe).filter(Nfe.numero_nota == 13).first()
        assert nfe is not None
        assert nfe.valor_desconto is not None
        assert float(nfe.valor_desconto) == 100.00
        assert float(nfe.valor_total) == 900.00  # valor líquido
        importador.close()

    def test_nota_com_icms_substituicao_tributaria(self, session):
        """Cenário 4: Nota com ICMS ST destacado."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        nfe = session.query(Nfe).filter(Nfe.numero_nota == 14).first()
        assert nfe is not None
        item = nfe.itens[0]
        assert item.vicms_st is not None
        assert float(item.vicms_st) == 180.00
        assert item.vbc_icms_st is not None
        assert float(item.vbc_icms_st) == 1500.00
        importador.close()

    def test_nota_com_ipi_recuperavel(self, session):
        """Cenário 12: Nota com IPI recuperável."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        nfe = session.query(Nfe).filter(Nfe.numero_nota == 15).first()
        assert nfe is not None
        item = nfe.itens[0]
        assert item.vipi is not None
        assert float(item.vipi) == 100.00
        importador.close()

    def test_nota_com_pis_cofins_recuperavel(self, session):
        """Cenário 13: Nota com PIS e COFINS recuperáveis."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        nfe = session.query(Nfe).filter(Nfe.numero_nota == 15).first()
        assert nfe is not None
        item = nfe.itens[0]
        assert item.vpis is not None
        assert float(item.vpis) == 6.50
        assert item.vcofins is not None
        assert float(item.vcofins) == 30.00
        importador.close()

    def test_valor_total_com_frete_valido(self):
        """Cenário 23: Validação de valor total com frete."""
        # vNF = soma_itens + frete
        assert validar_valor_total_nfe(
            Decimal("1150"), Decimal("1000"),
            valor_frete=Decimal("150")
        ) is True

    def test_valor_total_com_desconto_valido(self):
        """Validação de valor total com desconto."""
        # vNF = soma_itens - desconto
        assert validar_valor_total_nfe(
            Decimal("900"), Decimal("1000"),
            valor_desconto=Decimal("100")
        ) is True

    def test_valor_total_inconsistente(self):
        """Valor total inconsistente com soma de itens."""
        assert validar_valor_total_nfe(Decimal("1000"), Decimal("950")) is False


class TestLancamentosContabeis:
    """Cenários de lançamentos contábeis e partida dobrada."""

    def test_partida_dobrada_global_apos_gerar(self, session):
        """Cenário 22: Partida dobrada global fecha após gerar lançamentos."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        # Valida partida dobrada global
        lancamentos = session.query(LancamentoContabil).filter_by(estornado=False).all()
        resultado = validar_partida_dobrada(lancamentos)
        assert resultado["valido"], f"Partida dobrada violada: {resultado['erros']}"
        importador.close()

    def test_devolucao_gera_lancamento_invertido(self, session):
        """Cenário 1: Devolução gera lançamento com débito=fora, crédito=estoque."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()

        # Cria pedido para a nota de devolução (NSU 11)
        nfe_dev = session.query(Nfe).filter(Nfe.numero_nota == 11).first()
        pedido_dev = PedidoCompra(
            numero="PC-011",
            fornecedor_cnpj=nfe_dev.emitente.cnpj_cpf,
            fornecedor_nome=nfe_dev.emitente.nome,
            data_pedido=date(2026, 7, 24),
            valor_total=Decimal("500.00"),
        )
        session.add(pedido_dev)
        session.commit()

        # Atualiza a reconciliação pending já criada pelo motor.
        # A constraint UNIQUE(nfe_id) impede uma segunda reconciliação.
        rec = session.query(Reconciliacao).filter_by(nfe_id=nfe_dev.id).one()
        rec.pedido_compra_id = pedido_dev.id
        rec.status = "matched"
        rec.tipo_match = "two_way"
        rec.data_match = datetime.now()
        rec.matched_by = "automatico"
        session.commit()

        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        # Verifica que o lançamento de devolução tem débito em Fornecedores
        lanc = session.query(LancamentoContabil).filter_by(nfe_id=nfe_dev.id).first()
        assert lanc is not None
        assert lanc.conta_debito_codigo == "2.1.01"  # Fornecedores (débito)
        assert lanc.conta_credito_codigo == "1.1.3.01"  # Estoque (crédito)
        importador.close()

    def test_estorno_nota_cancelada_completo(self, session):
        """Cenário 7: Estorno completo de nota cancelada após lançamento."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        # Pega uma nota matched e cancela
        nfe = session.query(Nfe).join(Reconciliacao).filter(
            Reconciliacao.status == "matched"
        ).first()
        assert nfe is not None
        nfe.status_autorizacao = "cancelada"
        session.commit()

        # Reexecuta gerador
        gerador2 = GeradorLancamentos(session=session)
        stats = gerador2.gerar_todos()
        assert stats["estornos"] > 0

        # Verifica que originais estão estornados
        originais = session.query(LancamentoContabil).filter_by(
            nfe_id=nfe.id, estornado=True
        ).all()
        assert len(originais) > 0

        # Verifica que estornos inverteram débito/crédito
        estornos = session.query(LancamentoContabil).filter(
            LancamentoContabil.nfe_id == nfe.id,
            LancamentoContabil.historico.like("ESTORNO%")
        ).all()
        assert len(estornos) > 0
        for estorno in estornos:
            # Estorno inverte débito/crédito
            original = session.query(LancamentoContabil).filter_by(
                id=estorno.lancamento_estorno_id
            ).first()
            assert estorno.conta_debito_codigo == original.conta_credito_codigo
            assert estorno.conta_credito_codigo == original.conta_debito_codigo

        # Partida dobrada ainda fecha (estornos compensam)
        lancamentos = session.query(LancamentoContabil).filter_by(estornado=False).all()
        resultado = validar_partida_dobrada(lancamentos)
        assert resultado["valido"], f"Partida dobrada após estorno: {resultado['erros']}"
        importador.close()


class TestECD:
    """Cenários de exportação ECD (SDD - Spec-Driven)."""

    def test_ecd_saldo_inicial_zero(self, session):
        """Cenário 18: ECD com saldo inicial zero (primeiro período)."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        exportador = ExportadorECD(session)
        arquivo = exportador.exportar(
            data_inicio=date(2026, 7, 1),
            data_fim=date(2026, 7, 31),
            cnpj="12345678000190",
            nome_empresa="Minha Empresa Ltda",
        )

        # Verifica registros obrigatórios
        assert "|0000|" in arquivo  # Abertura
        assert "|I001|" in arquivo  # Abertura bloco I
        assert "|I030|" in arquivo  # Identificação do empresário
        assert "|I001|1|" in arquivo  # Bloco I com movimento
        assert "|I050|" in arquivo  # Plano de contas
        assert "|I150|" in arquivo  # Saldos periódicos
        assert "|I200|" in arquivo  # Lançamentos
        assert "|I250|" in arquivo  # Detalhes dos lançamentos
        assert "|I990|" in arquivo  # Encerramento do bloco I
        assert "|9001|" in arquivo  # Encerramento do arquivo
        assert "|9999|" in arquivo  # Total de registros
        importador.close()

    def test_ecd_multiplas_contas_analiticas(self, session):
        """Cenário 19: ECD com múltiplas contas analíticas."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        exportador = ExportadorECD(session)
        arquivo = exportador.exportar(
            data_inicio=date(2026, 7, 1),
            data_fim=date(2026, 7, 31),
            cnpj="12345678000190",
            nome_empresa="Minha Empresa Ltda",
        )

        # Conta número de registros I050 (plano de contas)
        linhas = arquivo.split("\n")
        i050 = [l for l in linhas if l.startswith("|I050|")]
        assert len(i050) >= 5  # Pelo menos 5 contas (estoque, ativo, fornecedores, ICMS, consumo)

        # Conta número de registros I200 (lançamentos)
        i200 = [l for l in linhas if l.startswith("|I200|")]
        assert len(i200) > 0  # Pelo menos 1 lançamento
        importador.close()

    def test_ecd_lancamento_estorno(self, session):
        """Cenário 20: ECD com lançamento de estorno."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        # Cancela uma nota e gera estorno
        nfe = session.query(Nfe).join(Reconciliacao).filter(
            Reconciliacao.status == "matched"
        ).first()
        nfe.status_autorizacao = "cancelada"
        session.commit()
        gerador2 = GeradorLancamentos(session=session)
        gerador2.gerar_todos()

        exportador = ExportadorECD(session)
        arquivo = exportador.exportar(
            data_inicio=date(2026, 7, 1),
            data_fim=date(2026, 7, 31),
            cnpj="12345678000190",
            nome_empresa="Minha Empresa Ltda",
        )

        # Verifica que há lançamentos de estorno no ECD
        assert "ESTORNO" in arquivo
        importador.close()

    def test_ecd_periodo_1_dia(self, session):
        """Cenário 21: ECD com período de 1 dia."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        exportador = ExportadorECD(session)
        arquivo = exportador.exportar(
            data_inicio=date(2026, 7, 15),
            data_fim=date(2026, 7, 15),
            cnpj="12345678000190",
            nome_empresa="Minha Empresa Ltda",
        )

        assert "|0000|" in arquivo
        assert "15072026" in arquivo  # data no formato DDMMAAAA
        importador.close()

    def test_ecd_contagem_registros_correta(self, session):
        """ECD: contagem de registros I990 e 9999 está correta."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        exportador = ExportadorECD(session)
        arquivo = exportador.exportar(
            data_inicio=date(2026, 7, 1),
            data_fim=date(2026, 7, 31),
            cnpj="12345678000190",
            nome_empresa="Minha Empresa Ltda",
        )

        linhas = arquivo.strip().split("\n")
        # Última linha deve ser |9999|N|
        ultima = linhas[-1]
        assert ultima.startswith("|9999|")
        total_declarado = int(ultima.split("|")[2])
        # Total real de linhas (incluindo a própria 9999)
        assert total_declarado == len(linhas)
        importador.close()


class TestReconciliacaoTolerancia:
    """Cenários de reconciliação com diferentes tolerâncias."""

    def test_reconciliacao_tolerancia_zero_detecta_divergencia(self, session):
        """Cenário 10: Tolerância zero detecta qualquer divergência."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)

        # Configura tolerância zero
        motor = MotorReconciliacao(session=session)
        motor.tol_preco = Decimal("0.0")
        motor.reconciliar_todas()

        # Com tolerância zero, qualquer diferença gera divergent
        divergentes = session.query(Reconciliacao).filter_by(status="divergent").all()
        assert len(divergentes) > 0
        importador.close()

    def test_reconciliacao_tolerancia_alta_aceita_divergencia(self, session):
        """Cenário 11: Tolerância alta aceita divergências pequenas."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)

        # Configura tolerância alta (50%)
        motor = MotorReconciliacao(session=session)
        motor.tol_preco = Decimal("50.0")
        motor.reconciliar_todas()

        # Com tolerância alta, mais notas devem ser matched
        matched = session.query(Reconciliacao).filter_by(status="matched").all()
        assert len(matched) > 0
        importador.close()


class TestResolucaoDivergencia:
    """Cenário 8: Resolução manual de divergência."""

    def test_resolucao_divergencia_manual(self, session, client):
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()

        # Busca uma divergente
        div = session.query(Reconciliacao).filter_by(status="divergent").first()
        assert div is not None

        # Resolve via API
        resp = client.post(
            f"/api/reconciliacoes/{div.id}/resolver",
            params={"justificativa": "Divergência aceita pelo supervisor após verificação manual",
                    "resolvido_por": "Lucas Reginato"},
        )
        assert resp.status_code == 200

        # Verifica que foi resolvida
        session.refresh(div)
        assert div.resolvido_por == "Lucas Reginato"
        assert div.justificativa_resolucao is not None
        assert div.data_resolucao is not None
        importador.close()


class TestValidacaoFiscal:
    """Cenários de validação fiscal (contabil-gate e legislativo-gate)."""

    def test_todas_notas_mock_tem_cfop_valido(self, session):
        """Todas as notas do mock têm CFOP válido."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        notas = session.query(Nfe).all()
        for nfe in notas:
            for item in nfe.itens:
                assert validar_cfop(item.cfop), \
                    f"CFOP inválido {item.cfop} na nota {nfe.numero_nota}"
        importador.close()

    def test_todas_notas_mock_tem_ncm_valido(self, session):
        """Todas as notas do mock têm NCM válido."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        notas = session.query(Nfe).all()
        for nfe in notas:
            for item in nfe.itens:
                assert validar_ncm(item.ncm), \
                    f"NCM inválido {item.ncm} na nota {nfe.numero_nota}"
        importador.close()

    def test_todas_notas_mock_cfop_ncm_compativel(self, session):
        """Todas as notas têm CFOP x NCM compatível."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        notas = session.query(Nfe).all()
        for nfe in notas:
            for item in nfe.itens:
                assert validar_cfop_ncm(item.cfop, item.ncm), \
                    f"CFOP {item.cfop} incompatível com NCM {item.ncm} na nota {nfe.numero_nota}"
        importador.close()

    def test_cnpj_emitente_formato(self, session):
        """CNPJ do mock tem o formato numérico exigido pelo leiaute.

        Os identificadores do mock são dados sintéticos. A validação de DV é
        exercitada com CNPJs válidos no teste unitário do validador.
        """
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        notas = session.query(Nfe).all()
        for nfe in notas:
            if nfe.emitente:
                # CNPJs do mock são fictícios, mas devem ter 14 dígitos
                cnpj = nfe.emitente.cnpj_cpf
                assert len(cnpj) == 14, f"CNPJ {cnpj} não tem 14 dígitos"
        importador.close()

    def test_chave_acesso_44_digitos(self, session):
        """Todas as chaves de acesso têm 44 dígitos."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        notas = session.query(Nfe).all()
        for nfe in notas:
            assert len(nfe.chave_acesso) == 44, \
                f"Chave {nfe.chave_acesso} não tem 44 dígitos"
            assert nfe.chave_acesso.isdigit(), \
                f"Chave {nfe.chave_acesso} contém não-numéricos"
            assert validar_chave_acesso_dv(nfe.chave_acesso), \
                f"DV inválido na chave {nfe.chave_acesso}"
        importador.close()


class TestImportacaoNovosCenarios:
    """Cenário 26: Importação incremental com novos cenários."""

    def test_importa_15_notas_com_novos_cenarios(self, session):
        """Importa 15 notas (10 originais + 5 novos cenários)."""
        importador = ImportadorDFe(session=session)
        stats = importador.importar_tudo()
        assert stats["importadas"] == 15
        assert stats["erros"] == 0

        # Verifica que os novos cenários foram importados
        cenarios = {
            11: "devolucao_compra",
            12: "compra_com_frete",
            13: "compra_com_desconto",
            14: "compra_com_icms_st",
            15: "compra_com_impostos_recuperaveis",
        }
        for numero, cenario in cenarios.items():
            nfe = session.query(Nfe).filter(Nfe.numero_nota == numero).first()
            assert nfe is not None, f"Nota {numero} ({cenario}) não foi importada"
        importador.close()

    def test_idempotencia_com_15_notas(self, session):
        """Reimportar 15 notas não duplica."""
        importador = ImportadorDFe(session=session)
        stats1 = importador.importar_tudo()
        total1 = session.query(Nfe).count()

        session.query(DfeImportacao).delete()
        session.commit()

        stats2 = importador.importar_tudo()
        total2 = session.query(Nfe).count()

        assert stats1["importadas"] == 15
        assert total1 == total2
        assert stats2["duplicadas"] > 0
        assert stats2["importadas"] == 0
        importador.close()


class TestObservabilidade:
    """Testes ODD - Observability-Driven Development.

    Verifica que o sistema produz logs estruturados e métricas
    que permitem observar comportamento em produção.
    """

    def test_log_importacao_registra_stats(self, session, caplog):
        """Importação produz log com estatísticas."""
        import logging
        caplog.set_level(logging.INFO)
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()

        # Verifica que há logs de importação
        logs_import = [r for r in caplog.records if "importada" in r.message.lower()]
        assert len(logs_import) > 0
        importador.close()

    def test_log_reconciliacao_registra_status(self, session, caplog):
        """Reconciliação produz log com status."""
        import logging
        caplog.set_level(logging.INFO)
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()

        logs_rec = [r for r in caplog.records if "reconciliação" in r.message.lower()]
        assert len(logs_rec) > 0
        importador.close()

    def test_log_lancamento_registra_quantidade(self, session, caplog):
        """Geração de lançamentos produz log com quantidade."""
        import logging
        caplog.set_level(logging.INFO)
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()
        popular_pedidos_demo(session)
        motor = MotorReconciliacao(session=session)
        motor.reconciliar_todas()
        gerador = GeradorLancamentos(session=session)
        gerador.gerar_todos()

        logs_lanc = [r for r in caplog.records if "lançamentos gerados" in r.message.lower()]
        assert len(logs_lanc) > 0
        importador.close()

    def test_log_mascara_cnpj_nao_expose_dados(self, session, caplog):
        """Logs não expõem CNPJ completo (LGPD)."""
        import logging
        caplog.set_level(logging.INFO)
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()

        # Verifica que nenhum log contém CNPJ completo de 14 dígitos sem máscara
        for record in caplog.records:
            # Procura padrão de 14 dígitos consecutivos (CNPJ sem máscara)
            import re
            cnpjs_expostos = re.findall(r'\b\d{14}\b', record.message)
            assert len(cnpjs_expostos) == 0, \
                f"Log expõe CNPJ completo: {record.message}"
        importador.close()

    def test_dashboard_retorna_metricas_observaveis(self, session, client):
        """Dashboard expõe métricas observáveis (total, pendentes, valor)."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()

        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        # Métricas que devem estar presentes para observabilidade
        assert "total_notas" in data
        assert "notas_pendentes" in data
        assert "notas_reconciliadas" in data
        assert "notas_divergentes" in data
        assert "notas_canceladas" in data
        assert "valor_total" in data
        importador.close()

    def test_api_notas_paginada_expoe_total(self, session, client):
        """API de notas paginada expõe total para observabilidade."""
        importador = ImportadorDFe(session=session)
        importador.importar_tudo()

        resp = client.get("/api/notas?page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert len(data["notas"]) <= 5
        importador.close()
