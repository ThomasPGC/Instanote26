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

### Authentification fastapi-users (session 6, branche feature/auth-fastapi-users)

- **But de cette session** : brancher l'inscription/connexion en isolation, sans
  protéger aucune route de calcul existante (calcul.py, pdf_test.py inchangés
  dans leur logique métier).
- **Nouveaux fichiers** :
  - `app/base.py` : classe `Base` (SQLAlchemy `DeclarativeBase`) partagée,
    séparée pour éviter un import circulaire entre `database.py` et
    `models/user.py`.
  - `app/database.py` : moteur SQLite async (`sqlite+aiosqlite:///./instanote26.db`,
    fichier gitignored par `*.db`), `create_db_and_tables()` appelé dans le
    `lifespan` de `app/main.py`. Migration Postgres prévue plus tard : remplacer
    `DATABASE_URL` par la variable d'env fournie par l'addon Postgres Railway
    (voir commentaire dans le fichier).
  - `app/models/user.py` : table `User` (hérite de `SQLAlchemyBaseUserTableUUID`
    → id/email/hashed_password/is_active/is_superuser/is_verified déjà inclus) +
    champ `plan` (S235/S275/S355) préparé pour une future intégration Stripe,
    **aucune logique ne l'utilise encore**.
  - `app/schemas/user.py` : schémas Pydantic `UserRead`/`UserCreate`/`UserUpdate`
    pour fastapi-users.
  - `app/users.py` : `UserManager`, backend d'authentification par **cookie**
    (plus adapté qu'un Bearer token à un site rendu côté serveur Jinja2 + HTMX),
    JWT signé avec le secret `INSTANOTE26_AUTH_SECRET` (variable d'env, valeur
    par défaut de dev en dur dans le code — **à définir sur Railway avant toute
    mise en prod**). Expose `current_active_user` et
    `current_active_user_optional`, prêts à être utilisés en `Depends(...)` sur
    n'importe quelle route le jour où on voudra protéger quelque chose.
  - `app/routers/auth.py` : routes `GET/POST /auth/login`, `GET/POST
    /auth/register`, `GET /auth/logout`. Ne réutilise pas les routeurs tout
    faits de fastapi-users (pensés pour une API JSON) : gère à la main l'appel à
    `UserManager` + au backend d'auth pour renvoyer de vraies pages Jinja2 et des
    redirects HTTP classiques (303) plutôt que des réponses JSON.
    - **Piège rencontré** : la version installée de fastapi-users (15.0.5) a une
      API différente de celle du module d'origine —
      `CookieTransport.get_login_response(token)` /
      `get_logout_response()` construisent et renvoient désormais eux-mêmes leur
      `Response` (au lieu de prendre une réponse existante en paramètre à
      modifier). Adapté en récupérant cette réponse puis en la transformant en
      redirect (`response.status_code = 303` + `response.headers["location"]`).
      À garder en tête si un futur `pip install --upgrade fastapi-users` change
      encore cette API.
  - `templates/auth/login.html` / `register.html` : déjà compatibles avec les
    blocks de `base.html` (`{% extends "base.html" %}` + `block content`), pas
    d'adaptation nécessaire.
  - `app/middleware.py` : `CurrentUserMiddleware` (Starlette
    `BaseHTTPMiddleware`) posé sur chaque requête via
    `app.add_middleware(...)` dans `main.py`. Décode le cookie
    `instanote26_auth` (nom lu depuis `cookie_transport.cookie_name`, pas
    dupliqué en dur) et peuple `request.state.user` (objet `User` actif, ou
    `None`) — sans cookie, retourne `None` immédiatement, aucune requête DB. Ça
    permet à `base.html` d'afficher l'état de connexion sans que chaque route
    (calcul, pdf...) ait à déclarer une dépendance `current_active_user`.
- **Centralisation Jinja2Templates** : il y avait 3 instances séparées de
  `Jinja2Templates(directory="templates")` (dans `main.py`, `calcul.py`,
  `pdf_test.py`). Regroupées dans `app/templating.py` (`from app.templating
  import templates`), utilisé aussi par `app/routers/auth.py`.
- **Nav conditionnelle** (`templates/base.html`) : `{% if request.state.user
  %}` → affiche "Mon compte — {email}" (texte simple, **pas un lien** : il n'y
  a pas encore de page compte) + lien "Déconnexion" (`/auth/logout`) ; sinon
  affiche les liens "Connexion"/"Inscription" comme avant.
- **Dépendances ajoutées** (`requirements.txt`) : `fastapi-users[sqlalchemy]`,
  `aiosqlite`, `argon2-cffi` (hashage des mots de passe). `python-multipart`
  était déjà présent (utilisé aussi par les formulaires HTMX existants).
- **Vérifié en local** : démarrage propre, cycle complet register → cookie posé
  → nav "Mon compte" → logout → nav repasse en Connexion/Inscription, et
  `/calcul` + `/test-pdf` toujours 200 sans changement de comportement.

**Reste à faire (auth)** :
- Aucune route n'est protégée : décider quelles pages nécessiteront
  `current_active_user` (ou `_optional` + redirect manuel vers `/auth/login`
  plutôt qu'un 401 JSON, plus adapté à un site HTML) et où.
- Créer une vraie page "Mon compte" (le lien nav n'est qu'un texte pour
  l'instant).
- Définir `INSTANOTE26_AUTH_SECRET` en variable d'environnement Railway avant
  toute mise en prod (actuellement secret de dev en dur en fallback).
- Le champ `plan` sur `User` n'est branché à aucune logique (préparation
  Stripe uniquement).

### Emails transactionnels (session 7, branche feature/auth-fastapi-users)

- **But** : vérification d'email à l'inscription + réinitialisation de mot de
  passe par un vrai email, envoyés via l'API **Brevo** (ex-Sendinblue), pas de
  SMTP direct.
- **`app/email.py`** : fonction générique `send_email(to, subject,
  html_content)`, appelle `POST https://api.brevo.com/v3/smtp/email` en async
  (`httpx`, déjà une dépendance du projet). Lève une erreur explicite si
  `BREVO_API_KEY` ou `EMAIL_FROM` ne sont pas définis — jamais de valeur en dur.
- **Vérification d'email** (`app/users.py` → `UserManager`) :
  - `on_after_register` appelle désormais `self.request_verify(user, request)`
    (fourni par `BaseUserManager` de fastapi-users) juste après la création du
    compte → déclenche automatiquement `on_after_request_verify`.
  - `on_after_request_verify` construit le lien `{APP_BASE_URL}/auth/verify?token=...`
    et envoie `templates/emails/verify.html` par email.
  - `GET /auth/verify?token=...` (`app/routers/auth.py`) appelle
    `user_manager.verify(token)` (passe `is_verified` à `True`) et affiche
    `templates/auth/verify_result.html` (succès, déjà vérifié, ou lien
    invalide/expiré — `InvalidVerifyToken`/`UserAlreadyVerified`).
  - **Non bloquant** : la vérification n'est pas exigée pour se connecter
    (`current_active_user` ne vérifie que `is_active`, pas `is_verified`) —
    à décider plus tard si on veut la rendre obligatoire pour certaines
    actions.
- **Réinitialisation de mot de passe** :
  - `on_after_forgot_password` (`app/users.py`) : le `print()` de la session 6
    est remplacé par un vrai envoi d'email (lien
    `{APP_BASE_URL}/auth/reset-password?token=...`,
    `templates/emails/reset_password.html`).
  - `GET/POST /auth/forgot-password` : formulaire email → déclenche
    `user_manager.forgot_password(user)`. Répond **toujours** par le même
    message ("si un compte existe...") que l'email soit connu ou non, pour ne
    pas permettre à quelqu'un de deviner quels emails sont inscrits
    (énumération de comptes).
  - `GET /auth/reset-password?token=...` : formulaire nouveau mot de passe
    (token dans un champ caché). `POST` appelle
    `user_manager.reset_password(token, password)`, gère
    `InvalidResetPasswordToken` / `UserInactive` / `InvalidPasswordException`
    avec un message d'erreur adapté sur le formulaire.
  - Lien "Mot de passe oublié ?" ajouté sous le formulaire de
    `templates/auth/login.html`.
- **Templates email** (`templates/emails/verify.html`,
  `templates/emails/reset_password.html`) : HTML simple avec styles inline
  (pas de lien vers `base.html` — un email n'a pas accès au CSS/Bootstrap du
  site), rendus via `templates.get_template(...).render(...)` (pas besoin de
  `request` : ce ne sont pas des pages web, juste du HTML à envoyer par email).
- **Anti-email jetable** : librairie `disposable-email-domains` (liste de
  domaines connus comme jetables/temporaires). Vérifié dans
  `POST /auth/register` (`app/routers/auth.py`) : le domaine de l'email est
  comparé à `disposable_email_domains.blocklist` *avant* la création du
  compte ; si jetable, retourne l'erreur "Merci d'utiliser une adresse email
  permanente" sur le formulaire d'inscription.
- **Nouvelles variables d'environnement requises** (aucune valeur par défaut en
  dur dans le code, contrairement à `INSTANOTE26_AUTH_SECRET`) :
  - `BREVO_API_KEY` : clé API du compte Brevo (Brevo → Settings → SMTP & API →
    API Keys).
  - `EMAIL_FROM` : adresse expéditeur — doit être un expéditeur **validé**
    dans le compte Brevo (Senders, Domains & Dedicated IPs), sinon l'API
    Brevo refuse l'envoi.
  - `APP_BASE_URL` : URL de base utilisée pour construire les liens dans les
    emails (ex. `http://localhost:8000` en local, `https://<domaine>.up.railway.app`
    en prod). Si absente, `app/users.py` lève une erreur explicite plutôt que
    de deviner une URL.
  - À définir **en local** (fichier `.env` à la racine, jamais committé —
    `.env` était déjà dans `.gitignore` ; modèle fourni dans `.env.example`) et
    **sur Railway** (Settings → Variables) avant tout test/déploiement.
  - `python-dotenv` ajouté à `requirements.txt` : `load_dotenv()` appelé tout
    en haut de `app/main.py`, **avant** les imports de `app.database`/
    `app.routers` (qui importent `app.users`/`app.email`, lisant ces variables
    au chargement du module) — sur Railway, `.env` n'existe pas et
    `load_dotenv()` ne fait rien, les variables viennent directement de
    l'environnement.
- **Vérifié en local sans configuration Brevo** : l'inscription échoue
  proprement (erreur explicite côté serveur signalant `APP_BASE_URL` manquant)
  plutôt que d'échouer silencieusement ou d'envoyer un email cassé — confirme
  que le point d'intégration est correctement branché avant le test avec de
  vraies clés API.

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
- le calcul du poids au mètre carré est faux, trop bas. le calcul est masse d'acier divisé par l'entraxe et la portée. c'est la longueur totale du batiment qui est prise à la place de l'entraxe vraisemblablement (bug repris tel quel dans templates/calcul/pdf_result.html, pas corrigé lors de l'ajout du PDF)
- vérifier `GET /test-pdf` juste après le prochain déploiement Railway pour confirmer
  que les paquets apt de `railpack.json` suffisent bien à WeasyPrint en prod

## Refactoring futur (branche séparée)
- Migration calcul vers PyNite pour géométrie variable (gestin fine des jarrets, portiques asymétriques,
  multi-travées) — créer branche refactor/pytnite, valider résultats numériques
  identiques avant merge sur master
- voir si des tests sont déjà en place, en créer si nécessaire pour être sûrs des résultats de calcul
