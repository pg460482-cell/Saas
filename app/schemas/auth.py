from pydantic import BaseModel, EmailStr, Field
from pydantic.functional_validators import AfterValidator
import re
from typing import Annotated,Optional

def verify_password_rules(v: str) -> str:
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one number")
    # Yahan special characters ko safe tarike se handle kiya gaya hai
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
        raise ValueError("Password must contain at least one special character")
    
    return v

strong_password = Annotated[
    str,
    Field(min_length=8, max_length=64),
    AfterValidator(verify_password_rules) 
]

class RegisterRequest(BaseModel):
    full_name: str
    username: str
    email: EmailStr
    password: strong_password  # Yahan humne aapka strong_password type lagaya

class LoginRequest(BaseModel):
    email:EmailStr
    password:strong_password
class TokenResponse(BaseModel):
    access_token:str
    refresh_token:str
    token_type:str
class UserUpdate(BaseModel):
    full_name:Optional[str]=None
    username:Optional[str]=None

class ChangePassword(BaseModel):
    old_password:str
    new_password:strong_password
class ForgotPassword(BaseModel):
    email:EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password:strong_password
