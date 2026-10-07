"""Роутер API версии 1: собирает роутеры всех эндпоинтов."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, oauth, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(oauth.router)
api_router.include_router(users.router)
