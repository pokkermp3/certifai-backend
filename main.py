"""
main.py

Application entry point.
Builds the FastAPI app, wires all dependencies via the Container,
and configures middleware.

Keep this file as small as possible — it just bootstraps.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.config import settings
from infrastructure.container import Container


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler.
    Code before 'yield' runs at startup.
    Code after 'yield' runs at shutdown.
    """
    container = app.state.container
    await container.init()
    print(f"""
  ██████╗███████╗██████╗ ████████╗██╗███████╗ █████╗ ██╗
 ██╔════╝██╔════╝██╔══██╗╚══██╔══╝██║██╔════╝██╔══██╗██║
 ██║     █████╗  ██████╔╝   ██║   ██║█████╗  ███████║██║
 ██║     ██╔══╝  ██╔══██╗   ██║   ██║██╔══╝  ██╔══██║██║
 ╚██████╗███████╗██║  ██║   ██║   ██║██║     ██║  ██║██║
  ╚═════╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝

 Stack:     Python + FastAPI + SQLite
 Pattern:   Hexagonal Architecture + SOLID
 API:       http://{settings.host}:{settings.port}/api/v1
 Verifier:  http://{settings.host}:{settings.port}/verify
 Dashboard: http://{settings.host}:{settings.port}/dashboard
 Docs:      http://{settings.host}:{settings.port}/docs
 ─────────────────────────────────────────────────────────
    """)
    yield
    # Shutdown — add cleanup here if needed


def create_app() -> FastAPI:
    container = Container(settings)

    app = FastAPI(
        title="CertifAI",
        description="Cryptographic File Integrity Certification API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Store container in app state so routes can access shared services
    app.state.container = container
#    app.state.hasher    = container.hasher

    # CORS — allows the mobile app and verifier to call the API
    origins = (
        ["*"] if settings.cors_origins == "*"
        else settings.cors_origins.split(",")
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all routes
    app.include_router(container.router)
    app.include_router(container.dashboard_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
