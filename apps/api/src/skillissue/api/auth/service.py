"""Authentication service: password hashing, JWT tokens, user management."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from skillissue.api.auth.models import (
    UserInDB,
    UserCreate,
    UserUpdate,
    UserOut,
    Token,
    TokenData,
    APIKeyResponse,
)
from skillissue.config import get_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        username = payload.get("username")
        if user_id is None:
            return None
        return TokenData(user_id=user_id, username=username)
    except jwt.JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            return None
        user_id = payload.get("sub")
        username = payload.get("username")
        if user_id is None:
            return None
        return TokenData(user_id=user_id, username=username)
    except jwt.JWTError:
        return None


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"sk_{secrets.token_urlsafe(32)}"


async def create_user(db: AsyncIOMotorDatabase, user_in: UserCreate) -> UserInDB:
    """Create a new user in MongoDB."""
    hashed_password = get_password_hash(user_in.password)
    user = UserInDB(
        email=user_in.email,
        username=user_in.username,
        hashed_password=hashed_password,
    )
    result = await db.users.insert_one(user.model_dump(by_alias=True, exclude={"id"}))
    user.id = result.inserted_id
    return user


async def get_user_by_username(db: AsyncIOMotorDatabase, username: str) -> Optional[UserInDB]:
    """Get user by username."""
    doc = await db.users.find_one({"username": username})
    if doc:
        return UserInDB(**doc)
    return None


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[UserInDB]:
    """Get user by email."""
    doc = await db.users.find_one({"email": email})
    if doc:
        return UserInDB(**doc)
    return None


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[UserInDB]:
    """Get user by ObjectId string."""
    from bson import ObjectId
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if doc:
        return UserInDB(**doc)
    return None


async def authenticate_user(db: AsyncIOMotorDatabase, username: str, password: str) -> Optional[UserInDB]:
    """Authenticate user with username/email and password."""
    user = await get_user_by_username(db, username)
    if not user:
        # Try email
        user = await get_user_by_email(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


async def update_user(db: AsyncIOMotorDatabase, user_id: str, update_data: UserUpdate) -> Optional[UserInDB]:
    """Update user fields."""
    from bson import ObjectId
    update_dict = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
    if not update_dict:
        return await get_user_by_id(db, user_id)
    update_dict["updated_at"] = datetime.now(timezone.utc)
    result = await db.users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict},
        return_document=True,
    )
    if result:
        return UserInDB(**result)
    return None


async def update_last_login(db: AsyncIOMotorDatabase, user_id: str) -> None:
    """Update user's last login timestamp."""
    from bson import ObjectId
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"last_login": datetime.now(timezone.utc)}},
    )


async def create_user_token(user: UserInDB) -> Token:
    """Create access token for user."""
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )
    return Token(
        access_token=access_token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


async def create_user_refresh_token(user: UserInDB) -> str:
    """Create refresh token for user."""
    return create_refresh_token(data={"sub": str(user.id), "username": user.username})


async def create_api_key(db: AsyncIOMotorDatabase, user_id: str, name: str = "default") -> APIKeyResponse:
    """Create a new API key for user."""
    from bson import ObjectId
    api_key = generate_api_key()
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"api_keys": api_key}},
    )
    return APIKeyResponse(
        api_key=api_key,
        name=name,
        created_at=datetime.now(timezone.utc),
    )


async def validate_api_key(db: AsyncIOMotorDatabase, api_key: str) -> Optional[UserInDB]:
    """Validate API key and return associated user."""
    doc = await db.users.find_one({"api_keys": api_key})
    if doc:
        return UserInDB(**doc)
    return None


async def revoke_api_key(db: AsyncIOMotorDatabase, user_id: str, api_key: str) -> bool:
    """Revoke an API key."""
    from bson import ObjectId
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$pull": {"api_keys": api_key}},
    )
    return result.modified_count > 0


def user_to_out(user: UserInDB) -> UserOut:
    """Convert UserInDB to UserOut."""
    return UserOut(
        id=str(user.id),
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        last_login=user.last_login,
    )