from pydantic import BaseModel,EmailStr
from datetime import datetime


class UserResponse(BaseModel):
    id:int
    full_name:str
    username:str
    email:EmailStr
    

    class Config:
        from_attributes=True