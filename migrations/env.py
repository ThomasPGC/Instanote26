"""Environnement Alembic pour Instanote26.

Points de configuration propres au projet :

- On ne lit PAS `sqlalchemy.url` depuis `alembic.ini`. L'URL de la base est
  reconstruite ici à partir de la variable d'environnement `SQLITE_DB_PATH`,
  exactement comme le fait `app/database.py` (fallback `./instanote26.db` si la
  variable est absente, ex. en local). En prod (Railway), `SQLITE_DB_PATH`
  pointe vers le Volume monté sur `/data`.
- L'app tourne en async (`sqlite+aiosqlite`), mais les migrations n'ont aucun
  besoin d'async : on utilise ici le pilote `sqlite3` synchrone de la stdlib
  (`sqlite:///...`). Moins de dépendances, pas de boucle asyncio à gérer.
- `render_as_batch=True` : SQLite ne sait pas faire tous les `ALTER TABLE`.
  Alembic contourne en recréant la table (copie + rename) quand c'est
  nécessaire. Sans effet sur un simple `ADD COLUMN`, mais indispensable pour
  les futures migrations (renommage/suppression de colonne, contraintes...).
"""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

# Charge le .env local (mêmes variables qu'en prod). Sur Railway, .env n'existe
# pas et load_dotenv() ne fait rien : les variables viennent de l'environnement.
load_dotenv()

# `prepend_sys_path = .` dans alembic.ini met déjà la racine du projet sur
# sys.path : on peut donc importer `app.*` directement.
from app.base import Base
import app.models.user  # noqa: F401  (enregistre la table `user` sur Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    sqlite_path = os.environ.get("SQLITE_DB_PATH", "./instanote26.db")
    return f"sqlite:///{sqlite_path}"


def run_migrations_offline() -> None:
    """Mode 'offline' : génère le SQL sans se connecter à la base."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Mode 'online' : se connecte réellement à la base et applique les migrations."""
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
