from sqlalchemy import Column,Integer,String,DateTime,ForeignKey,Boolean
from datetime import timezone,datetime
from app.db.session import Base
from sqlalchemy.orm import relationship

class RefreshToken(Base):
    __tablename__="refresh_tokens"

    id=Column(Integer,primary_key=True,index=True)
    user_id=Column(Integer,ForeignKey("users.id",ondelete="CASCADE"),nullable=False,index=True)
    token_hash=Column(String,nullable=False,unique=True,index=True)
    expires_at=Column(DateTime(timezone=True),nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
    user = relationship(
    "User",
    back_populates="refresh_tokens"
)

