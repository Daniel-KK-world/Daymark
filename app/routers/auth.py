from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import random
import os
import resend

from app.database import get_db
from app.models import User
from app.schemas import (
    UserCreate, UserLogin, OTPVerify, OTPRequest,
    PasswordResetRequest, PasswordResetConfirm, PasswordChange,
    UserResponse, LoginResponse
)
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# ─── Resend Setup ──────────────────────────
resend.api_key = settings.resend_api_key

# ─── Helpers ──────────────────────────────
def generate_otp(length: int = 6) -> str:
    return ''.join(random.choices('0123456789', k=length))

def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)

def send_otp_email(email: str, otp_code: str, purpose: str = "verification"):
    subject = f"Your {purpose} code"
    html = f"""
        <h2>{purpose.capitalize()} Code</h2>
        <p>Your OTP is: <strong>{otp_code}</strong></p>
        <p>It expires in 10 minutes.</p>
    """
    try:
        resend.Emails.send({
            "from": "noreply@kensvic.com",
            "to": email,
            "subject": subject,
            "html": html
        })
        print(f"✅ OTP sent to {email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def send_reset_email(email: str, reset_link: str):
    html = f"""
        <h2>Reset Your Password</h2>
        <p>Click <a href="{reset_link}">here</a> to reset your password.</p>
        <p>This link expires in 15 minutes.</p>
    """
    try:
        resend.Emails.send({
            "from": "noreply@kensvic.com",
            "to": email,
            "subject": "Password Reset Request",
            "html": html
        })
        print(f"✅ Reset link sent to {email}")
    except Exception as e:
        print(f"❌ Failed to send reset email: {e}")

# ═══════════════════════════════════════════
# 1. REGISTER
# ═══════════════════════════════════════════
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.email == user.email).first()

    if existing:
        if not existing.is_verified:
            otp = generate_otp()
            existing.otp_code = otp
            existing.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
            existing.password_hash = get_password_hash(user.password)
            db.commit()
            background_tasks.add_task(send_otp_email, existing.email, otp, "verification")
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Account exists but unverified. New OTP sent."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered."
            )

    otp = generate_otp()
    new_user = User(
        email=user.email,
        password_hash=get_password_hash(user.password),
        is_verified=False,
        otp_code=otp,
        otp_expires_at=datetime.utcnow() + timedelta(minutes=10),
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    background_tasks.add_task(send_otp_email, new_user.email, otp, "verification")
    return new_user

# ═══════════════════════════════════════════
# 2. VERIFY OTP
# ═══════════════════════════════════════════
@router.post("/verify-otp", status_code=status.HTTP_200_OK)
def verify_otp(payload: OTPVerify, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        return {"message": "Account already verified", "verified": True}
    if user.otp_code != payload.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if user.otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired. Request a new one.")

    user.is_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()
    return {"message": "Email verified successfully!", "verified": True}

# ═══════════════════════════════════════════
# 3. RESEND OTP
# ═══════════════════════════════════════════
@router.post("/resend-otp", status_code=status.HTTP_200_OK)
def resend_otp(
    payload: OTPRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Account already verified")

    otp = generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    background_tasks.add_task(send_otp_email, user.email, otp, "verification")
    return {"message": "New OTP sent to your email"}

# ═══════════════════════════════════════════
# 4. LOGIN
# ═══════════════════════════════════════════
@router.post("/login", response_model=LoginResponse)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_credentials.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Check lockout
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() // 60)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked. Try again in {remaining} minutes"
        )

    # Verify password
    if not verify_password(user_credentials.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Too many failed attempts. Account locked for 15 minutes"
            )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated"
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    db.commit()

    access_token = create_access_token(data={"user_id": str(user.id)})

    # ✅ FIXED: Convert SQLAlchemy model to dict
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": str(user.id),
            "email": user.email,
            "is_verified": user.is_verified,
            "is_active": user.is_active,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }
    )

# ═══════════════════════════════════════════
# 5. FORGOT PASSWORD
# ═══════════════════════════════════════════
@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        token = generate_reset_token()
        user.reset_password_token = token
        user.reset_password_expires_at = datetime.utcnow() + timedelta(minutes=15)
        db.commit()
        reset_link = f"{settings.frontend_url}/reset-password?token={token}"
        background_tasks.add_task(send_reset_email, user.email, reset_link)
    return {"message": "If your email is registered, you will receive a password reset link"}

# ═══════════════════════════════════════════
# 6. RESET PASSWORD
# ═══════════════════════════════════════════
@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_password_token == payload.token).first()
    if not user or user.reset_password_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    user.password_hash = get_password_hash(payload.new_password)
    user.reset_password_token = None
    user.reset_password_expires_at = None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return {"message": "Password reset successful. You can now log in."}

# ═══════════════════════════════════════════
# 7. CHANGE PASSWORD
# ═══════════════════════════════════════════
@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    current_user.password_hash = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}

# ═══════════════════════════════════════════
# 8. GET ME
# ═══════════════════════════════════════════
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# ═══════════════════════════════════════════
# 9. DEACTIVATE ACCOUNT
# ═══════════════════════════════════════════
@router.delete("/me", status_code=status.HTTP_200_OK)
def deactivate_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.is_active = False
    db.commit()
    return {"message": "Account deactivated successfully"}