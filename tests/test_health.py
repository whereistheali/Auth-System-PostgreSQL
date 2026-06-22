from httpx import AsyncClient


class TestHealth:
    async def test_health_returns_ok(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_health_method_not_allowed(self, client: AsyncClient):
        resp = await client.post("/health")
        assert resp.status_code == 405
