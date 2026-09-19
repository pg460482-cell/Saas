"""add is active to users

Revision ID: 80df77998cba
Revises: 42f3519065f4
Create Date: 2026-09-16 17:51:44.234963
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80df77998cba'
down_revision: Union[str, Sequence[str], None] = '42f3519065f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False
        )
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("users", "is_active")