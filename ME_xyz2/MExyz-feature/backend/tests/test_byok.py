"""Unit tests for BYOK: crypto round-trip, key CRUD, and call_with_fallback."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import byok
import crypto_util
import db
import providers


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Every test gets a fresh, throwaway SQLite file — never touch the real dev db."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_byok.db")
    db.init_db()
    yield


@pytest.fixture(autouse=True)
def stub_provider_calls(monkeypatch):
    """Never hit the network in tests — stub test_connection/make_client."""

    def fake_test_connection(provider_key, api_key, model_id):
        if api_key == "sk-bad-key":
            raise providers.ProviderError("invalid_key", "invalid")
        return None

    def fake_make_client(provider_key, api_key, model_id):
        def chat(messages, system=None, temperature=0.7):
            if api_key == "sk-bad-key":
                raise providers.ProviderError("invalid_key", "invalid")
            return "stub reply"

        def chat_json(messages, system=None, temperature=0.3):
            if api_key == "sk-bad-key":
                raise providers.ProviderError("invalid_key", "invalid")
            return {"ok": True}

        return chat, chat_json

    monkeypatch.setattr(providers, "test_connection", fake_test_connection)
    monkeypatch.setattr(providers, "make_client", fake_make_client)


# ---------- crypto ----------

def test_encrypt_decrypt_round_trip():
    token = crypto_util.encrypt_secret("sk-abc123xyz")
    assert token != "sk-abc123xyz"
    assert crypto_util.decrypt_secret(token) == "sk-abc123xyz"


# ---------- key CRUD ----------

def test_add_key_success_and_masking():
    result = byok.add_key("u_1", "deepseek", "sk-realkey-9999", "我的账号", None)
    assert result["provider_key"] == "deepseek"
    assert result["provider_display_name"] == "DeepSeek"
    assert result["key_last4"] == "9999"
    assert result["status"] == "active"
    assert result["is_current"] is True  # first key auto-becomes current
    keys = byok.list_keys("u_1")
    assert len(keys) == 1


def test_add_key_rejects_invalid_key_without_saving():
    with pytest.raises(HTTPException) as exc:
        byok.add_key("u_1", "deepseek", "sk-bad-key", None, None)
    assert exc.value.status_code == 400
    assert byok.list_keys("u_1") == []


def test_add_key_unknown_provider_rejected():
    with pytest.raises(HTTPException):
        byok.add_key("u_1", "not-a-real-provider", "sk-whatever-123", None, None)


def test_add_key_same_provider_updates_existing_row():
    first = byok.add_key("u_1", "deepseek", "sk-first-1111", "a", None)
    second = byok.add_key("u_1", "deepseek", "sk-second-2222", "b", None)
    assert first["id"] == second["id"]
    keys = byok.list_keys("u_1")
    assert len(keys) == 1
    assert keys[0]["key_last4"] == "2222"


def test_max_keys_per_user_enforced(monkeypatch):
    # Only 4 real providers exist; temporarily add fake ones so we can
    # actually exercise the 5-key cap through add_key's own logic.
    extra = {
        "fake1": {"display_name": "Fake1", "family": "openai", "base_url": "x",
                   "test_model": "x", "doc_url": None, "needs_model_id": False},
        "fake2": {"display_name": "Fake2", "family": "openai", "base_url": "x",
                   "test_model": "x", "doc_url": None, "needs_model_id": False},
    }
    monkeypatch.setattr(providers, "PROVIDERS", {**providers.PROVIDERS, **extra})

    for p in ["openai", "claude", "doubao", "deepseek", "fake1"]:
        model_id = "ep-test" if p == "doubao" else None
        byok.add_key("u_1", p, f"sk-{p}-key1", None, model_id)
    assert len(byok.list_keys("u_1")) == 5

    with pytest.raises(HTTPException) as exc:
        byok.add_key("u_1", "fake2", "sk-fake2-key1", None, None)
    assert exc.value.status_code == 400
    assert len(byok.list_keys("u_1")) == 5


def test_delete_key():
    added = byok.add_key("u_1", "deepseek", "sk-realkey-9999", None, None)
    byok.delete_key("u_1", added["id"])
    assert byok.list_keys("u_1") == []


def test_delete_key_not_owned_raises_404():
    added = byok.add_key("u_1", "deepseek", "sk-realkey-9999", None, None)
    with pytest.raises(HTTPException) as exc:
        byok.delete_key("u_2", added["id"])
    assert exc.value.status_code == 404


def test_set_current_mutual_exclusion():
    k1 = byok.add_key("u_1", "deepseek", "sk-a-1111", None, None)
    k2 = byok.add_key("u_1", "openai", "sk-b-2222", None, None)
    assert k1["is_current"] is True  # first one auto-activated
    byok.set_current("u_1", k2["id"])
    keys = {k["id"]: k for k in byok.list_keys("u_1")}
    assert keys[k1["id"]]["is_current"] is False
    assert keys[k2["id"]]["is_current"] is True


def test_set_current_rejects_invalid_key():
    added = byok.add_key("u_1", "deepseek", "sk-realkey-9999", None, None)
    conn = db.get_connection()
    conn.execute("UPDATE user_model_keys SET status='invalid' WHERE id=?", (added["id"],))
    conn.commit()
    conn.close()
    with pytest.raises(HTTPException):
        byok.set_current("u_1", added["id"])


def test_verify_key_marks_invalid_on_failure(monkeypatch):
    added = byok.add_key("u_1", "deepseek", "sk-realkey-9999", None, None)
    monkeypatch.setattr(
        providers, "test_connection",
        lambda *a, **k: (_ for _ in ()).throw(providers.ProviderError("invalid_key", "bad")),
    )
    with pytest.raises(HTTPException):
        byok.verify_key("u_1", added["id"])
    keys = {k["id"]: k for k in byok.list_keys("u_1")}
    assert keys[added["id"]]["status"] == "invalid"


# ---------- preference ----------

def test_preference_defaults_to_platform():
    assert byok.get_preference("u_new") == "platform"


def test_preference_set_and_get():
    byok.set_preference("u_1", "byok")
    assert byok.get_preference("u_1") == "byok"
    byok.set_preference("u_1", "platform")
    assert byok.get_preference("u_1") == "platform"


def test_preference_rejects_bad_mode():
    with pytest.raises(HTTPException):
        byok.set_preference("u_1", "not-a-mode")


# ---------- call_with_fallback ----------

def test_call_with_fallback_platform_mode_uses_llm_service(monkeypatch):
    import llm_service

    monkeypatch.setattr(llm_service, "chat", lambda *a, **k: "platform reply")
    byok.set_preference("u_1", "platform")
    result, notice = byok.call_with_fallback("u_1", "chat", [{"role": "user", "content": "hi"}])
    assert result == "platform reply"
    assert notice is None


def test_call_with_fallback_byok_mode_no_active_key_falls_back_silently(monkeypatch):
    import llm_service

    monkeypatch.setattr(llm_service, "chat", lambda *a, **k: "platform reply")
    byok.set_preference("u_1", "byok")  # no keys added at all
    result, notice = byok.call_with_fallback("u_1", "chat", [{"role": "user", "content": "hi"}])
    assert result == "platform reply"
    assert notice is None


def test_call_with_fallback_byok_mode_uses_user_key():
    added = byok.add_key("u_1", "deepseek", "sk-good-key", None, None)
    byok.set_preference("u_1", "byok")
    byok.set_current("u_1", added["id"])
    result, notice = byok.call_with_fallback("u_1", "chat", [{"role": "user", "content": "hi"}])
    assert result == "stub reply"
    assert notice is None


def test_call_with_fallback_degrades_to_platform_on_key_failure(monkeypatch):
    import llm_service

    monkeypatch.setattr(llm_service, "chat", lambda *a, **k: "platform reply")

    # Bypass add_key's own validation (which would reject sk-bad-key) by
    # inserting directly, to simulate a key that worked at add-time but
    # fails later (e.g. ran out of balance).
    cipher = crypto_util.encrypt_secret("sk-bad-key")
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO user_model_keys (id, user_id, provider_key, alias, model_id, "
        "api_key_cipher, key_last4, status, is_current, fail_count, last_verified_at, "
        "created_at, updated_at) VALUES ('mk_x','u_1','deepseek',NULL,NULL,?,?,'active',1,0,NULL,'t','t')",
        (cipher, "-key"),
    )
    conn.commit()
    conn.close()
    byok.set_preference("u_1", "byok")

    result, notice = byok.call_with_fallback("u_1", "chat", [{"role": "user", "content": "hi"}])
    assert result == "platform reply"
    assert notice is not None
    assert "已自动切换回平台默认模型" in notice
    # mode should have been reset so the next call doesn't keep retrying the dead key
    assert byok.get_preference("u_1") == "platform"
    keys = byok.list_keys("u_1")
    assert keys[0]["status"] == "active"  # only 1 failure so far, not yet invalid


def test_key_marked_invalid_after_three_failures(monkeypatch):
    import llm_service

    monkeypatch.setattr(llm_service, "chat", lambda *a, **k: "platform reply")
    cipher = crypto_util.encrypt_secret("sk-bad-key")
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO user_model_keys (id, user_id, provider_key, alias, model_id, "
        "api_key_cipher, key_last4, status, is_current, fail_count, last_verified_at, "
        "created_at, updated_at) VALUES ('mk_y','u_1','deepseek',NULL,NULL,?,?,'active',1,2,NULL,'t','t')",
        (cipher, "-key"),
    )
    conn.commit()
    conn.close()

    for _ in range(1):
        byok.set_preference("u_1", "byok")
        byok.call_with_fallback("u_1", "chat", [{"role": "user", "content": "hi"}])

    keys = byok.list_keys("u_1")
    assert keys[0]["status"] == "invalid"  # started at fail_count=2, this call pushes to 3
    assert keys[0]["is_current"] is False
