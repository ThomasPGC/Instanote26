import os
from typing import AsyncGenerator

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.base import Base
from app.models.user import User

# --- Dev : SQLite local ---
# SQLITE_DB_PATH permet de pointer vers un Volume Railway en prod (ex.
# /data/instanote26.db) pour persister la base entre redémarrages du service.
# Non définie -> fallback sur le fichier local ./instanote26.db (comportement
# inchangé en dev).
SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "./instanote26.db")
DATABASE_URL = f"sqlite+aiosqlite:///{SQLITE_DB_PATH}"

# --- Migration Postgres (plus tard, sur Railway) ---
# 1. Ajouter l'addon Postgres sur Railway -> il fournit une variable DATABASE_URL
# 2. Remplacer la ligne ci-dessus par :
#    import os
#    DATABASE_URL = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)
# 3. pip install asyncpg
# 4. Les modèles SQLAlchemy ne changent pas.

engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables() -> None:
    """À appeler une fois au démarrage de l'app (voir lifespan dans main.py)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)
