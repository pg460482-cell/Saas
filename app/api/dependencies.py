from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from datetime import datetime, timezone

from app.db.redis_session import redis_client
import jwt
from app.db.session import get_db
from app.models.user import User
from app.core.config import settings
from sqlalchemy.orm import Session
from app.models.blacklist import BlacklistedToken
from app.models.api_key import APIKey

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")
api_key_header_scheme = APIKeyHeader(name="x-api-key", auto_error=False)


def get_current_user(
        token:str=Depends(oauth2_scheme),
        db:Session=Depends(get_db)
):
    is_blacklisted=db.query(BlacklistedToken).filter(BlacklistedToken.token==token).first()


    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This token has been revoked.Please log in again",
            headers={"WWW-Authenticate":"Bearer"}
        )
    credentials_expection=HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could not validate credentails",
        headers={"WWW-Authenticate":"Bearer"}
    )

    try:
        paylaod=jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        email=paylaod.get("sub")

        if email is None:
            raise credentials_expection
        
    except jwt.PyJWTError:
        raise credentials_expection

    user=db.query(User).filter(User.email==email).first()

    if not user:
        raise credentials_expection

    return user


        

class RoleChecker:
    def __init__(self,allowed_roles:list):
        self.allowed_roles=allowed_roles

    def __call__(self, user:User=Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )

        return user


    
def verify_api_key(
        api_key_from_header:str=Security(api_key_header_scheme),
        db:Session=Depends(get_db)
):
    if not api_key_from_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key is headers (x-api-key)"
        )

    check_speed_limit(f"rate_limit_api_{api_key_from_header}",max_request=5,window_second=60)

    db_api_key=db.query(APIKey).filter(APIKey.key==api_key_from_header).first()

    if not db_api_key or not db_api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key"
        )

    today_date=datetime.now(timezone.utc).date()

    if db_api_key.last_request_date <today_date:
        db_api_key.request_today=0
        db_api_key.last_request_date=today_date

    if db_api_key.request_today >= db_api_key.daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily quota exceeded"
        )
    db_api_key.request_today+=1
    db.commit()
    return db_api_key

def check_speed_limit(
        unique_key:str,
        max_request:int,
        window_second:int
):
    current_request=redis_client.incr(unique_key)

    if current_request==1:
        redis_client.expire(unique_key,window_second)

    if current_request > max_request:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Slow down! Max {max_request} request allowed in {window_second} second"
        )
def check_ownership(resource_user_id: int,current_user:User):
    if current_user.role in ["admin","superadmin"]:
        return True


    if current_user.id!=resource_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied!"
        )
    return True