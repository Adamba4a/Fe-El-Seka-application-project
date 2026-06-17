from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.rides import router as rides_router
from .services.notification_service import email_retry_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background email retry sweep (T056)
    task = asyncio.create_task(email_retry_loop())
    logger.info("Email retry sweep started.")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Fe El Seka API",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rides_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
