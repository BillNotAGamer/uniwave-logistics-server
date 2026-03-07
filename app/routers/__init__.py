from fastapi import APIRouter

from app.routers.weather_forecast import router as weather_forecast_router

api_router = APIRouter()
api_router.include_router(
    weather_forecast_router,
    prefix="/weatherforecast",
    tags=["WeatherForecast"],
)
