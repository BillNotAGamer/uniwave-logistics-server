from __future__ import annotations

from app.core.config import Settings
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.email import EmailService, OutboundEmail


class ContactService:
    def __init__(self, *, settings: Settings, email_service: EmailService) -> None:
        self._settings = settings
        self._email_service = email_service

    async def submit_contact_form(
        self,
        *,
        request: ContactRequest,
    ) -> ContactResponse:
        sales_email = (
            (self._settings.sales_email or "").strip()
            or (self._settings.contact_recipient_email or "").strip()
            or "sales@uniwave-logistics.com"
        )
        cc_email = (self._settings.contact_cc_email or "").strip() or "rachel.ho@uniwave-logistics.com"

        subject_for_sales = "[Uniwave Logistics] Liên hệ mới từ website"
        body_for_sales = (
            "Có một liên hệ mới từ website Uniwave Logistics:\n\n"
            f"Họ tên: {request.name}\n"
            f"Số điện thoại: {request.phone}\n"
            f"Email: {request.email}\n"
            f"Nguồn: {request.source or 'Không xác định'}\n\n"
            "Nội dung:\n"
            f"{request.message}\n"
        )

        await self._email_service.send_email(
            OutboundEmail(
                to_email=sales_email,
                subject=subject_for_sales,
                text_body=body_for_sales,
                template_key="contact_submission_sales",
                payload={
                    "name": request.name,
                    "phone": request.phone,
                    "email": request.email,
                    "source": request.source,
                },
            )
        )

        await self._email_service.send_email(
            OutboundEmail(
                to_email=cc_email,
                subject=subject_for_sales,
                text_body=body_for_sales,
                template_key="contact_submission_cc",
                payload={
                    "name": request.name,
                    "phone": request.phone,
                    "email": request.email,
                    "source": request.source,
                },
            )
        )

        subject_for_customer = "Uniwave Logistics – Cảm ơn bạn đã liên hệ"
        text_for_customer = (
            f"Kính gửi Quý khách {request.name},\n\n"
            "Uniwave Logistics trân trọng cảm ơn Quý khách đã liên hệ.\n"
            "Chúng tôi đã tiếp nhận thông tin và sẽ sớm phản hồi.\n\n"
            "Trân trọng,\n"
            "Uniwave Logistics"
        )
        html_for_customer = (
            "<div style=\"font-family: Arial, sans-serif; line-height: 1.6;\">"
            f"<p>Kính gửi Quý khách <strong>{request.name}</strong>,</p>"
            "<p>Uniwave Logistics trân trọng cảm ơn Quý khách đã liên hệ với chúng tôi.</p>"
            "<p>Đội ngũ UniWave đã tiếp nhận thông tin và sẽ sớm phản hồi để hỗ trợ tư vấn phù hợp.</p>"
            "<p>Trân trọng,<br><strong>Uniwave Logistics</strong></p>"
            "</div>"
        )

        await self._email_service.send_email(
            OutboundEmail(
                to_email=request.email,
                subject=subject_for_customer,
                text_body=text_for_customer,
                html_body=html_for_customer,
                template_key="contact_thank_you",
                payload={"name": request.name},
            )
        )

        return ContactResponse(
            message="Thông tin liên hệ đã được gửi thành công. Cảm ơn bạn!",
        )
