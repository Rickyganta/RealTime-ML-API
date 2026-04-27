# Benchmark results (local)

Recorded from a **long read-heavy Locust** run in Safari (aggregated and `GET /recommendations/101` in the same test).

| Metric | Aggregated | `GET /recommendations/101` |
|--------|------------|-----------------------------|
| **# Requests** | 1,342,878 | 1,338,298 |
| **# Fails** | 0 | 0 |
| **Median (ms)** | 10 | 10 |
| **p95 (ms)** | 54 | 54 |
| **p99 (ms)** | 87 | 87 |
| **Average (ms)** | 15.68 | 15.64 |
| **Current RPS** | ~1,000.2 | ~1,000.2 |

Screenshot: `docs/benchmarks/locust-1000rps.png`

Re-run:

```bash
make loadtest-read
# or: ./.venv/bin/python -m locust -f locust/locustfile_readonly.py --host http://localhost:8000
```

To stay under the API rate limit at high RPS, set `LOADTEST_BYPASS_TOKEN` in `.env` and use the `X-Loadtest-Bypass` header (the Makefile load-test targets wire this for local runs).
