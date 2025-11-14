"""Security utilities such as MFA, encryption and signing helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Optional, Tuple

import pyotp
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Benutzer


class SecurityService:
    """Central security helper used across routers and services."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._fernet: Optional[Fernet] = None

    # ------------------------------------------------------------------
    # encryption helpers
    # ------------------------------------------------------------------
    def _derive_key(self) -> bytes:
        secret = settings.encryption_key or settings.secret_key
        if isinstance(secret, str):
            secret_bytes = secret.encode("utf-8")
        else:  # pragma: no cover - defensive
            secret_bytes = bytes(secret)
        digest = hashlib.sha256(secret_bytes).digest()
        return base64.urlsafe_b64encode(digest)

    def _get_fernet(self) -> Fernet:
        if not self._fernet:
            self._fernet = Fernet(self._derive_key())
        return self._fernet

    def encrypt_bytes(self, payload: bytes) -> bytes:
        return self._get_fernet().encrypt(payload)

    def decrypt_bytes(self, payload: bytes) -> bytes:
        return self._get_fernet().decrypt(payload)

    # ------------------------------------------------------------------
    # MFA helpers
    # ------------------------------------------------------------------
    @staticmethod
    def split_password_and_code(raw_password: str) -> Tuple[str, Optional[str]]:
        """Split "password::code" payloads used by the mobile client."""

        if "::" not in raw_password:
            return raw_password, None
        password, code = raw_password.rsplit("::", 1)
        return password, code

    @staticmethod
    def generate_mfa_secret() -> str:
        return pyotp.random_base32()

    def build_otpauth_url(self, username: str, secret: str) -> str:
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=username, issuer_name=settings.mfa_issuer)

    @staticmethod
    def verify_otp(secret: str, code: str) -> bool:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)

    def enable_mfa(self, user: Benutzer, secret: str, code: str) -> bool:
        if not self.verify_otp(secret, code):
            return False
        user.mfa_secret = secret
        user.mfa_enabled = True
        self.session.add(user)
        self.session.commit()
        return True

    def disable_mfa(self, user: Benutzer) -> None:
        user.mfa_secret = None
        user.mfa_enabled = False
        self.session.add(user)
        self.session.commit()

    # ------------------------------------------------------------------
    # signing helpers for blockchain/audit
    # ------------------------------------------------------------------
    @staticmethod
    def sign_payload(payload: str) -> str:
        secret = settings.blockchain_salt.encode("utf-8")
        return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def verify_signature(payload: str, signature: str) -> bool:
        expected = SecurityService.sign_payload(payload)
        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # key management
    # ------------------------------------------------------------------
    def ensure_user_keys(self, user: Benutzer) -> Benutzer:
        if user.public_key and user.encrypted_private_key:
            return user
        private_key = Fernet.generate_key()
        user.public_key = base64.urlsafe_b64encode(hashlib.sha256(private_key).digest()).decode("utf-8")
        user.encrypted_private_key = self.encrypt_bytes(private_key).decode("utf-8")
        self.session.add(user)
        self.session.commit()
        return user

    def get_private_key(self, user: Benutzer) -> bytes:
        if not user.encrypted_private_key:
            user = self.ensure_user_keys(user)
        encrypted = user.encrypted_private_key.encode("utf-8")
        return self.decrypt_bytes(encrypted)

