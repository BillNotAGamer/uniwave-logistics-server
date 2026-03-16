from __future__ import annotations

from datetime import date, timedelta
from random import choice, randint

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weather_forecast import WeatherForecast

SUMMARIES = [
    "Freezing",
    "Bracing",
    "Chilly",
    "Cool",
    "Mild",
    "Warm",
    "Balmy",
    "Hot",
    "Sweltering",
    "Scorching",
]


class WeatherForecastRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count(self) -> int:
        query = select(func.count(WeatherForecast.id))
        total = await self._session.scalar(query)
        return int(total or 0)

    async def list_by_date(self, *, limit: int = 5) -> list[WeatherForecast]:
        query = (
            select(WeatherForecast)
            .order_by(WeatherForecast.date.asc())
            .limit(limit)
        )
        rows = await self._session.scalars(query)
        return list(rows)

    async def seed_default_forecasts(self, *, days: int = 5) -> None:
        start = date.today()
        records = [
            WeatherForecast(
                date=start + timedelta(days=offset),
                temperature_c=randint(-20, 55),
                summary=choice(SUMMARIES),
            )
            for offset in range(1, days + 1)
        ]
        self._session.add_all(records)
        await self._session.commit()
