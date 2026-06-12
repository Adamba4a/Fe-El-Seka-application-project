from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings
from app.core.database import close_pool, create_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    pool = await create_pool(settings.database_url)
    app.state.pool = pool
    yield
    await close_pool()
    app.state.pool = None


app = FastAPI(
    title="Fe El Seka API",
    version=settings.api_version,
    lifespan=lifespan,
)

app.include_router(health_router)
