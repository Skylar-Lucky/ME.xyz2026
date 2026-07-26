"""Auth: password hashing, JWT, FastAPI dependency."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db import get_connection, init_db

load_dotenv()

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "dev-only-change-me-mexyz-please-use-env-in-production",
)
JWT_ALG = "HS256"
JWT_DAYS = 7

_bearer = HTTPBearer(auto_error=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        uid = payload.get("sub")
        if not uid:
            raise HTTPException(status_code=401, detail="invalid token")
        return str(uid)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="token expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="invalid token") from e


def create_user(email: str, password: str, nickname: str | None = None) -> dict[str, Any]:
    init_db()
    email = email.strip().lower()
    if not email or len(password) < 6:
        raise HTTPException(status_code=400, detail="email required and password min 6 chars")
    user_id = f"u_{uuid.uuid4().hex[:10]}"
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="email already registered")
        conn.execute(
            "INSERT INTO users (id, email, password_hash, nickname, created_at) VALUES (?,?,?,?,?)",
            (user_id, email, hash_password(password), nickname or email.split("@")[0], _now()),
        )
        conn.commit()
        return get_user_by_id(user_id)  # type: ignore
    finally:
        conn.close()


def authenticate_user(email: str, password: str) -> dict[str, Any]:
    init_db()
    email = email.strip().lower()
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="invalid email or password")
        return {
            "id": row["id"],
            "email": row["email"],
            "nickname": row["nickname"],
        }
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, nickname, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="not authenticated")
    user_id = decode_token(creds.credentials)
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return user
