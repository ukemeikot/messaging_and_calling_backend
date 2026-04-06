"""
Cache provider abstraction for Messaging & Calling SDK.

This module provides a pluggable caching system that supports:
- Redis (recommended for production)
- In-memory fallback (development mode)

Usage:
    from messaging_sdk.providers.cache import CacheProvider, get_cache_provider

    cache = get_cache_provider()
    await cache.set("key", "value", ttl=300)
    value = await cache.get("key")
"""

import json
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
import logging
from datetime import datetime, timedelta

from messaging_sdk.core.config import settings

logger = logging.getLogger(__name__)


class CacheProvider(ABC):
    """Abstract base class for cache providers."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache with optional TTL in seconds."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        pass

    @abstractmethod
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for a key."""
        pass

    @abstractmethod
    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key. Returns -1 if no TTL, -2 if key doesn't exist."""
        pass

    @abstractmethod
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value. Returns new value or None if key doesn't exist."""
        pass

    @abstractmethod
    async def publish(self, channel: str, message: str) -> bool:
        """Publish a message to a channel (for pub/sub)."""
        pass

    @abstractmethod
    async def subscribe(self, channel: str) -> Any:
        """Subscribe to a channel (returns async iterator for messages)."""
        pass


class InMemoryCacheProvider(CacheProvider):
    """In-memory cache provider for development."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._pubsub_channels: Dict[str, List[asyncio.Queue]] = {}
        logger.info("Using in-memory cache provider (development mode)")

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if entry.get("expires_at") and datetime.now() > entry["expires_at"]:
            # Expired, remove it
            del self._cache[key]
            return None

        return entry["value"]

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache with optional TTL."""
        expires_at = None
        if ttl:
            expires_at = datetime.now() + timedelta(seconds=ttl)

        self._cache[key] = {
            "value": value,
            "expires_at": expires_at
        }
        return True

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        value = await self.get(key)
        return value is not None

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for a key."""
        if key not in self._cache:
            return False

        self._cache[key]["expires_at"] = datetime.now() + timedelta(seconds=ttl)
        return True

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key."""
        if key not in self._cache:
            return -2

        entry = self._cache[key]
        if not entry.get("expires_at"):
            return -1

        remaining = entry["expires_at"] - datetime.now()
        if remaining.total_seconds() <= 0:
            del self._cache[key]
            return -2

        return int(remaining.total_seconds())

    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value."""
        current = await self.get(key)
        if current is None:
            return None

        if not isinstance(current, (int, float)):
            return None

        new_value = current + amount
        await self.set(key, new_value)
        return new_value

    async def publish(self, channel: str, message: str) -> bool:
        """Publish a message to a channel."""
        if channel not in self._pubsub_channels:
            return True  # No subscribers, but that's OK

        # Send to all subscribers
        for queue in self._pubsub_channels[channel]:
            try:
                await queue.put(message)
            except Exception as e:
                logger.error(f"Error publishing to channel {channel}: {e}")

        return True

    async def subscribe(self, channel: str):
        """Subscribe to a channel. Returns async iterator."""
        if channel not in self._pubsub_channels:
            self._pubsub_channels[channel] = []

        queue = asyncio.Queue()
        self._pubsub_channels[channel].append(queue)

        try:
            while True:
                message = await queue.get()
                yield message
        finally:
            # Cleanup when done
            if channel in self._pubsub_channels:
                self._pubsub_channels[channel].remove(queue)
                if not self._pubsub_channels[channel]:
                    del self._pubsub_channels[channel]


class RedisCacheProvider(CacheProvider):
    """Redis cache provider for production."""

    def __init__(self, redis_url: str, db: int = 0):
        try:
            import redis.asyncio as redis
        except ImportError:
            raise ImportError("redis package is required for RedisCacheProvider. Install with: pip install redis")

        self.redis = redis.from_url(redis_url, db=db, decode_responses=True)
        logger.info(f"Using Redis cache provider: {redis_url} (db={db})")

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis."""
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            # Try to parse as JSON, fallback to string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in Redis with optional TTL."""
        try:
            # Serialize value to JSON if it's not a string
            if not isinstance(value, str):
                value = json.dumps(value)

            if ttl:
                return await self.redis.setex(key, ttl, value)
            else:
                return await self.redis.set(key, value)
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from Redis."""
        try:
            return await self.redis.delete(key) > 0
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for a key."""
        try:
            return await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key."""
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"Redis ttl error for key {key}: {e}")
            return -2

    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value."""
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis incr error for key {key}: {e}")
            return None

    async def publish(self, channel: str, message: str) -> bool:
        """Publish a message to a Redis channel."""
        try:
            return await self.redis.publish(channel, message) > 0
        except Exception as e:
            logger.error(f"Redis publish error for channel {channel}: {e}")
            return False

    async def subscribe(self, channel: str):
        """Subscribe to a Redis channel. Returns async iterator."""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    yield message["data"]
        except Exception as e:
            logger.error(f"Redis subscribe error for channel {channel}: {e}")
            return


def get_cache_provider() -> CacheProvider:
    """
    Factory function to get the configured cache provider.

    Returns:
        Configured CacheProvider instance
    """
    cache_config = settings.cache

    if cache_config.redis_url:
        try:
            return RedisCacheProvider(cache_config.redis_url, cache_config.redis_db)
        except ImportError as e:
            logger.warning(f"Redis not available, falling back to in-memory cache: {e}")
            return InMemoryCacheProvider()
        except Exception as e:
            logger.warning(f"Redis connection failed, falling back to in-memory cache: {e}")
            return InMemoryCacheProvider()
    else:
        return InMemoryCacheProvider()


# Global cache provider instance
cache_provider = get_cache_provider()