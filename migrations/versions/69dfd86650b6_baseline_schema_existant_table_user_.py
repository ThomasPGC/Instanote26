"""baseline schema existant (table user fastapi-users)

Revision ID: 69dfd86650b6
Revises: 
Create Date: 2026-09-07 18:13:32.979121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69dfd86650b6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migration « baseline » volontairement vide.

    Au moment où Alembic a été introduit dans le projet, la table `user`
    (fastapi-users : id / email / hashed_password / is_active / is_superuser /
    is_verified + `plan`) existait déjà, créée par
    `Base.metadata.create_all` au démarrage de l'app.

    Cette révision ne fait donc rien : elle sert uniquement de point de départ
    à l'historique des migrations. Sur la base existante on a fait
    `alembic stamp head` pour marquer cet état comme déjà appliqué, sans
    rejouer de DDL. Sur une base neuve, `alembic upgrade head` passera ici
    sans rien créer — c'est `create_db_and_tables()` (lifespan de main.py) qui
    crée la table `user` de base.
    """
    pass


def downgrade() -> None:
    """Rien à annuler : voir upgrade()."""
    pass
