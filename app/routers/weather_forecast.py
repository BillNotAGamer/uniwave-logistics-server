from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.weather_forecast_repository import WeatherForecastRepository
from app.schemas.weather_forecast import WeatherForecastRead
from app.services.weather_forecast_service import WeatherForecastService

router = APIRouter()


def get_weather_forecast_service(
    session: AsyncSession = Depends(get_db_session),
) -> WeatherForecastService:
    repository = WeatherForecastRepository(session)
    return WeatherForecastService(repository)


@router.get("", response_model=list[WeatherForecastRead], summary="Get weather forecast")
async def get_weather_forecast(
    service: WeatherForecastService = Depends(get_weather_forecast_service),
) -> list[WeatherForecastRead]:
    return await service.get_forecasts()
