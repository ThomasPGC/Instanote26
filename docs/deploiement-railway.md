# Déploiement Railway — détail

> Extrait de `CLAUDE.md` (réorganisation doc). Le briefing court reste dans `CLAUDE.md`.

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
  défaut, comme en local. **`MOTEUR_CALCUL` : à définir = `pynite` sur
  Railway** (Settings → Variables) pour activer le backend PyNiteFEA en prod
  (`business/solveur_pynite.py`). Absente ⇒ backend maison `legacy` (résultats
  identiques ; fallback sûr). Voir « Roadmap moteur de calcul », étape 1.
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
