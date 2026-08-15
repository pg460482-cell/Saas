from sqlalchemy import Column,Integer,String,DateTime
from datetime import timezone,datetime
from app.db.session import Base

class BlacklistedToken(Base):
    __tablename__="blacklisted_token"

    id=Column(Integer,primary_key=True,index=True)

    token=Column(String,unique=True,index=True,nullable=False)
    blacklisted_on = Column(DateTime, default=lambda: datetime.now(timezone.utc))

