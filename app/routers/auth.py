import os

from disposable_email_domains import blocklist
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
from fastapi_users.exceptions import (
    InvalidPasswordException,
    InvalidResetPasswordToken,
    InvalidVerifyToken,
    UserAlreadyExists,
    UserAlreadyVerified,
    UserInactive,
    UserNotExists,
)

from app import siret as siret_service
from app.schemas.user import UserCreate
from app.templating import templates
from app.users import (
    UserManager,
    auth_backend,
    current_active_user_optional,
    get_jwt_strategy,
    get_user_manager,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Champs du formulaire d'inscription obligatoires côté validation (la base, elle,
# les accepte NULL : cf. app/models/user.py). `complement` d'adresse exclu.
_CHAMPS_INSCRIPTION_OBLIGATOIRES = (
    "nom", "prenom", "entreprise", "siret", "numero", "rue", "code_postal", "ville",
)

# Note : on n'utilise pas fastapi_users.get_auth_router() / get_register_router()
# directement. Ces routes sont pensées pour une API REST (réponses JSON) ; les
# mainteneurs de fastapi-users recommandent eux-mêmes de gérer la redirection
# côté "frontend" pour un site rendu côté serveur comme Instanote26. On appelle
# donc UserManager et le backend d'auth à la main, ce qui permet de renvoyer de
# vraies pages Jinja2 + des redirects classiques.


@router.get("/login")
async def login_page(request: Request, user=Depends(current_active_user_optional)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request=request, name="auth/login.html", context={})


@router.post("/login")
async def login(
    request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: UserManager = Depends(get_user_manager),
):
    user = await user_manager.authenticate(credentials)

    if user is None or not user.is_active:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "Email ou mot de passe incorrect."},
            status_code=400,
        )

    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)

    response = await auth_backend.transport.get_login_response(token)
    response.status_code = 303
    response.headers["location"] = "/"
    return response


@router.get("/register")
async def register_page(request: Request, user=Depends(current_active_user_optional)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request, name="auth/register.html", context={"form": {}}
    )


def _register_error(request: Request, form: dict, message: str):
    """Ré-affiche le formulaire d'inscription avec un message d'erreur et les
    valeurs déjà saisies (sauf le mot de passe)."""
    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={"error": message, "form": form},
        status_code=400,
    )


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    nom: str = Form(""),
    prenom: str = Form(""),
    entreprise: str = Form(""),
    siret: str = Form(""),
    numero: str = Form(""),
    rue: str = Form(""),
    complement: str = Form(""),
    code_postal: str = Form(""),
    ville: str = Form(""),
    user_manager: UserManager = Depends(get_user_manager),
):
    form = {
        "email": email.strip(),
        "nom": nom.strip(),
        "prenom": prenom.strip(),
        "entreprise": entreprise.strip(),
        "siret": siret.strip(),
        "numero": numero.strip(),
        "rue": rue.strip(),
        "complement": complement.strip(),
        "code_postal": code_postal.strip(),
        "ville": ville.strip(),
    }

    # 1. Champs obligatoires
    manquants = [c for c in _CHAMPS_INSCRIPTION_OBLIGATOIRES if not form[c]]
    if not form["email"] or not password:
        manquants.append("email")
    if manquants:
        return _register_error(
            request, form, "Merci de renseigner tous les champs obligatoires."
        )

    # 2. Formats
    if len(password) < 8:
        return _register_error(request, form, "Le mot de passe doit faire au moins 8 caractères.")

    siret_normalise = siret_service.normalize_siret(form["siret"])
    if len(siret_normalise) != 14:
        return _register_error(request, form, "Le numéro SIRET doit comporter 14 chiffres.")

    cp_normalise = "".join(ch for ch in form["code_postal"] if ch.isdigit())
    if len(cp_normalise) != 5:
        return _register_error(request, form, "Le code postal doit comporter 5 chiffres.")

    if "@" not in form["email"] or "." not in form["email"].rsplit("@", 1)[-1]:
        return _register_error(request, form, "Adresse email invalide.")

    if form["email"].rsplit("@", 1)[-1].lower() in blocklist:
        return _register_error(
            request, form,
            "Merci d'utiliser une adresse email permanente (pas d'adresse jetable).",
        )

    # 3. Vérification SIRET (bloquante sauf API indisponible)
    check = await siret_service.verify_siret(siret_normalise)
    if check.status == siret_service.NOT_FOUND:
        return _register_error(
            request, form,
            "Ce numéro SIRET est introuvable dans la base Sirene. Vérifiez la saisie.",
        )
    if check.status == siret_service.CLOSED:
        return _register_error(
            request, form,
            "L'établissement correspondant à ce SIRET est fermé ou l'entreprise est "
            "radiée. Utilisez le SIRET d'un établissement en activité.",
        )
    # check.status == API_UNAVAILABLE -> on ne bloque pas (déjà loggué dans app/siret.py)

    raison_sociale = (
        check.raison_sociale if check.status == siret_service.OK and check.raison_sociale
        else form["entreprise"]
    )

    # 4. Création du compte
    try:
        user_create = UserCreate(
            email=form["email"],
            password=password,
            nom=form["nom"],
            prenom=form["prenom"],
            entreprise=raison_sociale,
            siret=siret_normalise,
            numero=form["numero"],
            rue=form["rue"],
            complement=form["complement"] or None,
            code_postal=cp_normalise,
            ville=form["ville"],
        )
    except ValidationError:
        return _register_error(request, form, "Adresse email invalide.")

    try:
        user = await user_manager.create(user_create)
    except UserAlreadyExists:
        return _register_error(request, form, "Un compte existe déjà avec cet email.")
    except InvalidPasswordException as exc:
        return _register_error(request, form, f"Mot de passe invalide : {exc.reason}")

    # 5. Connexion automatique puis page « vérifiez votre boîte mail »
    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)
    response = await auth_backend.transport.get_login_response(token)
    response.status_code = 303
    response.headers["location"] = "/auth/inscription-terminee"
    return response


@router.get("/inscription-terminee")
async def inscription_terminee(request: Request):
    user = getattr(request.state, "user", None)
    return templates.TemplateResponse(
        request=request,
        name="auth/inscription_terminee.html",
        context={
            "email": user.email if user else None,
            "email_from": os.environ.get("EMAIL_FROM"),
        },
    )


@router.get("/logout")
async def logout(request: Request):
    response = await auth_backend.transport.get_logout_response()
    response.status_code = 303
    response.headers["location"] = "/auth/login"
    return response


@router.get("/verify")
async def verify_email(
    request: Request,
    token: str,
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        await user_manager.verify(token)
        message, success = "Votre adresse email a bien été vérifiée.", True
    except UserAlreadyVerified:
        message, success = "Cette adresse email était déjà vérifiée.", True
    except InvalidVerifyToken:
        message, success = "Ce lien de vérification est invalide ou a expiré.", False

    return templates.TemplateResponse(
        request=request,
        name="auth/verify_result.html",
        context={"message": message, "success": success},
    )


@router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="auth/forgot_password.html", context={}
    )


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        user = await user_manager.get_by_email(email)
        await user_manager.forgot_password(user)
    except (UserNotExists, UserInactive):
        pass  # on ne révèle pas si le compte existe ou non

    return templates.TemplateResponse(
        request=request,
        name="auth/forgot_password.html",
        context={"sent": True},
    )


@router.get("/reset-password")
async def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse(
        request=request,
        name="auth/reset_password.html",
        context={"token": token},
    )


@router.post("/reset-password")
async def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        await user_manager.reset_password(token, password)
    except InvalidResetPasswordToken:
        return templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context={
                "token": token,
                "error": "Ce lien de réinitialisation est invalide ou a expiré.",
            },
            status_code=400,
        )
    except UserInactive:
        return templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context={"token": token, "error": "Ce compte est désactivé."},
            status_code=400,
        )
    except InvalidPasswordException as exc:
        return templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context={"token": token, "error": f"Mot de passe invalide : {exc.reason}"},
            status_code=400,
        )

    return RedirectResponse(url="/auth/login", status_code=303)
