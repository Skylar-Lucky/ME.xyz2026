"""Auth: password hashing, JWT, FastAPI dependency."""
from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import mailer
from db import get_connection, init_db

load_dotenv()

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "dev-only-change-me-mexyz-please-use-env-in-production",
)
JWT_ALG = "HS256"
JWT_DAYS = 7

CODE_TTL_MINUTES = 10
CODE_RESEND_COOLDOWN_SECONDS = 60
CODE_MAX_ATTEMPTS = 5

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


def create_user(
    email: str,
    password: str,
    nickname: str | None = None,
    email_verified: bool = False,
) -> dict[str, Any]:
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
            "INSERT INTO users (id, email, password_hash, nickname, email_verified, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                user_id,
                email,
                hash_password(password),
                nickname or email.split("@")[0],
                1 if email_verified else 0,
                _now(),
            ),
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


def _hash_code(email: str, code: str) -> str:
    return hashlib.sha256(f"{email}:{code}".encode("utf-8")).hexdigest()


def request_email_code(email: str, purpose: str = "register") -> int:
    """Generate + store a verification code, email it, and return the resend cooldown."""
    init_db()
    email = email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="请填写有效邮箱")

    conn = get_connection()
    try:
        if purpose == "register":
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="email already registered")

        last = conn.execute(
            "SELECT created_at FROM email_verification_codes "
            "WHERE email = ? AND purpose = ? ORDER BY created_at DESC LIMIT 1",
            (email, purpose),
        ).fetchone()
        if last:
            elapsed = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(last["created_at"])
            ).total_seconds()
            if elapsed < CODE_RESEND_COOLDOWN_SECONDS:
                raise HTTPException(
                    status_code=429,
                    detail=f"请求过于频繁，请 {int(CODE_RESEND_COOLDOWN_SECONDS - elapsed)} 秒后再试",
                )

        code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)
        ).isoformat()
        conn.execute(
            "INSERT INTO email_verification_codes "
            "(email, code_hash, purpose, attempts, expires_at, created_at) VALUES (?,?,?,0,?,?)",
            (email, _hash_code(email, code), purpose, expires_at, _now()),
        )
        conn.commit()
    finally:
        conn.close()

    mailer.send_verification_code(email, code, CODE_TTL_MINUTES)
    return CODE_RESEND_COOLDOWN_SECONDS


def verify_email_code(email: str, code: str, purpose: str = "register") -> None:
    """Raise HTTPException if the code is missing/expired/wrong; otherwise consume it."""
    init_db()
    email = email.strip().lower()
    code = code.strip()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM email_verification_codes "
            "WHERE email = ? AND purpose = ? AND consumed_at IS NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (email, purpose),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="请先获取验证码")
        if datetime.now(timezone.utc) > datetime.fromisoformat(row["expires_at"]):
            raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
        if row["attempts"] >= CODE_MAX_ATTEMPTS:
            raise HTTPException(status_code=400, detail="验证码错误次数过多，请重新获取")
        if row["code_hash"] != _hash_code(email, code):
            conn.execute(
                "UPDATE email_verification_codes SET attempts = attempts + 1 WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            raise HTTPException(status_code=400, detail="验证码不正确")
        conn.execute(
            "UPDATE email_verification_codes SET consumed_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
        conn.commit()
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


def update_nickname(user_id: str, nickname: str) -> dict[str, Any]:
    nickname = nickname.strip()
    if not nickname:
        raise HTTPException(status_code=400, detail="昵称不能为空")
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET nickname = ? WHERE id = ?", (nickname, user_id))
        conn.commit()
    finally:
        conn.close()
    return get_user_by_id(user_id)  # type: ignore


def change_password(user_id: str, old_password: str, new_password: str) -> None:
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    conn = get_connection()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row or not verify_password(old_password, row["password_hash"]):
            # 400, not 401 — the frontend's global api() helper treats any 401 as
            # "session expired" and force-logs-out; a wrong current password is a
            # validation error, not an auth failure.
            raise HTTPException(status_code=400, detail="当前密码不正确")
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_account(user_id: str, email_confirm: str) -> None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        if row["email"].strip().lower() != email_confirm.strip().lower():
            raise HTTPException(status_code=400, detail="邮箱确认不匹配")
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM personas WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM mindmap_nodes WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM mindmap_edges WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM events WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
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
