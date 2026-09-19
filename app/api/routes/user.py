
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks,Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
import re
from datetime import timezone ,datetime,timedelta
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError

from app.db.session import get_db
from app.db.redis_session import redis_client
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.blacklist import BlacklistedToken
from app.models.wallet import Wallet

from app.core.security import (
    hashed_password,
    verify_password,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    fingerprint_secret,
)

from app.core.config import settings

from app.schemas.token import RefreshTokenRequest

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserUpdate,
    ChangePassword,
    ForgotPassword,
    ResetPassword,
)

from app.schemas.user import UserResponse

from app.api.dependencies import (
    get_current_user,
    check_ownership,
)

from app.utils.email import send_reset_link


router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/users/login"
)

_DUMMY_PASSWORD_HASH = hashed_password("not-a-real-password")

def sanitize_input(text):
    if text:
        return re.sub(r"[<>&\\]", "", text)

    return text


def _raise_login_lockout():
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Too many attempts. Account locked for 15 minutes",
    )


def record_failed_login(attempt_key: str, block_key: str) -> None:
    try:
        attempts = redis_client.incr(attempt_key)
        if attempts == 1:
            redis_client.expire(attempt_key, 900)
        if attempts >= 5:
            redis_client.setex(block_key, 900, "locked")
            _raise_login_lockout()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid credentials. You have {5 - attempts} attempts left",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        )
@router.post("/signup",response_model=UserResponse,status_code=status.HTTP_201_CREATED)
def create_user(
    user_in:RegisterRequest,
    db:Session=Depends(get_db)
):
    existing_email=(
        db.query(User).filter(User.email==user_in.email).first()
        
    )
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    existing_username=(
        db.query(User).filter(User.username==user_in.username).first()
    )
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken ! Please try another username"
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
        db.flush()
        db.add(Wallet(user_id=new_user.id))
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )


@router.post("/login",response_model=TokenResponse)
def login(
    request:Request,
    user_in:OAuth2PasswordRequestForm=Depends(),
    db:Session=Depends(get_db)
):
    login_input=user_in.username
    client_ip=request.client.host if request.client else "unknown"
    block_key=f"block_{login_input}:{client_ip}"
    attempt_key=f"failed_login_{login_input}:{client_ip}"

    try:
        if redis_client.get(block_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is locked! try again after 15 minutes"
            )
    except HTTPException:
        raise
    except RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        )
    user = (
    db.query(User)
    .filter(
        or_(
            User.email == login_input,
            User.username == login_input
        )
    )
    .first()
    )
    if not user:
        verify_password(user_in.password, _DUMMY_PASSWORD_HASH)
        record_failed_login(attempt_key, block_key)
    if not verify_password(user_in.password, user.hashed_password):
        record_failed_login(attempt_key, block_key)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    try:
        redis_client.delete(attempt_key)
    except RedisError:
        pass
    try:
        access_token=create_access_token(
            data={
                "sub":str(user.id),
                "type":"access"
            }
        
        )
        refresh_token=create_refresh_token(
            data={
                "sub":str(user.id),
                "type":"refresh"
            }
        )
        expires_at=datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        db_refresh_token=RefreshToken(
            user_id=user.id,
            token_hash=fingerprint_secret(refresh_token),
            expires_at=expires_at,
            revoked=False
        )
        db.add(db_refresh_token)
        db.commit()

        
        return {
            "access_token":access_token,
            "refresh_token":refresh_token,
            "token_type":"bearer"
        }
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating token"
        )
#

@router.get("/me",response_model=UserResponse)
def get_me(
    current_user:User=Depends(get_current_user)
):
    return  current_user


@router.patch("/me",response_model=UserResponse)
def update_profile(
    user_in:UserUpdate,
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    update_data=user_in.model_dump(exclude_unset=True)
    if not update_data:
        return current_user
    if "username" in update_data:
        existing_username=(
            db.query(User).filter(
                User.username==update_data["username"],
                User.id!=current_user.id
            )
            .first()
        )
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken! try another username!"
            )
       
        update_data["username"]=sanitize_input(
            update_data["username"]
        )
    if "email" in update_data:
        existing_email=(
            db.query(User)
            .filter(
                User.email==update_data["email"],
                User.id!=current_user.id
            )
            .first()
        )
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email alrady registered!"
            )
    if "full_name" in update_data:
        update_data["full_name"]=sanitize_input(
            update_data["full_name"]
        )
    try:
        for key, value in update_data.items():
            setattr(current_user, key,value)
        db.commit()
        db.refresh(current_user)
        return current_user
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@router.delete("/me")
def delete_user(
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    try:
        db.delete(current_user)
        db.commit()
        return {
            "message":"User account successfull deleted"
        }
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deleted account"
        )
@router.post("/me/password")
def change_password(
    body:ChangePassword,
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    if not verify_password(
        body.old_password,
        current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password"
        )
    
    if verify_password(
        body.new_password,
        current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password was not to easy plz try create new password"
        )
    try:
        current_user.hashed_password=hashed_password(
            body.new_password
        )
        current_user.password_reset_version += 1
        db.query(RefreshToken).filter(
            RefreshToken.user_id==current_user.id,
            RefreshToken.revoked.is_(False)
        ).update(
            {"revoked":True},
            synchronize_session=False
        )
        db.commit()
        db.refresh(current_user)
        return{
            "message":"Password updated successfully"
        }
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )


@router.post("/forgot_password")
def forgor_password(
    body:ForgotPassword,
    background_tasks:BackgroundTasks,
    db:Session=Depends(get_db)
):
    user=(
        db.query(User)
        .filter(User.email==body.email)
        .first()
    )
    if not user:
        return{
            "message":"If this email is registered, tou will receive a password reset link"
        }
    reset_token=create_password_reset_token(user.email,user.password_reset_version)
    background_tasks.add_task(
        send_reset_link,
        user.email,
        reset_token
    )
    return{
        "message":"If this email is registered,tou will receive a password reset link"
    }
@router.post("/reset-password")
def reset_password(
    body: ResetPassword,
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(
            body.token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        if (
            payload.get("purpose") != "reset_password"
            or payload.get("type") != "password_reset"
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )

        email = payload.get("sub")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )

        token_version = payload.get("reset_version")

        if token_version is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )

        user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )

        if token_version != user.password_reset_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has already been used"
            )

        user.hashed_password = hashed_password(
            body.new_password
        )

        # Invalidate this reset token
        user.password_reset_version += 1

        # Revoke all active refresh tokens
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked.is_(False)
        ).update(
            {"revoked": True},
            synchronize_session=False
        )

        db.commit()

        return {
            "message": "Password has been reset successfully"
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )
    
@router.post("/logout")
def logout(
    token:str=Depends(oauth2_scheme),
    db:Session=Depends(get_db),
    current_user:User=Depends(get_current_user),
):
    token_fingerprint=fingerprint_secret(token)
    already_blacklisted_token=(
        db.query(BlacklistedToken)
        .filter(
            BlacklistedToken.token.in_((token_fingerprint, token))
        )
        .first()
    )
    try:
        if already_blacklisted_token is None:
            db.add(BlacklistedToken(token=token_fingerprint))
        db.query(RefreshToken).filter(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked.is_(False),
        ).update(
            {"revoked": True},
            synchronize_session=False,
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout",
        )
    return {
        "message": "Successfully logged out.token revoked"
        if already_blacklisted_token is None
        else "Already logged out"
    }
@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

    try:
        # 1. Refresh token ko decode karo
        payload = jwt.decode(
            request.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        # 2. Token ka type check karo
        if payload.get("type") != "refresh":
            raise credential_exception

        # 3. User ID nikalo
        user_id = payload.get("sub")

        if not user_id:
            raise credential_exception

        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            raise credential_exception

        # 4. Refresh token ka fingerprint banao
        token_fingerprint = fingerprint_secret(
            request.refresh_token
        )

        # 5. DB mein refresh token find karo
        # with_for_update() concurrent refresh ko control karega
        db_refresh_token = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_fingerprint,
                RefreshToken.user_id == user_id
            )
            .with_for_update()
            .first()
        )

        # 6. Token DB mein nahi mila
        if not db_refresh_token:
            raise credential_exception

        # 7. Already revoked token = reuse detected
        if db_refresh_token.revoked:

            (
                db.query(RefreshToken)
                .filter(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked.is_(False)
                )
                .update(
                    {"revoked": True},
                    synchronize_session=False
                )
            )

            db.commit()

            raise credential_exception

        # 8. DB expiry check
        if db_refresh_token.expires_at <= datetime.now(timezone.utc):
            raise credential_exception

        # 9. User exist karta hai ya nahi
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if not user:
            raise credential_exception
        if not user.is_active:
           raise credential_exception

        # 10. OLD refresh token ko revoke karo
        db_refresh_token.revoked = True

        # 11. NEW access token
        new_access_token = create_access_token(
            data={
                "sub": str(user.id),
                "type": "access"
            }
        )

        # 12. NEW refresh token
        new_refresh_token = create_refresh_token(
            data={
                "sub": str(user.id),
                "type": "refresh"
            }
        )

        # 13. New refresh token ki expiry
        new_expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
        )

        # 14. New refresh token DB mein store karo
        new_db_refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=fingerprint_secret(
                new_refresh_token
            ),
            expires_at=new_expires_at,
            revoked=False
        )

        db.add(new_db_refresh_token)

        # 15. OLD revoke + NEW token insert
        # ek transaction mein
        db.commit()

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }

    except jwt.ExpiredSignatureError:
        db.rollback()
        raise credential_exception

    except jwt.InvalidTokenError:
        db.rollback()
        raise credential_exception

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error refreshing token"
        )
@router.put(
    "/{user_id}",
    response_model=UserResponse
)
def update_any_user_profile(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check ownership
    check_ownership(
        resource_user_id=user_id,
        current_user=current_user
    )

    # Find user
    user_to_update = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user_to_update:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    update_data = user_in.model_dump(
        exclude_unset=True
    )

    
    if "username" in update_data:

        existing_username = (
            db.query(User)
            .filter(
                User.username == update_data["username"],
                User.id != user_id
            )
            .first()
        )

        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken!"
            )

        update_data["username"] = sanitize_input(
            update_data["username"]
        )

    # Email uniqueness
    if "email" in update_data:

        existing_email = (
            db.query(User)
            .filter(
                User.email == update_data["email"],
                User.id != user_id
            )
            .first()
        )

        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered!"
            )

  
    if "full_name" in update_data:

        update_data["full_name"] = sanitize_input(
            update_data["full_name"]
        )

    try:

        for key, value in update_data.items():
            setattr(user_to_update, key, value)

        db.commit()
        db.refresh(user_to_update)

        return user_to_update

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )
