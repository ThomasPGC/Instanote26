import sys
import pathlib

_BUSINESS = pathlib.Path(__file__).parent.parent.parent / "business"
if str(_BUSINESS) not in sys.path:
    sys.path.insert(0, str(_BUSINESS))

import asyncio
import re
from datetime import date

import httpx
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from weasyprint import HTML

import calcport
import lecture_ipe_csv

router = APIRouter()
templates = Jinja2Templates(directory="templates")

_IPE_TABLE = lecture_ipe_csv.Tuple_tous_ipe()
IPE_SECTIONS = {
    row["Nom"]: {"h": row["h"], "tf": row["tf"], "Iy": row["Iy"]}
    for row in _IPE_TABLE.donnees
}

RUGOSITES = [
    ("0",    "Catégorie 0 — Mer, lac, zones côtières exposées"),
    ("II",   "Catégorie II — Rase campagne, prairies, lacs"),
    ("IIIa", "Catégorie IIIa — Campagne avec haies, bocage"),
    ("IIIb", "Catégorie IIIb — Zones périurbaines, forêts"),
    ("IV",   "Catégorie IV — Zones urbaines denses, forêts étendues"),
]

BAN_URL = "https://api-adresse.data.gouv.fr/search/"
BAN_REVERSE_URL = "https://api-adresse.data.gouv.fr/reverse/"
IGN_URL = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"


@router.get("/api/ipe-sections", response_class=JSONResponse)
async def ipe_sections():
    """Caractéristiques des profilés IPE (h, tf, Iy) pour le schéma SVG du portique —
    seule source : business/IPE.csv, via lecture_ipe_csv."""
    return IPE_SECTIONS


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
):
    dept = context.split(",")[0].strip() if context else ""
    altitude = 0
    old_city = ""
    async with httpx.AsyncClient(timeout=5.0) as client:
        alti_resp, reverse_resp = await asyncio.gather(
            client.get(IGN_URL, params={"lon": lon, "lat": lat, "resource": "ign_rge_alti_wld"}),
            client.get(BAN_REVERSE_URL, params={"lon": lon, "lat": lat}),
            return_exceptions=True,
        )
        try:
            z = alti_resp.json().get("elevations", [{}])[0].get("z", 0)
            altitude = max(0, int(round(z)))
        except Exception:
            altitude = 0
        try:
            for feature in reverse_resp.json().get("features", []):
                oldcity = feature.get("properties", {}).get("oldcity")
                if oldcity:
                    old_city = oldcity
                    break
        except Exception:
            old_city = ""
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
    is_error = status != "OK"

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


def _prepare_svg_for_pdf(svg_markup: str, target_width_px: int = 640) -> str:
    """WeasyPrint ignore le `width="100%"` / `style="...aspect-ratio...height:auto..."`
    utilisés pour le rendu temps réel dans le navigateur (svg minuscule, mal
    positionné) : on force donc des attributs width/height en pixels calculés à
    partir du viewBox, en remplacement du style et du width d'origine."""
    if not svg_markup:
        return svg_markup
    vb_match = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg_markup)
    vb_w, vb_h = (float(vb_match.group(1)), float(vb_match.group(2))) if vb_match else (560.0, 250.0)
    target_height_px = round(target_width_px * vb_h / vb_w)

    svg_markup = re.sub(r'\sstyle="[^"]*"', '', svg_markup, count=1)
    svg_markup = re.sub(r'\swidth="[^"]*"', '', svg_markup, count=1)
    return svg_markup.replace(
        "<svg ", f'<svg width="{target_width_px}" height="{target_height_px}" ', 1
    )


@router.post("/htmx/calcul-pdf")
async def calcul_pdf(
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
    svg_markup: str = Form(""),
):
    """Recalcule (le résultat n'est pas conservé côté serveur entre le calcul htmx et
    l'export) et génère la note de calcul en PDF, en mémoire (pas d'écriture disque).
    Le schéma est le SVG affiché à l'écran au moment du clic, transmis tel quel par le
    formulaire dédié #pdf-form (cf. static/js/portique.js, preparePdfForm())."""
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
    if status != "OK":
        return HTMLResponse(
            f"<p>Impossible de générer le PDF : {result.get('poteau', status)}</p>",
            status_code=422,
        )

    rugosite_label = dict(RUGOSITES).get(rugosite, rugosite)
    svg_markup = _prepare_svg_for_pdf(svg_markup)

    html_string = templates.get_template("calcul/pdf_result.html").render(
        request=request,
        date_du_jour=date.today().strftime("%d/%m/%Y"),
        result=result,
        geom=geom,
        hpot=hpot,
        portee=portee,
        pente_pct=pente_pct,
        longueur=longueur,
        entraxe=entraxe,
        h_acro=h_acro,
        nom_commune=nom_commune,
        ancien_nom_comm=ancien_nom_comm,
        departement=departement,
        altitude=altitude,
        rugosite_label=rugosite_label,
        couv=couv,
        divers=divers,
        svg_markup=svg_markup,
    )
    pdf_bytes = HTML(string=html_string, base_url=str(request.base_url)).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="note-calcul-instanote26.pdf"'
        },
    )
