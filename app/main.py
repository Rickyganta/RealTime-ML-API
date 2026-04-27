import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse, Response

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.database import Base, engine, get_db
from app.middleware.rate_limit import RateLimiter
from app.models.domain import Interaction, Movie, User
from app.schemas.api import (
    ExplainResponse,
    InteractionIn,
    RecommendationItem,
    RecommendationResponse,
    RetrainResponse,
    Strategy,
)
from app.services.ab_testing import assign_strategy
from app.services.cache import CacheClient
from app.services.feature_store import (
    cache_popular_fallback,
    increment_ab_click,
    increment_ab_impression,
    popular_key,
    precompute_user_recommendations,
    recommendation_key,
)
from app.services.metrics import CACHE_HITS, CACHE_MISSES, LATENCY, PREDICTIONS, REQUEST_COUNT
from app.services.recommender import RecommenderService
from app.services.statsig import chi_square_ctr_summary

logger = logging.getLogger(__name__)

cache_client: CacheClient | None = None
recommender: RecommenderService | None = None
rate_limiter: RateLimiter | None = None


async def _warm_recommendation_cache() -> None:
    """Heavy Redis warm runs off the startup critical path (avoids proxy 502s while booting)."""
    if not cache_client or not recommender:
        return
    try:
        stats = await asyncio.to_thread(
            precompute_user_recommendations, cache_client, recommender, 100
        )
        logger.info("cache_warm_complete", extra=stats)
    except Exception:
        logger.exception("cache_warm_failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global cache_client, recommender, rate_limiter
    configure_logging()
    Base.metadata.create_all(bind=engine)
    cache_client = CacheClient()
    rate_limiter = RateLimiter(cache_client)
    recommender = RecommenderService()
    cache_popular_fallback(cache_client, recommender, top_k=100)
    asyncio.create_task(_warm_recommendation_cache())
    logger.info(
        "service_started",
        extra={"model_version": recommender.model_version, "cache_warm": "background"},
    )
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/")
def root() -> RedirectResponse:
    """Base URL is unversioned; send browsers to interactive API docs."""
    return RedirectResponse(url="/docs")


def _ensure_services() -> tuple[CacheClient, RecommenderService, RateLimiter]:
    if not cache_client or not recommender or not rate_limiter:
        raise HTTPException(status_code=500, detail="Service not initialized")
    return cache_client, recommender, rate_limiter


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.env,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "loadtest_bypass_configured": bool(settings.loadtest_bypass_token),
    }


@app.post("/users/{id}/interactions")
def record_interaction(
    id: int,
    payload: InteractionIn,
    request: Request,
    db: Session = Depends(get_db),
):
    cache, _, limiter = _ensure_services()
    limiter.check(request)
    started = time.perf_counter()
    try:
        user = db.get(User, id)
        if not user:
            user = User(id=id)
            db.add(user)
        movie = db.get(Movie, payload.movie_id)
        if not movie:
            raise HTTPException(status_code=404, detail="Unknown movie_id")

        interaction = Interaction(user_id=id, movie_id=payload.movie_id, rating=payload.rating)
        db.add(interaction)
        db.commit()

        cache.set_json(f"features:user:{id}", {"last_rating": payload.rating, "movie_id": payload.movie_id})
        if payload.rating >= 3.5:
            increment_ab_click(cache, assign_strategy(id).strategy)
        REQUEST_COUNT.labels("/users/{id}/interactions", "POST", "200").inc()
        return {"status": "recorded"}
    except HTTPException:
        REQUEST_COUNT.labels("/users/{id}/interactions", "POST", "4xx").inc()
        raise
    finally:
        LATENCY.labels("/users/{id}/interactions").observe(time.perf_counter() - started)


@app.get("/recommendations/{user_id}", response_model=RecommendationResponse)
def get_recommendations(
    user_id: int,
    request: Request,
    n: int = Query(default=10, ge=1, le=50),
    strategy: Strategy = Query(default="ab_auto"),
):
    cache, rec, limiter = _ensure_services()
    limiter.check(request)
    started = time.perf_counter()
    endpoint = "/recommendations/{user_id}"

    served_strategy = strategy
    if strategy == "ab_auto":
        served_strategy = assign_strategy(user_id).strategy

    cache_key = recommendation_key(rec.model_version, user_id, served_strategy)
    cached_rows = cache.get_json(cache_key)
    if cached_rows:
        CACHE_HITS.labels("recommendation").inc()
        REQUEST_COUNT.labels(endpoint, "GET", "200").inc()
        increment_ab_impression(cache, served_strategy)
        LATENCY.labels(endpoint).observe(time.perf_counter() - started)
        return RecommendationResponse(
            user_id=user_id,
            served_strategy=served_strategy,
            model_version=rec.model_version,
            items=[RecommendationItem(**row) for row in cached_rows[:n]],
        )
    CACHE_MISSES.labels("recommendation").inc()

    fallback_rows = cache.get_json(popular_key(rec.model_version))
    if not fallback_rows:
        REQUEST_COUNT.labels(endpoint, "GET", "503").inc()
        LATENCY.labels(endpoint).observe(time.perf_counter() - started)
        raise HTTPException(status_code=503, detail="Recommendations not precomputed yet")

    payload = RecommendationResponse(
        user_id=user_id,
        served_strategy=served_strategy,
        model_version=rec.model_version,
        items=[RecommendationItem(**row) for row in fallback_rows[:n]],
    )
    increment_ab_impression(cache, served_strategy)
    PREDICTIONS.labels(served_strategy).inc(len(payload.items))
    REQUEST_COUNT.labels(endpoint, "GET", "200").inc()
    LATENCY.labels(endpoint).observe(time.perf_counter() - started)
    return payload


@app.get("/recommendations/{user_id}/explain", response_model=ExplainResponse)
def explain_recommendations(
    user_id: int,
    request: Request,
    strategy: Strategy = Query(default="ab_auto"),
):
    _, rec, limiter = _ensure_services()
    limiter.check(request)
    served_strategy = strategy if strategy != "ab_auto" else assign_strategy(user_id).strategy
    if served_strategy == "hybrid":
        reasons = [
            "Combines collaborative and content-based signals.",
            "Balances personalized affinity and semantic similarity.",
            f"Current model version: {rec.model_version}.",
        ]
    elif served_strategy == "collaborative":
        reasons = [
            "Based on similar users' rating patterns.",
            "Learns latent user-item factors with matrix factorization.",
            "Falls back to popularity for cold-start users.",
        ]
    else:
        reasons = [
            "Based on movie metadata (genres/tags/title tokens).",
            "Uses TF-IDF and cosine similarity against your profile.",
            "Great for catalog discovery and long-tail content.",
        ]
    REQUEST_COUNT.labels("/recommendations/{user_id}/explain", "GET", "200").inc()
    return ExplainResponse(user_id=user_id, served_strategy=served_strategy, reasons=reasons)


@app.get("/metrics")
def metrics():
    REQUEST_COUNT.labels("/metrics", "GET", "200").inc()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/admin/retrain", response_model=RetrainResponse)
def retrain(request: Request):
    cache, _, limiter = _ensure_services()
    limiter.check(request)
    global recommender
    recommender = RecommenderService()
    precompute_user_recommendations(cache, recommender, top_k=100)
    REQUEST_COUNT.labels("/admin/retrain", "POST", "200").inc()
    return RetrainResponse(status="retrained", model_version=recommender.model_version)


@app.get("/admin/ab/results")
def ab_results(db: Session = Depends(get_db)):
    cache, rec, _ = _ensure_services()
    assignments = {"collaborative": 0, "content": 0, "hybrid": 0}
    users = db.execute(select(User.id)).scalars().all()
    for uid in users:
        assignments[assign_strategy(uid).strategy] += 1

    ctr_counts = {}
    for strategy in ("collaborative", "content", "hybrid"):
        impressions = int(cache.client.get(f"ab:{rec.model_version}:{strategy}:impressions") or 0)
        clicks = int(cache.client.get(f"ab:{rec.model_version}:{strategy}:clicks") or 0)
        ctr_counts[strategy] = {"impressions": impressions, "clicks": clicks}

    return {
        "users": len(users),
        "assignments": assignments,
        "ctr": ctr_counts,
        "chi_squared": chi_square_ctr_summary(ctr_counts),
    }
