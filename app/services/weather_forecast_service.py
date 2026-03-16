from __future__ import annotations

from app.repositories.weather_forecast_repository import WeatherForecastRepository
from app.schemas.weather_forecast import WeatherForecastRead


class WeatherForecastService:
    def __init__(self, repository: WeatherForecastRepository) -> None:
        self._repository = repository

    async def get_forecasts(self) -> list[WeatherForecastRead]:
        if await self._repository.count() == 0:
            await self._repository.seed_default_forecasts(days=5)

        forecasts = await self._repository.list_by_date(limit=5)
        return [WeatherForecastRead.from_model(item) for item in forecasts]
