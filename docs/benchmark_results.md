# Benchmark results (local)

Recorded from a **long read-heavy Locust** run in Safari (aggregated and `GET /recommendations/101` in the same test).

| Metric | Aggregated | `GET /recommendations/101` |
|--------|------------|-----------------------------|
| **# Requests** | 1,164,035 | 1,159,455 |
| **# Fails** | 0 | 0 |
| **Median (ms)** | 11 | 11 |
| **p95 (ms)** | 56 | 56 |
| **p99 (ms)** | 89 | 89 |
| **Average (ms)** | 16.31 | 16.28 |
| **Current RPS** | ~1,000 | ~1,000 |

Screenshot: `docs/benchmarks/locust-1000rps.png`

Re-run:

```bash
make loadtest-read
# or: ./.venv/bin/python -m locust -f locust/locustfile_readonly.py --host http://localhost:8000
```

To stay under the API rate limit at high RPS, set `LOADTEST_BYPASS_TOKEN` in `.env` and use the `X-Loadtest-Bypass` header (the Makefile load-test targets wire this for local runs).
