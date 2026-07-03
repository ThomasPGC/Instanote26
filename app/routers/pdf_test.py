from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from weasyprint import HTML

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/test-pdf")
async def test_pdf(request: Request):
    lignes = [
        {"designation": "IPE 200", "quantite": 4, "poids_unitaire": 22.4},
        {"designation": "IPE 240", "quantite": 2, "poids_unitaire": 30.7},
        {"designation": "IPE 300", "quantite": 6, "poids_unitaire": 42.2},
    ]
    html_string = templates.get_template("pdf_test.html").render(
        request=request,
        titre="Instanote26 - Test PDF",
        date_du_jour=date.today().strftime("%d/%m/%Y"),
        lignes=lignes,
    )
    pdf_bytes = HTML(string=html_string, base_url=str(request.base_url)).write_pdf()
    return Response(content=pdf_bytes, media_type="application/pdf")
