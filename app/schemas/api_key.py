from pydantic import BaseModel
from datetime import datetime

class APIKeyCreate(BaseModel):
    name:str

class APIKeyResponse(BaseModel):
    id:int
    name:str
    key:str
    is_active:bool
    created_at:datetime
    request_today:int
    daily_limit:int


    class Config:
        from_attributes=True