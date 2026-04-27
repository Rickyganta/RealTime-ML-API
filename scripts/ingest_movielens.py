from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import requests
from sqlalchemy import delete

from app.db.database import Base, SessionLocal, engine
from app.models.domain import Interaction, Movie, User

MOVIELENS_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
DATA_DIR = Path("data")
ZIP_PATH = DATA_DIR / "ml-latest-small.zip"
EXTRACTED_DIR = DATA_DIR / "ml-latest-small"


def download_movielens() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if EXTRACTED_DIR.exists():
        return
    response = requests.get(MOVIELENS_URL, timeout=120)
    response.raise_for_status()
    ZIP_PATH.write_bytes(response.content)
    with ZipFile(ZIP_PATH) as zf:
        zf.extractall(DATA_DIR)


def ingest(reset: bool) -> None:
    Base.metadata.create_all(bind=engine)
    movies_df = pd.read_csv(EXTRACTED_DIR / "movies.csv")
    ratings_df = pd.read_csv(EXTRACTED_DIR / "ratings.csv")
    users_df = pd.DataFrame({"userId": sorted(ratings_df["userId"].unique())})

    db = SessionLocal()
    try:
        if reset:
            db.execute(delete(Interaction))
            db.execute(delete(User))
            db.execute(delete(Movie))
            db.commit()

        existing_movies = set(m[0] for m in db.query(Movie.id).all())
        existing_users = set(u[0] for u in db.query(User.id).all())

        new_movies = [
            Movie(id=int(row.movieId), title=str(row.title), genres=str(row.genres))
            for row in movies_df.itertuples(index=False)
            if int(row.movieId) not in existing_movies
        ]
        if new_movies:
            db.bulk_save_objects(new_movies)
            db.commit()

        new_users = [
            User(id=int(row.userId))
            for row in users_df.itertuples(index=False)
            if int(row.userId) not in existing_users
        ]
        if new_users:
            db.bulk_save_objects(new_users)
            db.commit()

        if reset:
            interactions = [
                Interaction(user_id=int(row.userId), movie_id=int(row.movieId), rating=float(row.rating))
                for row in ratings_df.itertuples(index=False)
            ]
            db.bulk_save_objects(interactions)
            db.commit()

        print(
            f"Ingested movies={len(movies_df)} users={len(users_df)} ratings={len(ratings_df)} "
            f"(reset={reset})"
        )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and ingest MovieLens into Postgres.")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not wipe existing tables before ingest.",
    )
    args = parser.parse_args()

    download_movielens()
    ingest(reset=not args.no_reset)


if __name__ == "__main__":
    main()
