from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.database import create_db_and_tables
from app.middleware import CurrentUserMiddleware
from app.routers import auth, calcul, pdf_test
from app.templating import templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(title="Instanote — Calcul charpente métallique", lifespan=lifespan)

app.add_middleware(CurrentUserMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(calcul.router)
app.include_router(pdf_test.router)
app.include_router(auth.router)


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="base.html")
