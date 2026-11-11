"""Accounts and sessions.

* Passwords: Argon2id via ``argon2-cffi`` (library defaults, rehash on parameter change).
* Sessions: 256-bit random opaque token in an HttpOnly cookie; only its SHA-256 is
  stored, so a database leak does not yield usable session tokens.
* CSRF: per-session random token, sent to the browser in a readable cookie and
  required back in the ``X-CSRF-Token`` header on state-changing requests.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.core.errors import AppError, ValidationFailed
from app.db import models as m
from app.db.repositories import SessionRepository, UserRepository


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


_hasher = PasswordHasher()
# Verified against when the email is unknown, so response time doesn't reveal account existence.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def validate_registration(email: str, password: str, display_name: str | None) -> tuple[str, str | None]:
    errors = []
    email_n = email.strip().lower()
    if len(email_n) > 254 or not _EMAIL.match(email_n):
        errors.append({"field": "email", "message": "Enter a valid email address."})
    if len(password) < 10:
        errors.append({"field": "password", "message": "Use at least 10 characters."})
    elif len(password) > 128:
        errors.append({"field": "password", "message": "Use at most 128 characters."})
    elif password.strip().lower() == email_n:
        errors.append({"field": "password", "message": "Password must not be your email."})
    name = display_name.strip() if display_name else None
    if name and len(name) > 80:
        errors.append({"field": "display_name", "message": "Use at most 80 characters."})
    if errors:
        raise ValidationFailed("Please correct the highlighted fields.", details=errors)
    return email_n, name or None


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    csrf_token: str
    expires_at: datetime


class AuthService:
    def __init__(self, ttl: timedelta) -> None:
        self.ttl = ttl

    def register(self, db: DbSession, email: str, password: str, display_name: str | None) -> m.User:
        email_n, name = validate_registration(email, password, display_name)
        users = UserRepository(db)
        if users.get_by_email(email_n):
            raise Conflict(
                "An account with this email already exists.",
                details=[{"field": "email", "message": "Already registered."}],
            )
        try:
            return users.create(email_n, _hasher.hash(password), name)
        except IntegrityError:  # concurrent registration race
            raise Conflict("An account with this email already exists.") from None

    def authenticate(self, db: DbSession, email: str, password: str, now: datetime) -> m.User:
        user = UserRepository(db).get_by_email(email) if len(email) <= 254 else None
        try:
            _hasher.verify(user.password_hash if user else _DUMMY_HASH, password[:256])
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            raise Unauthorized("Invalid email or password.") from None
        if user is None or not user.is_active:
            raise Unauthorized("Invalid email or password.")
        if _hasher.check_needs_rehash(user.password_hash):
            user.password_hash = _hasher.hash(password)
        user.last_login_at = now
        return user

    def issue_session(self, db: DbSession, user: m.User, now: datetime) -> IssuedSession:
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = now + self.ttl
        SessionRepository(db).create(user.id, hash_token(token), csrf, now, expires)
        return IssuedSession(token, csrf, expires)

    def resolve(self, db: DbSession, token: str | None, now: datetime) -> m.Session | None:
        if not token or len(token) > 128:
            return None
        session = SessionRepository(db).get_active(hash_token(token), now)
        if session is None or not session.user.is_active:
            return None
        # Sliding activity timestamp (expiry stays absolute).
        if now - session.last_seen_at > timedelta(minutes=5):
            session.last_seen_at = now
        return session

    @staticmethod
    def check_csrf(session: m.Session, header_value: str | None) -> None:
        if not header_value or not secrets.compare_digest(session.csrf_token, header_value):
            raise Forbidden("Missing or invalid CSRF token. Reload the page and try again.")
