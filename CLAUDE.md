# Instanote26 — SaaS calcul charpente métallique

Outil web de **prédimensionnement de portiques métalliques bipente** pour étude
de prix (choix des IPE poteau/traverse, flèche, taux de travail, masse, export
PDF). Public : professionnels du bâtiment.

Ce fichier est le **briefing** chargé à chaque session : l'essentiel pour
travailler *maintenant*. Le détail et l'historique sont dans `docs/` (voir
« Documentation » en bas).

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
- SQLite (dev **et** prod, via Volume Railway) → PostgreSQL envisagé à terme
- Auth : fastapi-users (cookie JWT) · Emails : API Brevo · Migrations : Alembic
- Back office : SQLAdmin (`/admin`) · PDF : WeasyPrint
- Déploiement : Railway.app (auto-deploy sur `master`)

## Carte du code (résumé — détail : `docs/architecture.md`)
- `app/main.py` — point d'entrée FastAPI ; `load_dotenv()` tout en haut
- `app/routers/` — endpoints : `calcul.py` (HTMX calcul + PDF), `compte.py`,
  `auth.py`, `entreprise.py` (JSON SIRET/adresse), `pdf_test.py` (`GET /test-pdf`)
- `app/templating.py` — instance **unique** `Jinja2Templates` + filtres typo
- `app/users.py` / `middleware.py` / `models/user.py` / `database.py` — auth,
  `request.state.user`, table `User`, moteur SQLite async
- `app/email.py` (Brevo), `app/siret.py` (base Sirene), `app/admin.py` (SQLAdmin)
- `business/` — code métier, indépendant du web. **Ne pas modifier sauf
  évolution métier explicite.**
  - `business/calcport.py` — moteur historique + `optimise_IPE` +
    `_SolveurLegacy` + aiguillage `MOTEUR_CALCUL`
  - `business/solveur_pynite.py` — backend PyNiteFEA (`MOTEUR_CALCUL=pynite`)
  - `business/jarret_discret.py` — renfort d'épaule discrétisé (étape 3) :
    section 3 semelles + `r`, topologie paramétrée par `N_DISC_JARRET`,
    diagnostic cisaillement a posteriori
  - `business/chargement_nv.py` — charges neige / vent
- `static/js/portique.js` — schéma SVG temps réel + géoloc + hooks calcul/PDF
- `static/js/entreprise-form.js` — aide SIRET + adresse (inscription, `/compte`)
- `migrations/` + `alembic.ini` — schéma de base (Alembic)
- `validation/` — jeux de référence + `validation/pynite_check/` (parité
  legacy ↔ PyNite)

## Fonction principale
`business/calcport.py` → `charge_et_sections(geom, locali, chpro)`
- `geom` : dict `{hpot, portee, pente, longueur, entraxe, h_acro}` (longueurs cm,
  `pente` = ratio)
- `locali` : dict `{nom_commune, ancien_nom_comm, departement, altitude, rugosite}`
- `chpro` : dict `{couv, divers}` (daN/m²)
- retourne : dict des résultats de calcul

## Conventions
- Templates FastAPI : `TemplateResponse(request=request, name="fichier.html")`.
  Toujours `from app.templating import templates` (instance unique).
- Endpoints HTMX du calcul dans `app/routers/calcul.py` ; compte utilisateur
  dans `app/routers/compte.py`.
- **Schéma de base : Alembic uniquement.** `alembic revision --autogenerate -m
  "..."` → **relire** le fichier généré → `alembic upgrade head`. Ne pas se
  reposer sur `Base.metadata.create_all` (supprimé). Migrations idempotentes.
  Recette complète : `docs/architecture.md`.
- **Typographie française de l'affichage** : voir `TYPOGRAPHIE.md`. Tout nombre
  montré à l'utilisateur (templates HTML + PDF WeasyPrint) passe par les filtres
  Jinja2 `| fr_nombre` / `| fr_mesure` (définis dans `app/templating.py`) —
  virgule décimale, espace insécable milliers + unité. **Ne jamais** appliquer
  ces filtres aux valeurs soumises au serveur, aux appels d'API (BAN/IGN/Sirene)
  ni aux propriétés CSS/ARIA.

## Moteur de calcul — décisions durables
Détail complet et roadmap : `docs/moteur-de-calcul.md`.

### Positionnement produit — choix DURABLE, ne pas « corriger »
Instanote26 fait du **prédimensionnement pour étude de prix**, pas de la
vérification réglementaire complète aux Eurocodes. Sont **volontairement et
durablement hors périmètre** (ce ne sont **pas des oublis** — ne pas les
« ajouter » sans validation explicite du user) :
- **flambement** (poteaux, arbalétriers) et **déversement** (semelle comprimée) ;
- classification de section EC3 (classes 1/2/3/4), interactions M+N et M+V,
  imperfections, analyse au 2ᵉ ordre / P-Δ.
À rappeler à l'utilisateur à 3 endroits : conditions générales, encart dans les
résultats (écran + PDF), acceptation à l'inscription.

### Vocabulaire (à respecter partout : code, commentaires, docs, réponses)
- **renfort d'épaule** — jamais « renfort de genou ». Anglais : **haunch**,
  jamais « knee ». La barre s'appelle historiquement `jarret()` dans le code
  (terme charpente correct, conservé).

### Décisions figées
- **Pieds de poteau bi-articulés** (encastrement hors périmètre ;
  piste offre premium / ponts roulants — `docs/roadmap-produit.md`).
- **Résolution Euler-Bernoulli** (cisaillement négligé dans la raideur).
  Diagnostic a posteriori non bloquant (`jarret_discret.diagnostic_cisaillement`)
  depuis l'étape 3 : effet < 1 % sur la flèche → EB confirmé.
- **Renfort d'épaule** : **legacy** = 1 barre prismatique `1,66 × h_traverse`
  (`jarret()`), figé = oracle de l'ancien modèle. **pynite** (étape 3 faite) =
  discrétisé en `N_DISC_JARRET` (défaut 6) tronçons, âme dégressive linéaire
  `2·h → 1·h`, section I à 3 semelles + congés `r` recoupée PropSection
  (`jarret_discret.caracs_section_jarret`) ; **nœuds excentrés sur l'axe neutre**
  (poteau modélisé raccourci ; `JARRET_EXCENTRE`, défaut activé). Longueur
  inchangée (10 % portée).
- **S235 seul** (`fy = 235` en dur).
- **Combinaisons `COMBI_DEPL` / `COMBI_EFF` inchangées.** Si un oubli EC0
  manifeste est repéré : **le signaler au user avant** toute correction.

### `MOTEUR_CALCUL` / `N_DISC_JARRET` / `JARRET_EXCENTRE` (variables d'env)
- `MOTEUR_CALCUL` absente / `legacy` → solveur maison, renfort d'épaule
  `1,66·h` prismatique ; `pynite` (alias `pynite_corrige`) →
  `business/solveur_pynite.py`, renfort d'épaule **discrétisé + excentré**.
- `N_DISC_JARRET` : tronçons par renfort d'épaule (défaut **6**). `1` = ancien
  modèle (barre unique), utilisé par les harnais de parité.
- `JARRET_EXCENTRE` : `0` = jarret colinéaire à la traverse ; sinon (défaut) =
  nœuds sur l'axe neutre (si `N_DISC_JARRET>1`).
- **Résultats identiques seulement en `N_DISC_JARRET=1`.** Défaut code =
  `legacy` (bascule vers `pynite` = commit séparé au push, après validation
  manuelle) ; Railway = `pynite`.

### État d'avancement
- **Étape 1 (bascule PyNite) : faite et validée** — journal
  `docs/historique/bascule-pynite-etape1.md`.
- **Étape 2 (validation croisée CTICM) : validée** — `validation/COMPARAISON_CTICM.md`.
- **Étape 3 (jarret discrétisé + excentré) : faite** — branche
  `feat/jarret-discretise-etape3`. Section 3 semelles + `r` recoupée PropSection ;
  nœuds du jarret sur l'axe neutre ; legacy figé = oracle ; diagnostic
  cisaillement non bloquant. **cas-02 « bas et large » IPE 600/600 → IPE 600/550**
  (−388 kg, 1 cran du CTICM ; résiduel = moment de poteau → étape 4) ;
  cas-01/03 inchangés. Journal :
  `docs/historique/jarret-discretise-etape3.md`. **Reste :** validation manuelle
  user en local (`MOTEUR_CALCUL=pynite` dans `.env`), puis push + commit de
  bascule `MOTEUR_CALCUL` défaut `legacy → pynite`.
- **Étape 4 (audit des charges de vent) : prochaine.**
- Scripts de parité : `validation/pynite_check/` (`check_1*` + `check_3*` — à
  relancer à toute montée de version PyNite ou refactor moteur ; PyNite **piqué
  à `==3.0.0`**, check-list dans `docs/moteur-de-calcul.md`).

## Déploiement (résumé — détail : `docs/deploiement-railway.md`)
- Service Railway connecté à la branche `master` : **push = rebuild + redémarrage**.
  → **Ne pas pousser sur `master` des changements mineurs / doc seule** (ce
  fichier, typos...). Committer en local, faire partir avec le prochain
  changement de code utile.
- **Start command** (Railway → Settings) :
  `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  → migrations appliquées automatiquement à chaque déploiement.
- Builder : **Railpack** (`railpack.json` à la racine — paquets apt WeasyPrint).
- Variables d'env configurées : `SQLITE_DB_PATH` (= `/data/instanote26.db`,
  Volume), `INSTANOTE26_AUTH_SECRET`, `BREVO_API_KEY`, `EMAIL_FROM`,
  `APP_BASE_URL`. **`MOTEUR_CALCUL=pynite` à poser** pour activer PyNite en prod.
- Après tout déploiement : tester `GET /test-pdf`, un export PDF réel, `/compte`.

## En cours / prochaine session
- **Focus** : mettre en valeur l'image du portique et les résultats de calcul.
- **Suivi d'usage / analytics** : table `calcul_log` (`user_id` nullable,
  `created_at`, sous-ensemble entrées/sorties), modèle SQLAlchemy + migration
  Alembic ; écriture depuis `POST /htmx/calcul` et l'export PDF, en `try/except`
  (ne pas bloquer la réponse) ; vues d'agrégation dans le back office. RGPD.
- **Mentions légales + disclaimer métier** : page `/mentions-legales` (éditeur,
  hébergeur Railway, cookies), disclaimer visible (près de « Calculer » + dans le
  PDF + acceptation à l'inscription), footer dans `base.html` (à créer).
- **Décider** si les routes `/calcul` et l'export PDF doivent être protégées
  (aujourd'hui : aucune protection) — à traiter avec la stratégie de paliers
  S235/S275/S355 (`docs/roadmap-produit.md`).
- Vérifier / migrer le schéma SVG PNG local → mémoire avant prod (collisions
  multi-utilisateurs) — cf. `docs/architecture.md`.

## Pièges actifs
- **`ProxyHeadersMiddleware`** doit rester le middleware le plus externe dans
  `app/main.py` (ajouté après `CurrentUserMiddleware`) : sans lui, Railway
  termine le TLS et SQLAdmin génère des URL `http://` → CSS/JS bloqués (mixed
  content). Cf. `docs/historique/corrections.md`.
- **Alembic est seul maître du schéma** : jamais de `Base.metadata.create_all`.
  Un schéma qui prend de l'avance sur le pointeur Alembic → crash-loop en prod.
- **PyNite piqué `==3.0.0`** : toute montée de version = projet à part entière,
  check-list obligatoire dans `docs/moteur-de-calcul.md`.
- **Parité legacy ↔ pynite = ancien modèle uniquement.** Depuis l'étape 3, le
  backend `pynite` discrétise le renfort d'épaule (`N_DISC_JARRET=6` par
  défaut) et **n'est plus identique au legacy**. `check_1g` est épinglé à
  `N_DISC_JARRET=1` ; `check_3c` teste la parité de l'ancien modèle ;
  `check_3d` valide le modèle discrétisé. Ne pas « réparer » une divergence
  `check_1g` en `N_DISC_JARRET=6` — c'est attendu.
- **fastapi-users 15.0.5** : `CookieTransport.get_login_response()` construit
  lui-même sa `Response` (API différente des versions antérieures).

## Documentation (`docs/`, non chargée automatiquement)
- `docs/architecture.md` — carte détaillée du code, features livrées, recettes
  opérationnelles (droits admin, migration Alembic, tests post-déploiement)
- `docs/deploiement-railway.md` — Railway en détail (builder, apt WeasyPrint,
  Volume, variables d'env, DNS, région)
- `docs/moteur-de-calcul.md` — positionnement produit, décisions figées,
  `MOTEUR_CALCUL`, roadmap étapes 2→8, check-list montée de version PyNite
- `docs/roadmap-produit.md` — décisions produit à trancher (paliers
  S235/S275/S355, démo sans compte, email admin, pied encastré premium)
- `docs/historique/` — journal de bord, conservé mot pour mot, **non chargé** :
  - `sessions-infra-1-10.md` — construction des features (auth → back office)
  - `bascule-pynite-etape1.md` — migration moteur legacy → PyNite (étape 1)
  - `corrections.md` — bugs déjà corrigés
- `TYPOGRAPHIE.md` — règles de typographie française de l'affichage
