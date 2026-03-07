from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.quote_repository import QuoteRepository
from app.schemas.quote import EstimateRequest, EstimateResponse, LeadRequest, LeadResponse
from app.services.email import EmailService, get_email_service
from app.services.quote_service import QuoteService

router = APIRouter(prefix="/api/quote", tags=["Quote"])


def get_quote_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> QuoteService:
    return QuoteService(
        session=session,
        repository=QuoteRepository(session),
        settings=settings,
    )


@router.post(
    "/estimate",
    response_model=EstimateResponse,
    status_code=status.HTTP_200_OK,
)
async def estimate(
    request: EstimateRequest,
    service: QuoteService = Depends(get_quote_service),
) -> EstimateResponse:
    return await service.estimate(request)


@router.post(
    "/lead",
    response_model=LeadResponse,
    status_code=status.HTTP_200_OK,
)
async def create_lead(
    request: LeadRequest,
    current_user: User = Depends(get_current_user),
    service: QuoteService = Depends(get_quote_service),
    email_service: EmailService = Depends(get_email_service),
) -> LeadResponse:
    return await service.create_lead(
        request=request,
        current_user=current_user,
        email_service=email_service,
    )
