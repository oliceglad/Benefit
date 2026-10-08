"""Роутер публичного API (префикс ``/api/v1/candidates``)."""

from fastapi import APIRouter

from app.api.v1.endpoints import dictionaries, employer, health, me

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dictionaries.router)
api_router.include_router(me.router)
# Последним: маршрут ``/{user_id}`` не должен перехватывать ``/me`` и др.
api_router.include_router(employer.router)
