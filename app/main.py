from dotenv import load_dotenv

# Doit être appelé avant les imports ci-dessous : app.users / app.email lisent
# des variables d'environnement (BREVO_API_KEY, APP_BASE_URL...) au chargement
# du module. En prod (Railway), les variables sont déjà dans l'environnement et
# .env n'existe pas — load_dotenv() ne fait rien dans ce cas.
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.middleware import CurrentUserMiddleware
from app.routers import auth, calcul, compte, pdf_test
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


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")
