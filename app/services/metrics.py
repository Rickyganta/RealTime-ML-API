from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "reco_api_requests_total", "Total API requests", ["endpoint", "method", "status"]
)
CACHE_HITS = Counter("reco_cache_hits_total", "Cache hits", ["kind"])
CACHE_MISSES = Counter("reco_cache_misses_total", "Cache misses", ["kind"])
PREDICTIONS = Counter("reco_predictions_total", "Recommendations served", ["strategy"])
LATENCY = Histogram("reco_request_latency_seconds", "Request latency", ["endpoint"])
