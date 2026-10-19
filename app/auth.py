from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jwt

from app.config import Settings
from app.errors import UnauthorizedError


def create_access_token(
    patient_id: int,
    email: str,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    payload: dict[str, Any] = {
        "sub": str(patient_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return cast(dict[str, Any], payload)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("TOKEN_EXPIRED", "Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(
            "INVALID_TOKEN", "Could not validate authentication credentials"
        ) from exc
