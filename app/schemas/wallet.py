from decimal import Decimal
from typing import Annotated
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


MoneyAmount = Annotated[
    Decimal,
    Field(gt=0, max_digits=18, decimal_places=2, description="Amount must be greater than zero"),
]


class DepositRequest(BaseModel):
    amount: MoneyAmount

class TransactionResponse(BaseModel):
    id:int
    amount:Decimal
    transaction_type:str
    status:str
    reference_id:str
    transaction_date:datetime

    model_config = ConfigDict(from_attributes=True)

class WalletResponse(BaseModel):
    id: int
    balance: Decimal
    is_active: bool
    transactions: list[TransactionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DepositResponse(BaseModel):
    message: str
    new_balance: Decimal
    reference_id: str



  
   
