from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(
    title="Fe El Seka AI Service",
    version=settings.ai_version,
    lifespan=lifespan,
)

app.include_router(health_router)
