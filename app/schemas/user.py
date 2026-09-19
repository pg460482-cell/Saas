from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime


class UserResponse(BaseModel):
    id:int
    full_name:str
    username:str
    email:EmailStr
    

    model_config = ConfigDict(from_attributes=True)
