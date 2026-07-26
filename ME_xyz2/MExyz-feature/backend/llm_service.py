"""Zhipu GLM (open.bigmodel.cn) OpenAI-compatible chat client."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

GLM_API_KEY = os.getenv("GLM_API_KEY", "")
GLM_BASE_URL = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
GLM_MODEL = os.getenv("GLM_MODEL", "glm-4.5-flash")
GLM_TRUST_ENV = os.getenv("GLM_TRUST_ENV", "false").lower() in {
    "1",
    "true",
    "yes",
}
_THINKING_RAW = os.getenv("GLM_THINKING", "disabled").strip().lower()
GLM_THINKING = "enabled" if _THINKING_RAW in {"1", "true", "yes", "enabled"} else "disabled"
GLM_MAX_TOKENS = int(os.getenv("GLM_MAX_TOKENS", "8192"))


class LLMError(Exception):
    pass


def _headers() -> dict[str, str]:
    if not GLM_API_KEY or GLM_API_KEY.startswith("sk-your"):
        raise LLMError("GLM_API_KEY 未配置，请在 backend/.env 中设置")
    return {
        "Authorization": f"Bearer {GLM_API_KEY}",
        "Content-Type": "application/json",
    }


def _strip_asterisks(text: str) -> str:
    """Remove all '*' from model output (markdown bold/italics noise)."""
    return text.replace("*", "")


def chat(
    messages: list[dict[str, str]],
    system: str | None = None,
    temperature: float = 0.7,
) -> str:
    """Send chat completion; return assistant text."""
    payload_messages: list[dict[str, str]] = []
    if system:
        payload_messages.append({"role": "system", "content": system})
    payload_messages.extend(messages)

    body: dict[str, Any] = {
        "model": GLM_MODEL,
        "messages": payload_messages,
        "temperature": temperature,
        "thinking": {"type": GLM_THINKING},
        "max_tokens": GLM_MAX_TOKENS,
    }

    try:
        with httpx.Client(timeout=60.0, trust_env=GLM_TRUST_ENV) as client:
            resp = client.post(
                f"{GLM_BASE_URL}/chat/completions",
                headers=_headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"GLM 请求失败: {e}") from e

    try:
        content = data["choices"][0]["message"]["content"] or ""
        return _strip_asterisks(content).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"GLM 响应格式异常: {data}") from e


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def chat_json(
    messages: list[dict[str, str]],
    system: str | None = None,
    temperature: float = 0.3,
) -> dict:
    """Ask model for JSON; retry once on parse failure."""
    last_err: Exception | None = None
    for _ in range(2):
        raw = chat(messages, system=system, temperature=temperature)
        try:
            result = _extract_json(raw)
            if isinstance(result, dict):
                return result
            raise LLMError(f"期望 JSON object，得到: {type(result)}")
        except Exception as e:
            last_err = e
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "请只返回合法 JSON 对象，不要 markdown 代码块。"},
            ]
    raise LLMError(f"无法解析 JSON: {last_err}")
