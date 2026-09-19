from pydantic import BaseModel, ConfigDict
from datetime import datetime

class APIKeyCreate(BaseModel):
    name:str

class APIKeyResponse(BaseModel):
    id:int
    name:str
    is_active:bool
    created_at:datetime
    request_today:int
    daily_limit:int


    model_config = ConfigDict(from_attributes=True)


class APIKeyCreatedResponse(APIKeyResponse):
    
    key: str
