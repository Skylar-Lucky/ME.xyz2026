"""BYOK: user-managed model API keys — CRUD + dispatch to the right chat client.

Mirrors auth.py's shape (plain functions over db.get_connection(), raising
HTTPException for anything user-facing). call_with_fallback() is the one
function main.py / conversation.py / memory_agent.py call at each real LLM
call site to decide whether to use the platform's GLM client or the user's
own key, transparently falling back to GLM (with a user-facing notice) if
the user's key fails.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

import crypto_util
import llm_service
import providers
from db import get_connection, init_db

logger = logging.getLogger("mexyz.byok")

MAX_KEYS_PER_USER = 5
FAIL_COUNT_TO_INVALID = 3

_ERROR_COPY = {
    "invalid_key": "该Key无效或已过期，请重新获取",
    "rate_limited": "请求过于频繁，请稍后重试",
    "network": "暂时无法连接到该服务，请稍后重试",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_error_to_http(err: providers.ProviderError, display_name: str) -> HTTPException:
    if err.kind == "insufficient_balance":
        msg = f"该账号余额不足，请前往{display_name}充值后重试"
    elif err.kind == "unsupported":
        msg = str(err) or "当前接口不支持该模型，请检查配置"
    else:
        msg = _ERROR_COPY.get(err.kind, "连接测试失败，请检查配置")
    return HTTPException(status_code=400, detail=msg)


def _row_to_public(row) -> dict[str, Any]:
    cfg = providers.PROVIDERS.get(row["provider_key"], {})
    return {
        "id": row["id"],
        "provider_key": row["provider_key"],
        "provider_display_name": cfg.get("display_name", row["provider_key"]),
        "alias": row["alias"],
        "key_last4": row["key_last4"],
        "status": row["status"],
        "is_current": bool(row["is_current"]),
        "last_verified_at": row["last_verified_at"],
    }


def list_keys(user_id: str) -> list[dict[str, Any]]:
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM user_model_keys WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,),
        ).fetchall()
        return [_row_to_public(r) for r in rows]
    finally:
        conn.close()


def add_key(
    user_id: str,
    provider_key: str,
    api_key: str,
    alias: str | None,
    model_id: str | None,
) -> dict[str, Any]:
    if provider_key not in providers.PROVIDERS:
        raise HTTPException(status_code=400, detail="不支持的供应商")
    api_key = (api_key or "").strip()
    if len(api_key) < 8:
        raise HTTPException(status_code=400, detail="请检查Key格式是否正确")

    cfg = providers.PROVIDERS[provider_key]
    display_name = cfg["display_name"]

    init_db()
    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM user_model_keys WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        existing = conn.execute(
            "SELECT id FROM user_model_keys WHERE user_id = ? AND provider_key = ?",
            (user_id, provider_key),
        ).fetchone()
        if not existing and count >= MAX_KEYS_PER_USER:
            raise HTTPException(status_code=400, detail=f"最多只能接入 {MAX_KEYS_PER_USER} 个模型账号")

        try:
            providers.test_connection(provider_key, api_key, model_id)
        except providers.ProviderError as e:
            raise _provider_error_to_http(e, display_name) from e

        cipher = crypto_util.encrypt_secret(api_key)
        last4 = api_key[-4:]
        now = _now()

        if existing:
            key_id = existing["id"]
            conn.execute(
                "UPDATE user_model_keys SET alias=?, model_id=?, api_key_cipher=?, key_last4=?, "
                "status='active', fail_count=0, last_verified_at=?, updated_at=? WHERE id=?",
                (alias, model_id, cipher, last4, now, now, key_id),
            )
        else:
            key_id = f"mk_{uuid.uuid4().hex[:10]}"
            conn.execute(
                "INSERT INTO user_model_keys "
                "(id, user_id, provider_key, alias, model_id, api_key_cipher, key_last4, "
                "status, is_current, fail_count, last_verified_at, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,'active',0,0,?,?,?)",
                (key_id, user_id, provider_key, alias, model_id, cipher, last4, now, now, now),
            )
            has_current = conn.execute(
                "SELECT COUNT(*) AS n FROM user_model_keys WHERE user_id = ? AND is_current = 1",
                (user_id,),
            ).fetchone()["n"]
            if has_current == 0:
                conn.execute("UPDATE user_model_keys SET is_current = 1 WHERE id = ?", (key_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM user_model_keys WHERE id = ?", (key_id,)).fetchone()
        return _row_to_public(row)
    finally:
        conn.close()


def _get_owned_row(conn, user_id: str, key_id: str):
    row = conn.execute(
        "SELECT * FROM user_model_keys WHERE id = ? AND user_id = ?", (key_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="未找到该模型账号")
    return row


def update_key(
    user_id: str,
    key_id: str,
    api_key: str | None,
    alias: str | None,
    model_id: str | None,
) -> dict[str, Any]:
    init_db()
    conn = get_connection()
    try:
        row = _get_owned_row(conn, user_id, key_id)
        provider_key = row["provider_key"]
        cfg = providers.PROVIDERS[provider_key]
        new_model_id = model_id if model_id is not None else row["model_id"]
        now = _now()

        if api_key:
            api_key = api_key.strip()
            try:
                providers.test_connection(provider_key, api_key, new_model_id)
            except providers.ProviderError as e:
                raise _provider_error_to_http(e, cfg["display_name"]) from e
            cipher = crypto_util.encrypt_secret(api_key)
            last4 = api_key[-4:]
            conn.execute(
                "UPDATE user_model_keys SET api_key_cipher=?, key_last4=?, model_id=?, "
                "alias=COALESCE(?, alias), status='active', fail_count=0, last_verified_at=?, "
                "updated_at=? WHERE id=?",
                (cipher, last4, new_model_id, alias, now, now, key_id),
            )
        else:
            conn.execute(
                "UPDATE user_model_keys SET alias=COALESCE(?, alias), model_id=?, updated_at=? WHERE id=?",
                (alias, new_model_id, now, key_id),
            )
        conn.commit()
        updated = conn.execute("SELECT * FROM user_model_keys WHERE id = ?", (key_id,)).fetchone()
        return _row_to_public(updated)
    finally:
        conn.close()


def delete_key(user_id: str, key_id: str) -> None:
    init_db()
    conn = get_connection()
    try:
        _get_owned_row(conn, user_id, key_id)
        conn.execute("DELETE FROM user_model_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
        conn.commit()
    finally:
        conn.close()


def verify_key(user_id: str, key_id: str) -> dict[str, Any]:
    init_db()
    conn = get_connection()
    try:
        row = _get_owned_row(conn, user_id, key_id)
        api_key = crypto_util.decrypt_secret(row["api_key_cipher"])
        now = _now()
        try:
            providers.test_connection(row["provider_key"], api_key, row["model_id"])
        except providers.ProviderError as e:
            conn.execute(
                "UPDATE user_model_keys SET status='invalid', updated_at=? WHERE id=?", (now, key_id)
            )
            conn.commit()
            cfg = providers.PROVIDERS[row["provider_key"]]
            raise _provider_error_to_http(e, cfg["display_name"]) from e
        conn.execute(
            "UPDATE user_model_keys SET status='active', fail_count=0, last_verified_at=?, updated_at=? "
            "WHERE id=?",
            (now, now, key_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM user_model_keys WHERE id = ?", (key_id,)).fetchone()
        return _row_to_public(updated)
    finally:
        conn.close()


def set_current(user_id: str, key_id: str) -> dict[str, Any]:
    init_db()
    conn = get_connection()
    try:
        row = _get_owned_row(conn, user_id, key_id)
        if row["status"] != "active":
            raise HTTPException(status_code=400, detail="该模型账号当前状态异常，无法设为使用中")
        now = _now()
        conn.execute("UPDATE user_model_keys SET is_current = 0 WHERE user_id = ?", (user_id,))
        conn.execute(
            "UPDATE user_model_keys SET is_current = 1, updated_at = ? WHERE id = ?", (now, key_id)
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM user_model_keys WHERE id = ?", (key_id,)).fetchone()
        return _row_to_public(updated)
    finally:
        conn.close()


def get_preference(user_id: str) -> str:
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT mode FROM user_model_preference WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["mode"] if row else "platform"
    finally:
        conn.close()


def set_preference(user_id: str, mode: str) -> str:
    if mode not in ("platform", "byok"):
        raise HTTPException(status_code=400, detail="mode 必须是 platform 或 byok")
    init_db()
    conn = get_connection()
    try:
        now = _now()
        conn.execute(
            "INSERT INTO user_model_preference (user_id, mode, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode, updated_at=excluded.updated_at",
            (user_id, mode, now),
        )
        conn.commit()
        return mode
    finally:
        conn.close()


def _force_platform_mode(user_id: str) -> None:
    try:
        set_preference(user_id, "platform")
    except Exception:
        logger.warning("byok: failed to reset user %s back to platform mode", user_id)


def _mark_failure(key_id: str) -> None:
    init_db()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE user_model_keys SET fail_count = fail_count + 1, updated_at = ? WHERE id = ?",
            (_now(), key_id),
        )
        row = conn.execute("SELECT fail_count FROM user_model_keys WHERE id = ?", (key_id,)).fetchone()
        if row and row["fail_count"] >= FAIL_COUNT_TO_INVALID:
            conn.execute(
                "UPDATE user_model_keys SET status = 'invalid', is_current = 0, updated_at = ? WHERE id = ?",
                (_now(), key_id),
            )
            logger.warning("byok: key %s marked invalid after %s failures", key_id, row["fail_count"])
        conn.commit()
    finally:
        conn.close()


def _current_active_key_row(user_id: str):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM user_model_keys WHERE user_id = ? AND is_current = 1 AND status = 'active'",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def call_with_fallback(user_id: str, fn_name: str, *args: Any, **kwargs: Any) -> tuple[Any, str | None]:
    """Call llm_service.<fn_name> or the user's own provider client, whichever
    applies for this user right now. Returns (result, notice) — notice is a
    user-facing string (or None) explaining an automatic fallback, if one happened.
    """
    platform_fn = getattr(llm_service, fn_name)

    init_db()
    mode = get_preference(user_id)
    if mode != "byok":
        return platform_fn(*args, **kwargs), None

    row = _current_active_key_row(user_id)
    if not row:
        # byok 模式但没有可用 key：静默回退到平台模型，不算失败
        return platform_fn(*args, **kwargs), None

    key_id = row["id"]
    provider_key = row["provider_key"]
    display_name = providers.PROVIDERS.get(provider_key, {}).get("display_name", provider_key)

    try:
        api_key = crypto_util.decrypt_secret(row["api_key_cipher"])
        chat_fn, chat_json_fn = providers.make_client(provider_key, api_key, row["model_id"])
        fn = chat_fn if fn_name == "chat" else chat_json_fn
        return fn(*args, **kwargs), None
    except Exception as e:
        kind = getattr(e, "kind", None)
        logger.warning(
            "byok: user %s key %s (%s) call failed [%s]: %s",
            user_id, key_id, provider_key, kind, str(e)[:200],
        )
        _mark_failure(key_id)
        _force_platform_mode(user_id)
        notice = (
            f"你接入的 {display_name} 账号调用失败，本次已自动切换回平台默认模型。"
            "如需继续使用你的模型，请前往【我的-AI模型接入】重新选择。"
        )
        return platform_fn(*args, **kwargs), notice
