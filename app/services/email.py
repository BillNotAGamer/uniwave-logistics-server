from __future__ import annotations

import asyncio
import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage as SMTPEmailMessage
from email.utils import formataddr, make_msgid
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.models.email_log import EmailLog
from app.models.mixins import utc_now
from app.db.session import AsyncSessionFactory

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OutboundEmail:
    to_email: str
    subject: str
    text_body: str
    html_body: str | None = None
    user_id: int | None = None
    template_key: str | None = None
    payload: dict[str, Any] | None = None


class EmailService:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory

    async def send_email(
        self,
        email: OutboundEmail,
        *,
        background_tasks: BackgroundTasks | None = None,
        raise_on_failure: bool = False,
    ) -> None:
        if background_tasks is not None:
            background_tasks.add_task(self._send_and_log, email, False)
            return

        await self._send_and_log(email, raise_on_failure)

    async def send_password_reset_email(
        self,
        *,
        to_email: str,
        token: str,
        user_id: int,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        reset_base_url = (
            self._settings.frontend_reset_password_url
            or f"{self._settings.frontend_base_url.rstrip('/')}/reset-password"
        )
        separator = "&" if "?" in reset_base_url else "?"
        reset_link = (
            f"{reset_base_url}{separator}token={quote(token)}"
            f"&email={quote(to_email)}"
        )
        text_body = (
            "We received a password reset request.\n\n"
            f"Reset your password using this link: {reset_link}\n\n"
            f"Or use this token directly: {token}\n\n"
            "If you did not request this, you can ignore this email.\n"
        )

        await self.send_email(
            OutboundEmail(
                to_email=to_email,
                subject="Reset your password",
                text_body=text_body,
                user_id=user_id,
                template_key="password_reset",
                payload={"reset_link": reset_link},
            ),
            background_tasks=background_tasks,
        )

    async def send_password_changed_email(
        self,
        *,
        to_email: str,
        user_id: int,
        background_tasks: BackgroundTasks | None = None,
        raise_on_failure: bool = False,
    ) -> None:
        await self.send_email(
            OutboundEmail(
                to_email=to_email,
                subject="Your password has been changed",
                text_body=(
                    "Your password has been successfully changed. "
                    "If you did not request this change, contact support immediately."
                ),
                user_id=user_id,
                template_key="password_changed",
            ),
            background_tasks=background_tasks,
            raise_on_failure=raise_on_failure,
        )

    async def send_verification_email(
        self,
        *,
        to_email: str,
        token: str,
        user_id: int,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        verify_link = (
            f"{self._settings.frontend_base_url.rstrip('/')}/verify-email"
            f"?token={quote(token)}"
        )
        text_body = (
            "Thanks for registering.\n\n"
            f"Verify your email with this link: {verify_link}\n\n"
            f"Or use this token directly: {token}\n"
        )

        await self.send_email(
            OutboundEmail(
                to_email=to_email,
                subject="Verify your email",
                text_body=text_body,
                user_id=user_id,
                template_key="email_verification",
                payload={"verify_link": verify_link},
            ),
            background_tasks=background_tasks,
        )

    async def send_order_created_detailed_email(
        self,
        *,
        to_email: str,
        customer_name: str,
        order_code: str,
        receiver_name: str,
        receiver_phone: str,
        pickup_address: str,
        dropoff_address: str,
        distance_km: Decimal,
        estimated_price: Decimal,
        background_tasks: BackgroundTasks | None = None,
        raise_on_failure: bool = False,
    ) -> None:
        text_body = (
            f"Hello {customer_name},\n\n"
            "Your order at Uniwave Logistics has been created successfully.\n\n"
            f"Order code: {order_code}\n"
            f"Receiver: {receiver_name} - {receiver_phone}\n"
            f"Pickup: {pickup_address}\n"
            f"Dropoff: {dropoff_address}\n"
            f"Estimated distance: {distance_km} km\n"
            f"Estimated price: {estimated_price} VND\n\n"
            "Current order status: In transit.\n\n"
            "Regards,\n"
            "Uniwave Logistics\n"
        )

        await self.send_email(
            OutboundEmail(
                to_email=to_email,
                subject=f"Order created successfully - Code: {order_code}",
                text_body=text_body,
                template_key="order_created_detailed",
                payload={"order_code": order_code},
            ),
            background_tasks=background_tasks,
            raise_on_failure=raise_on_failure,
        )

    async def send_order_confirmation_to_customer(
        self,
        *,
        to_email: str,
        customer_name: str,
        order_code: str,
        background_tasks: BackgroundTasks | None = None,
        raise_on_failure: bool = False,
    ) -> None:
        text_body = (
            f"Hello {customer_name},\n\n"
            "Your order has been created successfully.\n"
            f"Order code: {order_code}\n\n"
            "Thank you for choosing Uniwave Logistics."
        )

        await self.send_email(
            OutboundEmail(
                to_email=to_email,
                subject="Your order has been created",
                text_body=text_body,
                template_key="order_confirmation",
                payload={"order_code": order_code},
            ),
            background_tasks=background_tasks,
            raise_on_failure=raise_on_failure,
        )

    async def _send_and_log(self, email: OutboundEmail, raise_on_failure: bool = False) -> None:
        status = "sent"
        error_message: str | None = None
        provider_message_id: str | None = None
        sent_at: datetime | None = utc_now()

        exc: Exception | None = None
        try:
            provider_message_id = await asyncio.to_thread(self._send_via_smtp, email)
        except Exception as send_exc:  # pragma: no cover - external I/O
            status = "failed"
            error_message = str(send_exc)
            sent_at = None
            exc = send_exc
            logger.exception("Failed to send email to %s", email.to_email)

        await self._log_email(
            email=email,
            status=status,
            error_message=error_message,
            sent_at=sent_at,
            provider_message_id=provider_message_id,
        )

        if exc is not None and raise_on_failure:
            raise exc

    def _send_via_smtp(self, email: OutboundEmail) -> str:
        message = SMTPEmailMessage()
        message["Subject"] = email.subject
        message["From"] = formataddr((self._settings.smtp_from_name, self._settings.smtp_from_email))
        message["To"] = email.to_email
        message_id = make_msgid()
        message["Message-ID"] = message_id

        message.set_content(email.text_body)
        if email.html_body:
            message.add_alternative(email.html_body, subtype="html")

        if self._settings.smtp_use_ssl:
            smtp_client: smtplib.SMTP = smtplib.SMTP_SSL(
                self._settings.smtp_host,
                self._settings.smtp_port,
                timeout=self._settings.smtp_timeout_seconds,
            )
        else:
            smtp_client = smtplib.SMTP(
                self._settings.smtp_host,
                self._settings.smtp_port,
                timeout=self._settings.smtp_timeout_seconds,
            )

        with smtp_client as client:
            if self._settings.smtp_use_tls and not self._settings.smtp_use_ssl:
                client.starttls()

            if self._settings.smtp_username:
                client.login(self._settings.smtp_username, self._settings.smtp_password or "")

            client.send_message(message)

        return message_id.strip("<>")

    async def _log_email(
        self,
        *,
        email: OutboundEmail,
        status: str,
        error_message: str | None,
        sent_at: datetime | None,
        provider_message_id: str | None,
    ) -> None:
        async with self._session_factory() as session:
            log = EmailLog(
                user_id=email.user_id,
                to_email=email.to_email,
                subject=email.subject,
                template_key=email.template_key,
                provider_name="smtp",
                provider_message_id=provider_message_id,
                status=status,
                error_message=error_message,
                payload=email.payload,
                sent_at=sent_at,
            )
            session.add(log)
            await session.commit()


@lru_cache
def get_email_service() -> EmailService:
    return EmailService(settings=get_settings(), session_factory=AsyncSessionFactory)
