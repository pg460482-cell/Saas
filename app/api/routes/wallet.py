import uuid
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.wallet import Wallet, Transaction
from app.schemas.wallet import DepositRequest, DepositResponse, WalletResponse, TransactionResponse
from app.api.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/wallet", tags=["Wallet"])
logger = logging.getLogger(__name__)


def _get_locked_wallet(db: Session, user_id: int) -> Wallet:
    wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == user_id)
        .with_for_update()
        .first()
    )
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )
    if not wallet.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wallet is inactive",
        )
    return wallet


@router.get("/", response_model=WalletResponse)
def get_my_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = (
        db.query(Wallet)
        .options(joinedload(Wallet.transactions))
        .filter(Wallet.user_id == current_user.id)
        .unique()
        .first()
    )
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )
    return wallet


@router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )
    return (
        db.query(Transaction)
        .filter(Transaction.wallet_id == wallet.id)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )


def _apply_balance_change(
    db: Session,
    wallet: Wallet,
    amount: Decimal,
    transaction_type: str,
    success_message: str,
) -> dict:
    try:
        wallet.balance = wallet.balance + amount
        new_transaction = Transaction(
            wallet_id=wallet.id,
            amount=abs(amount),
            transaction_type=transaction_type,
            status="COMPLETED",
            reference_id=str(uuid.uuid4()),
        )
        db.add(new_transaction)
        db.commit()
        db.refresh(wallet)
        return {
            "message": success_message,
            "new_balance": wallet.balance,
            "reference_id": new_transaction.reference_id,
        }
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Unable to process wallet transaction")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Wallet service is temporarily unavailable",
        )


@router.post("/deposit", response_model=DepositResponse)
@router.post("/deposite", response_model=DepositResponse, include_in_schema=False)
def deposit_money(
    request: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = _get_locked_wallet(db, current_user.id)
    return _apply_balance_change(
        db,
        wallet,
        request.amount,
        "DEPOSIT",
        "Money deposited successfully",
    )


@router.post("/withdraw", response_model=DepositResponse)
def withdraw_money(
    request: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = _get_locked_wallet(db, current_user.id)
    if wallet.balance < request.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance",
        )
    return _apply_balance_change(
        db,
        wallet,
        -request.amount,
        "WITHDRAWAL",
        "Money withdrawn successfully",
    )
