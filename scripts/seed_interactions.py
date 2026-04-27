from __future__ import annotations

import argparse
import os

import requests

"""
Seed synthetic interactions to make dashboard counters move during demos.

Example:
  API_BASE=http://127.0.0.1:8000 \
  python scripts/seed_interactions.py --users 1-50 --movie-id 1 --rating 4.0
"""


def post_rating(api_base: str, user_id: int, movie_id: int, rating: float) -> int:
    url = f"{api_base}/users/{user_id}/interactions"
    r = requests.post(
        url,
        json={"movie_id": int(movie_id), "rating": float(rating)},
        timeout=10,
    )
    return int(r.status_code)


def main() -> None:
    parser = argparse.ArgumentParser(description="POST synthetic ratings to the API")
    parser.add_argument("--api-base", default=os.getenv("API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--users", default="1-50", help="Range like 1-50 or a single id like 7")
    parser.add_argument("--movie-id", type=int, default=1)
    parser.add_argument("--rating", type=float, default=4.0)
    args = parser.parse_args()

    if "-" in args.users:
        start_s, end_s = args.users.split("-", 1)
        uids = list(range(int(start_s), int(end_s) + 1))
    else:
        uids = [int(args.users)]

    ok = 0
    for uid in uids:
        code = post_rating(args.api_base, uid, args.movie_id, args.rating)
        if 200 <= code < 300:
            ok += 1
    print(f"Posted interactions: {ok}/{len(uids)} successful (api_base={args.api_base})")


if __name__ == "__main__":
    main()
