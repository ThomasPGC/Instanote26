# Instanote26 — SaaS calcul charpente métallique

## Communication
- Toujours répondre en français.
- Le user maîtrise bien le métier (calcul de charpente métallique, Eurocodes,
  IPE...) et le code Python dédié (business/). Il est plutôt débutant sur tout
  le reste (dev web, FastAPI/Jinja2/HTMX, git, infra, déploiement...) → être
  pédagogue sur ces sujets-là : expliquer les concepts et le vocabulaire
  technique au fil de l'eau, pas juste balancer du jargon ou des commandes sans
  contexte.

## Stack
- FastAPI + Jinja2 + HTMX + Bootstrap 5
- SQLite (dev) → PostgreSQL (prod)
- Déploiement : Railway.app

## Déploiement (Railway)
- Service Railway connecté à la branche `master` du repo GitHub, déploiement
  automatique à chaque push sur cette branche.
- Builder : Railpack (successeur de Nixpacks, standard actuel Railway —
  config dans `railpack.json` à la racine, voir section Export PDF plus bas
  pour le détail des paquets apt).
- Variables d'environnement configurées sur Railway (Settings > Variables) :
  **aucune variable custom à ce jour**. Railway a seulement détecté
  `AUDIT_MODE` comme variable suggérée (présente dans le code), mais elle
  n'a jamais été ajoutée — l'instrumentation d'audit reste donc désactivée
  en prod par défaut, comme en local.
- Base de données : **actuellement SQLite en fichier local sur le service
  Railway, pas encore persistante en prod** (aucun Volume Railway attaché).
  Concrètement : si le service redémarre (déploiement, crash, veille du plan
  gratuit...), le fichier SQLite local est potentiellement réinitialisé et
  toutes les données utilisateurs (comptes créés via fastapi-users) seraient
  perdues. **Point bloquant à traiter avant de merger la branche
  `feature/auth-fastapi-users`** — soit attacher un Volume Railway au
  fichier SQLite, soit migrer vers l'addon PostgreSQL Railway (prévu de
  toute façon à terme, cf. `app/database.py`).
- Variables d'environnement supplémentaires nécessaires **quand la branche
  auth sera mergée** (pas encore définies sur Railway à ce jour, voir
  `.env.example`) : `BREVO_API_KEY`, `EMAIL_FROM`, `APP_BASE_URL`,
  `INSTANOTE26_AUTH_SECRET`.
- Nom de domaine : pas encore branché sur Railway. Prévu plus tard
  (insta-note.com), avec une bascule DNS à faire depuis l'ancien site Dokos.
- Région : pas encore vérifiée ni choisie explicitement — à faire une fois
  passé sur le plan Hobby.

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

### Export PDF (session 5)

- **Endpoint de test isolé** (`app/routers/pdf_test.py` + `templates/pdf_test.html`,
  `GET /test-pdf`) : valide la chaîne HTML → PDF avec WeasyPrint, PDF généré en
  mémoire (`HTML(string=...).write_pdf()`, pas d'écriture disque). Volontairement
  déconnecté du calcul réel (n'importe rien de `business/`) — sert de sonde rapide
  pour tester WeasyPrint en prod après déploiement, indépendamment du reste.
- **Export PDF de la note de calcul** (`app/routers/calcul.py` → `POST
  /htmx/calcul-pdf`, `templates/calcul/pdf_result.html`) : hypothèses (dimensions,
  adresse, terrain, charges), schéma du portique, sections retenues, tableau
  flèche/déplacements, taux de travail, masse estimée.
  - Bouton "Télécharger le PDF" à côté de "Calculer" (`templates/calcul/form.html`),
    grisé par défaut, activé/regrisé via les mêmes hooks JS que le schéma
    (`updatePortiqueAfterCalc` / `resetPortiqueSections` dans `portique.js`) —
    donc grisé dès qu'un champ change après un calcul, pas seulement en cas d'erreur.
  - Formulaire dédié `#pdf-form`, séparé du formulaire principal (qui a `hx-post` —
    un bouton avec `formaction` dans ce même form aurait été ignoré par htmx, qui
    intercepte l'event submit du form entier). Le bouton PDF s'y rattache via
    l'attribut HTML5 `form="pdf-form"` tout en restant visuellement à côté de
    Calculer. Soumission navigateur classique (pas ajax) pour laisser le
    téléchargement du PDF se faire nativement.
  - `preparePdfForm()` (portique.js) recopie les valeurs du formulaire principal +
    le schéma SVG affiché (`outerHTML`) dans les champs cachés de `#pdf-form`
    juste avant l'envoi.
  - Le résultat n'est pas conservé côté serveur entre le calcul htmx et l'export :
    `/htmx/calcul-pdf` relance `calcport.charge_et_sections()` avec les valeurs
    soumises.
  - `_prepare_svg_for_pdf()` (calcul.py) : WeasyPrint ignore le `width="100%"` /
    `style="...aspect-ratio...height:auto..."` du SVG live (rendu minuscule et
    mal positionné) → remplacés par des attributs `width`/`height` en pixels
    calculés depuis le `viewBox`, seule approche fiable constatée.
- **Dépendance système WeasyPrint** (pas gérée par pip) : nécessite Pango/GObject
  au runtime, pas seulement à l'install.
  - Windows (dev) : runtime GTK installé manuellement hors venv (paquet GTK
    packagé par l'équipe WeasyPrint) — sans lui, `ImportError`/`OSError` au
    premier `from weasyprint import HTML`.
  - Railway (prod) : builder confirmé = **Railpack** (successeur de Nixpacks,
    standard actuel Railway). `railpack.json` (racine du repo) déclare
    `deploy.aptPackages` : `libpango-1.0-0`, `libpangoft2-1.0-0`,
    `libharfbuzz-subset0` (liste officielle WeasyPrint pour Debian ≥ 11 avec
    wheels — `libgdk-pixbuf2.0-0` n'est plus nécessaire depuis que WeasyPrint
    utilise Pillow pour les images). Paquets déclarés en `deploy` (runtime) et non
    `build` : WeasyPrint n'est sollicité qu'à l'exécution des requêtes PDF, pas à
    l'install pip. Si le service Railway est un jour repassé sur l'ancien builder
    Nixpacks, l'équivalent est `[phases.setup] aptPkgs = [...]` dans un
    `nixpacks.toml` (non créé pour l'instant, pas de doublon de config tant que
    Railpack est actif).
  - Procfile inchangé et toujours respecté par Railpack (détection automatique
    des Procfile confirmée dans la doc Railway) — aucun conflit entre les deux
    fichiers.
  - À tester après chaque déploiement Railway : `GET /test-pdf` (sonde isolée,
    ne dépend pas du calcul métier).

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

### Instrumentation de diagnostic AUDIT_MODE (business/calcport.py + app/routers/calcul.py)
- Contexte : audit du moteur de calcul (comparaison Cype/Portal+) et de la boucle
  d'optimisation de sections IPE, suite à un résultat massivement surdimensionné
  (IPE 400/400) observé sur une ancienne infrastructure externe (celle dont on
  cherche à sortir). **Non reproduit en local sur cette base de code** : moteur
  physique et boucle d'optimisation vérifiés corrects (convergent vers IPE
  300/270 sur le cas testé, cohérent avec l'attendu métier) — le problème
  observé était propre à l'ancienne infra, pas à ce code.
- Activation : variable d'environnement `AUDIT_MODE=1` (absente/à "0" par
  défaut → aucun effet sur le comportement normal, entièrement désactivé).
- `business/calcport.py` :
  - `audit_section_forcee(geom, localisation, cp, poteau, arba, label)` :
    calcule tous les cas caractéristiques (G, N, W) et toutes les combinaisons
    ELS/ELU pour une section poteau/traverse **imposée** (court-circuite la
    boucle de `optimise_IPE()`) — tableaux détaillés : charges par barre/noeud
    avant pondération, efforts N/V/M par barre et par cas, déplacements par
    noeud, taux de travail par combinaison pondérée avec la valeur retenue.
  - `optimise_IPE()` : instrumentation additive uniquement (aucune ligne de
    logique de calcul/optimisation modifiée) qui affiche, à chaque itération de
    la boucle : la section testée, la branche empruntée ("incrément traverse
    seule" vs "bump poteau + reset traverse à poteau-4"), le résultat détaillé
    de chaque critère (tête G/D, flèche, taux) et si la section est retenue ou
    rejetée.
  - `calcport()` : paramètre optionnel `debug_capture` (dict, `None` par
    défaut) pour récupérer le vecteur déplacements complet de tous les noeuds ;
    sans effet si non fourni, donc aucun changement pour les appels existants.
- `app/routers/calcul.py` (`POST /htmx/calcul`) : log, gated par
  `calcport.AUDIT_MODE`, du payload brut reçu du formulaire, du
  `geom`/`localisation`/`cp` effectivement construits et envoyés à
  `charge_et_sections()`, et du résultat retourné — permet de comparer les
  entrées/sorties d'une vraie requête web à un cas de référence.
- Usage : positionner `AUDIT_MODE=1` dans l'environnement avant de lancer le
  serveur (ou un script Python qui importe `calcport` directement), reproduire
  le cas à auditer, lire les tableaux dans la sortie/les logs.
- Volontairement laissée dans le code (désactivée par défaut) pour resservir
  en cas de nouveau doute sur le calcul ou sur la boucle d'optimisation.

## Points en cours / prochaine session
- mettre le focus sur l'image et les resultats de calcul
- vérifier `GET /test-pdf` juste après le prochain déploiement Railway pour confirmer
  que les paquets apt de `railpack.json` suffisent bien à WeasyPrint en prod

## Corrigés récemment
- **Masse au m² faux** (`templates/calcul/result_partial.html` +
  `templates/calcul/pdf_result.html`) : la surface utilisée pour ramener la
  masse du portique en kg/m² était `portée × longueur du bâtiment` (surface
  totale du bâtiment) au lieu de `portée × entraxe` (surface réellement
  portée par UN portique) — corrigé dans les deux templates
  (`geom.longueur` → `geom.entraxe`).
- **Libellés résultats** (mêmes templates) : "Résultats — Sections retenues"
  → "Résultats — sections retenues" (pas de majuscule après le tiret) ;
  "État limite de service (déplacements)" → "Déplacements" et "État limite
  ultime (contraintes)" → "Contraintes" (l'outil fait du prédimensionnement,
  pas une vérification complète aux états limites — titres trompeurs) ;
  "Flèche faîtière" → "Flèche faîtage" ; "Dérive tête poteau..." →
  "Déplacement tête poteau..." (3 occurrences par template).

## Refactoring futur (branche séparée)
- Migration calcul vers PyNite pour géométrie variable (gestin fine des jarrets, portiques asymétriques,
  multi-travées) — créer branche refactor/pytnite, valider résultats numériques
  identiques avant merge sur master
- voir si des tests sont déjà en place, en créer si nécessaire pour être sûrs des résultats de calcul
