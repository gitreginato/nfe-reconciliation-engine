"""Criacao inicial do schema - 14 tabelas.

Revision ID: 001
Revises:
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Tabelas de dominio
    op.create_table(
        "plano_contas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("codigo_referencial", sa.String(20), unique=True, nullable=False),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("conta_pai", sa.String(20)),
        sa.Column("natureza", sa.String(10)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "participante",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cnpj_cpf", sa.String(14), unique=True, nullable=False),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("nome_fantasia", sa.String(255)),
        sa.Column("endereco", sa.Text),
        sa.Column("municipio", sa.String(60)),
        sa.Column("uf", sa.CHAR(2)),
        sa.Column("cep", sa.String(8)),
        sa.Column("ie", sa.String(20)),
        sa.Column("im", sa.String(20)),
        sa.Column("telefone", sa.String(20)),
        sa.Column("email", sa.String(255)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "nfe",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("chave_acesso", sa.String(44), unique=True, nullable=False),
        sa.Column("numero_nota", sa.Integer, nullable=False),
        sa.Column("serie", sa.Integer, nullable=False),
        sa.Column("modelo", sa.String(2), server_default="55", nullable=False),
        sa.Column("data_emissao", sa.DateTime, nullable=False),
        sa.Column("natureza_operacao", sa.String(255)),
        sa.Column("tipo_operacao", sa.CHAR(1), nullable=False),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("valor_produtos", sa.Numeric(14, 2)),
        sa.Column("valor_desconto", sa.Numeric(14, 2)),
        sa.Column("valor_frete", sa.Numeric(14, 2)),
        sa.Column("valor_seguro", sa.Numeric(14, 2)),
        sa.Column("valor_outros", sa.Numeric(14, 2)),
        sa.Column("status_autorizacao", sa.String(20), server_default="autorizada"),
        sa.Column("xml_original", sa.Text),
        sa.Column("protocolo", sa.String(20)),
        sa.Column("data_autorizacao", sa.DateTime),
        sa.Column("manifestacao_destinatario", sa.String(20)),
        sa.Column("nsu", sa.BigInteger),
        sa.Column("emitente_id", sa.Integer, sa.ForeignKey("participante.id")),
        sa.Column("destinatario_id", sa.Integer, sa.ForeignKey("participante.id")),
        sa.Column("transportador_id", sa.Integer, sa.ForeignKey("participante.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "nfe_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nfe_id", sa.Integer, sa.ForeignKey("nfe.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero_item", sa.Integer, nullable=False),
        sa.Column("codigo_produto", sa.String(60)),
        sa.Column("codigo_ean", sa.String(14)),
        sa.Column("descricao", sa.Text, nullable=False),
        sa.Column("ncm", sa.String(8)),
        sa.Column("cfop", sa.String(4)),
        sa.Column("unidade", sa.String(10)),
        sa.Column("quantidade", sa.Numeric(14, 4)),
        sa.Column("valor_unitario", sa.Numeric(14, 4)),
        sa.Column("valor_total", sa.Numeric(14, 2)),
        sa.Column("valor_desconto", sa.Numeric(14, 2)),
        sa.Column("valor_frete", sa.Numeric(14, 2)),
        sa.Column("valor_seguro", sa.Numeric(14, 2)),
        sa.Column("valor_outros", sa.Numeric(14, 2)),
        sa.Column("vbc_icms", sa.Numeric(14, 2)),
        sa.Column("vbc_icms_st", sa.Numeric(14, 2)),
        sa.Column("vicms", sa.Numeric(14, 2)),
        sa.Column("vicms_st", sa.Numeric(14, 2)),
        sa.Column("vipi", sa.Numeric(14, 2)),
        sa.Column("vpis", sa.Numeric(14, 2)),
        sa.Column("vcofins", sa.Numeric(14, 2)),
        sa.Column("vbc_ibscbs", sa.Numeric(14, 2)),
        sa.Column("vibscbs", sa.Numeric(14, 2)),
        sa.Column("aliquota_ibscbs", sa.Numeric(5, 2)),
        sa.UniqueConstraint("nfe_id", "numero_item"),
    )

    op.create_table(
        "nfe_tributo",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nfe_id", sa.Integer, sa.ForeignKey("nfe.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("nfe_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("base_calculo", sa.Numeric(14, 2)),
        sa.Column("aliquota", sa.Numeric(5, 2)),
        sa.Column("valor", sa.Numeric(14, 2)),
        sa.Column("cst", sa.String(3)),
        sa.Column("csosn", sa.String(4)),
    )

    op.create_table(
        "nfe_pagamento",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nfe_id", sa.Integer, sa.ForeignKey("nfe.id", ondelete="CASCADE"), nullable=False),
        sa.Column("forma_pagamento", sa.String(50)),
        sa.Column("valor_pago", sa.Numeric(14, 2)),
        sa.Column("bandeira", sa.String(30)),
        sa.Column("cnpj_credenciadora", sa.String(14)),
    )

    op.create_table(
        "nfe_evento",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nfe_id", sa.Integer, sa.ForeignKey("nfe.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo_evento", sa.String(30)),
        sa.Column("data_evento", sa.DateTime),
        sa.Column("sequencia", sa.Integer),
        sa.Column("xml_evento", sa.Text),
        sa.Column("protocolo", sa.String(20)),
        sa.Column("status", sa.String(20)),
    )

    op.create_table(
        "pedido_compra",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("numero", sa.String(30), unique=True, nullable=False),
        sa.Column("fornecedor_cnpj", sa.String(14), nullable=False),
        sa.Column("fornecedor_nome", sa.String(255)),
        sa.Column("data_pedido", sa.Date, nullable=False),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("condicao_pagamento", sa.String(100)),
        sa.Column("status", sa.String(20), server_default="aberto"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "pedido_compra_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("pedido_id", sa.Integer, sa.ForeignKey("pedido_compra.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero_item", sa.Integer, nullable=False),
        sa.Column("codigo_produto", sa.String(60)),
        sa.Column("descricao", sa.Text, nullable=False),
        sa.Column("ncm", sa.String(8)),
        sa.Column("cfop", sa.String(4)),
        sa.Column("unidade", sa.String(10)),
        sa.Column("quantidade", sa.Numeric(14, 4), nullable=False),
        sa.Column("valor_unitario", sa.Numeric(14, 4), nullable=False),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("pedido_id", "numero_item"),
    )

    op.create_table(
        "recebimento",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("pedido_id", sa.Integer, sa.ForeignKey("pedido_compra.id")),
        sa.Column("data_recebimento", sa.Date, nullable=False),
        sa.Column("responsavel", sa.String(255)),
        sa.Column("observacao", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "recebimento_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("recebimento_id", sa.Integer, sa.ForeignKey("recebimento.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pedido_item_id", sa.Integer, sa.ForeignKey("pedido_compra_item.id")),
        sa.Column("quantidade_recebida", sa.Numeric(14, 4), nullable=False),
        sa.Column("conferido", sa.Boolean, server_default=sa.false()),
        sa.Column("divergencia", sa.Text),
    )

    op.create_table(
        "reconciliacao",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nfe_id", sa.Integer, sa.ForeignKey("nfe.id")),
        sa.Column("pedido_compra_id", sa.Integer, sa.ForeignKey("pedido_compra.id")),
        sa.Column("recebimento_id", sa.Integer, sa.ForeignKey("recebimento.id")),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("tipo_match", sa.String(20)),
        sa.Column("divergencias", sa.JSON),
        sa.Column("tolerancia_percentual", sa.Numeric(5, 2), server_default="2.00"),
        sa.Column("data_match", sa.DateTime),
        sa.Column("matched_by", sa.String(50), server_default="automatico"),
        sa.Column("resolvido_por", sa.String(255)),
        sa.Column("data_resolucao", sa.DateTime),
        sa.Column("justificativa_resolucao", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "lancamento_contabil",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nfe_id", sa.Integer, sa.ForeignKey("nfe.id")),
        sa.Column("data_lancamento", sa.Date, nullable=False),
        sa.Column("numero_documento", sa.String(30)),
        sa.Column("historico", sa.Text),
        sa.Column("conta_debito_codigo", sa.String(20), sa.ForeignKey("plano_contas.codigo_referencial")),
        sa.Column("conta_credito_codigo", sa.String(20), sa.ForeignKey("plano_contas.codigo_referencial")),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("estornado", sa.Boolean, server_default=sa.false()),
        sa.Column("lancamento_estorno_id", sa.Integer, sa.ForeignKey("lancamento_contabil.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "dfe_importacao",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cnpj_consultado", sa.String(14)),
        sa.Column("ultimo_nsu", sa.BigInteger),
        sa.Column("total_documentos", sa.Integer),
        sa.Column("data_ultima_consulta", sa.DateTime),
        sa.Column("status", sa.String(20)),
        sa.Column("erro_mensagem", sa.Text),
    )

    # Indices
    op.create_index("idx_nfe_chave", "nfe", ["chave_acesso"])
    op.create_index("idx_nfe_data", "nfe", ["data_emissao"])
    op.create_index("idx_nfe_status", "nfe", ["status_autorizacao"])
    op.create_index("idx_nfe_nsu", "nfe", ["nsu"])
    op.create_index("idx_nfe_emitente", "nfe", ["emitente_id"])
    op.create_index("idx_nfe_destinatario", "nfe", ["destinatario_id"])
    op.create_index("idx_participante_cnpj", "participante", ["cnpj_cpf"])
    op.create_index("idx_nfe_item_nfe", "nfe_item", ["nfe_id"])
    op.create_index("idx_nfe_item_ncm", "nfe_item", ["ncm"])
    op.create_index("idx_nfe_item_cfop", "nfe_item", ["cfop"])
    op.create_index("idx_nfe_tributo_nfe", "nfe_tributo", ["nfe_id"])
    op.create_index("idx_nfe_tributo_item", "nfe_tributo", ["item_id"])
    op.create_index("idx_nfe_evento_nfe", "nfe_evento", ["nfe_id"])
    op.create_index("idx_reconciliacao_nfe", "reconciliacao", ["nfe_id"])
    op.create_index("idx_reconciliacao_status", "reconciliacao", ["status"])
    op.create_index("idx_reconciliacao_pedido", "reconciliacao", ["pedido_compra_id"])
    op.create_index("idx_lancamento_nfe", "lancamento_contabil", ["nfe_id"])
    op.create_index("idx_lancamento_data", "lancamento_contabil", ["data_lancamento"])
    op.create_index("idx_pedido_fornecedor", "pedido_compra", ["fornecedor_cnpj"])
    op.create_index("idx_pedido_data", "pedido_compra", ["data_pedido"])


def downgrade():
    op.drop_table("dfe_importacao")
    op.drop_table("lancamento_contabil")
    op.drop_table("reconciliacao")
    op.drop_table("recebimento_item")
    op.drop_table("recebimento")
    op.drop_table("pedido_compra_item")
    op.drop_table("pedido_compra")
    op.drop_table("nfe_evento")
    op.drop_table("nfe_pagamento")
    op.drop_table("nfe_tributo")
    op.drop_table("nfe_item")
    op.drop_table("nfe")
    op.drop_table("participante")
    op.drop_table("plano_contas")
