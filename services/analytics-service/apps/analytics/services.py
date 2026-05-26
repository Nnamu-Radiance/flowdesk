from django.core.cache import cache


class AnalyticsService:
    @staticmethod
    def cached_payload(key: str, callback, ttl: int = 1800):
        payload = cache.get(key)
        if payload is not None:
            return payload
        payload = callback()
        cache.set(key, payload, ttl)
        return payload
