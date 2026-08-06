"""Testes para cobrir buracos remanescentes de cobertura.

Cobre linhas não testadas em:
- src/dashboard/main.py (86% -> 95%+)
- src/importador/dfe.py (91% -> 98%+)
- src/gates/legislativo.py (92% -> 98%+)
- src/gates/contabil.py (95% -> 100%)
- src/reconciliacao/gerador_pedidos.py (92% -> 100%)
- Outros: rate_limit, apuracao, calculo, engine, models, registry
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.persistencia.models import (
    Base, Nfe, NfeItem, Participante, Reconciliacao, LancamentoContabil,
    PlanoContas, PedidoCompra, PedidoCompraItem, Recebimento, RecebimentoItem,
    NfeEvento, NfePagamento, DfeImportacao, get_session,
)
from src.gates.engine import (
    Control, LegalRef, ProjectContext, CheckResult, RiskType, Severity,
    Environment, AdaptiveGate, GateReport, ControlEvaluation, detect_context,
)
from src.gates.contabil import (
    _check_partida_dobrada, _check_plano_contas, _check_cfop, _check_ncm,
    _check_cst_csosn, _check_ecd, _check_reconciliacao, _check_tributos,
    _check_estorno, _check_rastreabilidade, _check_precisao_monetaria,
    _check_periodo_data, _read_file,
)
from src.gates.legislativo import (
    _check_nfe_chave, _check_ecd_prazo, _check_reforma_tributaria,
    _check_icms, _check_manifestacao, _check_lgpd, _check_obrigacoes,
    _check_cadeia_evidencia,
)
from src.gates.registry import LegislationEntry, REGISTRY, get_vigente


ROOT = Path(__file__).parents[2]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_engine():
    """Cria engine SQLite em memória com StaticPool."""
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def session():
    """Sessão SQLite em memória para testes de DB."""
    engine = _make_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def client_rich():
    """Cliente de teste com NF-e completa (reconciliação, lançamentos, IBS/CBS)."""
    engine = _make_engine()
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    s = TestSession()
    # Emitente
    emitente = Participante(cnpj_cpf="11222333000144", nome="Distribuidora SP",
                            municipio="Sao Paulo", uf="SP")
    s.add(emitente)
    # Destinatario
    dest = Participante(cnpj_cpf="12345678000190", nome="Minha Empresa Ltda",
                        municipio="Sao Paulo", uf="SP")
    s.add(dest)
    s.flush()

    # Plano de contas para lancamentos
    for codigo, nome, tipo, natureza in [
        ("1.1.3.01", "Estoque", "ativo", "devedora"),
        ("2.1.01", "Fornecedores", "passivo", "credora"),
        ("2.2.06", "Ibs Cbs a Recolher", "passivo", "credora"),
    ]:
        s.add(PlanoContas(codigo_referencial=codigo, nome=nome, tipo=tipo,
                          natureza=natureza))
    s.flush()

    # NF-e
    nfe = Nfe(
        chave_acesso="1" * 44, numero_nota=1, serie=1, modelo="55",
        data_emissao=datetime(2026, 7, 15, 10, 0),
        natureza_operacao="Compra", tipo_operacao="0",
        valor_total=Decimal("1500.00"), status_autorizacao="autorizada",
        origem="sefaz", protocolo="33520260715100000",
        manifestacao_destinatario="ciencia_emissao",
        emitente_id=emitente.id, destinatario_id=dest.id,
    )
    s.add(nfe)
    s.flush()

    # Item com IBS/CBS
    item = NfeItem(
        nfe_id=nfe.id, numero_item=1, codigo_produto="001",
        descricao="Farinha de trigo 1kg", ncm="11010010", cfop="1102",
        unidade="UN", quantidade=Decimal("100"),
        valor_unitario=Decimal("15.00"), valor_total=Decimal("1500.00"),
        vicms=Decimal("180.00"), vbc_ibscbs=Decimal("1500.00"),
        aliquota_ibscbs=Decimal("1.00"), vibscbs=Decimal("15.00"),
    )
    s.add(item)

    # Evento
    s.add(NfeEvento(
        nfe_id=nfe.id, tipo_evento="ciencia_emissao",
        data_evento=datetime(2026, 7, 15, 12, 0),
        sequencia=1, protocolo="33520260715100001", status="registrado",
    ))

    # Pagamento
    s.add(NfePagamento(
        nfe_id=nfe.id, forma_pagamento="15", valor_pago=Decimal("1500.00"),
        bandeira="VISA",
    ))

    # Pedido de compra
    pedido = PedidoCompra(
        numero="PC-001", fornecedor_cnpj="11222333000144",
        fornecedor_nome="Distribuidora SP", data_pedido=date(2026, 7, 10),
        valor_total=Decimal("1500.00"), condicao_pagamento="30 dias",
        status="aberto",
    )
    s.add(pedido)
    s.flush()

    # Item do pedido
    pi = PedidoCompraItem(
        pedido_id=pedido.id, numero_item=1, codigo_produto="001",
        descricao="Farinha de trigo 1kg", ncm="11010010", cfop="1102",
        unidade="UN", quantidade=Decimal("100"),
        valor_unitario=Decimal("15.00"), valor_total=Decimal("1500.00"),
    )
    s.add(pi)
    s.flush()

    # Recebimento
    receb = Recebimento(
        pedido_id=pedido.id, data_recebimento=date(2026, 7, 16),
        responsavel="Joao Silva",
    )
    s.add(receb)
    s.flush()

    # Item do recebimento
    s.add(RecebimentoItem(
        recebimento_id=receb.id, pedido_item_id=pi.id,
        quantidade_recebida=Decimal("100"), conferido=True,
    ))

    # Reconciliacao com divergencias
    rec = Reconciliacao(
        nfe_id=nfe.id, pedido_compra_id=pedido.id, recebimento_id=receb.id,
        status="divergent", tipo_match="three_way",
        divergencias=[{"campo": "valor", "esperado": "1500", "encontrado": "1500",
                       "diferenca": "0"}],
        data_match=datetime(2026, 7, 16, 14, 0), matched_by="automatico",
    )
    s.add(rec)
    s.flush()

    # Lancamento contabil
    s.add(LancamentoContabil(
        nfe_id=nfe.id, data_lancamento=date(2026, 7, 15),
        numero_documento="1", historico="Compra de mercadorias",
        conta_debito_codigo="1.1.3.01", conta_credito_codigo="2.1.01",
        valor=Decimal("1500.00"), estornado=False,
    ))

    s.commit()
    s.close()

    # Override da dependencia get_session
    def _get_test_session():
        ss = TestSession()
        try:
            yield ss
        finally:
            ss.close()

    from src.dashboard import main as dashboard_main
    dashboard_main.app.dependency_overrides[dashboard_main.get_session] = _get_test_session

    client = TestClient(dashboard_main.app)
    yield client

    dashboard_main.app.dependency_overrides.clear()


@pytest.fixture
def client_empty():
    """Cliente de teste com banco vazio (sem notas)."""
    engine = _make_engine()
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def _get_test_session():
        ss = TestSession()
        try:
            yield ss
        finally:
            ss.close()

    from src.dashboard import main as dashboard_main
    dashboard_main.app.dependency_overrides[dashboard_main.get_session] = _get_test_session

    client = TestClient(dashboard_main.app)
    yield client

    dashboard_main.app.dependency_overrides.clear()


@pytest.fixture
def client_resolver():
    """Cliente com reconciliacao divergent para testar resolver divergencia."""
    engine = _make_engine()
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    s = TestSession()
    emitente = Participante(cnpj_cpf="11222333000144", nome="Fornecedor")
    s.add(emitente)
    s.flush()
    nfe = Nfe(
        chave_acesso="2" * 44, numero_nota=2, serie=1, modelo="55",
        data_emissao=datetime(2026, 7, 15), tipo_operacao="0",
        valor_total=Decimal("500.00"), status_autorizacao="autorizada",
        emitente_id=emitente.id,
    )
    s.add(nfe)
    s.flush()
    rec = Reconciliacao(
        nfe_id=nfe.id, status="divergent", tipo_match="three_way",
        divergencias=[{"campo": "valor", "esperado": "500", "encontrado": "450",
                       "diferenca": "50"}],
        matched_by="automatico",
    )
    s.add(rec)
    s.commit()
    rec_id = rec.id
    s.close()

    def _get_test_session():
        ss = TestSession()
        try:
            yield ss
        finally:
            ss.close()

    from src.dashboard import main as dashboard_main
    dashboard_main.app.dependency_overrides[dashboard_main.get_session] = _get_test_session

    client = TestClient(dashboard_main.app)
    yield client, rec_id

    dashboard_main.app.dependency_overrides.clear()


@pytest.fixture
def client_csv():
    """Cliente com reconciliacao e lancamento para export CSV com dados."""
    engine = _make_engine()
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    s = TestSession()
    for codigo, nome, tipo, natureza in [
        ("1.1.3.01", "Estoque", "ativo", "devedora"),
        ("2.1.01", "Fornecedores", "passivo", "credora"),
    ]:
        s.add(PlanoContas(codigo_referencial=codigo, nome=nome, tipo=tipo,
                          natureza=natureza))
    emitente = Participante(cnpj_cpf="11222333000144", nome="Fornecedor")
    s.add(emitente)
    s.flush()
    nfe = Nfe(
        chave_acesso="3" * 44, numero_nota=3, serie=1, modelo="55",
        data_emissao=datetime(2026, 7, 15), tipo_operacao="0",
        valor_total=Decimal("300.00"), status_autorizacao="autorizada",
        emitente_id=emitente.id,
    )
    s.add(nfe)
    s.flush()
    rec = Reconciliacao(
        nfe_id=nfe.id, status="matched", tipo_match="three_way",
        matched_by="automatico", data_match=datetime(2026, 7, 16, 10, 0),
    )
    s.add(rec)
    s.add(LancamentoContabil(
        nfe_id=nfe.id, data_lancamento=date(2026, 7, 15),
        historico="Compra", conta_debito_codigo="1.1.3.01",
        conta_credito_codigo="2.1.01", valor=Decimal("300.00"),
    ))
    s.commit()
    s.close()

    def _get_test_session():
        ss = TestSession()
        try:
            yield ss
        finally:
            ss.close()

    from src.dashboard import main as dashboard_main
    dashboard_main.app.dependency_overrides[dashboard_main.get_session] = _get_test_session

    client = TestClient(dashboard_main.app)
    yield client

    dashboard_main.app.dependency_overrides.clear()


# ===========================================================================
# 1. src/dashboard/main.py
# ===========================================================================


class TestDashboardCoberturaHTML:
    """Cobre linhas HTML do dashboard: detalhe NF-e, crossover, empty states."""

    def test_home_sem_notas_link_importacao(self, client_empty):
        """Linha 210: mensagem 'Nenhuma nota importada' quando banco vazio."""
        r = client_empty.get("/")
        assert r.status_code == 200
        assert "Nenhuma nota importada" in r.text

    def test_crossover_sem_notas(self, client_empty):
        """Linha 618: crossover sem notas mostra mensagem."""
        r = client_empty.get("/crossover")
        assert r.status_code == 200
        assert "Nenhuma nota importada" in r.text

    def test_detalhe_nfe_com_ibscbs(self, client_rich):
        """Linha 403: detalhe HTML mostra IBS/CBS quando item tem vibscbs."""
        r = client_rich.get(f"/notas/{'1' * 44}")
        assert r.status_code == 200
        assert "IBS/CBS" in r.text
        assert "Valor IBS/CBS" in r.text

    def test_detalhe_nfe_com_eventos(self, client_rich):
        """Linhas 434-435: detalhe HTML renderiza eventos."""
        r = client_rich.get(f"/notas/{'1' * 44}")
        assert r.status_code == 200
        assert "ciencia_emissao" in r.text

    def test_detalhe_nfe_com_pagamentos(self, client_rich):
        """Linhas 448-449: detalhe HTML renderiza pagamentos."""
        r = client_rich.get(f"/notas/{'1' * 44}")
        assert r.status_code == 200
        assert "VISA" in r.text

    def test_detalhe_nfe_com_reconciliacoes(self, client_rich):
        """Linhas 461-462: detalhe HTML renderiza reconciliacoes."""
        r = client_rich.get(f"/notas/{'1' * 44}")
        assert r.status_code == 200
        assert "three_way" in r.text
        assert "divergent" in r.text

    def test_detalhe_nfe_com_lancamentos(self, client_rich):
        """Linhas 476-478: detalhe HTML renderiza lancamentos."""
        r = client_rich.get(f"/notas/{'1' * 44}")
        assert r.status_code == 200
        assert "Compra de mercadorias" in r.text
        assert "1.1.3.01" in r.text

    def test_crossover_detalhe_com_pedido(self, client_rich):
        """Linhas 670-671: crossover detalhado mostra pedido vinculado."""
        r = client_rich.get(f"/crossover/{'1' * 44}")
        assert r.status_code == 200
        assert "PC-001" in r.text
        assert "Pedido de Compra" in r.text

    def test_crossover_detalhe_com_recebimento(self, client_rich):
        """Linha 690: crossover detalhado mostra recebimento."""
        r = client_rich.get(f"/crossover/{'1' * 44}")
        assert r.status_code == 200
        assert "Recebimento" in r.text
        assert "Joao Silva" in r.text

    def test_crossover_detalhe_com_lancamentos(self, client_rich):
        """Linhas 707-710: crossover detalhado mostra lancamentos."""
        r = client_rich.get(f"/crossover/{'1' * 44}")
        assert r.status_code == 200
        assert "Lancamento Contabil" in r.text

    def test_crossover_detalhe_com_divergencias(self, client_rich):
        """Linhas 730-739: crossover detalhado mostra tabela de divergencias."""
        r = client_rich.get(f"/crossover/{'1' * 44}")
        assert r.status_code == 200
        assert "Divergencias Detectadas" in r.text
        assert "valor" in r.text


class TestDashboardCoberturaAPI:
    """Cobre linhas de API do dashboard: resolver, CSV, erros."""

    def test_resolver_divergencia_sucesso(self, client_resolver):
        """Linhas 825-830: resolver divergencia com sucesso."""
        client, rec_id = client_resolver
        r = client.post(
            f"/api/reconciliacoes/{rec_id}/resolver"
            "?justificativa=resolvido+manualmente+apos+verificacao"
            "&resolvido_por=Joao+Auditor"
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["novo_status"] == "matched"

    def test_export_csv_reconciliacoes_com_dados(self, client_csv):
        """Linha 857: CSV de reconciliacoes com dados reais."""
        r = client_csv.get("/api/export/csv?tipo=reconciliacoes")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        # Tem pelo menos header + 1 linha de dados
        lines = r.text.strip().split("\n")
        assert len(lines) >= 2

    def test_export_csv_lancamentos_com_dados(self, client_csv):
        """Linha 867: CSV de lancamentos com dados reais."""
        r = client_csv.get("/api/export/csv?tipo=lancamentos")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        lines = r.text.strip().split("\n")
        assert len(lines) >= 2

    def test_api_detalhe_nfe_nao_encontrada(self, client_empty):
        """Linha 1081-1082: api_detalhe_nfe com nota nao encontrada retorna 404."""
        r = client_empty.get(f"/api/notas/{'5' * 44}")
        assert r.status_code == 404

    def test_api_detalhe_nfe_chave_invalida(self, client_empty):
        """Linha 1079: api_detalhe_nfe com chave invalida retorna 400."""
        r = client_empty.get("/api/notas/abc")
        assert r.status_code == 400

    def test_api_apuracao_value_error(self, client_empty):
        """Linhas 1129-1130: apuracao com ValueError retorna 400."""
        with patch("src.dashboard.main.apurar_mes_dict",
                   side_effect=ValueError("erro de validacao")):
            r = client_empty.get("/api/apuracao/2026/7")
        assert r.status_code == 400
        assert "erro de validacao" in r.json()["detail"]

    def test_api_apuracao_erro_generico(self, client_empty):
        """Linhas 1131-1133: apuracao com erro generico retorna 500."""
        with patch("src.dashboard.main.apurar_mes_dict",
                   side_effect=RuntimeError("boom")):
            r = client_empty.get("/api/apuracao/2026/7")
        assert r.status_code == 500
        assert r.json()["status"] == "erro"

    def test_api_manifestacao_pendentes_erro(self, client_empty):
        """Linhas 1173-1175: manifestacao pendentes com erro retorna 500."""
        with patch("src.dashboard.main.identificar_notas_pendentes",
                   side_effect=RuntimeError("falha")):
            r = client_empty.get("/api/manifestacao/pendentes")
        assert r.status_code == 500
        assert r.json()["status"] == "erro"


class TestDashboardErroDB:
    """Cobre linhas 184-189 e 1057-1059: erros de DB no dashboard."""

    def test_home_erro_db_retorna_html(self):
        """Linhas 184-189: dashboard inicial com erro de DB nao quebra."""
        engine = _make_engine()
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)

        def _get_session_erro():
            ss = MagicMock()
            ss.query.side_effect = RuntimeError("DB down")
            yield ss
            ss.close()

        from src.dashboard import main as dashboard_main
        dashboard_main.app.dependency_overrides[dashboard_main.get_session] = _get_session_erro

        client = TestClient(dashboard_main.app)
        r = client.get("/")
        assert r.status_code == 200
        assert "Nenhuma nota importada" in r.text

        dashboard_main.app.dependency_overrides.clear()

    def test_api_dashboard_erro_db(self):
        """Linhas 1057-1059: api_dashboard com erro de DB retorna zeros."""
        engine = _make_engine()
        Base.metadata.create_all(engine)

        def _get_session_erro():
            ss = MagicMock()
            ss.query.side_effect = RuntimeError("DB down")
            yield ss
            ss.close()

        from src.dashboard import main as dashboard_main
        dashboard_main.app.dependency_overrides[dashboard_main.get_session] = _get_session_erro

        client = TestClient(dashboard_main.app)
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert data["total_notas"] == 0
        assert data["valor_total"] == 0

        dashboard_main.app.dependency_overrides.clear()


# ===========================================================================
# 2. src/importador/dfe.py
# ===========================================================================


class TestDfeCobertura:
    """Cobre linhas remanescentes do importador DF-e."""

    def _chave_valida(self):
        """Gera chave de 44 digitos com DV valido (modulo 11)."""
        base = "52" + "2406" + "11" + "222333000144" + "55" + "001" + "000000001" + "1"
        base = base[:43].ljust(43, "0")
        pesos = [2, 3, 4, 5, 6, 7, 8, 9]
        soma = 0
        for i in range(43):
            soma += int(base[42 - i]) * pesos[i % 8]
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        return base + str(dv)

    def _resumo_valido(self, chave=None):
        if chave is None:
            chave = self._chave_valida()
        return {
            "chave": chave,
            "valor_total": "1500.00",
            "data_emissao": "2026-07-15T00:00:00",
            "emitente_cnpj": "11222333000144",
            "emitente_nome": "Distribuidora SP",
            "tipo": "entrada",
            "natureza": "Compra",
            "numero": 1,
            "serie": 1,
            "nsu": "12345",
            "itens": [
                {"codigo": "001", "descricao": "Farinha 1kg", "ncm": "11010010",
                 "cfop": "1102", "valor_total": "1500.00",
                 "valor_unitario": "15.00", "quantidade": "100"},
            ],
        }

    def _make_importador(self):
        from src.importador.dfe import ImportadorDFe
        engine = _make_engine()
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        with patch("src.importador.dfe.Session", return_value=session):
            imp = ImportadorDFe()
        imp.session = session
        imp.client = MagicMock()
        return imp, session

    def test_consultar_dfe_sem_nsu_usa_get_ultimo(self):
        """Linha 97: consultar_dfe sem ultimo_nsu chama _get_ultimo_nsu."""
        imp, session = self._make_importador()
        imp._get_ultimo_nsu = MagicMock(return_value=0)
        imp._consultar_dfe_retry = MagicMock(
            return_value={"documentos": [], "ultimo_nsu": "1"}
        )
        imp.consultar_dfe()
        imp._get_ultimo_nsu.assert_called_once()
        session.close()

    def test_persistir_nfe_ncm_incompativel_cfop(self):
        """Linha 182: NCM incompativel com CFOP levanta ValueError."""
        imp, session = self._make_importador()
        resumo = self._resumo_valido()
        # CFOP de servico (1933) exige NCM='00', mas usamos NCM de mercadoria
        resumo["itens"][0]["cfop"] = "1933"
        resumo["itens"][0]["ncm"] = "11010010"
        with pytest.raises(ValueError, match="NCM incompat"):
            imp.persistir_nfe(resumo, "<xml/>")
        session.close()

    def test_persistir_nfe_ibscbs_sem_parametrizacao(self):
        """Linha 276: IBS/CBS sem parametrizacao vigente loga warning."""
        imp, session = self._make_importador()
        resumo = self._resumo_valido()
        resumo["tem_ibscbs"] = True
        # Data em ano sem aliquota (2030)
        resumo["data_emissao"] = "2030-07-15T00:00:00"
        with patch("src.importador.dfe.get_aliquota_ibscbs") as mock_alq:
            mock_alq.return_value = {"ibs": None, "cbs": None, "fase": "pendente"}
            nfe = imp.persistir_nfe(resumo, "<xml/>")
        assert nfe is not None
        # Item sem vibscbs calculado
        item = nfe.itens[0]
        assert item.vibscbs is None
        session.close()

    def test_importar_tudo_xml_invalido(self):
        """Linhas 323-325: XML invalido incrementa erros e continua."""
        imp, session = self._make_importador()
        chave = self._chave_valida()
        imp.consultar_dfe = lambda: {"documentos": [{"chave": chave}], "ultimo_nsu": "1"}
        imp.manifestar = lambda ch: None
        imp.baixar_xml = lambda ch: "<xml-invalido/>"
        imp.buscar_resumo = lambda ch: self._resumo_valido(ch)
        imp._salvar_nsu = lambda *a, **kw: None
        with patch("src.importador.dfe.validar_xml_nfe") as mock_val:
            mock_val.return_value = MagicMock(valido=False, erros=["erro"])
            stats = imp.importar_tudo()
        assert stats["erros"] == 1
        assert stats["importadas"] == 0
        session.close()

    def test_importar_tudo_erro_ao_importar_nota(self):
        """Linhas 335-342: erro ao importar nota faz rollback e continua."""
        imp, session = self._make_importador()
        chave = self._chave_valida()
        imp.consultar_dfe = lambda: {"documentos": [{"chave": chave}], "ultimo_nsu": "1"}
        imp.manifestar = lambda ch: None
        imp.baixar_xml = lambda ch: "<xml/>"
        # buscar_resumo levanta excecao
        imp.buscar_resumo = MagicMock(side_effect=RuntimeError("falha resumo"))
        imp._salvar_nsu = lambda *a, **kw: None
        with patch("src.importador.dfe.validar_xml_nfe") as mock_val:
            mock_val.return_value = MagicMock(valido=True, erros=[])
            stats = imp.importar_tudo()
        assert stats["erros"] == 1
        session.close()

    def test_importar_tudo_erro_geral(self):
        """Linhas 347-350: erro geral na importacao (consultar_dfe falha)."""
        imp, session = self._make_importador()
        imp.consultar_dfe = MagicMock(side_effect=RuntimeError("SEFAZ down"))
        imp._get_ultimo_nsu = lambda: 0
        imp._salvar_nsu = lambda *a, **kw: None
        stats = imp.importar_tudo()
        assert stats["erros"] == 1
        session.close()

    def test_importar_tudo_nota_cancelada(self):
        """Linha 335: importar_tudo com nota cancelada incrementa canceladas."""
        imp, session = self._make_importador()
        chave = self._chave_valida()
        imp.consultar_dfe = lambda: {"documentos": [{"chave": chave}], "ultimo_nsu": "1"}
        imp.manifestar = lambda ch: None
        imp.baixar_xml = lambda ch: "<xml/>"
        resumo = self._resumo_valido(chave)
        resumo["cancelada"] = True
        imp.buscar_resumo = lambda ch: resumo
        imp._salvar_nsu = lambda *a, **kw: None
        with patch("src.importador.dfe.validar_xml_nfe") as mock_val:
            mock_val.return_value = MagicMock(valido=True, erros=[])
            stats = imp.importar_tudo()
        assert stats["importadas"] == 1
        assert stats["canceladas"] == 1
        session.close()

    def test_importar_tudo_nota_duplicada(self):
        """Linha 337: importar_tudo com nota duplicada incrementa duplicadas."""
        imp, session = self._make_importador()
        chave = self._chave_valida()
        # Primeiro persiste a nota
        resumo = self._resumo_valido(chave)
        imp.persistir_nfe(resumo, "<xml/>")
        # Depois simula importar_tudo tentando importar a mesma
        imp.consultar_dfe = lambda: {"documentos": [{"chave": chave}], "ultimo_nsu": "1"}
        imp.manifestar = lambda ch: None
        imp.baixar_xml = lambda ch: "<xml/>"
        imp.buscar_resumo = lambda ch: resumo
        imp._salvar_nsu = lambda *a, **kw: None
        with patch("src.importador.dfe.validar_xml_nfe") as mock_val:
            mock_val.return_value = MagicMock(valido=True, erros=[])
            stats = imp.importar_tudo()
        assert stats["duplicadas"] == 1
        assert stats["importadas"] == 0
        session.close()


# ===========================================================================
# 3. src/gates/legislativo.py
# ===========================================================================


class TestLegislativoCobertura:
    """Cobre linhas remanescentes dos checks legislativos."""

    def test_check_nfe_chave_sem_validadores(self, tmp_path):
        """Linha 21: FAIL quando nao ha validadores no projeto."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_nfe_chave(ctx)
        assert result == CheckResult.FAIL

    def test_check_ecd_prazo_sem_modulo(self, tmp_path):
        """Linha 37: PASS_WITH_ISSUES quando modulo ECD nao encontrado."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_ecd_prazo(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "ECD" in details or "ecd" in details.lower()

    def test_check_ecd_prazo_com_gate_global(self, tmp_path):
        """Linhas 51-52: busca prazo junho no gate global quando local nao existe."""
        src = tmp_path / "src"
        src.mkdir()
        ecd = src / "contabilidade" / "ecd.py"
        ecd.parent.mkdir(parents=True)
        ecd.write_text("data_inicio = True\ndata_fim = True\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))

        real_read = _read_file

        def exists_side(path):
            # Gate local nao existe
            if "legislativo-gate" in path and str(tmp_path) in path:
                return False
            # Gate global existe
            if "legislativo-gate" in path and ".config" in path:
                return True
            return True

        def read_side(path):
            if "SKILL.md" in path:
                return "prazo de junho"
            return real_read(path)

        with patch("os.path.exists", side_effect=exists_side), \
             patch("src.gates.legislativo._read_file", side_effect=read_side):
            result, details = _check_ecd_prazo(ctx)
        assert result == CheckResult.PASS

    def test_check_reforma_tributaria_sem_modulos(self, tmp_path):
        """Linha 66: PASS_WITH_ISSUES quando modulos relevantes nao encontrados."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_reforma_tributaria(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_reforma_tributaria_ibs_sem_config(self, tmp_path):
        """Linha 76: PASS_WITH_ISSUES quando IBS presente mas sem config."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "models.py").write_text("ibs = True\ncbs = True\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_reforma_tributaria(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES
        assert "hardcoded" in details.lower() or "vigencia" in details.lower()

    def test_check_icms_sem_modulo_calculo(self, tmp_path):
        """Linha 85: PASS_WITH_ISSUES quando modulo de calculo nao encontrado."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_icms(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_manifest_sem_modulo(self, tmp_path):
        """Linha 102: PASS_WITH_ISSUES quando modulo de manifestacao nao encontrado."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_manifestacao(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_obrigacoes_sem_modulo(self, tmp_path):
        """Linha 137: PASS_WITH_ISSUES quando modulo apuracao nao encontrado."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_obrigacoes(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_cadeia_evidencia_sem_models(self, tmp_path):
        """Linha 153: PASS_WITH_ISSUES quando models nao encontrados."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_cadeia_evidencia(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES


# ===========================================================================
# 4. src/gates/contabil.py
# ===========================================================================


class TestContabilCobertura:
    """Cobre linhas remanescentes dos checks contabeis."""

    def test_read_file_erro_retorna_vazio(self, tmp_path):
        """Linhas 34-35: _read_file com arquivo inexistente retorna ''."""
        result = _read_file(str(tmp_path / "inexistente.py"))
        assert result == ""

    def test_check_plano_contas_sem_models(self, tmp_path):
        """Linha 72: PASS_WITH_ISSUES quando models nao encontrados."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_plano_contas(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_ncm_sem_validador(self, tmp_path):
        """Linha 105: PASS_WITH_ISSUES quando validador nao encontrado."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_ncm(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_cst_csosn_sem_csosn_e_sem_isento(self, tmp_path):
        """Linha 129: PASS_WITH_ISSUES quando cst referenciado mas incompleto."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("cst = '00'\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_cst_csosn(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_reconciliacao_sem_motor(self, tmp_path):
        """Linha 151: PASS_WITH_ISSUES quando motor nao encontrado."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_reconciliacao(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_tributos_sem_modulo(self, tmp_path):
        """Linha 168: PASS_WITH_ISSUES quando modulo calculo nao encontrado."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_tributos(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_estorno_sem_gerador(self, tmp_path):
        """Linha 186: PASS_WITH_ISSUES quando gerador nao encontrado."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_estorno(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_rastreabilidade_sem_models(self, tmp_path):
        """Linha 203: PASS_WITH_ISSUES quando models nao encontrados."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_rastreabilidade(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES

    def test_check_periodo_data_sem_ecd(self, tmp_path):
        """Linha 236: PASS_WITH_ISSUES quando modulo ECD nao encontrado."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "outro.py").write_text("x = 1\n", encoding="utf-8")
        ctx = ProjectContext(project_path=str(tmp_path))
        result, details = _check_periodo_data(ctx)
        assert result == CheckResult.PASS_WITH_ISSUES


# ===========================================================================
# 5. src/reconciliacao/gerador_pedidos.py
# ===========================================================================


class TestGeradorPedidosCobertura:
    """Cobre linhas remanescentes do gerador de pedidos."""

    def _criar_nfe_basica(self, session, chave_suffix="01", status="autorizada",
                          origem="sefaz", sem_emitente=False):
        """Cria NF-e para teste do gerador."""
        if sem_emitente:
            emitente = None
        else:
            emitente = Participante(cnpj_cpf=f"11222333000{chave_suffix}",
                                    nome=f"Fornecedor {chave_suffix}")
            session.add(emitente)
            session.flush()
        nfe = Nfe(
            chave_acesso=f"352008112223330001445500100000000{chave_suffix}0000000{chave_suffix}",
            numero_nota=int(chave_suffix), serie=1, modelo="55",
            data_emissao=datetime(2026, 7, 15, 10, 0),
            tipo_operacao="0", valor_total=Decimal("1000.00"),
            status_autorizacao=status, origem=origem,
            emitente_id=emitente.id if emitente else None,
        )
        session.add(nfe)
        session.flush()
        session.add(NfeItem(
            nfe_id=nfe.id, numero_item=1, descricao="Produto",
            ncm="11010010", cfop="1102", unidade="UN",
            quantidade=Decimal("10"), valor_unitario=Decimal("100"),
            valor_total=Decimal("1000"),
        ))
        session.commit()
        return nfe

    def test_gerar_pedidos_cria_session_propria(self):
        """Linha 43: gerar_pedidos_para_notas sem session cria propria."""
        from src.reconciliacao.gerador_pedidos import gerar_pedidos_para_notas
        engine = _make_engine()
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)
        with patch("src.reconciliacao.gerador_pedidos.SessionClass",
                   return_value=TestSession()):
            stats = gerar_pedidos_para_notas(session=None)
        assert "notas_verificadas" in stats

    def test_gerar_pedidos_sem_emitente_continua(self, session):
        """Linha 84: NF-e sem emitente e pulada (continue)."""
        from src.reconciliacao.gerador_pedidos import gerar_pedidos_para_notas
        self._criar_nfe_basica(session, sem_emitente=True)
        stats = gerar_pedidos_para_notas(session=session)
        # Nao quebra, apenas nao cria pedido para nota sem emitente
        assert stats["pedidos_criados"] == 0

    def test_gerar_pedidos_cenarios_divergencia(self, session):
        """Linhas 97-102: cenarios de divergencia de preco e quantidade."""
        from src.reconciliacao.gerador_pedidos import gerar_pedidos_para_notas
        # Cria varias notas para forcar cenarios divergentes
        for i in range(20):
            self._criar_nfe_basica(session, chave_suffix=f"{i:02d}")
        stats = gerar_pedidos_para_notas(session=session)
        # Com 20 notas e seed=42, deve ter pelo menos algum pedido criado
        assert stats["pedidos_criados"] > 0

    def test_gerar_pedidos_fecha_session_propria(self):
        """Linha 194: session propria e fechada no finally."""
        from src.reconciliacao.gerador_pedidos import gerar_pedidos_para_notas
        engine = _make_engine()
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)
        mock_session = MagicMock(wraps=TestSession())
        with patch("src.reconciliacao.gerador_pedidos.SessionClass",
                   return_value=mock_session):
            gerar_pedidos_para_notas(session=None)
        mock_session.close.assert_called_once()


# ===========================================================================
# 6. Outros pequenos
# ===========================================================================


class TestRateLimitCobertura:
    """Cobre linhas 58-59 (timeout) e 83 (sleep fallback) do rate_limit."""

    def test_rate_limiter_timeout(self):
        """Linhas 58-59: rate limiter levanta TimeoutError apos timeout."""
        from src.importador.rate_limit import RateLimiter
        import redis as redis_mod
        rl = RateLimiter(max_calls=1, window_seconds=10.0, timeout=0.2)
        rl.redis = MagicMock()
        rl.redis.zremrangebyscore.return_value = 0
        rl.redis.zcard.return_value = 1  # sempre cheio
        rl.redis.zrange.return_value = [["old", 0]]
        with pytest.raises(TimeoutError, match="timeout"):
            rl.acquire("timeout_test")

    def test_rate_limiter_sleep_fallback_sem_oldest(self):
        """Linha 83: quando oldest esta vazio, faz sleep(0.1)."""
        from src.importador.rate_limit import RateLimiter
        import redis as redis_mod
        rl = RateLimiter(max_calls=1, window_seconds=10.0, timeout=5.0)
        rl.redis = MagicMock()
        rl.redis.zremrangebyscore.return_value = 0
        rl.redis.zcard.return_value = 1  # cheio
        rl.redis.zrange.return_value = []  # oldest vazio
        with patch("src.importador.rate_limit.time.sleep") as mock_sleep:
            # Vai fazer varios sleeps ate timeout, mas testamos que sleep(0.1) e chamado
            rl.timeout = 0.05  # timeout curto para nao demorar
            with pytest.raises(TimeoutError):
                rl.acquire("fallback_test")
            mock_sleep.assert_called()


class TestApuracaoCobertura:
    """Cobre linhas 145 (mes==12) e 238 (imp_dict None) da apuracao."""

    def test_apurar_mes_dezembro(self, session):
        """Linha 145: apuracao de dezembro usa data_fim = 31/12."""
        from src.fiscal.apuracao import apurar_mes
        resultado = apurar_mes(session, 2026, 12)
        assert resultado.data_fim == date(2026, 12, 31)
        assert resultado.periodo == "2026-12"

    def test_apurar_mes_dict_com_imposto_none(self, session):
        """Linha 238: imp_dict retorna None quando imposto e None."""
        from src.fiscal.apuracao import apurar_mes_dict, ApuracaoMensal, ApuracaoImposto
        # Mock apurar_mes para retornar ApuracaoMensal com impostos None
        with patch("src.fiscal.apuracao.apurar_mes") as mock_ap:
            mock_ret = ApuracaoMensal(
                periodo="2026-07", data_inicio=date(2026, 7, 1),
                data_fim=date(2026, 7, 31),
            )
            mock_ret.icms = ApuracaoImposto(imposto="ICMS")
            mock_ret.icms_st = None
            mock_ret.ipi = None
            mock_ret.pis = None
            mock_ret.cofins = None
            mock_ret.ibs_cbs = None
            mock_ap.return_value = mock_ret
            d = apurar_mes_dict(session, 2026, 7)
        assert d["icms_st"] is None
        assert d["ipi"] is None
        assert d["pis"] is None


class TestCalculoCobertura:
    """Cobre linhas 228, 370, 377 do calculo tributario."""

    def test_calcular_icms_st_valor_negativo_zera(self):
        """Linha 228: ICMS ST negativo e zerado."""
        from src.fiscal.calculo import calcular_icms_st
        # valor_icms maior que valor_st_bruto para forcar negativo
        base_st, valor_st = calcular_icms_st(
            valor_total=Decimal("100"),
            uf_destino="SP",
            ncm="11010010",  # MVA 36%
            aliquota_icms_interna=Decimal("18"),
            valor_icms=Decimal("1000"),  # maior que st_bruto
        )
        assert valor_st == Decimal("0")

    def test_calcular_tributos_alerta_mva_nao_encontrado(self):
        """Linha 370: alerta quando MVA-ST nao encontrado para NCM."""
        from src.fiscal.calculo import calcular_tributos_item
        r = calcular_tributos_item(
            valor_total=Decimal("1000"),
            ncm="99999999",  # NCM sem MVA
            cfop="1102",
            uf_origem="SP", uf_destino="SP",
            calcular_st=True,
        )
        assert any("MVA" in a for a in r.alertas)

    def test_calcular_tributos_alerta_ipi_nao_encontrado(self):
        """Linha 377: alerta quando aliquota IPI nao encontrada para NCM."""
        from src.fiscal.calculo import calcular_tributos_item
        r = calcular_tributos_item(
            valor_total=Decimal("1000"),
            ncm="99999999",  # NCM sem IPI na tabela
            cfop="1102",
            uf_origem="SP", uf_destino="SP",
        )
        assert any("IPI" in a for a in r.alertas)


class TestEngineCobertura:
    """Cobre linhas 155, 158, 233, 289-290 do engine."""

    def test_legal_refs_vigentes(self):
        """Linha 155: Control.legal_refs_vigentes filtra por data."""
        ref_vigente = LegalRef("Lei A", vigencia_inicio="2020-01-01")
        ref_expirada = LegalRef("Lei B", vigencia_inicio="2010-01-01",
                                vigencia_fim="2015-01-01")
        ctrl = Control(
            id="T1", name="Teste", category="c",
            risk_type=RiskType.FINANCIAL, base_severity=Severity.HIGH,
            legal_refs=[ref_vigente, ref_expirada],
        )
        vigentes = ctrl.legal_refs_vigentes("2026-01-01")
        assert len(vigentes) == 1
        assert vigentes[0].name == "Lei A"

    def test_has_lapsed_legislation(self):
        """Linha 158: has_lapsed_legislation detecta legislacao expirada."""
        ref_vigente = LegalRef("Lei A", vigencia_inicio="2020-01-01")
        ref_expirada = LegalRef("Lei B", vigencia_inicio="2010-01-01",
                                vigencia_fim="2015-01-01")
        ctrl = Control(
            id="T1", name="Teste", category="c",
            risk_type=RiskType.FINANCIAL, base_severity=Severity.HIGH,
            legal_refs=[ref_vigente, ref_expirada],
        )
        assert ctrl.has_lapsed_legislation("2026-01-01") is True

        ctrl2 = Control(
            id="T2", name="Teste2", category="c",
            risk_type=RiskType.FINANCIAL, base_severity=Severity.HIGH,
            legal_refs=[ref_vigente],
        )
        assert ctrl2.has_lapsed_legislation("2026-01-01") is False

    def test_lapsed_legislation_property(self):
        """Linha 233: GateReport.lapsed_legislation retorna controles expirados."""
        ref_expirada = LegalRef("Lei B", vigencia_inicio="2010-01-01",
                                vigencia_fim="2015-01-01")
        ctrl = Control(
            id="T1", name="Teste", category="c",
            risk_type=RiskType.FINANCIAL, base_severity=Severity.HIGH,
            legal_refs=[ref_expirada],
            applicable_when=lambda ctx: True,
            check=lambda ctx: (CheckResult.PASS, "ok"),
        )
        gate = AdaptiveGate("teste", [ctrl])
        ctx = ProjectContext(regulatory_period="2026")
        report = gate.evaluate(ctx)
        lapsed = report.lapsed_legislation
        assert len(lapsed) == 1
        assert lapsed[0].id == "T1"

    def test_detect_context_erro_leitura_arquivo(self, tmp_path):
        """Linhas 289-290: erro ao ler arquivo em detect_context e ignorado."""
        src = tmp_path / "src"
        src.mkdir()
        # Cria arquivo .py que causa erro ao ler (permissoes)
        arq = src / "mod.py"
        arq.write_text("nfe = True\n", encoding="utf-8")
        with patch("builtins.open", side_effect=PermissionError("denied")):
            ctx = detect_context(str(tmp_path))
        # Nao quebra, apenas nao detecta nada
        assert ctx.handles_nfe is False


class TestModelsCobertura:
    """Cobre linhas 286 (init_db) e 291-295 (get_session) de models."""

    def test_init_db_cria_tabelas(self):
        """Linha 286: init_db chama create_all."""
        from src.persistencia.models import Base, init_db
        with patch.object(Base.metadata, "create_all") as mock_create:
            init_db()
            mock_create.assert_called_once()

    def test_get_session_yields_e_fecha(self):
        """Linhas 291-295: get_session e um generator que fecha a sessao."""
        from src.persistencia.models import get_session
        mock_sessao = MagicMock()
        mock_sessao.is_active = True
        with patch("src.persistencia.models.Session", return_value=mock_sessao):
            gen = get_session()
            sessao = next(gen)
            assert sessao is mock_sessao
            # Simular fim do generator (finally fecha a sessao)
            try:
                next(gen)
            except StopIteration:
                pass
            mock_sessao.close.assert_called_once()


class TestRegistryCobertura:
    """Cobre linha 32 de registry: is_vigente com vigencia_fim."""

    def test_is_vigente_com_vigencia_fim_expirada(self):
        """Linha 32: LegislationEntry.is_vigente retorna False quando expirada."""
        entry = LegislationEntry(
            id="test", name="Teste",
            vigencia_inicio=date(2020, 1, 1),
            vigencia_fim=date(2023, 12, 31),
        )
        assert entry.is_vigente(date(2024, 1, 1)) is False

    def test_is_vigente_com_vigencia_fim_dentro(self):
        """LegislationEntry.is_vigente retorna True quando dentro da vigencia."""
        entry = LegislationEntry(
            id="test", name="Teste",
            vigencia_inicio=date(2020, 1, 1),
            vigencia_fim=date(2030, 12, 31),
        )
        assert entry.is_vigente(date(2026, 1, 1)) is True
