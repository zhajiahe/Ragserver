"""FastAPI server configuration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ragbackend.config import (
    APP_NAME, 
    APP_VERSION, 
    APP_DESCRIPTION, 
    ALLOW_ORIGINS
)
from ragbackend.database.connection import init_db_pool, close_db_pool, init_database_tables
from ragbackend.services.minio_service import initialize_minio_service
from ragbackend.api.collections import router as collections_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting up RagBackend application...")
    
    try:
        # Initialize database
        await init_db_pool()
        await init_database_tables()
        logger.info("Database initialized successfully")
        
        # Initialize MinIO
        minio_initialized = await initialize_minio_service()
        if not minio_initialized:
            logger.error("Failed to initialize MinIO service")
        else:
            logger.info("MinIO service initialized successfully")
        
        logger.info("RagBackend application started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down RagBackend application...")
    await close_db_pool()
    logger.info("RagBackend application shutdown complete")


# Create FastAPI application
APP = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan
)

# Add CORS middleware
APP.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@APP.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": APP_NAME,
        "version": APP_VERSION
    }

# Include routers
APP.include_router(collections_router, tags=["Collections"])

logger.info(f"FastAPI application configured: {APP_NAME} v{APP_VERSION}")
