import os
import shutil
import logging
import asyncio
from datetime import datetime, timedelta
from app.core.config import settings
from app.services.dataset_store import dataset_store

logger = logging.getLogger(__name__)

def run_auto_cleanup() -> int:
    """
    Cleans up expired active sessions in the memory store and removes orphaned directories.
    Returns the total number of sessions/folders cleaned up.
    """
    # 1. Clean up active sessions in memory (which also deletes their folders)
    initial_sessions = list(dataset_store.active_sessions.keys())
    dataset_store.cleanup_expired()
    cleaned_sessions_count = len(initial_sessions) - len(dataset_store.active_sessions)
    
    # 2. Clean up orphaned directories in storage/temp
    cleaned_orphans_count = 0
    temp_dir = os.path.join(settings.storage_path, "temp")
    if os.path.exists(temp_dir):
        now = datetime.utcnow()
        for name in os.listdir(temp_dir):
            dir_path = os.path.join(temp_dir, name)
            if os.path.isdir(dir_path):
                # If the directory is not in active sessions, it is orphaned.
                # Check modification time to avoid deleting directories that are in the middle of being created.
                if name not in dataset_store.active_sessions:
                    try:
                        mtime = datetime.utcfromtimestamp(os.path.getmtime(dir_path))
                        if now - mtime > timedelta(minutes=settings.session_expiration_minutes):
                            shutil.rmtree(dir_path)
                            cleaned_orphans_count += 1
                            logger.info(f"Cleaned up orphaned directory: {dir_path}")
                    except Exception as e:
                        logger.error(f"Failed to check/delete orphaned directory {dir_path}: {e}")
                        
    return cleaned_sessions_count + cleaned_orphans_count


async def cleanup_worker_task():
    """Background task running the cleanup logic periodically."""
    logger.info("Starting background TTL cleanup worker task")
    while True:
        try:
            run_auto_cleanup()
        except Exception as e:
            logger.error(f"Error in background cleanup worker: {e}", exc_info=True)
        # Sleep for 60 seconds
        await asyncio.sleep(60)


_cleanup_task = None


def start_cleanup_worker():
    """Start the background cleanup worker."""
    global _cleanup_task
    if _cleanup_task is None:
        _cleanup_task = asyncio.create_task(cleanup_worker_task())
        logger.info("Background cleanup worker started.")
