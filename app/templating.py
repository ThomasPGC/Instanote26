from fastapi.templating import Jinja2Templates

# Espace insécable (U+00A0) : séparateur de milliers et liant nombre/unité,
# conformément à TYPOGRAPHIE.md.
NBSP = " "  # espace insécable


def fr_nombre(value, decimals=None, group=True):
    """Formate un nombre pour l'affichage selon la typographie française :
    virgule décimale, espace insécable comme séparateur de milliers.

    - ``decimals=None`` : garde les décimales significatives de la valeur
      (un entier reste sans décimale) ;
    - ``decimals=N`` : force exactement N décimales ;
    - ``group=False`` : pas de séparateur de milliers.

    Filtre d'affichage **uniquement** : ne jamais réinjecter le résultat dans
    un calcul (``business/``) ou un appel d'API (BAN, IGN, Sirene) ni dans une
    valeur CSS/ARIA — la virgule et l'espace insécable cassent le parsing
    numérique. Voir TYPOGRAPHIE.md.
    """
    if value is None or value == "":
        return ""
    try:
        nombre = float(value)
    except (TypeError, ValueError):
        return value

    if decimals is None:
        decimals = 0 if nombre == int(nombre) else len(
            f"{abs(nombre):.6f}".rstrip("0").split(".")[1]
        )

    texte = f"{nombre:,.{decimals}f}"  # ex. "1,234,567.80" (format C, point décimal)
    partie_entiere, _, partie_decimale = texte.partition(".")
    partie_entiere = partie_entiere.replace(",", NBSP if group else "")
    return f"{partie_entiere},{partie_decimale}" if partie_decimale else partie_entiere


def fr_mesure(value, unite, decimals=None, group=True):
    """``fr_nombre`` suivi d'un espace insécable et de l'unité :
    ``3,50 m``, ``10,0 daN/m²``. Renvoie une chaîne vide si la valeur est vide.
    """
    nombre = fr_nombre(value, decimals=decimals, group=group)
    if nombre == "":
        return ""
    return f"{nombre}{NBSP}{unite}"


templates = Jinja2Templates(directory="templates")
templates.env.filters["fr_nombre"] = fr_nombre
templates.env.filters["fr_mesure"] = fr_mesure
