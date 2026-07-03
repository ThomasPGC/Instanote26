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
- static/js/portique.js : dessin SVG temps réel + géolocalisation

## Code métier (business/)
Contient le moteur de calcul Python — indépendant du framework web.
Ne pas modifier sauf évolution métier explicite.
Évolutions futures prévues : migration vers PyNite (branche dédiée),
enrichissement des calculs Eurocodes, nouvelles sections.

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

## Features développées (sessions 1 à 3)

### Schéma SVG temps réel (static/js/portique.js)
- Vue de face 2D mise à jour à chaque saisie (hpot, portee, pente, entraxe, h_acro)
- Perspective légère (tirets) pour visualiser l'entraxe
- Cotes annotées sur le schéma
- Après calcul : sections IPE dessinées à l'échelle sur poteaux et arbalétriers
- Jarret d'about en pied de poteau
- Le schéma est actuellement sauvegardé en PNG local? à vérifier (AppData/Local/Temp)
  → À migrer en mémoire (bytes) avant mise en prod pour éviter collisions multi-utilisateurs

### Géolocalisation adresse (app/routers/calcul.py + portique.js)
- Autocomplétion adresse complète via API Base Adresse Nationale (api-adresse.data.gouv.fr)
  sans clé API, debounce 300ms
- Sélection → récupération commune, département, coords GPS précises
- Appel IGN altimétrie sur les coords exactes (pas le centroïde commune)
- Gestion communes fusionnées : remontée à la commune de référence Eurocode
  via api geo.api.gouv.fr/communes
- La rugosité (catégorie de terrain) reste un choix manuel utilisateur
- httpx installé dans le venv pour les appels async

### Gestion erreur IPE insuffisants (session 3)
- business/calcport.py : exception métier explicite `PasDeSolutionIPE`, levée par
  `optimise_IPE()` quand aucun profil du catalogue ne satisfait les critères
  (flèche/déplacement/résistance), capturée dans `charge_et_sections()`
- app/routers/calcul.py : `is_error` basé sur `status != "OK"` (fiable) au lieu
  d'un test de sous-chaîne `"problème" in ...` (fragile, ne matchait pas tous les cas)
- templates/calcul/result_partial.html : bloc erreur → message rouge explicite
  ("Aucun profil IPE disponible... — nous contacter pour une étude spécifique")
  + appel JS `resetPortiqueSections()` pour effacer les sections obsolètes
- static/js/portique.js : `resetPortiqueSections()` + délégation d'événements
  sur tout le formulaire (géométrie, adresse, rugosité, charges, sélection/reset
  de commune) → le schéma repasse en filaire dès qu'un champ change, plus
  seulement au clic sur Calculer

### Compactage formulaire (session 4, templates/calcul/form.html)
- Les 3 cartes (Géométrie, Charges permanentes, Localisation) passent de côte-à-côte
  (col-lg-4) à empilées en pleine largeur (col-12), dans cet ordre — Localisation
  en dernier, en bas
- Chaque champ numérique : étiquette + input sur la même ligne (classe utilitaire
  `.field-inline`, flexbox, définie en `<style>` inline dans form.html) plutôt
  qu'étiquette au-dessus — évite une ligne perdue par champ. `.field-inline` a
  `flex-wrap: wrap` en filet de sécurité : si la colonne devient trop étroite,
  le champ repasse sous l'étiquette au lieu de déborder de l'écran
- Géométrie : 3 champs par ligne (`col-12 col-lg-4`) ; Charges permanentes :
  2 champs par ligne (`col-12 col-lg-6`) ; empilés en colonne unique sous lg
  (992px) — breakpoint volontairement plus haut que `md` pour que les mobiles
  en paysage et les petites tablettes restent aussi en une seule colonne
- Spinners resserrés à largeur fixe 100px (`.form-control-narrow` dans
  `.field-inline`) — les valeurs sont toutes du type xxx,xx, pas besoin de plus
- Localisation : adresse seule sur sa ligne, pleine largeur (autocomplétion) ;
  catégorie de terrain en dessous, étiquette + select sur la même ligne
  (`.field-inline`, le select en `flex: 1 1 200px` pour rester lisible sans être
  tronqué, ex. "Catégorie IIIb — Zones périurbaines, forêts")
- static/js/portique.js s'appuie uniquement sur les id (#hpot, #localisation-card,
  etc.), aucune dépendance aux classes de grille → resterait à vérifier si un futur
  changement de layout modifie/supprime ces id

## Points en cours / prochaine session
- mettre le focus sur l'image et les resultats de calcul
- le calcul du poids au mètre carré est faux, trop bas. le calcul est masse d'acier divisé par l'entraxe et la portée. c'est la longueur totale du batiment qui est prise à la place de l'entraxe vraisemblablement
- Préparer la sortie image pour futur PDF (WeasyPrint) : évaluer SVG inline
  vs PNG en mémoire (voir aussi ci dessus dans le chapitre svg)

## Refactoring futur (branche séparée)
- Migration calcul vers PyNite pour géométrie variable (gestin fine des jarrets, portiques asymétriques,
  multi-travées) — créer branche refactor/pytnite, valider résultats numériques
  identiques avant merge sur master
- voir si des tests sont déjà en place, en créer si nécessaire pour être sûrs des résultats de calcul
