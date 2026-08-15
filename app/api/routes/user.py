from fastapi import APIRouter,Depends,HTTPException,status,BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.core.security import (
    hashed_password,
    verify_password,
    create_access_token,
    create_refresh_token
)
from app.schemas.token import RefreshTokenRequest

from app.api.dependencies import check_speed_limit,check_ownership
from app.models.blacklist import BlacklistedToken
from fastapi.security import OAuth2PasswordBearer
from app.utils.email import send_reset_link
from sqlalchemy import or_
import jwt 
from app.core.config import settings
from app.schemas.auth import(
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserUpdate,
    ChangePassword,
    ForgotPassword,
    ResetPassword,
)
from app.schemas.user import UserResponse
from fastapi.security import OAuth2PasswordRequestForm
import re
from app.db.redis_session import redis_client


from app.api.dependencies import get_current_user
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")

router=APIRouter()
def sanitize_input(text):
    if text:
        return re.sub(r'[<>&\]','',text)

    return text
@router.post("/signup",response_model=UserResponse,status_code=status.HTTP_201_CREATED)

def create_user(
    user_in:RegisterRequest,
    db:Session=Depends(get_db)
):
    existing_email=db.query(User).filter(User.email==user_in.email).first()

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid credentails"
        )

    existing_username=db.query(User).filter(User.username==user_in.username).first()

    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered plz try another username!"
        )
   
    try:
        secure_password=hashed_password(user_in.password)

        new_user=User(
            full_name=sanitize_input(user_in.full_name),
            username=sanitize_input(user_in.username),
            email=user_in.email,
            hashed_password=secure_password
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error:{str(e)}"
        )

@router.post("/login") 
def login(
    user_in:OAuth2PasswordRequestForm=Depends(),
    db:Session=Depends(get_db)
):
    login_input=user_in.username


    block_key=f"block_{login_input}"

    if redis_client.get(block_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked! try again after 15 minutes"
        )
    user=db.query(User).filter(
        or_(User.email==login_input,User.username==login_input)
    ).first()

    if not user or not verify_password(user_in.password,user.hashed_password):
        attempts_key=f"failed_login{login_input}"
        attempts=redis_client.incr(attempts_key)

        if attempts==1:
            redis_client.expire(attempts_key, 900)


        if attempts>=5:
            redis_client.setex(block_key,900, "locked")



            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="To many attempts.Account locked for 15 minutes"
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid Credentials.You have {5-attempts} attempts left"
        )
    redis_client.delete(f"failed_attempts_{login_input}")

    try:
        access_token=create_access_token(data={"sub":user.email})
        refresh_token=create_refresh_token(data={"sub":user.email})

        return {
            "access_token":access_token,
            "refresh_token":refresh_token,
            "token_type":"bearer"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating token"
        )

@router.get("/me",response_model=UserResponse)
def get_current_user(
    current_user:User=Depends(get_current_user)
):
    return current_user

@router.post("/me",response_model=UserResponse)

def update_profile(
    user_in:UserUpdate,
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    update_data=user_in.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(current_user,key,value)


    db.add(current_user)
    db.commit()
    db.refresh(current_user)
@router.delete("/me")
def delete_user(
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    db.delete(current_user)
    db.commit()

    return {"message":"user account successfully deleted"}

@router.post("/me/password")
def change_password(
    body:ChangePassword,
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    is_valid_password=verify_password(body.old_password,current_user.hashed_password)

    if not is_valid_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password"
        )

    try:
        new_secure_password=hashed_password(body.new_password)
        current_user.hashed_password=new_secure_password

        db.add(current_user)
        db.commit()
        return {"message":"Password updated successfull"}

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error:{str(e)}"
        )

@router.post("/forgot_password")
def forgot_password(
    body:ForgotPassword,
    background_tasks:BackgroundTasks,
    db:Session=Depends(get_db)
):
    user=db.query(User).filter(User.email==body.email).first()

    if not user:
        return {"message":"if this email is registered,you will receive a password reset token"}
    reset_token=create_access_token(
        data={"sub":user.email,
              "purpose":"reset_password"}
    )

    background_tasks.add_task(send_reset_link.email,reset_token)
    return {"message":"If this email is registered,you will recieve a passeword reset token"}



@router.post("/reset-password")
def reset_password(
    body:ResetPassword,
    db:Session=Depends(get_db)
):
    try:
        payload=jwt.decode(
            body.token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        if payload.get("purpose")!="reset_password":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detai="Invalid token purpose! please use reset password token"
            )

        email=payload.get("sub")

        user=db.query(User).filter(User.email==email).first()


        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        net_secure_password=hashed_password(body.new_password)
        user.hashed_password=net_secure_password


        db.add(user)

        db.commit()

        return{"message":"Password has been reset successfully"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Reset token has expired. Please request a new one."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid reset token."
        )
@router.post("/logout")
def logout(
    token:str=Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    already_blacklisted_token=db.query(BlacklistedToken).filter(BlacklistedToken.token==token).first()

    if already_blacklisted_token:
        return {"message":"Already logged out"}

    blacklisted_token=BlacklistedToken(token=token)

    db.add(blacklisted_token)
    db.commit()

    return {"message": "Successfully logged out. Token revoked."}


@router.post("/refresh")
def refresh_access_token(
    request:RefreshTokenRequest
):
    credential_expections=HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload=jwt.decode(
            request.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        user_id:str=payload.get("sub")
        token_type:str=payload.get("type")

        if user_id is None or token_type!="refresh":
            raise credential_expections



    except jwt.InvalidTokenError:
        raise credential_expections

    new_access_token=create_access_token(data={"sub":user_id})

    return {
        "access_token":new_access_token,
        "token_type":"bearer"
    }

@router.put("/{user_id}",response_model=UserResponse)
def update_any_user_profile(
    user_id:int,
    user_in:UserUpdate,
    db:Session=Depends(get_db),
    current_user:User=Depends(get_current_user)
):
    check_ownership(resource_user_id=user_id,current_user=current_user)
    user_to_update=db.query(User).filter(User.id==user_id).first()

    if not user_to_update:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not Found "
        )

    update_data=user_in.model_dump(exclude_unset=True)

    for key ,value in update_data.items():
        setattr(user_to_update,key,value)

    db.add(user_to_update)
    db.commit()
    db.refresh(user_to_update)
    return user_to_update



    