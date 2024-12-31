import os
from aiohttp_session.redis_storage import RedisStorage

from redis import Redis
from redis import asyncio as aioredis

from redis_service import RedisService

# Session
COOKIE_NAME = "aiohttp_chat_app_session_id"
COOKIE_EXPIRATION_TIME = 60 * 60

# Redis
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
REDIS_DECODE_RESPONSES = False

class Container:
    def __init__(self):
        self._init_redis_client()
        self._init_redis_storage()
        self._init_redis_service()

    def _init_redis_client(self) -> None:
        self.redis_client = Redis(
            host=REDIS_HOST, 
            port=REDIS_PORT, 
            decode_responses=REDIS_DECODE_RESPONSES
        )
    
    def _init_redis_storage(self) -> None:
        self.redis_storage = RedisStorage(
            aioredis.Redis().from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}"), 
            cookie_name=COOKIE_NAME,
            max_age=COOKIE_EXPIRATION_TIME
        )
    
    def _init_redis_service(self) -> None:
        self.redis_service = RedisService(redis_client=self.redis_client)
    
container = Container()