"""Testes do exportador ECD com blocos J e K."""
from datetime import date, datetime
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistencia.models import Base, Nfe, NfeItem, Participante, LancamentoContabil, PlanoContas
from src.contabilidade.ecd import ExportadorECD


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _popular_dados(session):
    """Popula contas, participante, NF-e e lançamentos para teste ECD."""
    contas = [
        PlanoContas(codigo_referencial="1.1.3.01", nome="Estoque", tipo="ativo", natureza="devedora"),
        PlanoContas(codigo_referencial="2.1.01", nome="Fornecedores", tipo="passivo", natureza="credora"),
        PlanoContas(codigo_referencial="3.1.01", nome="Despesas", tipo="despesa", natureza="devedora"),
    ]
    for c in contas:
        session.add(c)

    emit = Participante(cnpj_cpf="11222333000144", nome="Emitente")
    dest = Participante(cnpj_cpf="12345678000190", nome="Destinatario")
    session.add(emit, dest)
    session.flush()

    nfe = Nfe(
        chave_acesso="35200811222333000144550010000000011000000001",
        numero_nota=1, serie=1, modelo="55",
        data_emissao=datetime(2026, 7, 15, 10, 0),
        tipo_operacao="0", valor_total=Decimal("1000.00"),
        status_autorizacao="autorizada", origem="sefaz",
        emitente_id=emit.id, destinatario_id=dest.id,
    )
    session.add(nfe)
    session.flush()

    lancs = [
        LancamentoContabil(
            nfe_id=nfe.id, data_lancamento=date(2026, 7, 15),
            numero_documento="1", historico="Compra teste",
            conta_debito_codigo="1.1.3.01", conta_credito_codigo="2.1.01",
            valor=Decimal("1000.00"),
        ),
        LancamentoContabil(
            nfe_id=nfe.id, data_lancamento=date(2026, 7, 20),
            numero_documento="2", historico="Despesa teste",
            conta_debito_codigo="3.1.01", conta_credito_codigo="2.1.01",
            valor=Decimal("500.00"),
        ),
    ]
    for l in lancs:
        session.add(l)
    session.commit()


class TestExportadorECD:
    def test_gera_bloco_0000(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        linhas = conteudo.strip().split("\n")
        assert linhas[0].startswith("|0000|")
        assert "ECD" in linhas[0]

    def test_gera_bloco_I(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        assert "|I001|" in conteudo
        assert "|I030|" in conteudo
        assert "|I050|" in conteudo
        assert "|I051|" in conteudo
        assert "|I012|" in conteudo
        assert "|I200|" in conteudo
        assert "|I250|" in conteudo
        assert "|I990|" in conteudo

    def test_gera_bloco_J(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        assert "|J001|" in conteudo
        assert "|J005|" in conteudo
        assert "|J100|" in conteudo
        assert "|J990|" in conteudo

    def test_gera_bloco_K(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        assert "|K001|" in conteudo
        assert "|K030|" in conteudo
        assert "|K100|" in conteudo
        assert "|K990|" in conteudo

    def test_gera_bloco_9(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        assert "|9001|" in conteudo
        assert "|9900|" in conteudo
        assert "|9990|" in conteudo
        assert "|9999|" in conteudo

    def test_total_registros_9999(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        linhas = conteudo.strip().split("\n")
        ultima = linhas[-1]
        # |9999|N| onde N = total de linhas
        partes = ultima.split("|")
        total_na_linha = int(partes[2])
        assert total_na_linha == len(linhas)

    def test_validacao_periodo_excessivo(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        with pytest.raises(ValueError):
            exp.exportar(date(2024, 1, 1), date(2026, 1, 1), "12345678000190", "Empresa Teste")

    def test_validacao_data_invertida(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        with pytest.raises(ValueError):
            exp.exportar(date(2026, 7, 31), date(2026, 7, 1), "12345678000190", "Empresa Teste")

    def test_validacao_cnpj_obrigatorio(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        with pytest.raises(ValueError):
            exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "", "Empresa Teste")

    def test_validacao_nome_obrigatorio(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        with pytest.raises(ValueError):
            exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "")

    def test_sem_lancamentos_gera_arquivo_valido(self, session):
        _popular_dados(session)
        # Remove lançamentos
        session.query(LancamentoContabil).delete()
        session.commit()
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        assert "|0000|" in conteudo
        assert "|I001|0|" in conteudo  # sem movimento
        assert "|9999|" in conteudo

    def test_dre_calculada(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        # Deve ter Receita ou Despesa no J100
        assert "Receita Operacional" in conteudo or "Despesas Operacionais" in conteudo
        assert "Resultado do Exercicio" in conteudo

    def test_balanco_patrimonial(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        assert "Balanco Patrimonial" in conteudo
        assert "Ativo Total" in conteudo

    def test_cnpj_formatado_14_digitos(self, session):
        _popular_dados(session)
        exp = ExportadorECD(session)
        conteudo = exp.exportar(date(2026, 7, 1), date(2026, 7, 31), "12345678000190", "Empresa Teste")
        # CNPJ no registro 0000 deve ter 14 dígitos
        linha_0000 = [l for l in conteudo.split("\n") if l.startswith("|0000|")][0]
        partes = linha_0000.split("|")
        # |0000|ECD|data_ini|data_fim|CNPJ|nome|A|1|
        # partes[0]="" [1]="0000" [2]="ECD" [3]=data_ini [4]=data_fim [5]=CNPJ
        cnpj = partes[5]
        assert len(cnpj) == 14
        assert cnpj == "12345678000190"
