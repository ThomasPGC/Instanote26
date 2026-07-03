from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.exceptions import UserAlreadyExists

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
