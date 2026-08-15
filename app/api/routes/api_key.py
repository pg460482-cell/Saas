from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.orm import Session
import secrets
from app.db.session import get_db
from app.api.dependencies import get_current_user 
from app.models.api_key import APIKey
from app.schemas.api_key import APIKeyCreate, APIKeyResponse

from app.api.dependencies import verify_api_key
router=APIRouter()
@router.post("/",response_model=APIKeyResponse)
def create_api_key(
    key_data:APIKeyCreate,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    raw_key="sk_live_" + secrets.token_urlsafe(32)

    new_api_key=APIKey(
        key=raw_key,
        name=key_data.name,
        user_id=current_user.id
    )
    db.add(new_api_key)
    db.commit()
    db.refresh(new_api_key)
    return new_api_key
@router.get("/",response_model=list[APIKeyResponse])
def get_user_api_key(
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    keys=db.query(APIKey).filter(APIKey.user_id==current_user.id).all()

    return keys


@router.get("/use-ai-feature")
def user_premium_features(api_key_data=Depends(verify_api_key)):
    return {
        "message":"Success! API KEY was a correct",
        "key_name":api_key_data.name,
        "request_used_today":api_key_data.request_today,
        "daily_limit":api_key_data.daily_limit,
        "remaining_quota":api_key_data.daily_limit -api_key_data.request_today
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

    db.commit()

    return {"message":"key revoked!"}
   

