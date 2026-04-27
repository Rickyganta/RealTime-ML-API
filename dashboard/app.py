import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Movie recs — live",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
  .block-container { padding-top: 1.25rem; }
  h1 { letter-spacing: -0.02em; }
  div[data-testid="stMetric"] {
    background: linear-gradient(180deg, #fafbfc 0%, #f1f5f9 100%);
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 0.85rem 1rem 1rem;
    border-top: 3px solid #6366f1;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  }
  [data-testid="stMetricLabel"] p {
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #64748b !important;
  }
  [data-testid="stMetricValue"] p {
    font-size: 1.65rem !important;
    font-weight: 600 !important;
    color: #0f172a !important;
  }
  .stSubheader { margin-top: 0.25rem; }
</style>
""",
    unsafe_allow_html=True,
)


def _api_base() -> str:
    # Streamlit Cloud: set API_BASE in Settings → Secrets (TOML). Also works via env locally.
    if "API_BASE" in st.secrets:
        return str(st.secrets["API_BASE"]).strip().rstrip("/")
    return os.getenv("API_BASE", "http://localhost:8000").strip().rstrip("/")


API_BASE = _api_base()

st.title("Movie recs")
st.caption(f"Live API · [OpenAPI docs]({API_BASE}/docs) · [health]({API_BASE}/health)")

main_tab, bench_tab = st.tabs(["Main", "Performance (Locust)"])


@st.cache_data(ttl=3)
def _fetch_json(url: str) -> dict:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3)
def _fetch_text(url: str) -> str:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text


def _extract_metric_value(metrics_text: str, metric_name: str, selectors: list[str]) -> float:
    for line in metrics_text.splitlines():
        if not line.startswith(metric_name):
            continue
        if selectors and not all(s in line for s in selectors):
            continue
        try:
            return float(line.rsplit(" ", 1)[-1])
        except ValueError:
            return 0.0
    return 0.0


root_dir = Path(__file__).resolve().parents[1]
bench_png = root_dir / "docs" / "benchmarks" / "locust-1000rps.png"

with main_tab:
    with st.spinner("Loading metrics…"):
        try:
            ab = _fetch_json(f"{API_BASE}/admin/ab/results")
        except Exception as exc:  # noqa: BLE001
            st.error("Could not load /admin/ab/results. Is the API running?")
            st.caption(str(exc))
            ab = {}
        try:
            metrics_text = _fetch_text(f"{API_BASE}/metrics")
        except Exception as exc:  # noqa: BLE001
            st.error("Could not load /metrics. Is the API running?")
            st.caption(str(exc))
            metrics_text = ""

    if metrics_text:
        hit_count = _extract_metric_value(
            metrics_text, "reco_cache_hits_total", ['kind="recommendation"']
        )
        miss_count = _extract_metric_value(
            metrics_text, "reco_cache_misses_total", ['kind="recommendation"']
        )
        cache_total = hit_count + miss_count
        cache_hit_rate = (hit_count / cache_total) * 100 if cache_total else 0.0

        latency_sum = _extract_metric_value(
            metrics_text,
            "reco_request_latency_seconds_sum",
            ['endpoint="/recommendations/{user_id}"'],
        )
        latency_count = _extract_metric_value(
            metrics_text,
            "reco_request_latency_seconds_count",
            ['endpoint="/recommendations/{user_id}"'],
        )
        avg_latency_ms = ((latency_sum / latency_count) * 1000) if latency_count else 0.0

        total_interactions = _extract_metric_value(
            metrics_text,
            "reco_api_requests_total",
            [
                'endpoint="/users/{id}/interactions"',
                'method="POST"',
                'status="200"',
            ],
        )
    else:
        hit_count = 0.0
        miss_count = 0.0
        cache_total = 0.0
        cache_hit_rate = 0.0
        avg_latency_ms = 0.0
        total_interactions = 0.0

    st.markdown("##### Observability")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Avg latency (recs)", f"{avg_latency_ms:.2f} ms")
    kpi2.metric("Cache hit rate (recs)", f"{cache_hit_rate:.1f}%")
    kpi3.metric("Ratings recorded (POST)", f"{int(total_interactions)}")

    with st.expander("How CTR & A/B data get populated", expanded=False):
        st.markdown(
            """
1. **Impressions:** each **`GET /recommendations/{user_id}`** (including from the widgets below) increments A/B impressions for the served strategy.
2. **Clicks:** **`POST /users/{id}/interactions`** with a **rating ≥ 3.5** counts as a click for that user’s bucket strategy (movie must exist in the API DB—use a `movie_id` from the recs table or ingest data first).
3. **Manual tries:** use **[OpenAPI docs](%s)** → *Try it out*, or **`curl`**, or the form below.
            """
            % API_BASE
        )
        st.code(
            f'curl -sS -X POST "{API_BASE}/users/1/interactions" \\\n'
            f'  -H "Content-Type: application/json" \\\n'
            f'  -d \'{{"movie_id": 1, "rating": 4.0}}\'',
            language="bash",
        )

    with st.expander("Record a rating (POST /users/{id}/interactions)", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            post_uid = st.number_input("User ID", min_value=1, value=1, key="post_uid")
        with c2:
            post_mid = st.number_input("Movie ID", min_value=1, value=1, key="post_mid")
        with c3:
            post_rating = st.slider("Rating", 0.5, 5.0, 4.0, 0.5, key="post_rating")
        st.caption("Unknown `movie_id` returns 404 from the API (DB must contain that movie).")
        if st.button("Submit rating", type="primary", key="post_btn"):
            try:
                r = requests.post(
                    f"{API_BASE}/users/{int(post_uid)}/interactions",
                    json={"movie_id": int(post_mid), "rating": float(post_rating)},
                    timeout=15,
                )
            except Exception as exc:  # noqa: BLE001
                st.error("Request failed.")
                st.caption(str(exc))
            else:
                if r.ok:
                    st.success("Recorded. Metrics refresh in a few seconds.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"{r.status_code}: {r.text}")

    st.markdown("### CTR by strategy (A/B bucket)")
    ctr = ab.get("ctr", {}) if ab else {}
    ctr_df = (
        pd.DataFrame(
            {
                "strategy": ["collaborative", "content", "hybrid"],
                "ctr": [
                    (
                        ctr.get("collaborative", {}).get("clicks", 0)
                        / max(ctr.get("collaborative", {}).get("impressions", 0), 1)
                    ),
                    (
                        ctr.get("content", {}).get("clicks", 0)
                        / max(ctr.get("content", {}).get("impressions", 0), 1)
                    ),
                    (
                        ctr.get("hybrid", {}).get("clicks", 0)
                        / max(ctr.get("hybrid", {}).get("impressions", 0), 1)
                    ),
                ],
            }
        )
        .set_index("strategy")
    )
    st.bar_chart(ctr_df, height=280)

    left, right = st.columns(2)
    with left:
        st.subheader("Recs for a user")
        user_id = st.number_input("User ID", min_value=1, value=1)
        strategy = st.selectbox("Strategy", ["ab_auto", "collaborative", "content", "hybrid"])
        try:
            rec = _fetch_json(
                f"{API_BASE}/recommendations/{int(user_id)}?n=10&strategy={strategy}"
            )
        except Exception as exc:  # noqa: BLE001
            st.error("Could not load recommendations.")
            st.caption(str(exc))
            rec = {}
        st.dataframe(pd.DataFrame(rec.get("items", [])), use_container_width=True)

    with right:
        st.subheader("Why these recs")
        explain_user_id = st.number_input("Explain for User ID", min_value=1, value=1, key="explain_uid")
        explain_strategy = st.selectbox(
            "Explain Strategy",
            ["ab_auto", "collaborative", "content", "hybrid"],
            key="explain_strategy",
        )
        try:
            explain_rec = _fetch_json(
                f"{API_BASE}/recommendations/{int(explain_user_id)}?n=5&strategy={explain_strategy}"
            )
        except Exception as exc:  # noqa: BLE001
            st.error("Could not load explain recommendations.")
            st.caption(str(exc))
            explain_rec = {}
        for idx, item in enumerate(explain_rec.get("items", [])[:5], start=1):
            st.markdown(
                f"**{idx}. {item.get('title', 'Unknown Movie')}**  \n"
                f"Score: `{item.get('score', 0)}`  \n"
                f"Explanation: {item.get('explanation', 'N/A')}"
            )

    with st.expander("Raw A/B JSON & metrics (debug)", expanded=False):
        st.json(ab)
        st.text((metrics_text or "")[:5000])

with bench_tab:
    st.subheader("Performance (Locust)")
    st.caption("Read-heavy run. I keep big read tests separate from write tests so the numbers stay easy to explain.")
    if bench_png.exists():
        st.image(str(bench_png), use_container_width=True)
    else:
        st.info("Missing benchmark image. Run: `python scripts/generate_benchmark_png.py`")
    st.markdown("**Recorded Locust results (summary row)**")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Scenario": "Read-heavy (cached) GET /recommendations/*",
                    "Total requests": 1_164_035,
                    "Users": 100,
                    "Spawn rate (/s)": 10,
                    "Current RPS": "~1,000",
                    "Failures": 0,
                    "Median (ms)": 11,
                    "p95 (ms)": 56,
                    "p99 (ms)": 89,
                    "Average (ms)": 16.31,
                }
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown(
        "Notes: recommendations are served from Redis in this setup, and I use a load-test bypass header so Locust "
        "doesn’t trip the per-IP rate limit while I’m hammering reads."
    )

st.sidebar.divider()
st.sidebar.markdown("**Built by Ricky Johnson Ganta**")
st.sidebar.markdown("[LinkedIn](https://www.linkedin.com/in/ricky--ganta-53869118b/)")
st.sidebar.markdown("[GitHub](https://github.com/Rickyganta)")
