import sys
import pathlib

_BUSINESS = pathlib.Path(__file__).parent.parent.parent / "business"
if str(_BUSINESS) not in sys.path:
    sys.path.insert(0, str(_BUSINESS))

import httpx
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import calcport

router = APIRouter()
templates = Jinja2Templates(directory="templates")

RUGOSITES = [
    ("0",    "Catégorie 0 — Mer, lac, zones côtières exposées"),
    ("II",   "Catégorie II — Rase campagne, prairies, lacs"),
    ("IIIa", "Catégorie IIIa — Campagne avec haies, bocage"),
    ("IIIb", "Catégorie IIIb — Zones périurbaines, forêts"),
    ("IV",   "Catégorie IV — Zones urbaines denses, forêts étendues"),
]

BAN_URL = "https://api-adresse.data.gouv.fr/search/"
IGN_URL = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"


@router.get("/calcul", response_class=HTMLResponse)
async def calcul_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="calcul/form.html",
        context={"rugosites": RUGOSITES},
    )


@router.get("/htmx/geocode-search", response_class=HTMLResponse)
async def geocode_search(request: Request, q: str = Query(default="")):
    q = q.strip()
    if len(q) < 3:
        return HTMLResponse("")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(BAN_URL, params={"q": q, "limit": 6})
            data = r.json()
            features = data.get("features", [])
        except Exception:
            features = []
    return templates.TemplateResponse(
        request=request,
        name="calcul/geocode_suggestions.html",
        context={"features": features},
    )


@router.get("/htmx/geocode-fill", response_class=HTMLResponse)
async def geocode_fill(
    request: Request,
    lat: float = Query(...),
    lon: float = Query(...),
    city: str = Query(...),
    context: str = Query(...),
    old_city: str = Query(default=""),
):
    dept = context.split(",")[0].strip() if context else ""
    altitude = 0
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(IGN_URL, params={"lon": lon, "lat": lat, "resource": "ign_rge_alti_wld"})
            data = r.json()
            z = data.get("elevations", [{}])[0].get("z", 0)
            altitude = max(0, int(round(z)))
        except Exception:
            altitude = 0
    return templates.TemplateResponse(
        request=request,
        name="calcul/geocode_filled.html",
        context={
            "city": city,
            "old_city": old_city,
            "dept": dept,
            "altitude": altitude,
        },
    )


@router.post("/htmx/calcul", response_class=HTMLResponse)
async def htmx_calcul(
    request: Request,
    hpot: float = Form(...),
    portee: float = Form(...),
    pente_pct: float = Form(...),
    longueur: float = Form(...),
    entraxe: float = Form(...),
    h_acro: float = Form(0.0),
    departement: str = Form(...),
    nom_commune: str = Form(...),
    ancien_nom_comm: str = Form(""),
    altitude: int = Form(...),
    rugosite: str = Form(...),
    couv: float = Form(...),
    divers: float = Form(...),
):
    geom = {
        "hpot":     round(hpot * 100),
        "portee":   round(portee * 100),
        "pente":    pente_pct / 100,
        "longueur": round(longueur * 100),
        "entraxe":  round(entraxe * 100),
        "h_acro":   round(h_acro * 100),
    }
    localisation = {
        "nom_commune":     nom_commune.strip(),
        "ancien_nom_comm": ancien_nom_comm.strip(),
        "departement":     departement.strip(),
        "altitude":        altitude,
        "rugosite":        rugosite,
    }
    cp = {"couv": couv, "divers": divers}

    result, status = calcport.charge_et_sections(geom, localisation, cp)
    is_error = "problème" in str(result.get("poteau", ""))

    return templates.TemplateResponse(
        request=request,
        name="calcul/result_partial.html",
        context={
            "result": result,
            "status": status,
            "is_error": is_error,
            "geom": geom,
            "pente_pct": pente_pct,
            "entraxe": entraxe,
        },
    )
