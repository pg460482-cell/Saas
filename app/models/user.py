from sqlalchemy import Column, Integer, String, DateTime

from sqlalchemy.sql import func
from app.db.session import Base

from sqlalchemy.orm import relationship
class user(Base):
    __tablename__="users"
    id=Column(Integer,primary_key=True,nullable=False)
    full_name=Column(String,nullable=False)

    username=Column(String,unique=True,nullable=False)

    email=Column(String,nullable=True,unique=True,index=True)
    hashed_password=Column(String,nullable=False)

    created_at=Column(DateTime(timezone=True),server_default=func.now())

    api_key=relationship("APIKey",back_populates="owner")

    role=Column(String,default="user")
