from disposable_email_domains import blocklist
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.exceptions import (
    InvalidPasswordException,
    InvalidResetPasswordToken,
    InvalidVerifyToken,
    UserAlreadyExists,
    UserAlreadyVerified,
    UserInactive,
    UserNotExists,
)

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
    return templates.TemplateResponse(request=request, name="auth/register.html", context={})


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    user_manager: UserManager = Depends(get_user_manager),
):
    domain = email.rsplit("@", 1)[-1].lower()
    if domain in blocklist:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": "Merci d'utiliser une adresse email permanente (pas d'adresse jetable)."},
            status_code=400,
        )

    try:
        user = await user_manager.create(UserCreate(email=email, password=password))
    except UserAlreadyExists:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": "Un compte existe déjà avec cet email."},
            status_code=400,
        )

    # Connexion automatique juste après l'inscription
    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)
    response = await auth_backend.transport.get_login_response(token)
    response.status_code = 303
    response.headers["location"] = "/"
    return response


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
