"""notes internes admin + created_at sur user

Revision ID: 93d735ca7575
Revises: 7f738729c0ef
Create Date: 2026-09-09 10:06:48.951308

Ajoute deux colonnes à `user`, pour le back office admin (session 10) :
- `notes`      : TEXT nullable  -> notes internes libres de l'administrateur.
- `created_at` : DATETIME NOT NULL, défaut `CURRENT_TIMESTAMP` -> date
  d'inscription. Les lignes déjà présentes reçoivent l'instant d'application
  de la migration (le `server_default` remplit les valeurs existantes).

Migration idempotente, comme 7239b9e48d12 / 7f738729c0ef : n'ajoute que les
colonnes réellement absentes, pour ne pas casser une base dont le schéma aurait
pris de l'avance sur le pointeur de version Alembic.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93d735ca7575'
down_revision: Union[str, Sequence[str], None] = '7f738729c0ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_user_columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}


def upgrade() -> None:
    existing = _existing_user_columns()
    columns = {
        "notes": sa.Column("notes", sa.Text(), nullable=True),
        "created_at": sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    }
    to_add = [col for name, col in columns.items() if name not in existing]
    if not to_add:
        return

    with op.batch_alter_table("user", schema=None) as batch_op:
        for col in to_add:
            batch_op.add_column(col)


def downgrade() -> None:
    existing = _existing_user_columns()
    to_drop = [n for n in ("created_at", "notes") if n in existing]
    if not to_drop:
        return

    with op.batch_alter_table("user", schema=None) as batch_op:
        for name in to_drop:
            batch_op.drop_column(name)
