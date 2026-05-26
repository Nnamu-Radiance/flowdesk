import json
import logging
import uuid
from datetime import datetime, timezone

import redis

logger = logging.getLogger(__name__)


def publish_event(event_type: str, payload: dict, source_service: str, correlation_id: str | None = None) -> dict:
    """Publish an event envelope to Redis Pub/Sub."""
    redis_url = __import__("os").environ.get("REDIS_URL", "redis://localhost:6379/0")
    client = redis.Redis.from_url(redis_url)

    event = {
        "event_type": event_type,
        "version": "1.0",
        "source_service": source_service,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "payload": payload,
    }

    client.publish(event_type, json.dumps(event))
    logger.info("event_published type=%s correlation_id=%s", event_type, event["correlation_id"])
    return event
