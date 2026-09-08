"""Page « Mon compte » : consultation et édition du profil utilisateur.

Routes rendues côté serveur (Jinja2 + HTMX), pas une API JSON :
- GET  /compte : formulaire pré-rempli.
- POST /compte : mise à jour HTMX, renvoie le formulaire re-rendu + bandeau.

Champs :
- email / offre (`plan`) / entreprise  -> lecture seule
  (`entreprise` = raison sociale liée au SIREN, figée après l'inscription).
- nom / prénom / SIRET / adresse (numero, rue, complement, code_postal, ville)
  -> modifiables. Un changement de SIRET est revérifié auprès de la base Sirene
  (mêmes règles qu'à l'inscription : bloquant si introuvable/fermé, toléré avec
  avertissement si l'API est indisponible).

Protection : `current_active_user_optional` + redirection manuelle vers
/auth/login (303) — pas `current_active_user` qui renverrait un 401 JSON.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import siret as siret_service
from app.database import get_async_session
from app.models.user import User
from app.templating import templates
from app.users import current_active_user_optional

router = APIRouter(tags=["compte"])

# Libellés lisibles pour le champ `plan` (affiché en lecture seule pour l'instant,
# la sélection/paiement d'une offre viendra avec l'intégration Stripe).
PLAN_LABELS = {
    "S235": "S235 — entrée",
    "S275": "S275 — intermédiaire",
    "S355": "S355 — premium",
}

_EDITABLE_FIELDS = ("nom", "prenom", "siret", "numero", "rue", "complement", "code_postal", "ville")


def _values_from_user(u: User) -> dict:
    return {f: (getattr(u, f) or "") for f in _EDITABLE_FIELDS}


def _render_form(request: Request, user: User, values: dict, **extra):
    # Toujours 200 : HTMX ne « swap » pas les réponses non-2xx par défaut, or on
    # veut ré-afficher le formulaire (avec son bandeau rouge) même en cas
    # d'erreur de validation SIRET.
    context = {"user": user, "values": values, "plan_labels": PLAN_LABELS}
    context.update(extra)
    return templates.TemplateResponse(
        request=request, name="compte/_form.html", context=context
    )


@router.get("/compte")
async def compte_page(
    request: Request,
    user: User | None = Depends(current_active_user_optional),
):
    if user is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="compte/compte.html",
        context={"user": user, "values": _values_from_user(user), "plan_labels": PLAN_LABELS},
    )


@router.post("/compte")
async def compte_update(
    request: Request,
    nom: str = Form(""),
    prenom: str = Form(""),
    siret: str = Form(""),
    numero: str = Form(""),
    rue: str = Form(""),
    complement: str = Form(""),
    code_postal: str = Form(""),
    ville: str = Form(""),
    user: User | None = Depends(current_active_user_optional),
    session: AsyncSession = Depends(get_async_session),
):
    if user is None:
        # Cookie expiré entre l'affichage de la page et l'envoi du formulaire :
        # on demande à HTMX de faire une redirection navigateur.
        response = HTMLResponse(status_code=401)
        response.headers["HX-Redirect"] = "/auth/login"
        return response

    # `user` vient de la session de la dépendance d'auth (déjà fermée) : on
    # recharge l'objet dans NOTRE session avant de le modifier / committer.
    db_user = await session.get(User, user.id)

    submitted = {
        "nom": nom.strip(),
        "prenom": prenom.strip(),
        "siret": siret.strip(),
        "numero": numero.strip(),
        "rue": rue.strip(),
        "complement": complement.strip(),
        "code_postal": "".join(c for c in code_postal if c.isdigit())[:5],
        "ville": ville.strip(),
    }

    # --- Vérification SIRET seulement s'il a changé ---
    new_siret = siret_service.normalize_siret(submitted["siret"])
    siret_warning = None
    if new_siret != (db_user.siret or ""):
        if new_siret and len(new_siret) != 14:
            return _render_form(
                request, db_user, submitted,
                error="Le numéro SIRET doit comporter 14 chiffres.",
            )
        if new_siret:
            check = await siret_service.verify_siret(new_siret)
            if check.status == siret_service.NOT_FOUND:
                return _render_form(
                    request, db_user, submitted,
                    error="Ce numéro SIRET est introuvable dans la base Sirene. "
                          "La modification n'a pas été enregistrée.",
                )
            if check.status == siret_service.CLOSED:
                return _render_form(
                    request, db_user, submitted,
                    error="L'établissement correspondant à ce SIRET est fermé ou "
                          "l'entreprise est radiée. La modification n'a pas été enregistrée.",
                )
            if check.status == siret_service.API_UNAVAILABLE:
                siret_warning = (
                    "La vérification du SIRET n'a pas pu être effectuée (service "
                    "momentanément indisponible) ; la modification a tout de même "
                    "été enregistrée."
                )

    # --- Enregistrement (entreprise NON modifiée : lecture seule) ---
    db_user.nom = submitted["nom"] or None
    db_user.prenom = submitted["prenom"] or None
    db_user.siret = new_siret or None
    db_user.numero = submitted["numero"] or None
    db_user.rue = submitted["rue"] or None
    db_user.complement = submitted["complement"] or None
    db_user.code_postal = submitted["code_postal"] or None
    db_user.ville = submitted["ville"] or None
    await session.commit()

    return _render_form(
        request, db_user, _values_from_user(db_user),
        saved=True, siret_warning=siret_warning,
    )
