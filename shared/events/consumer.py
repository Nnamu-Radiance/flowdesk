import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class EventConsumer:
    """Base event consumer for Redis event payloads."""

    def handle(self, event: dict[str, Any]) -> None:
        raise NotImplementedError("handle must be implemented")

    def consume(self, event_json: str) -> None:
        try:
            event = json.loads(event_json)
            self.handle(event)
            logger.info("event_consumed type=%s", event.get("event_type"))
        except Exception as exc:
            logger.exception("event_consume_failed error=%s", exc)
            raise
