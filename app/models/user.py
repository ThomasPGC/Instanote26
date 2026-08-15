from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Table utilisateur. Hérite déjà de id / email / hashed_password /
    is_active / is_superuser / is_verified via SQLAlchemyBaseUserTableUUID.

    `plan` est une préparation légère pour Stripe (pas branché cette session) :
    S235 = gratuit/entrée, S275 = intermédiaire, S355 = haut de gamme.
    Aucune logique ne dépend encore de ce champ.
    """
    plan: Mapped[str] = mapped_column(String(10), default="S235", server_default="S235")
