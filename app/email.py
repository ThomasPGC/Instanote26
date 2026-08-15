import os

import httpx

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


async def send_email(to: str, subject: str, html_content: str) -> None:
    """Envoie un email transactionnel via l'API Brevo (ex-Sendinblue).

    BREVO_API_KEY et EMAIL_FROM doivent être définis en variable d'environnement
    (voir CLAUDE.md) — jamais en dur dans le code.
    """
    api_key = os.environ.get("BREVO_API_KEY")
    email_from = os.environ.get("EMAIL_FROM")
    if not api_key or not email_from:
        raise RuntimeError(
            "BREVO_API_KEY et EMAIL_FROM doivent être définis en variable "
            "d'environnement pour envoyer un email (voir CLAUDE.md)."
        )

    payload = {
        "sender": {"email": email_from},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_content,
    }
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            BREVO_API_URL, json=payload, headers=headers, timeout=10.0
        )
        response.raise_for_status()
