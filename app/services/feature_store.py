from __future__ import annotations

from app.core.config import settings
from app.services.ab_testing import assign_strategy
from app.services.cache import CacheClient
from app.services.recommender import RecommenderService, ScoredMovie

STRATEGIES = ("collaborative", "content", "hybrid")


def cache_popular_fallback(
    cache: CacheClient, recommender: RecommenderService, top_k: int = 100
) -> None:
    """Write cold-start popular list to Redis (fast; used before heavy per-user warm)."""
    model_version = recommender.model_version
    popular = _serialize(recommender._popular_fallback(top_k), "popular_fallback")
    cache.set_json(
        f"model:{model_version}:cold_start:popular",
        popular,
        ttl=24 * 60 * 60,
    )


def _serialize(items: list[ScoredMovie], strategy: str) -> list[dict[str, object]]:
    return [
        {
            "movie_id": item.movie_id,
            "title": item.title,
            "score": round(float(item.score), 6),
            "strategy": strategy,
            "explanation": item.explanation,
        }
        for item in items
    ]


def precompute_user_recommendations(
    cache: CacheClient,
    recommender: RecommenderService,
    top_k: int = 100,
) -> dict[str, int]:
    model_version = recommender.model_version
    cache_popular_fallback(cache, recommender, top_k)

    user_ids = sorted({int(u) for u in recommender.ratings_df["userId"].unique().tolist()})

    for user_id in user_ids:
        per_strategy: dict[str, list[dict[str, object]]] = {}
        for strategy in STRATEGIES:
            if strategy == "collaborative":
                rows = recommender.collaborative(user_id, top_k)
            elif strategy == "content":
                rows = recommender.content(user_id, top_k)
            else:
                rows = recommender.hybrid(user_id, top_k)

            serialized = _serialize(rows, strategy)
            per_strategy[strategy] = serialized
            cache.set_json(
                f"model:{model_version}:user:{user_id}:strategy:{strategy}:recs",
                serialized,
                ttl=24 * 60 * 60,
            )

        assigned_strategy = assign_strategy(user_id).strategy
        cache.set_json(
            f"model:{model_version}:user:{user_id}:recs",
            per_strategy.get(assigned_strategy, []),
            ttl=24 * 60 * 60,
        )

    return {"users_precomputed": len(user_ids), "top_k": top_k}


def recommendation_key(model_version: str, user_id: int, strategy: str) -> str:
    if strategy == "ab_auto":
        return f"model:{model_version}:user:{user_id}:recs"
    return f"model:{model_version}:user:{user_id}:strategy:{strategy}:recs"


def popular_key(model_version: str) -> str:
    return f"model:{model_version}:cold_start:popular"


def increment_ab_impression(cache: CacheClient, strategy: str) -> None:
    key = f"ab:{settings.model_version}:{strategy}:impressions"
    count = cache.incr(key)
    if count == 1:
        cache.expire(key, 7 * 24 * 60 * 60)


def increment_ab_click(cache: CacheClient, strategy: str) -> None:
    key = f"ab:{settings.model_version}:{strategy}:clicks"
    count = cache.incr(key)
    if count == 1:
        cache.expire(key, 7 * 24 * 60 * 60)
