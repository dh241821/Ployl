"""Security hardening endpoints for MFA and SSO."""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_session
from ..models import Benutzer
from ..schemas import (
    BenutzerRead,
    MFAEnableRequest,
    MFADisableRequest,
    MFASetupResponse,
    SSOCallbackRequest,
    SSOInitiateResponse,
)
from ..services.security import SecurityService

router = APIRouter(prefix="/api/security", tags=["security"])


@router.post("/mfa/setup", response_model=MFASetupResponse)
def mfa_setup(session: Session = Depends(get_session), user: Benutzer = Depends(get_current_user)) -> MFASetupResponse:
    service = SecurityService(session)
    secret = SecurityService.generate_mfa_secret()
    url = service.build_otpauth_url(user.username, secret)
    return MFASetupResponse(secret=secret, otpauth_url=url)


@router.post("/mfa/enable", response_model=BenutzerRead)
def mfa_enable(
    request: MFAEnableRequest,
    session: Session = Depends(get_session),
    user: Benutzer = Depends(get_current_user),
) -> BenutzerRead:
    service = SecurityService(session)
    if not service.enable_mfa(user, request.secret, request.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA verification failed")
    session.refresh(user)
    return BenutzerRead.from_orm(user)


@router.post("/mfa/disable", response_model=BenutzerRead)
def mfa_disable(
    request: MFADisableRequest,
    session: Session = Depends(get_session),
    user: Benutzer = Depends(get_current_user),
) -> BenutzerRead:
    if not user.mfa_secret or not SecurityService.verify_otp(user.mfa_secret, request.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")
    SecurityService(session).disable_mfa(user)
    session.refresh(user)
    return BenutzerRead.from_orm(user)


@router.get("/sso/initiate", response_model=SSOInitiateResponse)
def sso_initiate(_user: Benutzer = Depends(get_current_user)) -> SSOInitiateResponse:
    client_id = settings.sso_client_id or "demo-client"
    state = uuid4().hex
    authorization_url = f"https://sso.example.org/authorize?client_id={client_id}&response_type=code&state={state}"
    return SSOInitiateResponse(authorization_url=authorization_url)


@router.post("/sso/callback", response_model=BenutzerRead)
def sso_callback(
    request: SSOCallbackRequest,
    session: Session = Depends(get_session),
    user: Benutzer = Depends(get_current_user),
) -> BenutzerRead:
    user.sso_subject = f"{request.state}:{request.code}"
    session.add(user)
    session.commit()
    session.refresh(user)
    SecurityService(session).ensure_user_keys(user)
    return BenutzerRead.from_orm(user)

