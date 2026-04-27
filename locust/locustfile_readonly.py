"""
Read-heavy load test (recommended for headline RPS / latency charts).

Run:
  make loadtest-read
"""

import os

from locust import HttpUser, constant_throughput, task


class RecommendationUser(HttpUser):
    wait_time = constant_throughput(10)
    host = "http://localhost:8000"

    def _bypass_headers(self) -> dict[str, str]:
        token = os.getenv("LOADTEST_BYPASS_TOKEN", "")
        return {"X-Loadtest-Bypass": token} if token else {}

    @task
    def get_recommendations(self):
        user_id = 1 + (self.environment.runner.user_count % 600)
        path = f"/recommendations/{user_id}"
        with self.client.get(
            path,
            params={"n": 10, "strategy": "ab_auto"},
            name=path,
            headers=self._bypass_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}: {response.text[:200]}")
