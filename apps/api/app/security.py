import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

_bearer = HTTPBearer(auto_error=False)


def get_current_owner(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    settings = get_settings()
    if not settings.private_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private document access is not configured",
        )
    if credentials is None or not secrets.compare_digest(
        credentials.credentials,
        settings.private_api_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid bearer authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return settings.private_owner_id
