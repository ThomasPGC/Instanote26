# Typographie — Instanote26

## Règles de typographie française — affichage web et PDF

- Séparateur décimal : virgule (ex. 3,50 m), jamais le point
- Espace insécable avant : ! ? : ; (ex. "Attention !", "Section : IPE 160")
- Espace insécable avant et après les guillemets français « »
- Majuscules : toujours garder les diacritiques là où elles sont nécessaires
  (ex. "À", "É", "Ç")
- Espace insécable pour les unités : "3,50 m" et "10,0 daN/m²",
  jamais collé au nombre

## Mise en œuvre (templates)

- Ces règles concernent **uniquement l'affichage** (templates Jinja2 HTML +
  template PDF WeasyPrint). Les valeurs numériques utilisées en interne pour
  les calculs (`business/`) et dans les échanges avec les APIs (BAN, IGN,
  Sirene) ne doivent **pas** être touchées : elles gardent le point décimal
  et aucun espace, sinon le parsing casse.
- Formatage des nombres : filtres Jinja2 réutilisables définis dans
  `app/templating.py`, à préférer à tout formatage manuel (`"%.2f"|format`,
  `round`, concaténation d'unité) :
  - `{{ valeur | fr_nombre }}` → virgule décimale, espace insécable comme
    séparateur de milliers ; `fr_nombre(2)` force 2 décimales, `fr_nombre(0)`
    aucune.
  - `{{ valeur | fr_mesure("m") }}` → `fr_nombre` + espace insécable + unité
    (ex. `3,50 m`, `10,0 daN/m²`). Deuxième argument = nombre de décimales
    (`fr_mesure("m", 2)`).
- Ne jamais passer le résultat de ces filtres à un champ soumis au serveur
  (`<input type="hidden">`, `data-*` lus par du JS qui rappelle une API) ni
  à une propriété CSS (`style="width: … %"`) / ARIA (`aria-valuenow`) : ces
  valeurs-là restent en format machine (point décimal).
