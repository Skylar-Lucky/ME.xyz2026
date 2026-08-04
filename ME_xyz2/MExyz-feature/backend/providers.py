"""BYOK provider registry + request adapters for user-supplied model keys.

Two request "families" are supported:
- openai: OpenAI-compatible /chat/completions (OpenAI, Doubao/Ark, DeepSeek)
- anthropic: Claude's native /messages shape (different auth header + body)

Each adapter exposes a `chat(messages, system=None, temperature=0.7) -> str`
function with the exact same signature as llm_service.chat, so call sites in
main.py/conversation.py/memory_agent.py don't need to know which provider
they're talking to.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

import httpx

PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "display_name": "OpenAI",
        "family": "openai",
        "base_url": "https://api.openai.com/v1",
        "test_model": "gpt-4o-mini",
        "doc_url": "https://platform.openai.com/api-keys",
        "needs_model_id": False,
    },
    "claude": {
        "display_name": "Claude",
        "family": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "test_model": "claude-3-5-haiku-20241022",
        "doc_url": "https://console.anthropic.com/settings/keys",
        "needs_model_id": False,
    },
    "doubao": {
        "display_name": "豆包",
        "family": "openai",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "test_model": None,
        "doc_url": "https://console.volcengine.com/ark",
        "needs_model_id": True,
    },
    "deepseek": {
        "display_name": "DeepSeek",
        "family": "openai",
        "base_url": "https://api.deepseek.com",
        "test_model": "deepseek-chat",
        "doc_url": "https://platform.deepseek.com/api_keys",
        "needs_model_id": False,
    },
}


class ProviderError(Exception):
    """kind: invalid_key | insufficient_balance | rate_limited | network | unsupported"""

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


def _resolve_model(provider_key: str, model_id: str | None) -> str:
    cfg = PROVIDERS[provider_key]
    if cfg["needs_model_id"]:
        if not model_id:
            raise ProviderError("unsupported", f"{cfg['display_name']} 需要填写接入点/模型 ID")
        return model_id
    return model_id or cfg["test_model"]


def _classify_http_error(status_code: int) -> str:
    if status_code in (401, 403):
        return "invalid_key"
    if status_code == 402:
        return "insufficient_balance"
    if status_code == 429:
        return "rate_limited"
    if status_code == 404 or status_code == 400:
        return "unsupported"
    return "network"


def _strip_asterisks(text: str) -> str:
    return text.replace("*", "")


def _call_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    system: str | None,
    temperature: float,
) -> str:
    payload_messages: list[dict[str, str]] = []
    if system:
        payload_messages.append({"role": "system", "content": system})
    payload_messages.extend(messages)

    body = {"model": model, "messages": payload_messages, "temperature": temperature}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=body)
    except httpx.HTTPError as e:
        raise ProviderError("network", f"请求失败: {e}") from e

    if resp.status_code >= 400:
        raise ProviderError(_classify_http_error(resp.status_code), f"HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"] or ""
        return _strip_asterisks(content).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError("unsupported", f"响应格式异常: {data}") from e


def _call_anthropic(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    system: str | None,
    temperature: float,
) -> str:
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": temperature,
    }
    if system:
        body["system"] = system
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{base_url.rstrip('/')}/messages", headers=headers, json=body)
    except httpx.HTTPError as e:
        raise ProviderError("network", f"请求失败: {e}") from e

    if resp.status_code >= 400:
        raise ProviderError(_classify_http_error(resp.status_code), f"HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        blocks = data["content"]
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        return _strip_asterisks(text).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError("unsupported", f"响应格式异常: {data}") from e


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _make_chat_json(chat_fn: Callable[..., str]) -> Callable[..., dict]:
    def chat_json(
        messages: list[dict[str, str]],
        system: str | None = None,
        temperature: float = 0.3,
    ) -> dict:
        last_err: Exception | None = None
        for _ in range(2):
            raw = chat_fn(messages, system=system, temperature=temperature)
            try:
                result = _extract_json(raw)
                if isinstance(result, dict):
                    return result
                raise ProviderError("unsupported", f"期望 JSON object，得到: {type(result)}")
            except Exception as e:
                last_err = e
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": "请只返回合法 JSON 对象，不要 markdown 代码块。"},
                ]
        raise ProviderError("unsupported", f"无法解析 JSON: {last_err}")

    return chat_json


def make_client(
    provider_key: str, api_key: str, model_id: str | None
) -> tuple[Callable[..., str], Callable[..., dict]]:
    """Return (chat_fn, chat_json_fn) bound to this provider + key."""
    if provider_key not in PROVIDERS:
        raise ProviderError("unsupported", f"未知的供应商: {provider_key}")
    cfg = PROVIDERS[provider_key]
    model = _resolve_model(provider_key, model_id)
    base_url = cfg["base_url"]
    family = cfg["family"]

    def chat(messages: list[dict[str, str]], system: str | None = None, temperature: float = 0.7) -> str:
        if family == "anthropic":
            return _call_anthropic(base_url, api_key, model, messages, system, temperature)
        return _call_openai_compatible(base_url, api_key, model, messages, system, temperature)

    return chat, _make_chat_json(chat)


def test_connection(provider_key: str, api_key: str, model_id: str | None) -> None:
    """Raise ProviderError if the key/model combo doesn't work. Minimal-cost ping."""
    chat_fn, _ = make_client(provider_key, api_key, model_id)
    chat_fn([{"role": "user", "content": "hi"}], system=None, temperature=0)
