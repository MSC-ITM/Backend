import redis
from app.config import settings
client = redis.Redis.from_url(settings.redis_url)
