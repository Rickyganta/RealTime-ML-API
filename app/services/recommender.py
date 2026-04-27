from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings


@dataclass
class ScoredMovie:
    movie_id: int
    title: str
    score: float
    explanation: str


class RecommenderService:
    def __init__(self) -> None:
        self.movies_df = pd.DataFrame()
        self.ratings_df = pd.DataFrame()
        self.tfidf_matrix = None
        self.user_item_matrix = pd.DataFrame()
        self.user_similarity_matrix = pd.DataFrame()
        self.model_version = settings.model_version
        self._movie_index: dict[int, int] = {}
        self._load_data()
        self._train()

    def _load_data(self) -> None:
        base = Path(settings.movielens_path)
        movies_path = base / "movies.csv"
        ratings_path = base / "ratings.csv"
        if not movies_path.exists() or not ratings_path.exists():
            raise FileNotFoundError(
                "MovieLens data missing. Run scripts/download_movielens.py first."
            )
        self.movies_df = pd.read_csv(movies_path)
        self.ratings_df = pd.read_csv(ratings_path)
        self._movie_index = {
            int(mid): i for i, mid in enumerate(self.movies_df["movieId"].tolist())
        }

    def _train(self) -> None:
        self.user_item_matrix = self.ratings_df.pivot_table(
            index="userId", columns="movieId", values="rating", fill_value=0.0
        )
        if not self.user_item_matrix.empty:
            sim = cosine_similarity(self.user_item_matrix.values)
            self.user_similarity_matrix = pd.DataFrame(
                sim,
                index=self.user_item_matrix.index,
                columns=self.user_item_matrix.index,
            )

        # Content features: genres plus simple title tokenization.
        self.movies_df["content_text"] = (
            self.movies_df["genres"].fillna("").str.replace("|", " ", regex=False)
            + " "
            + self.movies_df["title"].fillna("")
        )
        tfidf = TfidfVectorizer(stop_words="english", max_features=5000)
        self.tfidf_matrix = tfidf.fit_transform(self.movies_df["content_text"])

    def _popular_fallback(self, n: int) -> list[ScoredMovie]:
        popular = (
            self.ratings_df.groupby("movieId")["rating"]
            .agg(["mean", "count"])
            .sort_values(["count", "mean"], ascending=False)
            .head(n)
            .reset_index()
        )
        out: list[ScoredMovie] = []
        for _, row in popular.iterrows():
            movie_id = int(row["movieId"])
            meta = self.movies_df[self.movies_df["movieId"] == movie_id].iloc[0]
            out.append(
                ScoredMovie(
                    movie_id=movie_id,
                    title=str(meta["title"]),
                    score=float(row["mean"]),
                    explanation="Popular fallback due to cold start.",
                )
            )
        return out

    def collaborative(self, user_id: int, n: int) -> list[ScoredMovie]:
        if self.user_item_matrix.empty or user_id not in self.user_item_matrix.index:
            return self._popular_fallback(n)

        watched = set(
            self.ratings_df.loc[self.ratings_df["userId"] == user_id, "movieId"].tolist()
        )
        if not watched:
            return self._popular_fallback(n)

        target_ratings = self.user_item_matrix.loc[user_id]
        sims = self.user_similarity_matrix.loc[user_id].drop(index=user_id, errors="ignore")
        top_neighbors = sims.sort_values(ascending=False).head(50)
        if top_neighbors.empty:
            return self._popular_fallback(n)

        weighted_sum = pd.Series(0.0, index=self.user_item_matrix.columns)
        weight_total = pd.Series(0.0, index=self.user_item_matrix.columns)
        for neighbor_id, similarity in top_neighbors.items():
            if similarity <= 0:
                continue
            neighbor_ratings = self.user_item_matrix.loc[neighbor_id]
            rated_mask = neighbor_ratings > 0
            weighted_sum[rated_mask] += similarity * neighbor_ratings[rated_mask]
            weight_total[rated_mask] += similarity

        predicted = weighted_sum / weight_total.replace(0, np.nan)
        predicted = predicted.fillna(0.0)
        predicted[target_ratings > 0] = -1.0

        top = (
            predicted.sort_values(ascending=False)
            .head(n)
            .reset_index()
            .values.tolist()
        )
        return [
            ScoredMovie(
                movie_id=int(m_id),
                title=str(
                    self.movies_df.loc[self.movies_df["movieId"] == int(m_id), "title"].iloc[0]
                ),
                score=float(score),
                explanation="Predicted from similar users' rating behavior.",
            )
            for m_id, score in top
            if float(score) > 0
        ]

    def content(self, user_id: int, n: int) -> list[ScoredMovie]:
        watched = self.ratings_df.loc[self.ratings_df["userId"] == user_id, "movieId"].tolist()
        if not watched:
            return self._popular_fallback(n)
        watched_idx = [self._movie_index[int(mid)] for mid in watched if int(mid) in self._movie_index]
        if not watched_idx:
            return self._popular_fallback(n)
        profile = np.asarray(self.tfidf_matrix[watched_idx].mean(axis=0))
        sims = cosine_similarity(profile, self.tfidf_matrix).flatten()
        ranked_idx = np.argsort(-sims)
        watched_set = set(int(x) for x in watched)
        out: list[ScoredMovie] = []
        for idx in ranked_idx:
            movie_id = int(self.movies_df.iloc[idx]["movieId"])
            if movie_id in watched_set:
                continue
            out.append(
                ScoredMovie(
                    movie_id=movie_id,
                    title=str(self.movies_df.iloc[idx]["title"]),
                    score=float(sims[idx]),
                    explanation="Similar genres/tags to your highly rated movies.",
                )
            )
            if len(out) >= n:
                break
        return out

    def hybrid(self, user_id: int, n: int, cf_weight: float | None = None) -> list[ScoredMovie]:
        cf_weight = cf_weight if cf_weight is not None else settings.default_hybrid_weight_cf
        cf_items = self.collaborative(user_id, n * 3)
        cb_items = self.content(user_id, n * 3)
        by_movie: dict[int, dict[str, float | str]] = {}

        for item in cf_items:
            by_movie[item.movie_id] = {
                "title": item.title,
                "cf": item.score,
                "cb": 0.0,
            }
        for item in cb_items:
            if item.movie_id not in by_movie:
                by_movie[item.movie_id] = {"title": item.title, "cf": 0.0, "cb": item.score}
            else:
                by_movie[item.movie_id]["cb"] = item.score

        out = []
        for movie_id, data in by_movie.items():
            score = cf_weight * float(data["cf"]) + (1 - cf_weight) * float(data["cb"])
            out.append(
                ScoredMovie(
                    movie_id=movie_id,
                    title=str(data["title"]),
                    score=score,
                    explanation="Hybrid score from collaborative and content signals.",
                )
            )
        out.sort(key=lambda x: x.score, reverse=True)
        return out[:n]
