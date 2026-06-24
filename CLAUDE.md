# Instanote26 — SaaS calcul charpente métallique

## Stack
- FastAPI + Jinja2 + HTMX + Bootstrap 5
- SQLite (dev) → PostgreSQL (prod)
- Déploiement : Railway.app

## Structure
- app/main.py : point d'entrée FastAPI
- app/routers/ : les endpoints
- business/ : code métier Python
- templates/ : HTML Jinja2
- static/ : CSS/JS

## Code métier (business/)
Contient le moteur de calcul Python — indépendant du framework web.
Ne pas modifier pendant la phase de migration Flask → FastAPI.
Évolutions futures prévues : enrichissement des calculs Eurocodes,
nouvelles sections, visualisation SVG améliorée.

Fonction principale : charge_et_sections(geom, locali, chpro)

## Fonction principale
business/calcport.py → charge_et_sections(geom, locali, chpro)
- geom : dict {hpot, portee, pente, longueur, entraxe, h_acro}
- locali : dict {nom_commune, ancien_nom_comm, departement, altitude, rugosite}
- chpro : dict {couv, divers}
- retourne : dict avec les résultats de calcul

## Conventions
- Templates FastAPI : TemplateResponse(request=request, name="fichier.html")
- Tous les endpoints HTMX dans app/routers/calcul.py