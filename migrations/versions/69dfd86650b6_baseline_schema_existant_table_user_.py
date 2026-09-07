"""baseline schema existant (table user fastapi-users)

Revision ID: 69dfd86650b6
Revises:
Create Date: 2026-09-07 18:13:32.979121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from fastapi_users_db_sqlalchemy.generics import GUID


# revision identifiers, used by Alembic.
revision: str = '69dfd86650b6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    """Baseline : crée la table `user` telle qu'elle existait avant la
    session 8 (colonnes fastapi-users + `plan`).

    Idempotent : si la table existe déjà (base « adoptée » — prod session 8,
    base de dev créée jadis par `create_db_and_tables`...), on ne fait rien,
    cette révision reste juste le point de départ de l'historique. Sur une
    base neuve, c'est ici que la table est créée — Alembic est désormais le
    seul à gérer le schéma (plus de `Base.metadata.create_all` au démarrage).
    """
    if _has_table("user"):
        return

    op.create_table(
        "user",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("plan", sa.String(length=10), server_default="S235", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)


def downgrade() -> None:
    """Retour à une base vierge : on supprime la table `user`."""
    if _has_table("user"):
        op.drop_index("ix_user_email", table_name="user")
        op.drop_table("user")
