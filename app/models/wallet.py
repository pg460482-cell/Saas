from decimal import Decimal
from sqlalchemy import(
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String
)
from sqlalchemy.orm import relationship
from datetime import datetime,timezone
from app.db.session import Base

class Wallet(Base):
    __tablename__="wallets"
    id=Column(Integer,primary_key=True,index=True)
    user_id=Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    balance=Column(Numeric(18 , 2),nullable=False,default=Decimal("0.00"))
    is_active=Column(Boolean,default=True)
    owner=relationship("User", back_populates="wallet")
    transactions=relationship(
        "Transaction",
        back_populates="wallet",
        cascade="all, delete-orphan",
    )
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
    )

class Transaction(Base):
    __tablename__="transactions"
    id=Column(Integer,primary_key=True,index=True)
    wallet_id=Column(Integer,ForeignKey("wallets.id",ondelete="CASCADE"),nullable=False)
    amount=Column(Numeric(18,2),nullable=False)
    transaction_type=Column(String,nullable=False)
    status=Column(String,nullable=False,default="COMPLETED")
    reference_id=Column(String,unique=True,index=True,nullable=False)
    transaction_date=Column(DateTime,default=lambda:datetime.now(timezone.utc))
    wallet=relationship("Wallet", back_populates="transactions")
    __table_args__=(
        CheckConstraint("amount > 0",name="ck_transactions_amount_positive"),
    )
   
