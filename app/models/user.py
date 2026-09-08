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

    `siret` + adresse (`numero` / `rue` / `complement` / `code_postal` /
    `ville`) : identité professionnelle collectée à l'inscription (session 9).
    **Tous nullable en base** : les comptes créés avant la session 9 n'ont pas
    ces données et doivent continuer à fonctionner. Le caractère obligatoire
    est imposé uniquement à la validation du formulaire d'inscription.
    """
    plan: Mapped[str] = mapped_column(String(10), default="S235", server_default="S235")

    nom: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prenom: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entreprise: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    siret: Mapped[Optional[str]] = mapped_column(String(14), nullable=True)
    numero: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    rue: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    complement: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    code_postal: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    ville: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
