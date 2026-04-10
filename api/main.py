from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router
from api.websocket import router as ws_router
from core.config import Settings, get_settings
from core.runtime import FridayRuntime


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        runtime = FridayRuntime(resolved)
        application.state.runtime = runtime
        application.state.settings = resolved
        await runtime.start()
        yield
        await runtime.stop()

    application = FastAPI(title=resolved.app_name, version="0.2.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    application.include_router(ws_router)
    return application


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run("api.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
