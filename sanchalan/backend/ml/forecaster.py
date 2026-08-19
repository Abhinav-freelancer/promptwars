"""XGBoost-based CRS forecaster — predicts CRS 15-30 min ahead.

Trains on simulated historical data from corridor_features table.
When no trained model exists, falls back to the rule-based CRS from prediction.py.
"""

import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

MODEL_PATH = os.path.join(os.path.dirname(__file__), "crs_forecaster.pkl")

# Feature columns used for prediction
FEATURE_COLS = [
    "vehicle_flow", "mean_speed", "bus_headway_var", "capacity_ratio",
    "bus_count", "weather_risk", "crs_score",
]

LABEL_COL = "crs_crosses_red"  # 1 if CRS >= RED_THRESHOLD within next 20 ticks


def generate_training_data(db_session, corridor_features_table, red_threshold: float = 0.70, horizon: int = 20):
    """Generate labeled training data from historical corridor features.

    For each row, look ahead `horizon` ticks on the same corridor.
    Label = 1 if any future CRS >= red_threshold.
    """
    rows = db_session.query(corridor_features_table).order_by(
        corridor_features_table.corridor_id,
        corridor_features_table.tick,
    ).all()

    if not rows:
        return None, None

    df = pd.DataFrame([{
        "corridor_id": r.corridor_id,
        "tick": r.tick,
        "vehicle_flow": r.vehicle_flow,
        "mean_speed": r.mean_speed,
        "bus_headway_var": r.bus_headway_var,
        "capacity_ratio": r.capacity_ratio,
        "bus_count": r.bus_count,
        "weather_risk": r.weather_risk,
        "crs_score": r.crs_score,
    } for r in rows])

    # Vectorized label generation: for each corridor, check if any future CRS
    # within `horizon` ticks crosses red_threshold
    labels = []
    for cid, group in df.groupby("corridor_id"):
        scores = group["crs_score"].values
        ticks = group["tick"].values
        n = len(scores)
        label_arr = np.zeros(n, dtype=int)
        for i in range(n):
            # Find rows within horizon ticks ahead
            future_mask = (ticks > ticks[i]) & (ticks <= ticks[i] + horizon)
            if future_mask.any() and (scores[future_mask] >= red_threshold).any():
                label_arr[i] = 1
        group[LABEL_COL] = label_arr
        labels.append(group)

    df = pd.concat(labels)
    df = df.sort_values(["corridor_id", "tick"]).reset_index(drop=True)
    return df[FEATURE_COLS].values, df[LABEL_COL].values


def train_model(X: np.ndarray, y: np.ndarray):
    """Train XGBoost classifier and save to disk."""
    from xgboost import XGBClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    report = classification_report(y_test, y_pred, output_dict=True)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    print(f"[ML] Model trained. Saved to {MODEL_PATH}")
    print(f"[ML] Precision: {report['1']['precision']:.3f}, Recall: {report['1']['recall']:.3f}")
    return model, report


def load_model():
    """Load trained model from disk, or return None."""
    if not os.path.exists(MODEL_PATH):
        return None
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def predict_crs_risk(features: dict) -> dict:
    """Predict probability of CRS crossing red threshold in next 15-30 min.

    Args:
        features: dict with keys matching FEATURE_COLS

    Returns:
        dict with 'probability', 'confidence', 'model_used'
    """
    model = load_model()
    if model is None:
        return {"probability": None, "confidence": 0.0, "model_used": "rule_based"}

    x = np.array([[features.get(col, 0.0) for col in FEATURE_COLS]])
    prob = float(model.predict_proba(x)[0, 1])
    confidence = max(prob, 1.0 - prob)  # how confident the model is

    return {
        "probability": round(prob, 4),
        "confidence": round(confidence, 4),
        "model_used": "xgboost",
    }


def maybe_retrain(db_session, corridor_features_table, min_rows: int = 50):
    """Retrain model if we have enough new data and model is stale or missing."""
    count = db_session.query(corridor_features_table).count()
    if count < min_rows:
        print(f"[ML] Only {count} rows, need {min_rows} for training. Skipping.")
        return None

    X, y = generate_training_data(db_session, corridor_features_table)
    if X is None or len(X) < min_rows:
        return None

    # Check class balance
    pos_rate = y.mean()
    if pos_rate < 0.05 or pos_rate > 0.95:
        print(f"[ML] Class imbalance ({pos_rate:.1%} positive). Skipping retrain.")
        return None

    model, report = train_model(X, y)
    return report
