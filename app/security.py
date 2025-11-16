"""Security helpers for password hashing and verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Tuple

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 480_000
_SALT_BYTES = 16


class InvalidPasswordFormat(ValueError):
    """Raised when a stored password hash cannot be parsed."""


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _build_hash(iterations: int, salt: bytes, dk: bytes) -> str:
    return f"{_ALGO}${iterations}${_encode(salt)}${_encode(dk)}"


def hash_password(plain: str, *, iterations: int = _ITERATIONS) -> str:
    """Hash ``plain`` using PBKDF2-HMAC-SHA256."""

    if not plain:
        raise ValueError("password must not be empty")
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return _build_hash(iterations, salt, dk)


def _legacy_hash(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def _parse_hash(value: str) -> Tuple[int, bytes, bytes]:
    algo, iter_str, salt_b64, hash_b64 = value.split("$")
    if algo != _ALGO:
        raise InvalidPasswordFormat(value)
    return int(iter_str), _decode(salt_b64), _decode(hash_b64)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True when ``plain`` matches the stored ``hashed`` value."""

    try:
        iterations, salt, digest = _parse_hash(hashed)
    except (ValueError, InvalidPasswordFormat):
        # Fallback for older SHA-256 hashes without metadata
        return hmac.compare_digest(_legacy_hash(plain), hashed)

    candidate = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(candidate, digest)


__all__ = ["hash_password", "verify_password", "InvalidPasswordFormat"]
