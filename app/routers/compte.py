"""Page « Mon compte » : consultation et édition du profil utilisateur.

Routes rendues côté serveur (Jinja2 + HTMX), pas une API JSON :
- GET  /compte : formulaire pré-rempli (email + offre en lecture seule,
  nom / prénom / entreprise éditables).
- POST /compte : mise à jour HTMX des 3 champs éditables, renvoie le
  formulaire re-rendu avec un bandeau de confirmation.

Protection : on utilise `current_active_user_optional` + redirection manuelle
vers /auth/login (303) plutôt que `current_active_user` qui renverrait un
401 JSON — inadapté à une navigation HTML (cf. CLAUDE.md).
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

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
        context={"user": user, "plan_labels": PLAN_LABELS},
    )


@router.post("/compte")
async def compte_update(
    request: Request,
    nom: str = Form(""),
    prenom: str = Form(""),
    entreprise: str = Form(""),
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
    db_user.nom = nom.strip() or None
    db_user.prenom = prenom.strip() or None
    db_user.entreprise = entreprise.strip() or None
    await session.commit()

    return templates.TemplateResponse(
        request=request,
        name="compte/_form.html",
        context={"user": db_user, "plan_labels": PLAN_LABELS, "saved": True},
    )
