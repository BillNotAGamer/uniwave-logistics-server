from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.config import Settings, get_settings
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.contact_service import ContactService
from app.services.email import EmailService, get_email_service

router = APIRouter(prefix="/api/contact", tags=["Contact"])


def get_contact_service(
    settings: Settings = Depends(get_settings),
    email_service: EmailService = Depends(get_email_service),
) -> ContactService:
    return ContactService(settings=settings, email_service=email_service)


@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_contact_form(
    request: ContactRequest,
    service: ContactService = Depends(get_contact_service),
) -> ContactResponse:
    return await service.submit_contact_form(request=request)
