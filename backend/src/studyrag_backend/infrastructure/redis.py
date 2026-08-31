from redis.asyncio import Redis


class RedisManager:
    def __init__(self, url: str) -> None:
        self.client: Redis = Redis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30,
        )

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def close(self) -> None:
        await self.client.aclose()
