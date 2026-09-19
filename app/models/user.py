from sqlalchemy import Column, Integer, String, DateTime,Boolean

from sqlalchemy.sql import func
from app.db.session import Base

from sqlalchemy.orm import relationship
class User(Base):
    __tablename__="users"
    id=Column(Integer,primary_key=True,nullable=False)
    full_name=Column(String,nullable=False)

    username=Column(String,unique=True,nullable=False)

    email=Column(String,nullable=True,unique=True,index=True)
    hashed_password=Column(String,nullable=False)
    password_reset_version=Column(Integer,nullable=False,default=0,server_default="0")

    created_at=Column(DateTime(timezone=True),server_default=func.now())

    api_keys=relationship("APIKey", back_populates="owner", cascade="all, delete-orphan")

    role=Column(String,default="user")
    is_active=Column(Boolean,nullable=False,default=True,server_default="true")

    wallet = relationship(
        "Wallet",
        back_populates="owner",
        uselist=False,
        cascade="all, delete-orphan",
    )
    refresh_tokens = relationship(
    "RefreshToken",
    back_populates="user",
    cascade="all, delete-orphan"
)
