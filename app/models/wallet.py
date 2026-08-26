from sqlalchemy import Column,Integer,Column,String,Boolean,ForeignKey,DateTime,Float
from sqlalchemy.orm import relationship
from datetime import datetime,timezone

from db.session import Base


class Wallet(Base):
  __tablename__="wallet"

  id=Column(Integer,primary_key=True,index=True)
  user_id=Column(Integer,ForeignKey("users.id"),nullable=False)
  balance=Column(Float,default=0)
  is_active=Column(Boolean,default=True)
  owner=relationship("User",back_populates="Wallet")
  transaction=relationship("Transaction",back_populates="Wallet")


class Transaction(Base):
  __tablename__="transaction"
  id=Column(Integer,primary_key=True,index=True)
  wallet_id=Column(Integer,ForeignKey("Wallets.id", ondelete="CASCADE"),nullable=False)
  amount=Column(Float,nullable=False)
  transaction=Column(String,nullable=False)
  status=Column(String,default="COMPLETED")
  reference_id=Column(String,unique=True,index=True)
  transaction_date=Column(DateTime,default=lambda:datetime.now(timezone.utc))

  wallet=relationship("Wallet",back_populates="transactions")
  





