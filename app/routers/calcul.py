import sys
import pathlib

# business/ n'est pas un package installé — on l'ajoute au path
_BUSINESS = pathlib.Path(__file__).parent.parent.parent / "business"
if str(_BUSINESS) not in sys.path:
    sys.path.insert(0, str(_BUSINESS))

from fastapi import APIRouter, Form, Request
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


@router.get("/calcul", response_class=HTMLResponse)
async def calcul_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="calcul/form.html",
        context={"rugosites": RUGOSITES},
    )


@router.post("/htmx/calcul", response_class=HTMLResponse)
async def htmx_calcul(
    request: Request,
    # Géométrie — saisie en mètres, convertie en cm pour le moteur
    hpot: float = Form(...),
    portee: float = Form(...),
    pente_pct: float = Form(...),
    longueur: float = Form(...),
    entraxe: float = Form(...),
    h_acro: float = Form(0.0),
    # Localisation
    departement: str = Form(...),
    nom_commune: str = Form(...),
    ancien_nom_comm: str = Form(""),
    altitude: int = Form(...),
    rugosite: str = Form(...),
    # Charges permanentes (daN/m²)
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
        },
    )
