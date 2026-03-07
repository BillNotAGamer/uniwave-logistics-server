from __future__ import annotations

from datetime import date

from app.models.weather_forecast import WeatherForecast
from app.schemas.base import APIModel


class WeatherForecastRead(APIModel):
    date: date
    temperature_c: int
    temperature_f: int
    summary: str

    @classmethod
    def from_model(cls, model: WeatherForecast) -> "WeatherForecastRead":
        return cls(
            date=model.date,
            temperature_c=model.temperature_c,
            temperature_f=32 + int(model.temperature_c / 0.5556),
            summary=model.summary,
        )
