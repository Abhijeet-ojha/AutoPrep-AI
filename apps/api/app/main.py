"""Main FastAPI application with production hardening."""

import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.security import SecurityMiddleware
from app.routers.dataset import router as dataset_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="Production-hardened AI-assisted dataset cleaning and analysis platform",
)

# Add middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info(f"Starting {settings.app_name} in {settings.environment} mode")
    logger.info(f"Gemini API configured: {bool(settings.gemini_api_key)}")
    logger.info(f"Storage backend: {settings.storage_backend}")
    
    # Start the background TTL cleanup worker
    from app.services.cleanup_service import start_cleanup_worker
    start_cleanup_worker()


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down application")
    from app.services.cleanup_service import _cleanup_task
    import asyncio
    if _cleanup_task:
        logger.info("Canceling background cleanup worker task...")
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error during cleanup task cancellation: {e}")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "environment": settings.environment,
    }


@app.get("/metrics")
def metrics():
    """Basic metrics endpoint."""
    from app.services.dataset_store import dataset_store
    return {
        "active_sessions_count": len(dataset_store.active_sessions),
        "total_datasets_processed": len(dataset_store.active_sessions),
        "average_health_score": 0.0,
        "most_common_cleaning_action": "None",
        "gemini_vs_fallback_usage": {"gemini": 0, "fallback": 0}
    }


app.include_router(dataset_router)
