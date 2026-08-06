"""Modelos SQLAlchemy - espelham o schema.sql."""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, Date,
    Numeric, Boolean, ForeignKey, JSON, CHAR, BigInteger, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from src.config import settings

Base = declarative_base()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)
Session = sessionmaker(bind=engine)


class PlanoContas(Base):
    __tablename__ = "plano_contas"
    id = Column(Integer, primary_key=True)
    codigo_referencial = Column(String(20), unique=True, nullable=False)
    nome = Column(String(255), nullable=False)
    tipo = Column(String(20), nullable=False)
    conta_pai = Column(String(20))
    natureza = Column(String(10))
    created_at = Column(DateTime, default=datetime.now)


class Participante(Base):
    __tablename__ = "participante"
    id = Column(Integer, primary_key=True)
    cnpj_cpf = Column(String(14), unique=True, nullable=False)
    nome = Column(String(255), nullable=False)
    nome_fantasia = Column(String(255))
    endereco = Column(Text)
    municipio = Column(String(60))
    uf = Column(CHAR(2))
    cep = Column(String(8))
    ie = Column(String(20))
    im = Column(String(20))
    telefone = Column(String(20))
    email = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)

    notas_emitidas = relationship("Nfe", foreign_keys="Nfe.emitente_id", back_populates="emitente")
    notas_recebidas = relationship("Nfe", foreign_keys="Nfe.destinatario_id", back_populates="destinatario")


class Nfe(Base):
    __tablename__ = "nfe"
    id = Column(Integer, primary_key=True)
    chave_acesso = Column(String(44), unique=True, nullable=False)
    numero_nota = Column(Integer, nullable=False)
    serie = Column(Integer, nullable=False)
    modelo = Column(String(2), default="55", nullable=False)
    data_emissao = Column(DateTime, nullable=False)
    natureza_operacao = Column(String(255))
    tipo_operacao = Column(CHAR(1), nullable=False)
    valor_total = Column(Numeric(14, 2), nullable=False)
    valor_produtos = Column(Numeric(14, 2))
    valor_desconto = Column(Numeric(14, 2))
    valor_frete = Column(Numeric(14, 2))
    valor_seguro = Column(Numeric(14, 2))
    valor_outros = Column(Numeric(14, 2))
    status_autorizacao = Column(String(20), default="autorizada")
    origem = Column(String(20), default="sefaz")  # sefaz, sintetica, manual
    xml_original = Column(Text)
    protocolo = Column(String(20))
    data_autorizacao = Column(DateTime)
    manifestacao_destinatario = Column(String(20))
    nsu = Column(BigInteger)
    emitente_id = Column(Integer, ForeignKey("participante.id"))
    destinatario_id = Column(Integer, ForeignKey("participante.id"))
    transportador_id = Column(Integer, ForeignKey("participante.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    emitente = relationship("Participante", foreign_keys=[emitente_id], back_populates="notas_emitidas")
    destinatario = relationship("Participante", foreign_keys=[destinatario_id], back_populates="notas_recebidas")
    itens = relationship("NfeItem", back_populates="nfe", cascade="all, delete-orphan")
    tributos = relationship("NfeTributo", back_populates="nfe", cascade="all, delete-orphan")
    pagamentos = relationship("NfePagamento", back_populates="nfe", cascade="all, delete-orphan")
    eventos = relationship("NfeEvento", back_populates="nfe", cascade="all, delete-orphan")
    reconciliacoes = relationship("Reconciliacao", back_populates="nfe")
    lancamentos = relationship("LancamentoContabil", back_populates="nfe")


class NfeItem(Base):
    __tablename__ = "nfe_item"
    id = Column(Integer, primary_key=True)
    nfe_id = Column(Integer, ForeignKey("nfe.id", ondelete="CASCADE"), nullable=False)
    numero_item = Column(Integer, nullable=False)
    codigo_produto = Column(String(60))
    codigo_ean = Column(String(14))
    descricao = Column(Text, nullable=False)
    ncm = Column(String(8))
    cfop = Column(String(4))
    unidade = Column(String(10))
    quantidade = Column(Numeric(14, 4))
    valor_unitario = Column(Numeric(14, 4))
    valor_total = Column(Numeric(14, 2))
    valor_desconto = Column(Numeric(14, 2))
    valor_frete = Column(Numeric(14, 2))
    valor_seguro = Column(Numeric(14, 2))
    valor_outros = Column(Numeric(14, 2))
    vbc_icms = Column(Numeric(14, 2))
    vbc_icms_st = Column(Numeric(14, 2))
    vicms = Column(Numeric(14, 2))
    vicms_st = Column(Numeric(14, 2))
    vipi = Column(Numeric(14, 2))
    vpis = Column(Numeric(14, 2))
    vcofins = Column(Numeric(14, 2))
    vbc_ibscbs = Column(Numeric(14, 2))
    vibscbs = Column(Numeric(14, 2))
    aliquota_ibscbs = Column(Numeric(5, 2))

    nfe = relationship("Nfe", back_populates="itens")
    tributos = relationship("NfeTributo", back_populates="item", cascade="all, delete-orphan")


class NfeTributo(Base):
    __tablename__ = "nfe_tributo"
    id = Column(Integer, primary_key=True)
    nfe_id = Column(Integer, ForeignKey("nfe.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("nfe_item.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(String(20), nullable=False)
    base_calculo = Column(Numeric(14, 2))
    aliquota = Column(Numeric(5, 2))
    valor = Column(Numeric(14, 2))
    cst = Column(String(3))
    csosn = Column(String(4))

    nfe = relationship("Nfe", back_populates="tributos")
    item = relationship("NfeItem", back_populates="tributos")


class NfePagamento(Base):
    __tablename__ = "nfe_pagamento"
    id = Column(Integer, primary_key=True)
    nfe_id = Column(Integer, ForeignKey("nfe.id", ondelete="CASCADE"), nullable=False)
    forma_pagamento = Column(String(50))
    valor_pago = Column(Numeric(14, 2))
    bandeira = Column(String(30))
    cnpj_credenciadora = Column(String(14))

    nfe = relationship("Nfe", back_populates="pagamentos")


class NfeEvento(Base):
    __tablename__ = "nfe_evento"
    id = Column(Integer, primary_key=True)
    nfe_id = Column(Integer, ForeignKey("nfe.id", ondelete="CASCADE"), nullable=False)
    tipo_evento = Column(String(30))
    data_evento = Column(DateTime)
    sequencia = Column(Integer)
    xml_evento = Column(Text)
    protocolo = Column(String(20))
    status = Column(String(20))

    nfe = relationship("Nfe", back_populates="eventos")


class PedidoCompra(Base):
    __tablename__ = "pedido_compra"
    id = Column(Integer, primary_key=True)
    numero = Column(String(30), unique=True, nullable=False)
    fornecedor_cnpj = Column(String(14), nullable=False)
    fornecedor_nome = Column(String(255))
    data_pedido = Column(Date, nullable=False)
    valor_total = Column(Numeric(14, 2), nullable=False)
    condicao_pagamento = Column(String(100))
    status = Column(String(20), default="aberto")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    itens = relationship("PedidoCompraItem", back_populates="pedido", cascade="all, delete-orphan")
    recebimentos = relationship("Recebimento", back_populates="pedido")
    reconciliacoes = relationship("Reconciliacao", back_populates="pedido")


class PedidoCompraItem(Base):
    __tablename__ = "pedido_compra_item"
    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey("pedido_compra.id", ondelete="CASCADE"), nullable=False)
    numero_item = Column(Integer, nullable=False)
    codigo_produto = Column(String(60))
    descricao = Column(Text, nullable=False)
    ncm = Column(String(8))
    cfop = Column(String(4))
    unidade = Column(String(10))
    quantidade = Column(Numeric(14, 4), nullable=False)
    valor_unitario = Column(Numeric(14, 4), nullable=False)
    valor_total = Column(Numeric(14, 2), nullable=False)

    pedido = relationship("PedidoCompra", back_populates="itens")
    recebimento_itens = relationship("RecebimentoItem", back_populates="pedido_item")


class Recebimento(Base):
    __tablename__ = "recebimento"
    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey("pedido_compra.id"))
    data_recebimento = Column(Date, nullable=False)
    responsavel = Column(String(255))
    observacao = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    pedido = relationship("PedidoCompra", back_populates="recebimentos")
    itens = relationship("RecebimentoItem", back_populates="recebimento", cascade="all, delete-orphan")
    reconciliacoes = relationship("Reconciliacao", back_populates="recebimento")


class RecebimentoItem(Base):
    __tablename__ = "recebimento_item"
    id = Column(Integer, primary_key=True)
    recebimento_id = Column(Integer, ForeignKey("recebimento.id", ondelete="CASCADE"), nullable=False)
    pedido_item_id = Column(Integer, ForeignKey("pedido_compra_item.id"))
    quantidade_recebida = Column(Numeric(14, 4), nullable=False)
    conferido = Column(Boolean, default=False)
    divergencia = Column(Text)

    recebimento = relationship("Recebimento", back_populates="itens")
    pedido_item = relationship("PedidoCompraItem", back_populates="recebimento_itens")


class Reconciliacao(Base):
    __tablename__ = "reconciliacao"
    __table_args__ = (UniqueConstraint("nfe_id", name="uq_reconciliacao_nfe_id"),)
    id = Column(Integer, primary_key=True)
    nfe_id = Column(Integer, ForeignKey("nfe.id"))
    pedido_compra_id = Column(Integer, ForeignKey("pedido_compra.id"))
    recebimento_id = Column(Integer, ForeignKey("recebimento.id"))
    status = Column(String(20), default="pending")
    tipo_match = Column(String(20))
    divergencias = Column(JSON)
    tolerancia_percentual = Column(Numeric(5, 2), default=Decimal("2.00"))
    data_match = Column(DateTime)
    matched_by = Column(String(50), default="automatico")
    resolvido_por = Column(String(255))
    data_resolucao = Column(DateTime)
    justificativa_resolucao = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    nfe = relationship("Nfe", back_populates="reconciliacoes")
    pedido = relationship("PedidoCompra", back_populates="reconciliacoes")
    recebimento = relationship("Recebimento", back_populates="reconciliacoes")


class LancamentoContabil(Base):
    __tablename__ = "lancamento_contabil"
    id = Column(Integer, primary_key=True)
    nfe_id = Column(Integer, ForeignKey("nfe.id"))
    data_lancamento = Column(Date, nullable=False)
    numero_documento = Column(String(30))
    historico = Column(Text)
    conta_debito_codigo = Column(String(20), ForeignKey("plano_contas.codigo_referencial"))
    conta_credito_codigo = Column(String(20), ForeignKey("plano_contas.codigo_referencial"))
    valor = Column(Numeric(14, 2), nullable=False)
    estornado = Column(Boolean, default=False)
    lancamento_estorno_id = Column(Integer, ForeignKey("lancamento_contabil.id"))
    created_at = Column(DateTime, default=datetime.now)

    nfe = relationship("Nfe", back_populates="lancamentos")
    conta_debito = relationship("PlanoContas", foreign_keys=[conta_debito_codigo])
    conta_credito = relationship("PlanoContas", foreign_keys=[conta_credito_codigo])
    lancamento_estorno = relationship("LancamentoContabil", remote_side=[id])


class DfeImportacao(Base):
    __tablename__ = "dfe_importacao"
    id = Column(Integer, primary_key=True)
    cnpj_consultado = Column(String(14))
    ultimo_nsu = Column(BigInteger)
    total_documentos = Column(Integer)
    data_ultima_consulta = Column(DateTime)
    status = Column(String(20))
    erro_mensagem = Column(Text)


def init_db():
    """Cria todas as tabelas (usado em testes sem Alembic)."""
    Base.metadata.create_all(engine)


def get_session():
    """Retorna uma sessao do banco (para FastAPI dependency injection)."""
    session = Session()
    try:
        yield session
    finally:
        session.close()
