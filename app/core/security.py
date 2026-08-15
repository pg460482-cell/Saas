from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from datetime import datetime,timedelta,timezone
from app.core.config import settings
import jwt
ph=PasswordHasher()
def hashed_password(password: str) ->str:
    return ph.hash(password)

def verify_password(password:str,hashed_password:str) -> bool:
    try:
        return ph.verify(hashed_password,password)

    except VerificationError:
        return False

def create_access_token(data: dict)->str:
    to_encode=data.copy()
    expire=datetime.now(timezone.utc) + timedelta(minutes=30)
    to_encode.update({"exp":expire})

    encode_jwt=jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM

    )
    return encode_jwt

def create_refresh_token(data:dict)-> str:
    to_encode=data.copy()

    expire=datetime.now(timezone.utc) +timedelta(days=7)

    to_encode.update({"exp":expire, "type":"refresh"})

    encode_jwt=jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encode_jwt



