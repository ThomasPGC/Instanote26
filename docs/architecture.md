# Architecture — carte du code & choix non-évidents

> Vue d'ensemble « ce qui existe et où ». Le récit détaillé de chaque session
> de développement est dans `docs/historique/sessions-infra-1-10.md`.

## Arborescence

| Chemin | Rôle |
|---|---|
| `app/main.py` | point d'entrée FastAPI ; `load_dotenv()` **tout en haut**, avant tout import de `app.*` ; montage des routeurs, middlewares, `/static`, `setup_admin(app)` |
| `app/templating.py` | instance **unique** `Jinja2Templates` (`from app.templating import templates`) + filtres typo `fr_nombre` / `fr_mesure` |
| `app/base.py` | `Base` SQLAlchemy (`DeclarativeBase`), isolée pour casser un import circulaire `database.py` ↔ `models/user.py` |
| `app/database.py` | moteur SQLite **async** (`aiosqlite`) ; chemin lu depuis `SQLITE_DB_PATH` (fallback `./instanote26.db`). Plus de `create_all` : Alembic est seul maître du schéma |
| `app/models/user.py` | table `User` (fastapi-users + `plan`, `nom`, `prenom`, `entreprise`, `siret`, adresse, `notes`, `created_at`) |
| `app/schemas/user.py` | schémas Pydantic `UserRead` / `UserCreate` / `UserUpdate` |
| `app/users.py` | `UserManager`, backend d'auth **par cookie** JWT (`INSTANOTE26_AUTH_SECRET`), `current_active_user` + `current_active_user_optional`. Hooks email (`on_after_register` → `request_verify`, `on_after_forgot_password`) |
| `app/middleware.py` | `CurrentUserMiddleware` : décode le cookie `instanote26_auth`, peuple `request.state.user` (ou `None`, sans requête DB si pas de cookie) → `base.html` affiche l'état de connexion sans dépendance par route |
| `app/email.py` | `send_email(to, subject, html)` via API **Brevo** (`BREVO_API_KEY`, `EMAIL_FROM`). Erreur explicite si config absente |
| `app/siret.py` | `verify_siret(siret) -> SiretCheck` (async) via `recherche-entreprises.api.gouv.fr`. Statuts `ok` / `not_found` / `closed` (bloquants) / `api_unavailable` (non bloquant) |
| `app/admin.py` | back office **SQLAdmin** monté sur `/admin` ; `AdminAuth` relit le cookie fastapi-users + exige `is_active` **et** `is_superuser` |
| `app/routers/calcul.py` | endpoints HTMX du calcul : `POST /htmx/calcul`, `POST /htmx/calcul-pdf` ; `_prepare_svg_for_pdf()` |
| `app/routers/compte.py` | `GET/POST /compte` (profil pro, éditable) — protégé via `current_active_user_optional` + redirect 303 manuel |
| `app/routers/auth.py` | `/auth/login`, `/auth/register`, `/auth/logout`, `/auth/verify`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/inscription-terminee` — pages Jinja2 + redirects 303 (pas les routeurs JSON de fastapi-users) |
| `app/routers/entreprise.py` | endpoints JSON pour le JS des formulaires : `/htmx/siret-info`, `/htmx/communes`, `/htmx/rue-search` (jamais bloquants) |
| `app/routers/pdf_test.py` | `GET /test-pdf` — sonde WeasyPrint isolée, n'importe rien de `business/`. À tester après chaque déploiement |
| `business/calcport.py` | moteur historique (méthode des déplacements maison) + `optimise_IPE` + `_SolveurLegacy` + aiguillage `MOTEUR_CALCUL` |
| `business/solveur_pynite.py` | backend PyNiteFEA (`SolveurPyNite`), actif si `MOTEUR_CALCUL=pynite`. Stub `sys.modules['Pynite.ShearWall']` en tête = neutralise l'import matplotlib |
| `business/chargement_nv.py` | charges neige / vent |
| `static/js/portique.js` | schéma SVG temps réel + géolocalisation adresse + hooks calcul/PDF (`updatePortiqueAfterCalc`, `resetPortiqueSections`, `preparePdfForm`) |
| `static/js/entreprise-form.js` | aide saisie SIRET + adresse, partagé inscription + `/compte` ; `init()` idempotent, rejoué sur `htmx:afterSwap` |
| `migrations/` + `alembic.ini` | migrations de schéma (Alembic) ; `migrations/env.py` reconstruit l'URL depuis `SQLITE_DB_PATH`, moteur **synchrone**, `render_as_batch=True` |
| `validation/` | jeux de référence (PDF Instanote26 vs notes CTICM) + `validation/pynite_check/` (scripts de parité legacy ↔ PyNite, un par sous-étape) |
| `templates/` | HTML Jinja2 ; `base.html` (nav conditionnelle) ; `calcul/`, `auth/`, `compte/`, `emails/` |

## Fonctionnalités livrées (résumé)

- **Schéma SVG temps réel** (`portique.js`) — vue de face 2D + perspective entraxe + cotes ; après calcul, sections IPE à l'échelle. ⚠️ **à vérifier avant prod** : le schéma est-il encore sauvé en PNG local (AppData/Temp) ? → à passer en mémoire (bytes) pour éviter les collisions multi-utilisateurs.
- **Géolocalisation adresse** — autocomplétion API Base Adresse Nationale (sans clé, debounce 300 ms) → commune, département, GPS → altimétrie IGN sur coords exactes ; communes fusionnées gérées via `geo.api.gouv.fr`. Rugosité = choix manuel.
- **Erreur IPE insuffisants** — exception métier `PasDeSolutionIPE` (`optimise_IPE`), `is_error` basé sur `status != "OK"`, message rouge + `resetPortiqueSections()`.
- **Export PDF** (WeasyPrint, en mémoire) — `POST /htmx/calcul-pdf` relance `charge_et_sections()` (rien n'est conservé côté serveur entre le calcul HTMX et l'export). Bouton PDF dans un `#pdf-form` séparé (form principal en `hx-post` → `formaction` ignoré par htmx), rattaché via `form="pdf-form"`, soumission navigateur classique. `_prepare_svg_for_pdf()` : WeasyPrint ignore `width="100%"`/`aspect-ratio` → attributs `width`/`height` en px calculés depuis le `viewBox`.
- **Auth fastapi-users** — cookie JWT, register/login/logout à la main (pages Jinja2). fastapi-users 15.0.5 : `CookieTransport.get_login_response()` construit lui-même sa `Response` → on la transforme en redirect 303.
- **Emails transactionnels** (Brevo) — vérif email à l'inscription (**non bloquante** : `current_active_user` ne teste que `is_active`) + reset mot de passe. `forgot-password` répond toujours pareil (anti-énumération de comptes). Anti-email jetable via `disposable-email-domains`.
- **Page `/compte`** — profil pro éditable (nom, prénom, SIRET, adresse) ; `entreprise` (raison sociale) en lecture seule. SIRET modifiable (change au déménagement) → revérifié Sirene si différent. Endpoint HTMX : recharge `session.get(User, user.id)` (l'objet de la dépendance d'auth est sur une session fermée). Cookie expiré → 401 + `HX-Redirect`.
- **Inscription pro** — collecte nom/prénom/entreprise/SIRET/adresse ; SIRET vérifié Sirene (`not_found`/`closed` → formulaire réaffiché 400 ; `api_unavailable` → on continue). Pas de champ `pays` (SIRET franco-français uniquement, contrainte CAE). Connexion auto après succès.
- **Back office `/admin`** (SQLAdmin) — liste/recherche/édition/activation/suppression des comptes. `plan` en `<select>` fermé (S235/S275/S355). `hashed_password` exclu partout. `can_create = False`. Suppression = vrai `DELETE` (RGPD), log `email`+`id`+date avant effacement. Bouton « Admin » dans la navbar si `is_superuser`.
- **AUDIT_MODE** (`AUDIT_MODE=1`, désactivé par défaut) — instrumentation de diagnostic du moteur : `audit_section_forcee()`, traces d'itérations de `optimise_IPE`, `debug_capture` dans `calcport()`, log du payload dans `POST /htmx/calcul`. Laissée en place volontairement. Détail : `docs/historique/sessions-infra-1-10.md`.

## Recettes opérationnelles

### Se donner les droits admin (pas d'UI self-service)

Local (SQLite) :
```
python -c "import sqlite3; c=sqlite3.connect('instanote26.db'); c.execute(\"UPDATE user SET is_superuser=1 WHERE email='tomajeu@gmail.com'\"); c.commit()"
```
Prod (Railway) : shell sur le service →
```
sqlite3 /data/instanote26.db "UPDATE user SET is_superuser=1 WHERE email='...'"
```
Puis se reconnecter (le flag est relu à la connexion).

### Prochaine migration Alembic

1. modifier le(s) modèle(s) SQLAlchemy (`app/models/`) ;
2. `alembic revision --autogenerate -m "description courte"` ;
3. **relire** le fichier généré dans `migrations/versions/` (l'autogenerate n'est pas parfait, surtout sur SQLite) ;
4. `alembic upgrade head`.

`alembic downgrade -1` annule la dernière ; `alembic current` / `alembic history` pour l'état ; `alembic check` = modèle ⇔ schéma cohérents. En prod, la start command Railway fait `alembic upgrade head` automatiquement à chaque déploiement. Les migrations existantes sont **idempotentes** (guard `has_table` / `ADD COLUMN` seulement si absente).

### Tester après déploiement

- `GET /test-pdf` (sonde WeasyPrint isolée) ;
- export PDF d'une vraie note de calcul ;
- `/compte` (GET + POST).
