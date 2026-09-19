"""align wallets, transactions, blacklist, and api key types

Revision ID: c4b8a1d9e2f0
Revises: 802072f834c9
Create Date: 2026-09-19 03:26:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4b8a1d9e2f0"
down_revision: Union[str, Sequence[str], None] = "802072f834c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table)}


def _column_type(table: str, column: str):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for col in inspector.get_columns(table):
        if col["name"] == column:
            return col["type"]
    return None


def _create_wallets() -> None:
    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_wallets_id"), "wallets", ["id"], unique=False)


def _create_transactions() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="COMPLETED"),
        sa.Column("reference_id", sa.String(), nullable=False),
        sa.Column("transaction_date", sa.DateTime(), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transactions_id"), "transactions", ["id"], unique=False)
    op.create_index(
        op.f("ix_transactions_reference_id"),
        "transactions",
        ["reference_id"],
        unique=True,
    )


def upgrade() -> None:
    tables = _table_names()

    if "blacklisted_token" not in tables:
        op.create_table(
            "blacklisted_token",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("token", sa.String(), nullable=False),
            sa.Column("blacklisted_on", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_blacklisted_token_id"),
            "blacklisted_token",
            ["id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_blacklisted_token_token"),
            "blacklisted_token",
            ["token"],
            unique=True,
        )

    if "apikeys_v2" in tables:
        is_active_type = _column_type("apikeys_v2", "is_active")
        if is_active_type is not None and not isinstance(is_active_type, sa.Boolean):
            op.execute("ALTER TABLE apikeys_v2 ALTER COLUMN is_active DROP DEFAULT")
            op.execute(
                """
                ALTER TABLE apikeys_v2
                ALTER COLUMN is_active TYPE boolean
                USING (is_active IS NOT NULL)
                """
            )
            op.execute("ALTER TABLE apikeys_v2 ALTER COLUMN is_active SET DEFAULT true")

    wallets_exist = "wallets" in tables
    old_wallet_schema = wallets_exist and "currency" in _column_names("wallets")
    old_tx_schema = "transactions" in tables and "sender_wallet_id" in _column_names(
        "transactions"
    )

    if old_tx_schema:
        op.drop_index(op.f("ix_transactions_id"), table_name="transactions")
        op.drop_table("transactions")
        op.execute("DROP TYPE IF EXISTS transactionstatus")

    if old_wallet_schema:
        op.drop_index(op.f("ix_wallets_id"), table_name="wallets")
        op.drop_table("wallets")
        wallets_exist = False

    if not wallets_exist:
        _create_wallets()

    op.execute(
        """
        INSERT INTO wallets (user_id, balance, is_active)
        SELECT id, 0.00, true
        FROM users
        WHERE id NOT IN (SELECT user_id FROM wallets)
        """
    )

    if "transactions" not in _table_names():
        _create_transactions()


def downgrade() -> None:
    tables = _table_names()
    if "transactions" in tables and "wallet_id" in _column_names("transactions"):
        op.drop_index(op.f("ix_transactions_reference_id"), table_name="transactions")
        op.drop_index(op.f("ix_transactions_id"), table_name="transactions")
        op.drop_table("transactions")
    if "wallets" in tables and "currency" not in _column_names("wallets"):
        op.drop_index(op.f("ix_wallets_id"), table_name="wallets")
        op.drop_table("wallets")
