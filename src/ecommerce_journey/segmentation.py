"""Behavioral visitor segmentation.

Clusters visitors on engagement and funnel-behavior features derived from
``visitor_segmentation_features`` (see sql/05_segmentation.sql). The source
data has no category, price, or demographic fields, so segments describe
*how a visitor behaves* (engagement depth, funnel progression, recency),
not product taste or persona.

Cluster count is chosen by silhouette score over a small candidate range
rather than fixed in advance, and cluster labels are assigned by ranking
centroids on purchase and engagement behavior rather than hardcoded per
run, so labels stay meaningful if the underlying data changes.
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = (
    "recency_days",
    "session_count",
    "avg_events_per_session",
    "avg_session_duration_minutes",
    "cart_session_rate_pct",
    "cart_to_purchase_rate_pct",
    "beyond_browse_session_rate_pct",
)

MIN_CLUSTERS = 3
MAX_CLUSTERS = 6
RANDOM_STATE = 42

# Silhouette scoring and the elbow method use a bounded sample for speed on
# multi-million-row visitor tables; the fitted model is then applied to all
# visitors via `.predict`.
SAMPLE_SIZE_FOR_MODEL_SELECTION = 50_000


def load_features(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return connection.execute(
        "SELECT * FROM visitor_segmentation_features"
    ).df()


def _prepare_matrix(features: pd.DataFrame) -> tuple[np.ndarray, StandardScaler]:
    matrix = features[list(FEATURE_COLUMNS)].fillna(0.0).to_numpy()
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    return scaled, scaler


def choose_k(scaled_matrix: np.ndarray, random_state: int = RANDOM_STATE) -> tuple[int, pd.DataFrame]:
    """Pick cluster count by silhouette score over a small candidate range."""
    if len(scaled_matrix) > SAMPLE_SIZE_FOR_MODEL_SELECTION:
        rng = np.random.default_rng(random_state)
        sample_idx = rng.choice(
            len(scaled_matrix), size=SAMPLE_SIZE_FOR_MODEL_SELECTION, replace=False
        )
        sample = scaled_matrix[sample_idx]
    else:
        sample = scaled_matrix

    scores = []
    for k in range(MIN_CLUSTERS, MAX_CLUSTERS + 1):
        model = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        labels = model.fit_predict(sample)
        score = silhouette_score(sample, labels)
        scores.append({"k": k, "silhouette_score": score})

    scores_df = pd.DataFrame(scores)
    best_k = int(scores_df.loc[scores_df["silhouette_score"].idxmax(), "k"])
    return best_k, scores_df


def _label_segments(profiles: pd.DataFrame) -> dict[int, str]:
    """Rank cluster centroids to assign human-readable behavioral labels.

    Ranking, not hardcoded thresholds, so labels stay sensible if the
    pipeline is re-run on a different time window or a larger sample.
    """
    ranked_by_purchase = profiles["cart_to_purchase_rate_pct"].rank(ascending=False)
    ranked_by_engagement = profiles["avg_events_per_session"].rank(ascending=False)
    ranked_by_recency = profiles["recency_days"].rank(ascending=True)
    ranked_by_frequency = profiles["session_count"].rank(ascending=False)

    labels: dict[int, str] = {}
    for cluster_id in profiles.index:
        purchase_rank = ranked_by_purchase.loc[cluster_id]
        engagement_rank = ranked_by_engagement.loc[cluster_id]
        recency_rank = ranked_by_recency.loc[cluster_id]
        frequency_rank = ranked_by_frequency.loc[cluster_id]
        n = len(profiles)

        if purchase_rank <= n * 0.34 and frequency_rank <= n * 0.34:
            labels[cluster_id] = "loyal repeat purchasers"
        elif purchase_rank <= n * 0.34:
            labels[cluster_id] = "high-intent converters"
        elif engagement_rank <= n * 0.34 and recency_rank <= n * 0.34:
            labels[cluster_id] = "active high-intent browsers"
        elif recency_rank > n * 0.67:
            labels[cluster_id] = "lapsed / one-and-done"
        else:
            labels[cluster_id] = "casual browsers"

    return labels


def fit_segments(
    features: pd.DataFrame, random_state: int = RANDOM_STATE
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fit segmentation and return (assignments, profiles, model_selection).

    assignments: one row per visitor with `segment_id` and `segment_label`.
    profiles: one row per segment with centroid feature values and size.
    model_selection: silhouette score per candidate k, for transparency.
    """
    scaled_matrix, scaler = _prepare_matrix(features)
    best_k, model_selection = choose_k(scaled_matrix, random_state=random_state)

    model = KMeans(n_clusters=best_k, n_init=10, random_state=random_state)
    cluster_ids = model.fit_predict(scaled_matrix)

    assignments = features[["visitor_id"]].copy()
    assignments["segment_id"] = cluster_ids

    profiles = (
        assignments.join(features[list(FEATURE_COLUMNS)])
        .groupby("segment_id")[list(FEATURE_COLUMNS)]
        .mean()
        .round(2)
    )
    profiles["visitor_count"] = assignments["segment_id"].value_counts().sort_index()
    profiles["visitor_share_pct"] = (
        100 * profiles["visitor_count"] / profiles["visitor_count"].sum()
    ).round(2)

    label_map = _label_segments(profiles)
    profiles["segment_label"] = profiles.index.map(label_map)
    assignments["segment_label"] = assignments["segment_id"].map(label_map)

    profiles = profiles.reset_index()
    return assignments, profiles, model_selection
