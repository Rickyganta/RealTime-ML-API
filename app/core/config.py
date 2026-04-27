from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "real-time-ml-recommendation-api"
    env: str = "dev"
    postgres_url: str = "postgresql+psycopg2://recommender:recommender@localhost:5432/recommender"
    redis_url: str = "redis://localhost:6379/0"
    ab_salt: str = "portfolio-project-salt"
    default_hybrid_weight_cf: float = 0.6
    model_version: str = "v1"
    rate_limit_per_minute: int = 100
    # If set, clients may bypass rate limiting by sending this value in the
    # `X-Loadtest-Bypass` header. Keep empty in real deployments.
    loadtest_bypass_token: str = ""
    cache_ttl_seconds: int = 300
    movielens_path: str = "data/ml-latest-small"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
