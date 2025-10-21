import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqladmin import Admin

from scalar_fastapi import get_scalar_api_reference

from fastapi_rader import Rader as FastapiRader, RaderMiddleware  # type: ignore


from ragserver.app.models import Base
from ragserver.app.utils.sql_admin import setup_admin


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ragserver.db")
SQL_ECHO = os.getenv("SQL_ECHO", "0") == "1"

engine = create_engine(DATABASE_URL, echo=SQL_ECHO, future=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown

app = FastAPI(
    title=os.getenv("APP_TITLE", "Ragserver API"),
    version=os.getenv("APP_VERSION", "0.1.0"),
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


# Scalar API Reference at /docs (disable default docs above)
app.mount(
    "/docs",
    get_scalar_api_reference(
        openapi_url="/openapi.json",
        title=os.getenv("APP_TITLE", "Ragserver API"),
    ),
)
FastapiRader(app)
app.add_middleware(RaderMiddleware())

# SQLAdmin setup
admin = setup_admin(app, engine)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn  # type: ignore

    uvicorn.run(
        "ragserver.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )


