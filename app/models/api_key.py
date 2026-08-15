from sqlalchemy import Column,Integer,String,Boolean,ForeignKey,DateTime,Date
from sqlalchemy.orm import relationship
from datetime import datetime,timezone,date

from app.db.session import Base 

class APIKey(Base):
    __tablename__="apikeys_v2"

    id=Column(Integer,primary_key=True,index=True)

    user_id=Column(Integer,ForeignKey("users.id"),nullable=False)

    key=Column(String,unique=True,nullable=False,index=True)

    name=Column(String,nullable=False)
    is_active=Column(Boolean,default=True)
    created_at=Column(DateTime,default=lambda:datetime.now(timezone.utc))
    daily_limit=Column(Integer,default=50)
    request_today=Column(Integer,default=0)

    last_request=Column(Date,default=date.today)

    owner=relationship("User",back_populates="api_keys")

