"""Endpoints d'assistance à la saisie de l'identité professionnelle.

Utilisés en JSON par le JavaScript des formulaires d'inscription (/auth/register)
et de profil (/compte) — voir static/js/entreprise-form.js :

- GET /htmx/siret-info?siret=...      -> vérifie le SIRET + renvoie l'adresse établissement
- GET /htmx/communes?code_postal=...  -> communes correspondant à un code postal
- GET /htmx/rue-search?q=...&citycode=... -> autocomplétion de voie (API BAN), scopée commune

Ces routes ne bloquent jamais une inscription : la vérification SIRET qui fait
foi est refaite côté serveur au submit (app/routers/auth.py, app/routers/compte.py).
"""
import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app import siret as siret_service

router = APIRouter(tags=["entreprise"])

GEO_COMMUNES_URL = "https://geo.api.gouv.fr/communes"
BAN_URL = "https://api-adresse.data.gouv.fr/search/"


@router.get("/htmx/siret-info")
async def siret_info(siret: str = Query(default="")):
    check = await siret_service.verify_siret(siret)
    return JSONResponse(
        {
            "status": check.status,
            "raison_sociale": check.raison_sociale,
            "adresse": check.adresse,
        }
    )


@router.get("/htmx/communes")
async def communes(code_postal: str = Query(default="")):
    cp = "".join(ch for ch in code_postal if ch.isdigit())
    if len(cp) != 5:
        return JSONResponse([])
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                GEO_COMMUNES_URL, params={"codePostal": cp, "fields": "nom,code"}
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return JSONResponse([])
    communes = [
        {"nom": c.get("nom", ""), "code": c.get("code", "")}
        for c in data
        if c.get("nom") and c.get("code")
    ]
    return JSONResponse(communes)


@router.get("/htmx/rue-search")
async def rue_search(q: str = Query(default=""), citycode: str = Query(default="")):
    q = q.strip()
    if len(q) < 3:
        return JSONResponse([])
    params = {"q": q, "type": "street", "limit": 6, "autocomplete": 1}
    if citycode.strip():
        params["citycode"] = citycode.strip()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(BAN_URL, params=params)
            r.raise_for_status()
            features = r.json().get("features", [])
    except Exception:
        return JSONResponse([])
    rues = []
    for f in features:
        p = f.get("properties", {})
        if p.get("name"):
            rues.append({"name": p["name"], "city": p.get("city", ""), "citycode": p.get("citycode", "")})
    return JSONResponse(rues)
