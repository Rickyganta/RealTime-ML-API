"""
Mixed traffic load test (small write rate) — use for a separate, honest experiment.

This runs:
- High read traffic to /recommendations/{user_id}
- A low-rate background of POST /users/{id}/interactions

Run:
  make loadtest-mixed
"""

import os

from locust import HttpUser, between, constant_throughput, task


class ReadUser(HttpUser):
    weight = 9
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


class WriteUser(HttpUser):
    weight = 1
    wait_time = between(0.5, 1.5)
    host = "http://localhost:8000"

    def _bypass_headers(self) -> dict[str, str]:
        token = os.getenv("LOADTEST_BYPASS_TOKEN", "")
        return {"X-Loadtest-Bypass": token} if token else {}

    @task
    def post_interaction(self):
        user_id = 1 + (self.environment.runner.user_count % 300)
        path = f"/users/{user_id}/interactions"
        payload = {"movie_id": 1, "rating": 4.0}
        with self.client.post(
            path,
            json=payload,
            name=path,
            headers=self._bypass_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}: {response.text[:200]}")
