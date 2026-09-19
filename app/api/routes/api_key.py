from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import secrets
from app.db.session import get_db
from app.api.dependencies import get_current_user 
from app.models.api_key import APIKey
from app.core.security import fingerprint_secret
from app.schemas.api_key import APIKeyCreate, APIKeyCreatedResponse, APIKeyResponse
from datetime import date
from app.api.dependencies import verify_api_key
router=APIRouter()
@router.post("/",response_model=APIKeyCreatedResponse,status_code=status.HTTP_201_CREATED)
def crete_api_key(
    key_data:APIKeyCreate,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    raw_key="sk_live_" + secrets.token_urlsafe(32)

    try:
        new_api_key=APIKey(
            key=fingerprint_secret(raw_key),
            name=key_data.name,
            user_id=current_user.id
        )
        db.add(new_api_key)
        db.commit()
        db.refresh(new_api_key)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to create API key"
        )
        
    return {**APIKeyResponse.model_validate(new_api_key).model_dump(),"key":raw_key}
@router.get("/",response_model=list[APIKeyResponse])
def get_user_api(
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    keys=(
        db.query(APIKey)
        .filter(APIKey.user_id==current_user.id)
        .all()
    )
    return keys


@router.get("/premium-features")
@router.get("/user-ai_features", include_in_schema=False)
def user_premium_features(
    api_key_data:APIKey=Depends(verify_api_key),
    db:Session=Depends(get_db)
):
    try:
        api_key=db.query(APIKey).filter(APIKey.id==api_key_data.id).with_for_update().first()

        if api_key is None or not api_key. is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invali or apikey is Invalid"
            )
        today=date.today()
        if api_key.last_request!=today:
            api_key.request_today=0
            api_key.last_request=today
        if api_key.request_today >=api_key.daily_limit:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail='Daily key limit exceed'
            )
        api_key.request_today +=1
        db.commit()
        db.refresh(api_key)
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to process API key quota"
        )
    remaining_quota=(
        api_key.daily_limit -api_key.request_today
    )
    return{
        "message":"Success! API key is valid",
        "key_name":api_key.name,
        "request_used_today":api_key.request_today,
        "daily_limit":api_key.daily_limit,
        "remaining_quota":remaining_quota
    }







@router.delete("/{key_id}")
def revoke_api_key(
    key_id:int,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    db_api_key=db.query(APIKey).filter(APIKey.id==key_id,APIKey.user_id==current_user.id).first()

    if not db_api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="api key not found"
        )
    db_api_key.is_active=False
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to revoke API key right now"
        )
    return {"message":"key revoked"}
