from fastapi_users.db import SQLAlchemyUserDatabase
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.database import async_session_maker
from app.models.user import User
from app.users import UserManager, cookie_transport, get_jwt_strategy


class CurrentUserMiddleware(BaseHTTPMiddleware):
    """Pose request.state.user (User actif ou None) sur chaque requête, pour que
    les templates (base.html) puissent afficher l'état de connexion sans que
    chaque route ait à déclarer une dépendance current_active_user_optional.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user = await self._get_user(request)
        return await call_next(request)

    @staticmethod
    async def _get_user(request: Request) -> User | None:
        token = request.cookies.get(cookie_transport.cookie_name)
        if token is None:
            return None

        async with async_session_maker() as session:
            user_manager = UserManager(SQLAlchemyUserDatabase(session, User))
            user = await get_jwt_strategy().read_token(token, user_manager)

        return user if user and user.is_active else None
