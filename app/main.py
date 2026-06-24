from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.routers import calcul

app = FastAPI(title="Instanote — Calcul charpente métallique")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(calcul.router)


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="base.html")
