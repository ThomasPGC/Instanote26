from typing import Optional

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

    `nom` / `prenom` / `entreprise` : champs de profil éditables depuis la page
    « Mon compte » (/compte). Nullable : un compte fraîchement créé n'a que son
    email, ces champs sont renseignés après coup (ou jamais).
    """
    plan: Mapped[str] = mapped_column(String(10), default="S235", server_default="S235")

    nom: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prenom: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entreprise: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
