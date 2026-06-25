import json
import logging
import time
import uuid

logger = logging.getLogger("copilot.analytics")

class AnalyticsLogger:
    def __init__(self, session_id: str, provider: str = "Unknown", model: str = "Unknown"):
        self.request_id = str(uuid.uuid4())
        self.session_id = session_id
        self.provider = provider
        self.model = model
        self.start_time = time.time()
        self.first_token_time = None
        self.tokens_count = 0
        self.cache_hit = False
        self.errors = []
        self.retry_count = 0

    def record_first_token(self):
        self.first_token_time = time.time()

    def record_token(self, count: int = 1):
        self.tokens_count += count

    def record_cache_hit(self):
        self.cache_hit = True

    def record_error(self, err_msg: str):
        self.errors.append(err_msg)

    def record_retry(self):
        self.retry_count += 1

    def log_summary(self, event_type: str = "stream"):
        end_time = time.time()
        latency = round((end_time - self.start_time) * 1000, 2)
        first_token_latency = (
            round((self.first_token_time - self.start_time) * 1000, 2)
            if self.first_token_time
            else None
        )
        stream_duration = (
            round((end_time - self.first_token_time) * 1000, 2)
            if self.first_token_time
            else None
        )

        log_data = {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "event_type": event_type,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": latency,
            "first_token_latency_ms": first_token_latency,
            "stream_duration_ms": stream_duration,
            "tokens_streamed": self.tokens_count,
            "cache_hit": self.cache_hit,
            "retry_count": self.retry_count,
            "errors": self.errors,
            "success": len(self.errors) == 0
        }

        # Log as structured JSON
        logger.info(json.dumps(log_data))
        return log_data
