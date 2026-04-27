import pandas as pd
from sqlalchemy import select

from app.db.database import Base, SessionLocal, engine
from app.models.domain import Movie


def main() -> None:
    Base.metadata.create_all(bind=engine)
    movies = pd.read_csv("data/ml-latest-small/movies.csv")
    db = SessionLocal()
    try:
        existing = set(db.execute(select(Movie.id)).scalars().all())
        for _, row in movies.iterrows():
            mid = int(row["movieId"])
            if mid in existing:
                continue
            db.add(Movie(id=mid, title=str(row["title"]), genres=str(row["genres"])))
        db.commit()
        print(f"Seeded {len(movies)} movies")
    finally:
        db.close()


if __name__ == "__main__":
    main()
