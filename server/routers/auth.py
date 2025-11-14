"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..auth import create_access_token, hash_password, verify_password
from ..database import get_session
from ..models import Benutzer
from ..schemas import BenutzerCreate, BenutzerRead, Token
from ..services.security import SecurityService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)) -> Token:
    user = session.query(Benutzer).filter(Benutzer.username == form_data.username).first()
    security = SecurityService(session)
    password, otp_code = security.split_password_and_code(form_data.password)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.mfa_enabled:
        if not otp_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA code required")
        if not user.mfa_secret or not SecurityService.verify_otp(user.mfa_secret, otp_code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
    security.ensure_user_keys(user)
    return create_access_token(user.username)


@router.post("/users", response_model=BenutzerRead, status_code=status.HTTP_201_CREATED)
def create_user(user: BenutzerCreate, session: Session = Depends(get_session)) -> Benutzer:
    if session.query(Benutzer).filter(Benutzer.username == user.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    db_user = Benutzer(
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        email=user.email,
        password_hash=hash_password(user.password),
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    SecurityService(session).ensure_user_keys(db_user)
    return db_user
