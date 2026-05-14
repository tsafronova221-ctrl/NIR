from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .crud import get_user
from .database import get_session
from .models import User

settings = get_settings()
http_bearer = HTTPBearer(auto_error=False)


class TokenError(HTTPException):
    def __init__(self, detail: str = "Недействительный токен."):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class BotTokenError(HTTPException):
    def __init__(self, detail: str = "Недействительный токен бота."):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def create_access_token(*, user_id: int, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or settings.access_token_expire_timedelta
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Срок действия токена истёк.") from exc
    except jwt.PyJWTError as exc:
        raise TokenError() from exc
    return payload


def resolve_user_from_token(token: str, db: Session) -> User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise TokenError()

    user = get_user(db, int(user_id))
    if user is None:
        raise TokenError("Пользователь не найден.")

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_session),
) -> User:
    if not credentials or not credentials.credentials:
        raise TokenError("Отсутствует токен авторизации.")

    return resolve_user_from_token(credentials.credentials, db)


def verify_bot_token(token: str | None) -> None:
    if not token:
        raise BotTokenError("Требуется токен бота.")

    try:
        payload = jwt.decode(
            token,
            settings.BOT_JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError as exc:
        raise BotTokenError() from exc

    if payload.get("bot") is not True:
        raise BotTokenError()
