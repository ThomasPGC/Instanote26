# Historique — corrections passées

> Archive extraite de `CLAUDE.md`. Bugs déjà corrigés ; gardé comme mémoire.
> Les pièges encore actifs sont rappelés dans `CLAUDE.md` § « Pièges actifs ».

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
