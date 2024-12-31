from pathlib import Path

from aiohttp_session.redis_storage import RedisStorage

from redis import Redis
from redis import asyncio as aioredis

# HTML
INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / 'frontend' / 'view.html'

# Session
COOKIE_NAME = "aiohttp_chat_app_session_id"
COOKIE_EXPIRATION_TIME = 60 * 60

# Redis
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DECODE_RESPONSES = False
CHANNEL_NAME = "chat"

redis_client: Redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=REDIS_DECODE_RESPONSES)
redis_storage: RedisStorage = RedisStorage(
    aioredis.Redis(), 
    cookie_name=COOKIE_NAME,
    max_age=COOKIE_EXPIRATION_TIME
)