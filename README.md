![Locust (cropped stats only): ~1.16M requests, ~1k RPS, 0 failures, p95 ~56ms — read-heavy GET /recommendations/*](docs/benchmarks/locust-1000rps.png)

# Real-Time ML Recommendation API

Personal project: a small recommendation service with a real API, a cache layer, Postgres, and basic experimentation/monitoring hooks.

**Author:** Ricky Johnson Ganta

## What this is

- **API**: FastAPI
- **Cache / online store**: Redis (precomputed recommendation lists for fast `GET`s)
- **Database**: Postgres (movies/users/interactions)
- **Models (MovieLens `ml-latest-small`)**:
  - Collaborative: user–user style scoring from a user–user similarity matrix (cosine)
  - Content: TF–IDF over genres/title text + cosine similarity
  - Hybrid: weighted blend (default `0.6*CF + 0.4*CB`)
- **A/B test bucketing**: deterministic hash of `user_id` (stable assignment)
- **Metrics**: `/metrics` in Prometheus text format
- **Dashboard**: Streamlit app in `dashboard/app.py`
- **Retrain job**: a simple long-running loop in `app/jobs/nightly_retrain.py` (dev/demo; swap for a real scheduler in production)

`docker-compose.yml` is included for a full local stack. I mostly run the API directly on my laptop with local Postgres/Redis.

## Endpoints

- `POST /users/{id}/interactions` - record rating
- `GET /recommendations/{user_id}?n=10&strategy=hybrid|collaborative|content|ab_auto`
- `GET /recommendations/{user_id}/explain`
- `GET /metrics`
- `POST /admin/retrain`
- `GET /health`
- `GET /admin/ab/results`

## How to run (local, what I use)

1. `python3.11 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Start Postgres + Redis locally (`localhost:5432`, `localhost:6379`)
4. Ingest data:
   - `PYTHONPATH=. python scripts/ingest_movielens.py`
5. API:
   - `make dev-api`
6. Optional UI:
   - `make dashboard` → `http://localhost:8502`

If `streamlit`/`uvicorn` suddenly isn’t on your PATH after moving the project folder, the venv entrypoints are stale: `make repair-venv`.

**Docker note:** `docker-compose.yml` forces `postgres`/`redis` hostnames for containers. `.env` uses `localhost` for laptop runs.

**URLs**
- API: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Streamlit: `http://localhost:8502`

### Local troubleshooting (the stuff that actually bit me)

- `uvicorn: command not found` → use `./.venv/bin/python -m uvicorn ...` or `make dev-api`
- `could not resolve host "postgres"` → you’re not inside compose networking; use localhost URLs (or run compose)
- `429` from Locust → rate limit; set `LOADTEST_BYPASS_TOKEN` for the API and run Locust with the same value (`make loadtest-read` does this)
- `connection refused` from Locust → API isn’t running on `:8000`

## Load testing (Locust)

I split this into two runs on purpose: a **read heavy** test for headline latency/RPS, and a **mixed** test if I want a little write traffic.

**Read heavy (README image matches this run: ~1.16M total requests, mostly `GET /recommendations/101`, ~1k RPS):**
- `make loadtest-read` (opens Locust on `http://localhost:8089`)
- or headless: `./.venv/bin/python -m locust -f locust/locustfile_readonly.py --host http://localhost:8000 --headless --users 100 --spawn-rate 20 --run-time 2m`

**Mixed (some `POST /users/{id}/interactions`, mostly reads):**
- `make loadtest-mixed`

**Optional demo seeding (fills interaction counters without lying about a load test):**
- `make seed-interactions`

**Refresh the image file used by README + Streamlit tab:**
- replace `docs/benchmarks/locust-1000rps.png` with an exported screenshot, or
- `make gen-benchmark-png` (generates a simple table PNG from the summary numbers)

**Rate limiting note**
- The API enforces `RATE_LIMIT_PER_MINUTE` (default 100/min per IP). For anything above that, I use `LOADTEST_BYPASS_TOKEN` + the `X-Loadtest-Bypass` header in Locust. Quick check:

`curl -s http://127.0.0.1:8000/health` → `"loadtest_bypass_configured": true` when the token is set.

## Offline evaluation notes

- Notebook: `notebooks/model_training_and_eval.ipynb`
- That notebook uses **Surprise SVD** on ratings (good for RMSE/NDCG experiments). The **running API** is the sklearn user–user + TF–IDF stack above — same dataset, different model path. I kept both so I could show classic matrix-factorization eval without dragging Surprise into production dependencies.

## A/B test methodology

- Primary metric: CTR (click-through-rate from recommendation impressions)
- Secondary: watch-time proxy/engagement, novelty, catalog coverage
- Significance:
  - two-proportion z-test (see `app/services/statsig.py`)
- Guardrails:
  - latency, error-rate, and cache hit-rate should not regress

## Things I’d do before calling this “production”

- Put model artifacts in object storage and wire real versioning/rollback
- Add auth on `/admin/*`, migrate schemas with Alembic, and run CI (unit + smoke load)
- Replace the toy rate limiter with something distributed for multi-instance deploys
