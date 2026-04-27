import logging
import time

from app.services.cache import CacheClient
from app.services.feature_store import precompute_user_recommendations
from app.services.recommender import RecommenderService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    cache = CacheClient()
    while True:
        logger.info("nightly retrain started")
        recommender = RecommenderService()
        stats = precompute_user_recommendations(cache, recommender, top_k=100)
        logger.info("nightly retrain completed", extra=stats)
        time.sleep(24 * 60 * 60)


if __name__ == "__main__":
    main()
