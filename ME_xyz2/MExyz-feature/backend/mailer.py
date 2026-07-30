"""Verification email delivery. Falls back to server-log output when SMTP is not configured."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("mexyz.mailer")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "ME.xyz")


def _smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def send_verification_code(to_email: str, code: str, ttl_minutes: int) -> None:
    subject = "ME.xyz 注册验证码"
    body = (
        f"你的验证码是：{code}\n\n"
        f"{ttl_minutes} 分钟内有效，请勿泄露给他人。\n"
        f"如果不是你本人操作，请忽略此邮件。"
    )

    if not _smtp_configured():
        # Dev fallback: no SMTP credentials configured yet, surface the code in the
        # server log so registration is still testable end-to-end locally.
        logger.warning(
            "[DEV] SMTP not configured — verification code for %s is: %s", to_email, code
        )
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())
