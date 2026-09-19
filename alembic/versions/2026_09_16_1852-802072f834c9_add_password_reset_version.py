"""add password reset version

Revision ID: 802072f834c9
Revises: 80df77998cba
Create Date: 2026-09-16 18:52:43.633608

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "802072f834c9"
down_revision: Union[str, Sequence[str], None] = "80df77998cba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "password_reset_version",
            sa.Integer(),
            server_default="0",
            nullable=False
        )
    )


def downgrade() -> None:
    op.drop_column(
        "users",
        "password_reset_version"
    )