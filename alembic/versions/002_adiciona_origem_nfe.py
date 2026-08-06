"""adiciona campo origem na tabela nfe

Revision ID: 002
Revises: 001
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nfe", sa.Column("origem", sa.String(20), server_default="sefaz", nullable=False))


def downgrade():
    op.drop_column("nfe", "origem")
