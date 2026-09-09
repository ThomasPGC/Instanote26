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
  → **Ne pas pousser sur `master` des changements mineurs / doc seule**
  (ajustements de ce `CLAUDE.md`, typos...) : chaque push rebuild et redémarre
  le service Railway. Commit en local, et les faire partir avec le prochain
  changement de code utile.
- **Commande de démarrage** (Railway → Settings) :
  `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  Les migrations Alembic sont donc appliquées automatiquement à chaque
  déploiement, avant le lancement du serveur — plus besoin de `alembic upgrade
  head` manuel en shell. (Le `Procfile` du repo reste présent mais cette
  commande explicite le remplace côté Railway.)
- Builder : Railpack (successeur de Nixpacks, standard actuel Railway —
  config dans `railpack.json` à la racine, voir section Export PDF plus bas
  pour le détail des paquets apt).
- Variables d'environnement configurées sur Railway (Settings > Variables) :
  `SQLITE_DB_PATH`, `INSTANOTE26_AUTH_SECRET`, `BREVO_API_KEY`, `EMAIL_FROM`,
  `APP_BASE_URL` (posées en amont du merge de `feature/auth-fastapi-users`
  sur `master`, confirmées fonctionnelles après déploiement). `AUDIT_MODE`
  reste absente (Railway l'a seulement détectée comme variable suggérée,
  présente dans le code) — instrumentation d'audit désactivée en prod par
  défaut, comme en local.
- Base de données : **SQLite désormais persistante en prod** via un Volume
  Railway monté sur `/data`, combiné à `SQLITE_DB_PATH=/data/instanote26.db`
  (voir `app/database.py` — fallback `./instanote26.db` seulement si la
  variable est absente, ex. en local). Le service peut redémarrer
  (déploiement, crash, veille du plan gratuit...) sans perdre les données
  utilisateurs (comptes fastapi-users). Migration vers l'addon PostgreSQL
  Railway toujours envisagée à terme, mais plus aussi urgente maintenant.
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
- static/js/entreprise-form.js : aide saisie SIRET + adresse (inscription, /compte)
- app/siret.py : vérification SIRET (base Sirene), voir session 9
- app/admin.py : back office admin (SQLAdmin) monté sur /admin, voir session 10
- migrations/ + alembic.ini : migrations de schéma de base (Alembic, voir
  session 8)
- validation/ : références de validation croisée du moteur (PDF Instanote26
  vs notes CTICM par cas) + `validation/pynite_check/` : scripts de parité
  legacy ↔ PyNite, un par sous-étape (voir « Roadmap moteur de calcul »)

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
- Endpoints HTMX du calcul dans app/routers/calcul.py ; les endpoints du
  compte utilisateur dans app/routers/compte.py
- Évolution du schéma de base : passer par Alembic
  (`alembic revision --autogenerate -m "..."` puis `alembic upgrade head`),
  ne pas se reposer sur `Base.metadata.create_all` (voir session 8)
- Typographie française de l'affichage (nombres, unités, ponctuation) :
  voir `TYPOGRAPHIE.md`. Tout nombre montré à l'utilisateur (templates HTML +
  PDF WeasyPrint) passe par les filtres Jinja2 `| fr_nombre` / `| fr_mesure`
  (définis dans `app/templating.py`) — virgule décimale, espace insécable
  milliers + unité. Ne jamais appliquer ces filtres aux valeurs soumises au
  serveur, aux appels d'API (BAN/IGN/Sirene) ni aux propriétés CSS/ARIA.

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
  - `app/database.py` : moteur SQLite async, chemin du fichier lu depuis la
    variable d'env `SQLITE_DB_PATH` (fallback `./instanote26.db` si absente,
    fichier gitignored par `*.db`) — pensé pour brancher un Volume Railway en
    prod : `SQLITE_DB_PATH=/data/instanote26.db` (Volume monté sur `/data`),
    variable pas encore définie sur Railway à ce jour. `create_db_and_tables()`
    appelé dans le `lifespan` de `app/main.py`. Migration Postgres prévue plus
    tard : remplacer `DATABASE_URL` par la variable d'env fournie par l'addon
    Postgres Railway (voir commentaire dans le fichier).
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
  %}` → affiche "Mon compte — {email}" + lien "Déconnexion" (`/auth/logout`) ;
  sinon affiche les liens "Connexion"/"Inscription" comme avant.
  (session 8 : "Mon compte — {email}" est devenu un lien vers `/compte`.)
- **Dépendances ajoutées** (`requirements.txt`) : `fastapi-users[sqlalchemy]`,
  `aiosqlite`, `argon2-cffi` (hashage des mots de passe). `python-multipart`
  était déjà présent (utilisé aussi par les formulaires HTMX existants).
- **Vérifié en local** : démarrage propre, cycle complet register → cookie posé
  → nav "Mon compte" → logout → nav repasse en Connexion/Inscription, et
  `/calcul` + `/test-pdf` toujours 200 sans changement de comportement.

**Reste à faire (auth)** :
- Peu de routes protégées : seule `/compte` l'est (session 8, via
  `current_active_user_optional` + redirect manuel). Décider si d'autres pages
  (calcul, export PDF...) doivent l'être.
- ~~Créer une vraie page "Mon compte"~~ → fait en session 8 (`/compte`).
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

### Page « Mon compte » + Alembic (session 8, branche feature/page-compte)

- **But** : première page réservée aux utilisateurs connectés — édition du
  profil (nom, prénom, entreprise) — et mise en place d'Alembic pour gérer les
  évolutions du schéma de base sans repartir de zéro.

- **Alembic (migrations de schéma)** :
  - `alembic` ajouté à `requirements.txt`. Dossier `migrations/` à la racine
    (`alembic init migrations`), config dans `alembic.ini`.
  - `migrations/env.py` adapté au projet :
    - reconstruit l'URL de la base depuis la variable d'env `SQLITE_DB_PATH`
      (même logique que `app/database.py`, fallback `./instanote26.db`) — donc
      cohérent dev / prod (Volume Railway), `sqlalchemy.url` volontairement
      **vide** dans `alembic.ini`.
    - utilise un moteur **synchrone** (`sqlite://`, pilote `sqlite3` stdlib) :
      l'app tourne en async (`aiosqlite`) mais les migrations n'en ont pas
      besoin.
    - `render_as_batch=True` : SQLite ne sait pas faire tous les `ALTER TABLE`,
      Alembic recrée la table (copie + rename) quand nécessaire.
    - `target_metadata = Base.metadata` (+ `import app.models.user`) pour
      `--autogenerate`.
  - **Alembic est le seul maître du schéma** (depuis le fix
    `fix/alembic-ownership`, voir « Corrigés récemment ») : plus de
    `Base.metadata.create_all` au démarrage de l'app (`create_db_and_tables()`
    supprimé, `lifespan` retiré de `main.py`). La création de la table `user`
    comme ses évolutions passent **uniquement** par `alembic upgrade head`.
  - **Migration `69dfd86650b6` (« baseline »)** : crée la table `user` telle
    qu'elle était avant la session 8 (colonnes fastapi-users + `plan`), de
    façon **idempotente** (`if inspect(bind).has_table("user"): return`) — sans
    effet sur les bases déjà existantes (prod, dev), qui restent « adoptées »
    via `alembic stamp`.
  - **Migration `7239b9e48d12`** : `ADD COLUMN nom / prenom / entreprise` sur
    `user`, **idempotente elle aussi** (n'ajoute que les colonnes réellement
    absentes) — protège les bases dont le schéma aurait pris de l'avance sur le
    pointeur de version Alembic.
  - **Prochaine migration** :
    1. modifier le(s) modèle(s) SQLAlchemy (`app/models/`) ;
    2. `alembic revision --autogenerate -m "description courte"` ;
    3. **relire** le fichier généré dans `migrations/versions/` (l'autogenerate
       n'est pas parfait, surtout sur SQLite) ;
    4. `alembic upgrade head` pour appliquer.
    `alembic downgrade -1` pour annuler la dernière, `alembic current` /
    `alembic history` pour l'état.
  - **En prod (Railway)** : commande de démarrage
    `alembic upgrade head && uvicorn ...` (voir section « Déploiement ») → les
    migrations s'appliquent automatiquement à chaque déploiement. Base du
    Volume à `7239b9e48d12` (head), `/compte` + export PDF OK.
    (Historique de l'incident de mise en route : voir « Corrigés récemment ».)

- **Modèle `User`** (`app/models/user.py`) : 3 champs `Optional[str]` nullable
  ajoutés — `nom` (100), `prenom` (100), `entreprise` (200). Éditables depuis
  `/compte`. Le champ `plan` reste inchangé (toujours non branché, préparation
  Stripe) et est affiché en lecture seule sur la page.

- **Route `/compte`** (`app/routers/compte.py`, nouveau routeur, monté dans
  `main.py`) :
  - `GET /compte` : protégée via `current_active_user_optional` + `RedirectResponse`
    303 vers `/auth/login` si non connecté (pas `current_active_user` qui
    renverrait un 401 JSON, inadapté à une page HTML — cf. « Reste à faire (auth) »).
    Rend `templates/compte/compte.html` (formulaire pré-rempli).
  - `POST /compte` : endpoint HTMX. Recharge l'utilisateur dans sa propre
    session DB (`session.get(User, user.id)` — l'objet issu de la dépendance
    d'auth est sur une session déjà fermée), met à jour les 3 champs
    (`.strip() or None`), `commit`, puis renvoie le fragment
    `templates/compte/_form.html` re-rendu avec un bandeau « Profil enregistré ».
    Si le cookie a expiré entre-temps : réponse `401` + en-tête `HX-Redirect:
    /auth/login` (HTMX fait la redirection navigateur).
  - Templates : `compte/compte.html` (étend `base.html`) inclut
    `compte/_form.html` dans `<div id="compte-form">` ; le form a
    `hx-post="/compte" hx-target="#compte-form" hx-swap="outerHTML"` → le
    fragment renvoyé se remplace lui-même, bandeau compris. Style Bootstrap 5
    cohérent avec `auth/login.html` / `register.html`.

- **Navbar** (`templates/base.html`) : « Mon compte — {email} » n'est plus un
  `<span>` mais un `<a href="/compte">` (même style `btn btn-outline-light
  btn-sm`).

- **Vérifié en local** (script de test bout-en-bout, base SQLite temporaire) :
  - non connecté → `GET /compte` redirige (303) vers `/auth/login`, `POST` →
    401 + `HX-Redirect` ;
  - inscription → cookie posé → `GET /compte` 200 avec email pré-rempli ;
  - `POST /compte` met à jour les 3 champs, bandeau de confirmation, valeurs
    re-affichées ; champ vide/espaces → `NULL` ;
  - déconnexion puis **relogin** : les valeurs sont bien persistées en base ;
  - `alembic check` : « No new upgrade operations detected » (modèle ⇔ schéma
    cohérents).
  - Aparté : le cookie d'auth est `Secure` (`cookie_transport` dans
    `app/users.py`) → en dev il ne fonctionne que parce que les navigateurs
    traitent `localhost` comme contexte sécurisé même en `http`. Un test via
    `TestClient` doit utiliser `base_url="https://testserver"`.

### Identité professionnelle + adresse (session 9, branche feature/compte-entreprise)

- **But** : ne garder que des professionnels identifiés — l'inscription
  collecte nom, prénom, entreprise, **SIRET** et **adresse**, le SIRET est
  vérifié auprès de la base Sirene. L'adresse est aussi éditable sur `/compte`.

- **Contraintes métier qui expliquent les choix** :
  - **Pas de champ `pays`, SIRET franco-français uniquement** : l'éditeur
    facture via une coopérative d'entrepreneurs (CAE) qui ne l'autorise pas à
    vendre à l'étranger. Les clients sont donc tous des entreprises
    françaises → le SIRET (identifiant Insee, 14 chiffres) suffit, pas besoin
    de gérer des identifiants d'entreprise étrangers ni une adresse hors France.
  - **`siret` reste modifiable** (pas figé après l'inscription) : le SIRET
    d'un établissement change quand l'entreprise **déménage** (le NIC, les
    5 derniers chiffres, dépend de l'établissement) — le SIREN, lui, ne bouge
    pas. D'où la re-vérification Sirene à chaque changement de SIRET sur
    `/compte`. `entreprise` (raison sociale, liée au SIREN) est en revanche
    stable → lecture seule.

- **Modèle `User`** (`app/models/user.py`) — 6 nouvelles colonnes, **toutes
  nullable** (les comptes d'avant la session 9 n'ont pas ces données et doivent
  continuer à fonctionner) : `siret` (14), `numero` (20), `rue` (255),
  `complement` (255), `code_postal` (5), `ville` (100). `entreprise` (déjà là
  depuis la session 8) est réutilisé pour la raison sociale.
  - Migration `7f738729c0ef` (`ADD COLUMN` ×6), idempotente sur le modèle de
    `7239b9e48d12` (n'ajoute que les colonnes absentes). Testée base neuve +
    copie de l'état prod ; `alembic check` OK. Elle part toute seule au
    prochain déploiement (start command Railway `alembic upgrade head && ...`).
  - Schémas : `UserCreate` (`app/schemas/user.py`) reçoit ces champs
    (facultatifs au niveau Pydantic, obligatoires au niveau du formulaire) →
    `user_manager.create()` les recopie dans la ligne via `create_update_dict()`,
    un seul INSERT, pas de 2ᵉ session.

- **`app/siret.py`** — `verify_siret(siret) -> SiretCheck` (async, `httpx`).
  Interroge `https://recherche-entreprises.api.gouv.fr/search?q=<siret 14 chiffres>`
  (pas de clé). Statuts : `ok` / `not_found` / `closed` / `api_unavailable`.
  - `ok` : renvoie `raison_sociale` + `adresse` (numero/rue/complement/
    code_postal/ville — depuis `siege` si le SIRET est celui du siège, sinon
    parsée de la chaîne `adresse` des `matching_etablissements`).
  - `not_found` / `closed` (établissement fermé `etat_administratif` F, ou
    entreprise cessée C) → **bloquant** (`.blocking`).
  - `api_unavailable` (timeout, 5xx, réseau) → **non bloquant**, `logger.warning`
    (`logging.getLogger("instanote26.siret")`).

- **`app/routers/entreprise.py`** — endpoints JSON pour le JS des formulaires
  (jamais bloquants, la vérif qui fait foi est refaite au submit) :
  - `GET /htmx/siret-info?siret=` → `{status, raison_sociale, adresse}`.
  - `GET /htmx/communes?code_postal=` → `[{nom, code}]` (via
    `geo.api.gouv.fr/communes`).
  - `GET /htmx/rue-search?q=&citycode=` → `[{name, city, citycode}]` (API BAN,
    `type=street`, scopée commune).
  - Monté dans `main.py`.

- **`static/js/entreprise-form.js`** — partagé inscription + `/compte`. Au blur
  du champ `#siret` : appel `/htmx/siret-info`, retour visuel (`is-valid` /
  `is-invalid` + message), et pré-remplissage de `#entreprise` (si vide) et des
  champs adresse si l'API renvoie une adresse. `#code_postal` → `/htmx/communes`
  → `#commune-select` (présélection si une seule) + met à jour `#citycode`
  (hidden). `#rue` → autocomplétion BAN scopée `#citycode` dans
  `#rue-suggestions`. `init()` idempotent (garde `dataset.efInit`) et rejoué sur
  `htmx:afterSwap` (le fragment `/compte` est re-swappé).

- **Inscription** (`app/routers/auth.py`, `templates/auth/register.html`) :
  - Formulaire étoffé (email, mot de passe, prénom, nom, raison sociale, SIRET,
    puis adresse). Message d'en-tête : service réservé aux professionnels du
    bâtiment, infos nécessaires à l'identification de la clientèle pro.
  - `POST /auth/register` : validation manuelle (tous obligatoires sauf
    `complement`), formats (SIRET 14 chiffres, CP 5 chiffres), domaine jetable,
    puis `verify_siret` — `not_found`/`closed` → ré-affiche le formulaire (400,
    valeurs conservées via le dict `form`) ; `api_unavailable` → on continue.
    `entreprise` stockée = `raison_sociale` de l'API si dispo, sinon la saisie.
  - Succès → **connexion auto conservée** + redirect vers
    `GET /auth/inscription-terminee` (nouvelle page « vérifiez votre boîte mail »
    + bloc anti-spam entreprise : quarantaines MailInBlack / Altospam / Vade,
    expéditeur = `EMAIL_FROM`). Vérif email toujours **non bloquante**
    (cohérent session 7).

- **`/compte`** (`app/routers/compte.py`, `templates/compte/_form.html`) :
  - Lecture seule : email, offre (`plan`), **`entreprise`** (raison sociale
    liée au SIREN — le champ n'a pas de `name`, il n'est pas soumis).
  - Modifiables : nom, prénom, **SIRET**, adresse. Un SIRET **différent** de
    celui en base est revérifié : `not_found`/`closed` → rien n'est enregistré,
    bandeau rouge (réponse **200** — HTMX ne swappe pas les non-2xx) ;
    `api_unavailable` → enregistré + bandeau d'avertissement.
  - Le pré-remplissage adresse depuis le SIRET est fait côté JS (partagé avec
    l'inscription).

- **Comptes existants (avant session 9)** : `siret`/adresse à `NULL` →
  `/compte` s'affiche normalement, champs vides, aucune erreur ; on peut
  modifier l'adresse sans toucher au SIRET. Aucune route n'exige ces champs.

- **Vérifié** (script bout-en-bout, base neuve + mocks `verify_siret` /
  `send_email`) : inscription complète valide → compte + redirect ; SIRET
  introuvable/fermé → bloqué, aucun compte ; API SIRET indisponible → non
  bloqué ; champ obligatoire manquant → 400 ; `/htmx/siret-info` +
  `/htmx/communes` (appel réel) OK ; compte ancien sans SIRET → `/compte` OK,
  modif adresse persistée après relogin ; changement de SIRET sur `/compte`
  (valide / invalide / API indispo) ; `entreprise` bien en lecture seule.

### Back office admin — SQLAdmin (session 10, branche feature/admin-backoffice)

- **But** : interface d'administration des comptes utilisateurs (lister,
  chercher, éditer, activer/désactiver, supprimer), montée avec la librairie
  **SQLAdmin** — pas d'écrans faits main. `business/calcport.py` non touché.

- **Dépendances** (`requirements.txt`) : `sqladmin==0.31.1`,
  `itsdangerous==2.2.0` (requis par le `SessionMiddleware` que SQLAdmin ajoute
  pour son auth ; pas tiré automatiquement). `wtforms` est tiré
  automatiquement par sqladmin.

- **Montage** : `app/admin.py` → `setup_admin(app)`, appelé dans
  `app/main.py` juste après `add_middleware` / `mount("/static")`. SQLAdmin se
  monte comme une sous-application Starlette sur **`/admin`**.

- **Modèle `User` — 2 colonnes ajoutées** (`app/models/user.py`, migration
  `93d735ca7575`, idempotente comme les précédentes) :
  - `notes` (`Text`, nullable) : notes internes libres de l'admin (ex. raison
    d'une désactivation). Jamais affiché à l'utilisateur.
  - `created_at` (`DateTime`, `server_default=func.now()`, NOT NULL) : date
    d'inscription, pour la colonne « Inscription » de la liste. Les comptes
    créés avant la migration portent la date d'application de celle-ci. Part
    tout seul au prochain déploiement (start command Railway
    `alembic upgrade head && ...`).

- **Authentification du back office** (`app/admin.py` → `AdminAuth`,
  sous-classe de `sqladmin.authentication.AuthenticationBackend`) : **pas de
  login séparé**. `authenticate()` relit le cookie JWT `instanote26_auth` de
  fastapi-users (même logique que `app/middleware.py`) et exige
  `is_active` **ET** `is_superuser`.
  - non connecté → `RedirectResponse("/auth/login")`
  - connecté mais pas admin → `PlainTextResponse(403)`
  - `login()` / `logout()` de SQLAdmin sont court-circuités (renvoient vers
    `/auth/login` / `/auth/logout`) : le formulaire de login interne de
    SQLAdmin n'est jamais servi.
  - Ce contrôle est appliqué par le décorateur `login_required` de SQLAdmin
    sur **chaque** route de l'admin (liste, détail, édition, suppression,
    actions) → taper une URL `/admin/...` à la main ne contourne rien
    (vérifié : `/admin/user/list` en direct par un non-admin → 403).
  - `secret_key` du `SessionMiddleware` = `INSTANOTE26_AUTH_SECRET` (réutilisé,
    via `app.users.SECRET`).

- **Vue `UserAdmin`** (`ModelView`, `app/admin.py`) :
  - **Liste** : email, nom, prénom, entreprise, offre (`plan`), actif,
    email vérifié, admin, date d'inscription. Tri par `created_at`
    décroissant par défaut.
  - **Recherche** : `column_searchable_list = [email, entreprise]`.
  - **Édition** : tous les champs en texte libre **sauf `plan`** →
    `form_overrides = {"plan": SelectField}` + `form_args` avec
    `choices=[S235, S275, S355]` (liste déroulante fermée, pour qu'une faute
    de frappe ne casse pas un futur accès payant). `hashed_password` exclu
    de la liste, du détail (`column_details_exclude_list`) **et** du
    formulaire (`form_excluded_columns`). `can_create = False` : la création
    de compte passe par `/auth/register` (sinon mot de passe non hashé).
  - **Activer / Désactiver** : deux actions groupées SQLAdmin (`@action`),
    cases à cocher dans la liste → `is_active` True/False sur les comptes
    sélectionnés (désactivation avec message de confirmation). fastapi-users
    bloque déjà la connexion d'un compte `is_active=False`
    (`app/routers/auth.py` teste `not user.is_active`, `current_active_user`
    et le middleware aussi) — rien à ajouter côté login.
  - **Suppression** : vraie suppression SQL (`DELETE FROM user`), pas de soft
    delete — pour les demandes RGPD. `on_model_delete()` logge
    `email` + `id` + date ISO **avant** l'effacement, dans le logger
    `instanote26.admin` → trace applicative conservée même sans le compte.
  - Traçabilité create/update/delete en plus : `Admin(audit_backend=
    LoggingAuditBackend(logger_name="instanote26.admin.audit"))`.

- **Navbar** (`templates/base.html`) : bouton « Admin » (jaune) affiché
  uniquement si `request.state.user.is_superuser`.

- **Se donner les droits admin** (pas d'UI self-service) — passer un compte
  en superuser directement en base :
  - En local (SQLite) :
    ```
    python -c "import sqlite3; c=sqlite3.connect('instanote26.db'); c.execute(\"UPDATE user SET is_superuser=1 WHERE email='tomajeu@gmail.com'\"); c.commit()"
    ```
  - En prod (Railway) : shell sur le service, même `UPDATE` sur
    `/data/instanote26.db` (`sqlite3 /data/instanote26.db "UPDATE user SET
    is_superuser=1 WHERE email='...'"`), ou via l'addon Postgres le jour où
    on aura migré. Puis se reconnecter (le flag est lu depuis le cookie/DB à
    la connexion).

- **URL** : `/admin` (redirige vers `/admin/` puis la liste des utilisateurs).

- **Vérifié** (script bout-en-bout `test_admin.py`, base SQLite temporaire,
  `send_email` mocké — 30/30) : non-superuser → `/admin` et
  `/admin/user/list` en direct → 403 ; anonyme → redirection `/auth/login` ;
  superuser → `/admin` 200, liste (3 comptes, pas de `hashed_password`),
  recherche email/entreprise, détail sans hash ; formulaire d'édition avec
  `<select>` fermé pour `plan` ; `plan` S355 persiste, valeur hors liste
  refusée ; `notes` sauvegardées et rechargées ; action Désactiver → login
  ensuite refusé ; action Activer → login de nouveau OK ; suppression →
  compte absent de la base + ligne de log `SUPPRESSION DEFINITIVE ... email=`.

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
- ✅ déploiement session 8 vérifié en prod : `GET /test-pdf` OK, export PDF de
  la note de calcul OK, `/compte` OK (stamp + upgrade Alembic faits sur le
  Volume). WeasyPrint : paquets apt de `railpack.json` confirmés suffisants.

### Objectifs prochaine session (back office + suivi d'usage + mentions légales)
- ~~**Warm-up / validation du pipeline Alembic** : champs adresse sur `User`~~
  → fait en **session 9** (migration `7f738729c0ef` : siret + adresse), le
  cycle `revision --autogenerate` → relecture → `upgrade head` s'est déroulé
  proprement, `alembic check` OK.
- ~~**Back office admin** : interface pour gérer les utilisateurs~~ → fait en
  **session 10** (branche `feature/admin-backoffice`) avec **SQLAdmin** monté
  sur `/admin` (`app/admin.py`), auth adossée au cookie fastapi-users +
  `is_superuser`. Voir la section « Back office admin — SQLAdmin » plus haut.
  Choix vs. le plan initial : librairie SQLAdmin plutôt qu'un routeur Jinja2 +
  HTMX fait main (`app/routers/admin.py` non créé).
- **Suivi d'usage / analytics** : compter les calculs, la fréquence par
  utilisateur, les types de projet (portée, hauteur, couverture...).
  - Nouvelle table (ex. `calcul_log`) : `id`, `user_id` (nullable si calcul
    anonyme), `created_at`, un sous-ensemble des entrées (`portee`, `hpot`,
    `pente`, `entraxe`, `couv`, commune/département) et des sorties (sections
    retenues, statut OK / PasDeSolutionIPE). **Modèle SQLAlchemy + migration
    Alembic** (`alembic revision --autogenerate`).
  - Écriture depuis `POST /htmx/calcul` (et l'export PDF), en *plus* du calcul,
    sans bloquer la réponse si l'insert échoue (try/except).
  - Vues d'agrégation dans le back office (nb de calculs / jour, top
    utilisateurs, répartition des portées...). Attention RGPD : c'est de la
    donnée liée à des comptes → cf. mentions légales ci-dessous.
  - Réutiliser éventuellement l'instrumentation `AUDIT_MODE` déjà en place
    pour le contenu à logger, mais le logging d'usage doit être actif en prod
    (pas gated par `AUDIT_MODE`, qui reste réservé au diagnostic calcul).
- **Mentions légales + disclaimer métier** :
  - Page `/mentions-legales` (éditeur du site, hébergeur = Railway, contact,
    politique de données perso / cookies — le cookie d'auth `instanote26_auth`
    est un cookie strictement nécessaire, pas de consentement requis, mais à
    mentionner).
  - **Disclaimer** affiché de façon visible (près du bouton « Calculer » et/ou
    dans le PDF exporté, + acceptation à l'inscription) : l'outil fait du
    **pré-dimensionnement / chiffrage** uniquement, il ne remplace pas une note
    de calcul complète vérifiée aux états limites par un BE ; ne pas construire
    sur cette seule base. Cohérent avec les libellés déjà corrigés
    (« prédimensionnement », voir « Corrigés récemment »).
  - Lien vers ces pages dans le `<footer>` de `base.html` (footer à créer).
- ✅ **Migrations Alembic en prod automatisées** : commande de démarrage Railway
  = `alembic upgrade head && uvicorn ...` (voir section « Déploiement »).

## Sur l'horizon (décisions produit à trancher — pas de code pour l'instant)

### 1. Statut « email non vérifié » et accès aux calculs
- **État actuel (à re-confirmer en code au moment de la session concernée)** :
  les routes `/calcul` et l'export PDF n'ont **aucune protection d'accès** — ni
  connexion, ni vérification d'email requises.
- **Décision produit** : ce sujet ne doit **pas** être traité isolément mais
  **conjointement avec la stratégie de paliers S235/S275/S355** (point 2) : ce
  sont trois marches d'un même parcours
  `visiteur → inscrit non vérifié → inscrit vérifié → payant`.
- **Piste retenue** : garder une **démo de calcul accessible sans inscription et
  sans friction** (effet « waouh » immédiat), mais **fortement limitée
  fonctionnellement** — ex. charges permanentes (couverture, diverses) forcées à
  zéro ou quasi nulles, résultats non exportables en PDF, etc. (détails à
  définir).
- Le statut **« compte créé mais email non vérifié »** doit trouver sa place
  dans ce parcours : accès identique à la démo ? accès intermédiaire ? — à
  trancher.

### 2. Stratégie de paliers S235 / S275 / S355
- Toujours prévue, dans l'ordre convenu depuis le début du projet :
  **d'abord le marketing** (quelles fonctionnalités / limites par palier),
  **puis l'implémentation technique**.
- Le champ `plan` existe déjà sur `User` (défaut `"S235"`), prêt pour
  l'intégration Stripe future.
- **Session dédiée à prévoir**, qui doit **englober le point 1 ci-dessus**.

### 3. Email administrateur à changer un jour
- Le compte de test utilise une **adresse personnelle « de dépannage »**
  (`tomajeu@gmail.com`), pas destinée à rester en usage en production réelle.
- **Pas de fonctionnalité de changement d'email** aujourd'hui : le champ email
  est en lecture seule sur `/compte` (choix de sécurité, standard fastapi-users).
- **Au vrai lancement commercial**, deux options — à trancher selon le besoin
  réel à ce moment-là, probablement à rattacher à la session « back office
  admin » :
  - supprimer ce compte de test et en recréer un avec la vraie adresse
    professionnelle ; ou
  - développer un **changement d'email** (formulaire + confirmation par email
    envoyée sur la **nouvelle** adresse, pour éviter le vol de compte).

### 4. Pied de poteau encastré — offre premium éventuelle
- Le moteur ne calcule que des portiques à **pieds articulés** (choix figé,
  cf. « Roadmap moteur de calcul »). L'encastrement de pied n'est pas au
  programme : à l'échelle d'une étude de prix, le surcoût de fondation
  (massifs, ancrages) dépasse en général l'économie de métal permise par
  l'encastrement.
- **Piste commerciale future** : proposer le pied encastré comme **option
  d'un palier payant supérieur**, et/ou le rendre nécessaire le jour où on
  voudrait prendre en compte des **ponts roulants** (efforts horizontaux de
  chariot, qui changent la donne sur la dérive et rendent l'encastrement
  souvent incontournable).
- Rien à coder tant que ce n'est pas tranché ; noté ici pour ne pas
  redécouvrir la question à chaque passage sur le moteur.

## Corrigés récemment
- **Back office SQLAdmin sans aucun style en prod (fix `fix/admin-proxy-headers`)** :
  `/admin` s'affichait en HTML brut (le reste du site OK). Cause : Railway
  termine le TLS et transmet la requête en HTTP interne avec
  `X-Forwarded-Proto: https` ; sans prise en compte de cet en-tête, Starlette
  se croit en HTTP et `request.url_for('admin:statics', ...)` (utilisé par les
  templates SQLAdmin) génère des URL absolues `http://` → CSS/JS bloqués par le
  navigateur (contenu mixte sur page HTTPS). `base.html` du site, lui, charge
  Bootstrap depuis un CDN en `https://` écrit en dur (pas de `url_for`) → jamais
  affecté.
  - **Fix** : `app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")`
    dans `app/main.py`, ajouté **après** `CurrentUserMiddleware` donc middleware
    le plus externe (corrige le scope avant tout le reste). `trusted_hosts="*"` :
    le conteneur Railway n'est joignable que via le proxy. Vérifié en simulant
    l'en-tête : `url_for` repasse en `https://`, ressources statiques 200.
- **Crash prod « duplicate column name: nom » (fix `fix/alembic-ownership`)** :
  après avoir mis la commande de démarrage Railway
  `alembic upgrade head && uvicorn ...`, le service partait en crash-loop.
  Cause : deux systèmes se disputaient le schéma — `Base.metadata.create_all`
  (lifespan de `main.py`) créait `user` avec *toutes* les colonnes du modèle,
  et les migrations `ADD COLUMN` d'Alembic rejouaient par-dessus. Le
  `alembic stamp 69dfd86650b6` passé à la main en prod avait laissé le
  pointeur de version en retard sur le schéma réel → `upgrade head` tentait de
  re-créer des colonnes existantes.
  - **Dépannage immédiat** (déjà fait en prod) : `alembic stamp head` dans un
    shell Railway pour re-synchroniser le pointeur, puis restart.
  - **Fix de fond** : Alembic devient seul maître du schéma —
    `create_db_and_tables()` / `Base.metadata.create_all` supprimés, `lifespan`
    retiré de `main.py` ; migration baseline `69dfd86650b6` crée maintenant la
    table `user` (idempotent, `has_table` guard) ; migration `7239b9e48d12`
    rendue idempotente (n'ajoute que les colonnes absentes). Le schéma ne peut
    plus prendre de l'avance sur Alembic. Testé : base neuve, base adoptée à
    head, base adoptée bloquée à la baseline, round-trip downgrade/upgrade.
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

## Roadmap moteur de calcul (session post-infrastructure)

Contexte : l'infrastructure SaaS (auth, PDF, profil, migrations Alembic) est
en place. Prochaine phase : fiabiliser et enrichir le cœur de calcul avant
d'ouvrir Stripe. Objectif : rigueur et validation à chaque étape, ne pas
enchaîner sans avoir validé l'étape précédente.

#### Positionnement produit du moteur — choix DURABLE, ne pas « corriger »

Instanote26 fait du **prédimensionnement pour étude de prix**, pas de la
vérification réglementaire complète aux Eurocodes. Sont **volontairement et
durablement hors périmètre** du moteur (ce ne sont **pas des oublis** — ne
pas les « ajouter » dans une session future sans validation explicite du
user) :
- **flambement** (poteaux, arbalétriers) et **déversement** (semelle
  comprimée) : les bracons anti-dévers / anti-flambement réels sont non
  significatifs à l'échelle d'un chiffrage ;
- classification de section EC3 (classes 1/2/3/4), interactions M+N et M+V,
  imperfections, analyse au 2ᵉ ordre / P-Δ.
À rappeler explicitement à l'utilisateur, à trois endroits (cf. « Sur
l'horizon » et « Mentions légales + disclaimer ») : **conditions générales**
(à rédiger), **encart visible dans les résultats de calcul** (écran + PDF),
et **acceptation à l'inscription**.

#### Vocabulaire (à respecter partout : code, commentaires, docs, réponses)

- On dit **renfort d'épaule** — jamais « renfort de genou ». Anglais :
  **haunch**, jamais « knee ». La barre s'appelle historiquement `jarret()` /
  « Jarret » dans le code (`business/calcport.py`) — terme charpente correct,
  conservé tel quel.

#### Décisions figées à la session 1 d'audit (verrouillées pour étapes 1 et 2)

- **Pieds de poteau bi-articulés** — encastrement hors périmètre (cf. « Sur
  l'horizon » §4 : piste offre premium / ponts roulants).
- **Résolution Euler-Bernoulli** (déformation d'effort tranchant négligée
  dans la raideur). PyNite v3 : `add_section` sans aires de cisaillement =
  pas de terme Timoshenko, donc parité directe. Passage éventuel à
  Timoshenko réévalué **seulement à l'étape 3** (discrétisation du renfort).
- **Renfort d'épaule gelé** : 1 barre prismatique, section reconstituée à
  hauteur `1,66 × h_traverse` (fonction `jarret()`), longueur = 10 % de la
  portée en projection horizontale. Refonte en barres multiples à inertie
  variable = **étape 3**, pas avant.
- **S235 seul** (`fy = 235` en dur ; noter que le paramètre `lim_fy` de
  `calcport()` est mort — non propagé à `calculer_et_verifier_resultats`, à
  traiter à l'étape 8 avec S275/S355).
- **Combinaisons `COMBI_DEPL` / `COMBI_EFF` inchangées** (facteurs actuels).
  Si une erreur/oubli EC0 manifeste est repéré pendant l'implémentation :
  **le signaler au user avant** toute correction.

### Étape 1 — Bascule vers PyNite
- Créer branche refactor/pynite (déjà anticipée dans la structure business/)
- Remplacer le solveur interne par PyNite pour la résolution structurelle
- Le calcul doit rester pilotable via la même interface
  charge_et_sections(geom, locali, chpro) autant que possible

#### Audit réalisé (session 1) — synthèse

- **Méthode actuelle** : méthode des déplacements maison (raideur directe),
  1er ordre linéaire, élément poutre-poteau 2D **Euler-Bernoulli** (3 DDL/nœud).
  Modèle figé : **7 nœuds / 6 barres**, portique bipente symétrique, 1 poteau
  par côté, pieds **articulés**. `E = 2 100 000 daN/cm²`, unités cm/daN.
- **Renfort d'épaule** : barres B1 et B4 (`N1→N2`, `N4→N5`), section `jarret()`
  = I reconstitué `b`/`tf`/`tw` de la traverse mais âme haute `1,66·h`,
  **prismatique**, sur 10 % de portée. Résistance vérifiée au genou
  (`tx_mom_renf_*`, Wpl du I `1,66·h`) et en bout (`tx_mom_pied_arba_*`, Wpl
  traverse nue). Suspecté n°1 de l'écart croissant avec CTICM (hauteur `1,66h`
  < `≈2h` réel au genou + renfort constant au lieu de dégressif → outil
  sur-dimensionne). À contre-sens : l'absence de flambement/déversement rend
  l'outil moins conservatif → l'écart net est une résultante, à décomposer en
  étape 2.
- **Résistance** : `taux = M / (Wpl · fy)` (γM0 = 1) + `V / (Avz · fy/√3)`,
  superposés APRÈS résolution avec `COMBI_EFF` ; ELS via `COMBI_DEPL` contre
  `hpot/150` (tête) et `portée/200` (flèche). Pas de N/M, pas d'instabilités.
- **Point de couture retenu** : une fonction interne unique
  `resoudre_cas(geom, sections, cas) -> ens_resu` (mêmes clés :
  `depl_t_p_g/d`, `fleche_fait`, `tx_mom_*`, `tx_cis_*`).
  `optimise_IPE`, `charge_et_sections`, `chargement_nv`, catalogue IPE,
  combinaisons : **inchangés**. Flag `MOTEUR = "legacy" | "pynite"` pour faire
  tourner les deux en parallèle (étape 2).
- **Piège signe** : `calcport()` renvoie `D_avec_app` et
  `barre.efforts_noeuds` avec un **signe globalement inversé** vs axes
  physiques (cf. commentaire « les signes sont mauvais » dans
  `crea_matrice_force`). Invisible en aval car `calculer_et_verifier_resultats`
  est auto-cohérent et `optimise_IPE` prend des `abs()` partout. Le backend
  PyNite utilise les signes physiques → `resoudre_cas` doit extraire
  **déplacements ET efforts de PyNite** (jamais mélanger), en gardant une
  convention unique entre les cas CP/NEI/VENT.

#### Étape 1.a — validée

- `PyNiteFEA==3.0.0` ajouté à `requirements.txt`.
- Comparaison legacy vs PyNite sur 1 portique, cas CP seul, section constante,
  **sans renfort d'épaule** (géométrie cas-01-compact) : après correction du
  signe global, **les 21 DDL coïncident à la précision machine** (écart
  relatif 0,000 %, résidus ~1e-15). Parité Euler-Bernoulli confirmée sans
  bricolage (pas besoin de forcer `G`).
- Conventions d'effort d'extrémité : voir « Règle de signe » ci-dessous.

#### Étape 1.b — validée

Renfort d'épaule **réintroduit à l'identique** (`jarret()` 1,66·h, 10 % de
portée, barres B1/B4). Legacy vs PyNite (1 modèle, résolution **par cas
élémentaire**, sans combinaison ELU/ELS PyNite), sur cas-01-compact, avec
le **cas CP** *et* un **cas perpendiculaire synthétique** :
- 21 DDL : écart relatif 0,000 %, résidu ~1e-16 ;
- efforts d'extrémité des 6 barres (N, V, M aux 2 nœuds) : écart ~1e-10.
La règle de signe ci-dessous tient **à l'identique pour la charge
perpendiculaire** → c'est une convention, pas une correction propre à la
gravité (donc robuste quand le vent entrera en 1.d).

#### Règle de signe legacy ↔ PyNite (à appliquer telle quelle en 1.c–1.f)

Le backend PyNite adopte **les conventions PyNite partout** ; on ne
reproduit jamais les signes du legacy. Deux écarts, de natures différentes :

1. **Défaut de signe global du legacy** (commentaire « les signes sont
   mauvais » dans `crea_matrice_force`) : le vecteur `D_avec_app` de
   `calcport()` est l'**opposé** du déplacement physique. Invisible en aval
   car tout consommateur ré-emploie ce même vecteur, ou prend `abs()`.
   → `resoudre_cas` pose `depl_t_p_g = −DX(N1)`, `depl_t_p_d = −DX(N5)`,
     `fleche_fait = −DY(N3)` (PyNite) — le « − » appliqué **une seule fois**,
     à l'extraction des déplacements.

2. **Effort d'about (« barre → nœud ») vs effort interne N(x)/V(x)/M(x)** :
   `efforts_noeuds` du legacy sont des efforts d'about ; PyNite
   `axial/shear/moment(x)` sont les diagrammes internes. Identité de
   statique, vraie pour **tout** chargement (gravité, vent perpendiculaire,
   charges nodales) :

   | legacy `efforts_noeuds[b]` | PyNite |
   |---|---|
   | `[Nᵢ, Vᵢ, Mᵢ]` (nœud origine `i`) | `[ −N(0), −V(0), −M(0) ]` |
   | `[Nⱼ, Vⱼ, Mⱼ]` (nœud fin `j`)     | `[ +N(L), +V(L), +M(L) ]` |

   Le « − » côté `i` n'est **pas** lié à l'orientation de la charge : c'est
   « effort interne à la coupure `i` = −(effort que la barre exerce sur le
   nœud `i`) ». Côté `j`, la normale sortante de la coupure pointe déjà
   selon +x local → pas de changement de signe. Vérifié bit à bit sur
   gravité **et** perpendiculaire (étape 1.b).

3. **Invariance pour `optimise_IPE`** : chaque clé `tx_*` cible **un seul**
   about de barre → le map applique un ±1 **fixe par clé, identique pour
   tous les cas élémentaires**. Donc `Σ_cas (combi · tx)` puis `abs()` (déjà
   fait par `optimise_IPE`), et les tests `abs()` sur les déplacements, sont
   **prouvablement invariants** au map. Le map ne sert qu'à la comparaison
   **cas par cas** de l'étape 1.e.

`resoudre_cas` extrait donc **déplacements ET efforts de PyNite** (jamais un
mélange legacy/PyNite), applique (1) aux déplacements et (2) aux efforts.

#### Étape 1.b — profilage (⚠ point bloquant, à trancher avant 1.c)

Machine de dev, médianes sur 25–200 exécutions. Legacy =
`charge_et_sections()` actuel complet (boucle `optimise_IPE` réelle).

| Cas | itér. IPE | **legacy** | PyNite natif¹ | PyNite assembleur² |
|---|---|---|---|---|
| cas-01-compact | 13 | **32 ms** | ~420 ms (×13) | ~38 ms (×1,2) |
| cas-02-bas-large | 12 | **16 ms** | ~295 ms (×18) | ~32 ms (×2,0) |
| cas-03-haut-fin | 74 | **106 ms** | ~2400 ms (×22) | ~195 ms (×1,8) |

¹ **PyNite natif** = 1 modèle, 1 combo PyNite par cas élémentaire
  (`add_load_combo`, facteur 1), `analyze_linear()` puis lecture via
  `member.moment()/shear()`. Coût mesuré par résolution :
  `analyze_linear` **≈ 21 ms** + extraction **≈ 10 ms**, × nb d'itérations
  IPE. `sparse=False` ≈ `sparse=True` (21 DDL : la conversion CSR coûte plus
  qu'elle ne rapporte). Le coût **n'est pas** dans l'algèbre (assemblage
  `Ke` 0,5 ms, `spsolve` < 0,1 ms) mais dans l'orchestration Python de
  `analyze_linear` (`_calc_reactions`, `_store_displacements`,
  partition/renumber) et dans `member.*()` qui reconstruit les diagrammes.

² **PyNite assembleur** = PyNite fournit l'assemblage `Ke`, la conversion
  charges → `FER`/`P`, le catalogue de sections ; on pilote soi-même
  partition + `scipy.linalg.lu_factor` (1×/itération) + `lu_solve` par cas,
  **RHS des cas non-CP mis en cache** entre itérations (seul CP recalculé,
  pour le poids propre), efforts d'about par transformation locale.
  Mesuré : **≈ 2,3–2,6 ms/itération**. Contourne `analyze()`.

**Conclusion** : « PyNite natif » dégrade l'endpoint HTMX `/htmx/calcul`
d'un facteur **13–22** (jusqu'à 2,4 s) → **inacceptable en prod**.
« PyNite assembleur » tient (**×1,2–2**, < 200 ms) mais s'appuie sur des
méthodes internes de PyNite (`Ke`, `FER`, `P`) et ré-implémente
partition/solve/récupération.

**Décision (user) — option A retenue : PyNite assembleur.** PyNite fournit
l'assemblage `Ke`, le catalogue de sections et la conversion charges →
`FER`/`P` ; `resoudre_cas` pilote lui-même la partition (CL), la
factorisation (`scipy.linalg.lu_factor`, 1×/itération IPE) et le `lu_solve`
par cas élémentaire, RHS des cas non-CP mis en cache entre itérations.
Motifs : perf ×1,2–2 (B rejeté à ×13–22) ; on garde le bénéfice structurel
qui justifie la bascule (assemblage `Ke` + sections + charges→efforts
réutilisables tels quels pour le jarret discrétisé de l'étape 3 et le
portique asymétrique de l'étape 6, là où C obligerait à réécrire
l'assemblage maison à chaque nouvelle géométrie) ; argument externe (se
prévaloir de PyNiteFEA, lib EF établie, comme caution technique).

> ⚠️ **Politique de version PyNite** (risque accepté de l'option A —
> dépendance à des méthodes semi-internes `Ke` / `FER` / `P`) : PyNite est
> **piqué à `==3.0.0`** dans `requirements.txt`. Toute montée de version est
> un **projet à part entière**, pas une mise à jour de routine : re-run
> complet des tests de non-régression contre `validation/` (sorties
> identiques au chiffre près) **avant** merge. Ne jamais bumper PyNite dans
> un `pip install --upgrade` groupé.

Alternatives écartées : **(B) PyNite natif** (`analyze()` + combos) — le
plus propre mais ×13–22 ; **(C) solveur maison allégé** + PyNite seulement
comme oracle hors ligne — perf ×1 mais assemblage maison à maintenir pour
chaque géométrie future.

**Observation annexe** (hors périmètre étape 1, touche la logique
d'optimisation) : `optimise_IPE` fait **74 itérations** sur cas-03
(recherche gloutonne : +1 taille à la fois, reset traverse à poteau−4 à
chaque bump de poteau). Une recherche plus fine diviserait le temps par
3–5 pour **tous** les backends.

#### Étape 1.c — validée (CL bi-articulées + blocage hors-plan)

Backend assembleur (option A) : `m.Ke()` de PyNite, puis partition /
`scipy.linalg.lu_factor` / `lu_solve` pilotés dans `resoudre_cas`.
- Masque de DDL libres déduit des flags `def_support` : N0/N6 → `{RZ}`
  seul (DX, DY bloqués = rotule) ; N1–N5 → `{DX, DY, RZ}` ; `DZ, RX, RY`
  bloqués partout (modèle plan). Total **17 DDL libres**, identiques à la
  réduction du legacy (`rz N0 ; dx,dy,rz N1..N5 ; rz N6`).
- Sur cas-03-haut-fin (asymétrique, avec vent), **les 8 cas élémentaires**
  (CP, NEI, NEI_ACCI, 4× VEN long-pan, VEN pignon) : déplacements **0,000 %**
  d'écart, **réactions d'appui 0,000 %** (au signe global près, règle 1 —
  `R_legacy = K·D_legacy − F_legacy` porte le même flip).
- **Gotcha réutilisable (1.d–1.f)** : `m.Ke()` est indexée 6 DDL/nœud dans
  l'ordre `DX, DY, DZ, RX, RY, RZ`, nœuds en ordre d'`ID` (= ordre
  d'insertion). La rotation dans le plan est **RZ = indice local 5**, pas 2
  (2 = `DZ`, hors-plan, toujours nul). Extraire un vecteur « 3 DDL/nœud »
  façon legacy = prendre les indices locaux **(0, 1, 5)**.
- Le contrôle « ΣF appliqué + Σréactions » n'est **pas** un bon test
  d'équilibre quand des charges réparties perpendiculaires agissent sur des
  barres inclinées (`Σ FER` ≠ résultante appliquée) — se fier à l'égalité
  des réactions avec le legacy.

**Scripts de parité versionnés** : `validation/pynite_check/` — un script
autonome et figé par sous-étape (`check_1a_sans_jarret.py`,
`check_1b_renfort_epaule.py`, `check_1b_profilage.py`,
`check_1c_cl_et_vent.py`), rejouables (sortie `0`/`1`). À relancer lors de
toute montée de version de PyNite ou refactor du moteur. Voir le `README.md`
du dossier.

#### Jeux de validation (étape 2) — entrées `charge_et_sections`

Retrouvés depuis les PDF **Instanote26** de `validation/` (les PDF `… CTICM.pdf`
sont la **référence externe** de comparaison, pas des entrées). Longueurs en
cm, `pente` = ratio, `couv`/`divers` en daN/m². Sorties = algo actuel, à figer.

| Cas | geom | localisation | cp | Algo actuel |
|---|---|---|---|---|
| cas-01-compact | hpot 350, portee 400, pente 0.10, longueur 2000, entraxe 400, h_acro 0 | Blois / dept 41 / alt 114 / IIIb | couv 10, divers 2 | poteau **IPE 160**, traverse **IPE 140**, taux **40,0 %**, flèche faîtage 2,8 mm (L/1404), dérive H/160, masse 168 kg |
| cas-02-bas-large | hpot 500, portee 2200, pente 0.03, longueur 4000, entraxe 800, h_acro 100 | Millau / dept 12 / alt 631 / IIIa | couv 50, divers 20 | poteau **IPE 600**, traverse **IPE 600**, taux **100,0 %**, flèche faîtage 57,4 mm (L/383), dérive H/1057, masse 4174 kg |
| cas-03-haut-fin | hpot 1000, portee 800, pente 0.10, longueur 4000, entraxe 500, h_acro 100 | Brest / dept 29 / alt 50 / cat. 0 | couv 20, divers 5 | poteau **IPE 600**, traverse **IPE 500**, taux **60,0 %**, flèche faîtage 2,0 mm (L/4044), dérive **H/161** (pilotée par la dérive), masse 3242 kg |

`ancien_nom_comm` = `""` pour les trois. Reconstruction vérifiée : rejeu de
ces entrées dans `charge_et_sections` → sorties identiques aux PDF au chiffre
près.

### Étape 2 — Validation croisée (JALON BLOQUANT)
- Choisir 2 ou 3 modèles de portique représentatifs (dont un cas limite)
- Calculer chaque modèle avec : l'ancien algo, PyNite, et un logiciel externe
  de référence (CTICM)
- Définir AVANT de comparer les seuils d'écart acceptables (%) sur : flèche,
  moment fléchissant, effort normal, section retenue
- Ne pas passer à l'étape 3 tant que cette validation n'est pas actée

### Étape 3 — Jarrets en suite de petites barres
- Remplacer l'approximation actuelle (section à 2/3, longueur à 10% arbitraire)
  par une modélisation en plusieurs barres sur la longueur du jarret
- Permet à terme d'optimiser finement section et longueur

### Étape 4 — Audit des charges, en particulier celles de vent
- Revue exhaustive des configurations de vent (zones, catégories de terrain,
  coefficients de forme selon géométrie, faces au vent/sous le vent)
- Cas de test dédiés par configuration

### Étape 5 — Modèle d'appentis
- Reprendre l'ancien modèle back-office si dispo (portique à un seul arbalétrier)
  et le remettre au propre avec le nouveau moteur PyNite, sinon le créer

### Étape 6 — Portique bipente asymétrique
- Support de 2 poteaux distincts + 2 arbalétriers distincts
- Revoir l'algorithme d'optimisation : l'espace de recherche passe de
  2 variables discrètes (1 poteau, 1 arba) à un espace plus large
  (2 poteaux, 2 arbas, + longueurs de jarret cf étape suivante)

### Étape 7 — Optimisation de la longueur des jarrets
- Rendre la longueur de jarret variable en interne (non exposée utilisateur)
- Adapter l'optimisateur pour jouer sur ce paramètre en plus du choix IPE
  (ex : rallonger de quelques cm peut faire redescendre d'une section)

### Étape 8 — Option nuance d'acier en fin de calcul + renommage des forfaits

Contexte : les tests de validation croisée (étape 2) montrent que l'écart
entre le moteur interne et les logiciels de référence croît avec le taux
de travail ELU du portique (zone de marge faible). Pour les cas proches
de la limite de résistance, proposer une nuance d'acier supérieure
(S275/S355) permet de gagner une ou plusieurs sections IPE sans toucher
à l'ELS (le module d'élasticité E est identique entre nuances : seule fy
change, donc seules les vérifications de résistance sont affectées, pas
les déplacements).

Fonctionnalité :
- En fin de calcul, si le dimensionnement est piloté par une vérification
  de résistance (pas de déplacement), proposer à l'utilisateur les
  sections obtenues en S275 et S355 en plus du S235 par défaut
- Recalculer la classification de section (classe 1/2/3/4) pour chaque
  nuance, ne pas se contenter d'appliquer un facteur sur le taux de travail
- L'utilisateur choisit la nuance qui lui convient

Prérequis (à traiter AVANT d'implémenter cette fonctionnalité) :
Les forfaits d'abonnement actuels s'appellent S235/S275/S355 (grades
EN 10025). Une option de nuance d'acier sur le calcul dans le même
vocabulaire créerait une confusion forte entre "palier d'abonnement" et
"matériau de la structure". Renommer les forfaits AVANT d'introduire
cette fonctionnalité (impact : base de données - champ plan par défaut
"S235", UI, et éventuellement Stripe si déjà intégré à ce moment-là).

Cette étape se place après la validation croisée et l'audit des charges
de vent — c'est un ajout produit à part entière, pas une correction de
justesse.

Règle de méthode : chaque étape = une session dédiée, validée et
commitée avant de passer à la suivante. Pas de mélange d'étapes dans une
même session.
