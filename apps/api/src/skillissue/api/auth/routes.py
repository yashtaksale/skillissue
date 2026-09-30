"""Authentication API routes with in-memory user store (MongoDB-compatible)."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from passlib.context import CryptContext

from skillissue.api.auth.models import (
    UserCreate,
    UserUpdate,
    UserOut,
    Token,
    LoginRequest,
    RefreshTokenRequest,
    APIKeyResponse,
)
from skillissue.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_settings = get_settings()


# ── In-memory user store ─────────────────────────────────────────────────

class _UserDoc:
    """Internal user representation."""
    __slots__ = (
        "id", "email", "username", "hashed_password",
        "is_active", "is_superuser", "created_at", "updated_at",
        "last_login", "api_keys",
    )

    def __init__(self, id: str, email: str, username: str, hashed_password: str) -> None:
        self.id = id
        self.email = email
        self.username = username
        self.hashed_password = hashed_password
        self.is_active = True
        self.is_superuser = False
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.last_login: datetime | None = None
        self.api_keys: list[str] = []


_users_by_username: dict[str, _UserDoc] = {}
_users_by_email: dict[str, _UserDoc] = {}


def _find_by_username(username: str) -> _UserDoc | None:
    return _users_by_username.get(username)


def _find_by_email(email: str) -> _UserDoc | None:
    return _users_by_email.get(email)


def _find_by_id(user_id: str) -> _UserDoc | None:
    for doc in _users_by_username.values():
        if doc.id == user_id:
            return doc
    return None


# ── Auth helpers ─────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return pwd_context.hash(password)


def _verify(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _generate_api_key() -> str:
    return f"sk_{secrets.token_urlsafe(32)}"


def _make_access_token(user: _UserDoc) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=_settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user.id, "username": user.username, "exp": expire, "type": "access"},
        _settings.jwt_secret,
        algorithm=_settings.jwt_algorithm,
    )


def _make_refresh_token(user: _UserDoc) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    return jwt.encode(
        {"sub": user.id, "username": user.username, "exp": expire, "type": "refresh"},
        _settings.jwt_secret,
        algorithm=_settings.jwt_algorithm,
    )


def _decode_token(token: str, token_type: str) -> dict | None:
    try:
        payload = jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])
        if payload.get("type") != token_type:
            return None
        return payload
    except jwt.JWTError:
        return None


def _to_out(user: _UserDoc) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        last_login=user.last_login,
    )


# ── Auth Dependencies ─────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserOut:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_token(credentials.credentials, "access")
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _find_by_id(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _to_out(user)


async def get_current_user_unified(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: str = Header(None, alias="X-API-Key"),
) -> UserOut:
    # Try API key first
    if x_api_key:
        for doc in _users_by_username.values():
            if x_api_key in doc.api_keys and doc.is_active:
                return _to_out(doc)
    # Try JWT
    if credentials:
        payload = _decode_token(credentials.credentials, "access")
        if payload and payload.get("sub"):
            user = _find_by_id(payload["sub"])
            if user and user.is_active:
                return _to_out(user)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: str = Header(None, alias="X-API-Key"),
) -> str | None:
    """Extract user_id from authenticated user, or return None if no auth provided."""
    # Try API key first
    if x_api_key:
        for doc in _users_by_username.values():
            if x_api_key in doc.api_keys and doc.is_active:
                return doc.id
    # Try JWT
    if credentials:
        payload = _decode_token(credentials.credentials, "access")
        if payload and payload.get("sub"):
            user = _find_by_id(payload["sub"])
            if user and user.is_active:
                return user.id
    return None


# ── Public Routes ────────────────────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate):
    if _find_by_username(user_in.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if _find_by_email(user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = secrets.token_hex(12)
    doc = _UserDoc(
        id=user_id,
        email=user_in.email,
        username=user_in.username,
        hashed_password=_hash(user_in.password),
    )
    _users_by_username[user_in.username] = doc
    _users_by_email[user_in.email] = doc
    logger.info("user_registered", username=user_in.username, user_id=user_id)
    return _to_out(doc)


@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    user = _find_by_username(login_data.username)
    if not user:
        user = _find_by_email(login_data.username)
    if not user or not _verify(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")
    user.last_login = datetime.now(timezone.utc)
    access = _make_access_token(user)
    refresh = _make_refresh_token(user)
    return Token(access_token=access, expires_in=_settings.jwt_expire_minutes * 60)


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_data: RefreshTokenRequest):
    payload = _decode_token(refresh_data.refresh_token, "refresh")
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = _find_by_id(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return Token(access_token=_make_access_token(user), expires_in=_settings.jwt_expire_minutes * 60)


# ── Protected Routes ─────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def get_me(current_user: UserOut = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(update_data: UserUpdate, current_user: UserOut = Depends(get_current_user)):
    user = _find_by_id(current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if update_data.email and update_data.email != user.email:
        if _find_by_email(update_data.email):
            raise HTTPException(status_code=400, detail="Email already in use")
        _users_by_email.pop(user.email, None)
        user.email = update_data.email
        _users_by_email[user.email] = user
    if update_data.username and update_data.username != user.username:
        if _find_by_username(update_data.username):
            raise HTTPException(status_code=400, detail="Username already taken")
        _users_by_username.pop(user.username, None)
        user.username = update_data.username
        _users_by_username[user.username] = user
    user.updated_at = datetime.now(timezone.utc)
    return _to_out(user)


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key_route(name: str = "default", current_user: UserOut = Depends(get_current_user)):
    user = _find_by_id(current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    api_key = _generate_api_key()
    user.api_keys.append(api_key)
    return APIKeyResponse(api_key=api_key, name=name, created_at=datetime.now(timezone.utc))


@router.delete("/api-keys/{api_key}")
async def revoke_api_key_route(api_key: str, current_user: UserOut = Depends(get_current_user)):
    user = _find_by_id(current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        user.api_keys.remove(api_key)
        return {"detail": "API key revoked"}
    except ValueError:
        raise HTTPException(status_code=404, detail="API key not found")
