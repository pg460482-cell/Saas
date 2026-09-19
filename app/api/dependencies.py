import logging
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import fingerprint_secret
from app.db.redis_session import redis_client
from app.db.session import get_db
from app.models.api_key import APIKey
from app.models.blacklist import BlacklistedToken
from app.models.user import User


logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")

api_key_header_scheme = APIKeyHeader(name="x-api-key", auto_error=False)

bearer_scheme = HTTPBearer()


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        user_id = payload.get("sub")
        token_type = payload.get("type")
        purpose = payload.get("purpose")

        if not user_id or token_type != "access" or purpose is not None:
            raise credentials_exception

        user_id = int(user_id)

    except (jwt.PyJWTError, ValueError, TypeError):
        raise credentials_exception

    try:
        token_fingerprint = fingerprint_secret(token)

        is_blacklisted = (
            db.query(BlacklistedToken)
            .filter(BlacklistedToken.token == token_fingerprint)
            .first()
        )

    except SQLAlchemyError:
        logger.exception("Unable to check token revocation status")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        )

    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user
