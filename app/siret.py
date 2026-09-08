"""Vérification d'un SIRET auprès de l'API publique recherche-entreprises.

API : https://recherche-entreprises.api.gouv.fr/search  (pas de clé, gratuite)
On interroge par SIRET complet (14 chiffres) via le paramètre `q` : la réponse
contient alors `results[0].matching_etablissements` avec l'établissement exact,
son état administratif et son adresse.

Politique (cf. CLAUDE.md session 9) :
- SIRET inexistant / établissement fermé / entreprise cessée  -> on bloque.
- API injoignable (timeout, 5xx, réseau)                       -> on NE bloque PAS
  (dégradation gracieuse), mais on loggue l'incident.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger("instanote26.siret")

API_URL = "https://recherche-entreprises.api.gouv.fr/search"
_TIMEOUT = 8.0

# Valeurs de `status` renvoyées par verify_siret()
OK = "ok"
NOT_FOUND = "not_found"
CLOSED = "closed"
API_UNAVAILABLE = "api_unavailable"


@dataclass
class SiretCheck:
    status: str
    raison_sociale: Optional[str] = None
    # {"numero", "rue", "complement", "code_postal", "ville"} quand status == OK
    adresse: Optional[dict] = None

    @property
    def blocking(self) -> bool:
        """True si l'inscription / la sauvegarde doit être refusée."""
        return self.status in (NOT_FOUND, CLOSED)


def normalize_siret(raw: str) -> str:
    """Ne garde que les chiffres (l'utilisateur peut saisir des espaces)."""
    return re.sub(r"\D", "", raw or "")


async def verify_siret(raw_siret: str) -> SiretCheck:
    siret = normalize_siret(raw_siret)
    if len(siret) != 14:
        return SiretCheck(status=NOT_FOUND)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(API_URL, params={"q": siret, "page": 1, "per_page": 1})
        if resp.status_code >= 500:
            logger.warning("API SIRET indisponible (HTTP %s) pour %s", resp.status_code, siret)
            return SiretCheck(status=API_UNAVAILABLE)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.warning("API SIRET injoignable pour %s : %r", siret, exc)
        return SiretCheck(status=API_UNAVAILABLE)
    except Exception as exc:  # réponse illisible, JSON inattendu...
        logger.warning("API SIRET : réponse inattendue pour %s : %r", siret, exc)
        return SiretCheck(status=API_UNAVAILABLE)

    results = data.get("results") or []
    if not results:
        return SiretCheck(status=NOT_FOUND)

    entreprise = results[0]
    siege = entreprise.get("siege") or {}
    etablissements = entreprise.get("matching_etablissements") or []
    etab = next((e for e in etablissements if e.get("siret") == siret), None)
    if etab is None and siege.get("siret") == siret:
        etab = siege
    if etab is None:
        return SiretCheck(status=NOT_FOUND)

    raison = entreprise.get("nom_raison_sociale") or entreprise.get("nom_complet")

    entreprise_cessee = entreprise.get("etat_administratif") == "C"
    etab_ferme = etab.get("etat_administratif") in ("F", "C")
    if entreprise_cessee or etab_ferme:
        return SiretCheck(status=CLOSED, raison_sociale=raison)

    return SiretCheck(
        status=OK,
        raison_sociale=raison,
        adresse=_extract_adresse(siret, siege, etab),
    )


def _extract_adresse(siret: str, siege: dict, etab: dict) -> dict:
    """Reconstitue {numero, rue, complement, code_postal, ville}.

    Le bloc `siege` expose les champs déjà découpés (numero_voie / type_voie /
    libelle_voie) ; les `matching_etablissements` ne donnent qu'une chaîne
    `adresse` complète -> on la parse au mieux.
    """
    code_postal = (etab.get("code_postal") or "").strip()
    ville = (etab.get("libelle_commune") or "").strip()

    if siege.get("siret") == siret and siege.get("libelle_voie"):
        numero = (siege.get("numero_voie") or "").strip()
        indice = (siege.get("indice_repetition") or "").strip()
        if indice:
            numero = f"{numero} {indice}".strip()
        rue = " ".join(
            p for p in (siege.get("type_voie"), siege.get("libelle_voie")) if p
        ).strip()
        complement = (siege.get("complement_adresse") or "").strip()
        code_postal = (siege.get("code_postal") or code_postal).strip()
        ville = (siege.get("libelle_commune") or ville).strip()
    else:
        numero, rue, complement = _parse_adresse(etab.get("adresse") or "", code_postal, ville)

    return {
        "numero": numero,
        "rue": rue,
        "complement": complement,
        "code_postal": code_postal,
        "ville": ville,
    }


def _parse_adresse(full: str, code_postal: str, ville: str) -> tuple[str, str, str]:
    s = " ".join((full or "").split())
    for tail in (f"{code_postal} {ville}".strip(), code_postal, ville):
        if tail and s.upper().endswith(tail.upper()):
            s = s[: len(s) - len(tail)].strip()
            break
    m = re.match(r"^(\d+(?:\s*(?:bis|ter|quater|[A-Z]))?)\s+(.*)$", s, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip(), ""
    return "", s, ""
