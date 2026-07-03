import os
import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase

from app.database import get_user_db
from app.email import send_email
from app.models.user import User
from app.templating import templates

# IMPORTANT avant mise en prod : définir ces secrets comme variables d'env Railway
# (Settings -> Variables), ne jamais les committer en dur.
SECRET = os.environ.get("INSTANOTE26_AUTH_SECRET", "dev-secret-a-changer-absolument-en-prod")


def _app_base_url() -> str:
    """URL de base de l'app (ex: http://localhost:8000, https://instanote26.up.railway.app),
    utilisée pour construire les liens de vérification/réinitialisation dans les emails.
    Volontairement sans valeur par défaut en dur : à définir en variable d'env
    (voir CLAUDE.md), différente en local et en prod.
    """
    base_url = os.environ.get("APP_BASE_URL")
    if not base_url:
        raise RuntimeError(
            "APP_BASE_URL doit être défini en variable d'environnement "
            "(ex: http://localhost:8000 en local, voir CLAUDE.md)."
        )
    return base_url.rstrip("/")


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"[auth] Nouvel utilisateur inscrit : {user.email}")
        await self.request_verify(user, request)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        link = f"{_app_base_url()}/auth/verify?token={token}"
        html_content = templates.get_template("emails/verify.html").render(link=link)
        await send_email(user.email, "Vérifiez votre adresse email — Instanote26", html_content)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        link = f"{_app_base_url()}/auth/reset-password?token={token}"
        html_content = templates.get_template("emails/reset_password.html").render(link=link)
        await send_email(
            user.email, "Réinitialisation de mot de passe — Instanote26", html_content
        )


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


# Cookie plutôt que Bearer : plus adapté à un site rendu côté serveur (Jinja2 + HTMX)
# qu'à une API pure.
cookie_transport = CookieTransport(
    cookie_name="instanote26_auth",
    cookie_max_age=3600 * 24 * 7,  # 7 jours
    cookie_httponly=True,
    cookie_samesite="lax",
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600 * 24 * 7)


auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Dépendances prêtes à l'emploi pour protéger des routes :
#   @router.get("/dashboard")
#   async def dashboard(user: User = Depends(current_active_user)): ...
current_active_user = fastapi_users.current_user(active=True)
current_active_user_optional = fastapi_users.current_user(active=True, optional=True)
