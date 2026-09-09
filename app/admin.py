"""Back office administrateur (SQLAdmin), session 10.

Monté sur `/admin` par `setup_admin(app)` (appelé dans `app/main.py`).

Points clés :

- **Pas de système de login séparé.** `AdminAuth` réutilise le cookie JWT
  `instanote26_auth` posé par fastapi-users : mêmes identifiants que le reste
  du site. L'accès à `/admin` exige `is_active` **ET** `is_superuser`.
  - non connecté            -> redirection vers `/auth/login`
  - connecté mais pas admin -> réponse 403 explicite
  Ce contrôle est fait par `login_required` de SQLAdmin sur *chaque* route de
  l'admin (liste, détail, édition, suppression, actions) : taper l'URL à la
  main ne contourne rien.

- **Suppression = vraie suppression SQL** (`DELETE FROM user ...`), pas de soft
  delete — pour honorer les demandes RGPD de suppression de compte.
  `UserAdmin.on_model_delete` logge l'email + la date **avant** l'effacement,
  pour garder une trace applicative même une fois le compte parti.

- **`plan`** est le seul champ non librement éditable : liste déroulante fermée
  (S235 / S275 / S355), pour qu'une faute de frappe ne casse pas un accès
  payant. `hashed_password` n'est exposé ni en liste, ni en détail, ni en
  édition.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi_users.db import SQLAlchemyUserDatabase
from sqladmin import Admin, ModelView, action
from sqladmin.audit import LoggingAuditBackend
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse
from wtforms.fields import SelectField

from app.database import async_session_maker, engine
from app.models.user import User
from app.users import SECRET, UserManager, cookie_transport, get_jwt_strategy

logger = logging.getLogger("instanote26.admin")

PLAN_CHOICES = [("S235", "S235"), ("S275", "S275"), ("S355", "S355")]


class AdminAuth(AuthenticationBackend):
    """Authentification du back office adossée au cookie JWT de fastapi-users.

    `authenticate()` est appelée par SQLAdmin (`login_required`) sur chaque
    requête vers `/admin/...`. Elle peut renvoyer :
      - `True`                -> accès autorisé
      - une `Response`        -> renvoyée telle quelle au navigateur
      - `False` / falsy       -> SQLAdmin redirige vers son propre `/admin/login`

    On renvoie donc soit `True`, soit une `Response` (redirect login / 403), et
    jamais `False` : l'utilisateur n'atterrit jamais sur le formulaire de login
    interne de SQLAdmin, qu'on n'utilise pas.
    """

    async def _current_user(self, request: Request) -> User | None:
        token = request.cookies.get(cookie_transport.cookie_name)
        if not token:
            return None
        async with async_session_maker() as session:
            user_manager = UserManager(SQLAlchemyUserDatabase(session, User))
            user = await get_jwt_strategy().read_token(token, user_manager)
        return user

    async def authenticate(self, request: Request):
        user = await self._current_user(request)
        if user and user.is_active and user.is_superuser:
            return True
        if user is not None:
            # Connecté (cookie valide) mais pas administrateur.
            return PlainTextResponse(
                "403 — Accès réservé aux administrateurs.", status_code=403
            )
        # Pas de cookie / cookie invalide / compte désactivé.
        return RedirectResponse("/auth/login", status_code=302)

    async def login(self, request: Request):
        # Le formulaire de login interne de SQLAdmin n'est pas utilisé : on
        # renvoie toujours vers la page de connexion du site.
        return RedirectResponse("/auth/login", status_code=302)

    async def logout(self, request: Request):
        return RedirectResponse("/auth/logout", status_code=302)


class UserAdmin(ModelView, model=User):
    name = "Utilisateur"
    name_plural = "Utilisateurs"
    icon = "fa-solid fa-users"

    # --- Liste ---
    column_list = [
        User.email,
        User.nom,
        User.prenom,
        User.entreprise,
        User.plan,
        User.is_active,
        User.is_verified,
        User.is_superuser,
        User.created_at,
    ]
    column_default_sort = ("created_at", True)  # plus récents en haut
    column_sortable_list = [
        User.email,
        User.entreprise,
        User.plan,
        User.is_active,
        User.is_verified,
        User.created_at,
    ]
    column_searchable_list = [User.email, User.entreprise]

    column_labels = {
        User.email: "Email",
        User.nom: "Nom",
        User.prenom: "Prénom",
        User.entreprise: "Entreprise (raison sociale)",
        User.plan: "Offre",
        User.is_active: "Actif",
        User.is_verified: "Email vérifié",
        User.is_superuser: "Admin",
        User.created_at: "Inscription",
        User.siret: "SIRET",
        User.numero: "N°",
        User.rue: "Rue",
        User.complement: "Complément",
        User.code_postal: "Code postal",
        User.ville: "Ville",
        User.notes: "Notes internes",
    }

    # --- Détail : on masque le hash du mot de passe ---
    column_details_exclude_list = [User.hashed_password]

    # --- Formulaire d'édition ---
    # Tous les champs sont éditables en texte libre SAUF `plan` (liste fermée,
    # cf. form_overrides). `hashed_password` / `id` / `created_at` hors du form.
    can_create = False  # la création de compte passe par /auth/register (hash mdp)
    can_edit = True
    can_delete = True
    can_view_details = True

    form_excluded_columns = [User.hashed_password, User.id, User.created_at]
    form_overrides = {"plan": SelectField}
    form_args = {"plan": {"choices": PLAN_CHOICES}}

    # --- Actions groupées : activer / désactiver depuis la liste ---
    @action(
        name="activer",
        label="Activer",
        add_in_detail=True,
        add_in_list=True,
    )
    async def activer(self, request: Request):
        return await self._set_active(request, True)

    @action(
        name="desactiver",
        label="Désactiver",
        confirmation_message=(
            "Désactiver le(s) compte(s) sélectionné(s) ? "
            "Ils ne pourront plus se connecter."
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def desactiver(self, request: Request):
        return await self._set_active(request, False)

    async def _set_active(self, request: Request, value: bool):
        pks = [p for p in request.query_params.get("pks", "").split(",") if p]
        changed = 0
        if pks:
            async with self.session_maker() as session:
                for pk in pks:
                    obj = await session.get(User, uuid.UUID(pk))
                    if obj is not None and obj.is_active != value:
                        obj.is_active = value
                        changed += 1
                await session.commit()
            logger.info(
                "admin: is_active=%s appliqué à %d compte(s) (pks=%s)",
                value, changed, ",".join(pks),
            )
        return RedirectResponse(
            request.url_for("admin:list", identity=self.identity),
            status_code=302,
        )

    async def on_model_delete(self, model: User, request: Request) -> None:
        """Trace la suppression AVANT effacement effectif (demande RGPD).

        Le compte disparaît de la base ; cette ligne de log reste la seule
        preuve applicative que la suppression a eu lieu.
        """
        logger.info(
            "admin: SUPPRESSION DEFINITIVE compte email=%s id=%s date=%s",
            model.email,
            model.id,
            datetime.now(timezone.utc).isoformat(),
        )


def setup_admin(app) -> Admin:
    admin = Admin(
        app,
        engine,
        title="Instanote — Back office",
        authentication_backend=AdminAuth(secret_key=SECRET),
        # Trace create / update / delete dans le logger "instanote26.admin.audit".
        audit_backend=LoggingAuditBackend(logger_name="instanote26.admin.audit"),
    )
    admin.add_view(UserAdmin)
    return admin
