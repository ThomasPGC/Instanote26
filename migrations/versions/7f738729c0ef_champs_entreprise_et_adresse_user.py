"""champs entreprise et adresse user

Revision ID: 7f738729c0ef
Revises: 7239b9e48d12
Create Date: 2026-09-08 14:56:37.089643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f738729c0ef'
down_revision: Union[str, Sequence[str], None] = '7239b9e48d12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Colonnes ajoutées par cette révision (nom -> type SQLAlchemy).
_NEW_COLUMNS = {
    "siret": sa.String(length=14),
    "numero": sa.String(length=20),
    "rue": sa.String(length=255),
    "complement": sa.String(length=255),
    "code_postal": sa.String(length=5),
    "ville": sa.String(length=100),
}


def _existing_user_columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}


def upgrade() -> None:
    # Idempotent (cf. migration 7239b9e48d12) : n'ajoute que les colonnes
    # réellement absentes, pour ne pas casser une base dont le schéma aurait
    # pris de l'avance sur le pointeur de version Alembic.
    existing = _existing_user_columns()
    to_add = [(n, t) for n, t in _NEW_COLUMNS.items() if n not in existing]
    if not to_add:
        return

    with op.batch_alter_table("user", schema=None) as batch_op:
        for name, col_type in to_add:
            batch_op.add_column(sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    existing = _existing_user_columns()
    to_drop = [n for n in _NEW_COLUMNS if n in existing]
    if not to_drop:
        return

    with op.batch_alter_table("user", schema=None) as batch_op:
        for name in reversed(to_drop):
            batch_op.drop_column(name)
