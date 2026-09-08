import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    plan: str
    nom: str | None = None
    prenom: str | None = None
    entreprise: str | None = None
    siret: str | None = None
    numero: str | None = None
    rue: str | None = None
    complement: str | None = None
    code_postal: str | None = None
    ville: str | None = None


class UserCreate(schemas.BaseUserCreate):
    # Champs d'identité professionnelle : facultatifs au niveau du schéma (la
    # base les accepte NULL pour les comptes d'avant la session 9), mais rendus
    # obligatoires par la validation du formulaire d'inscription
    # (app/routers/auth.py). `user_manager.create()` les recopie tels quels
    # dans la ligne User via create_update_dict().
    nom: str | None = None
    prenom: str | None = None
    entreprise: str | None = None
    siret: str | None = None
    numero: str | None = None
    rue: str | None = None
    complement: str | None = None
    code_postal: str | None = None
    ville: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    plan: str | None = None
