from dotenv import load_dotenv

# Doit être appelé avant les imports ci-dessous : app.users / app.email lisent
# des variables d'environnement (BREVO_API_KEY, APP_BASE_URL...) au chargement
# du module. En prod (Railway), les variables sont déjà dans l'environnement et
# .env n'existe pas — load_dotenv() ne fait rien dans ce cas.
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.middleware import CurrentUserMiddleware
from app.routers import auth, calcul, compte, entreprise, pdf_test
from app.templating import templates

# Le schéma de base est géré exclusivement par Alembic (`alembic upgrade head`,
# lancé par la commande de démarrage Railway et à faire à la main en dev) —
# il n'y a plus de création de tables au démarrage de l'app.
app = FastAPI(title="Instanote — Calcul charpente métallique")

app.add_middleware(CurrentUserMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(calcul.router)
app.include_router(pdf_test.router)
app.include_router(auth.router)
app.include_router(compte.router)
app.include_router(entreprise.router)


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.exception_handler(404)
async def page_introuvable(request: Request, exc: StarletteHTTPException):
    """Page 404 HTML cohérente avec le reste du site, en gardant le code 404.

    Ne s'applique qu'aux navigations navigateur (en-tête `Accept: text/html`,
    hors requête HTMX). Les autres cas — requêtes HTMX, appels JSON/API, assets
    statiques manquants — conservent la réponse 404 « brute » `{"detail": ...}`,
    identique au comportement FastAPI par défaut. Aucun endpoint ne renvoie 404
    volontairement aujourd'hui, mais ça évite d'en casser un plus tard.
    """
    accept = request.headers.get("accept", "")
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    if is_htmx or "text/html" not in accept:
        return JSONResponse({"detail": exc.detail or "Not Found"}, status_code=404)

    return templates.TemplateResponse(
        request=request, name="errors/404.html", status_code=404
    )
