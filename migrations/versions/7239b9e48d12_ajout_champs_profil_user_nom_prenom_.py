"""ajout champs profil user (nom, prenom, entreprise)

Revision ID: 7239b9e48d12
Revises: 69dfd86650b6
Create Date: 2026-09-07 18:14:13.187544

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7239b9e48d12'
down_revision: Union[str, Sequence[str], None] = '69dfd86650b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Colonnes de profil ajoutées par cette révision (nom -> type SQLAlchemy).
_PROFIL_COLUMNS = {
    "nom": sa.String(length=100),
    "prenom": sa.String(length=100),
    "entreprise": sa.String(length=200),
}


def _existing_user_columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}


def upgrade() -> None:
    # Idempotent : n'ajoute que les colonnes réellement absentes. Protège les
    # bases où le schéma a pu prendre de l'avance sur le pointeur de version
    # Alembic (ex. ancienne base créée par create_all avec le modèle à jour).
    existing = _existing_user_columns()
    to_add = [(n, t) for n, t in _PROFIL_COLUMNS.items() if n not in existing]
    if not to_add:
        return

    with op.batch_alter_table("user", schema=None) as batch_op:
        for name, col_type in to_add:
            batch_op.add_column(sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    existing = _existing_user_columns()
    to_drop = [n for n in _PROFIL_COLUMNS if n in existing]
    if not to_drop:
        return

    with op.batch_alter_table("user", schema=None) as batch_op:
        for name in reversed(to_drop):
            batch_op.drop_column(name)
