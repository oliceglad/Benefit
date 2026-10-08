"""Роутер API версии 1: собирает роутеры всех эндпоинтов."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, status

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(status.router)
