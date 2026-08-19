"""Bus bunching predictor using exponential smoothing (NOT ML).

Uses statsmodels Holt-Winters / simple exponential smoothing to forecast
bus headway gaps. This is intentionally classical, not ML, per design doc.
"""

import numpy as np
from typing import Optional


def predict_headway_gap(
    recent_headways: list[float],
    forecast_horizon: int = 10,
) -> dict:
    """Forecast bus headway gap using exponential smoothing.

    Args:
        recent_headways: list of recent headway values (in meters or seconds)
        forecast_horizon: how many steps ahead to forecast

    Returns:
        dict with predicted_headway, current_trend, is_bunching, confidence
    """
    if len(recent_headways) < 3:
        return {
            "predicted_headway": recent_headways[-1] if recent_headways else 0.0,
            "current_trend": 0.0,
            "is_bunching": False,
            "confidence": 0.0,
            "method": "insufficient_data",
        }

    arr = np.array(recent_headways, dtype=float)

    try:
        from statsmodels.tsa.holtwinters import SimpleExpSmoothing
        model = SimpleExpSmoothing(arr, initialization_method="estimated")
        fit = model.fit(smoothing_level=0.3, optimized=False)
        forecast = fit.forecast(forecast_horizon)
        predicted = float(forecast[-1])
        trend = float(forecast[-1] - arr[-1])
    except Exception:
        # Fallback: weighted moving average
        weights = np.array([0.1, 0.2, 0.3, 0.4])[-len(arr):]
        weights = weights / weights.sum()
        predicted = float(np.dot(arr[-len(weights):], weights))
        trend = predicted - arr[-1]

    # Bunching threshold: headway variance spikes or headway drops below mean/2
    mean_hw = arr.mean()
    is_bunching = (predicted < mean_hw * 0.5) or (arr.std() > mean_hw * 0.8)

    # Confidence based on how stable recent headways are
    cv = arr.std() / max(mean_hw, 1e-6)  # coefficient of variation
    confidence = max(0.0, 1.0 - cv)

    return {
        "predicted_headway": round(predicted, 2),
        "current_trend": round(trend, 2),
        "is_bunching": bool(is_bunching),
        "confidence": round(confidence, 4),
        "method": "exponential_smoothing",
        "mean_headway": round(mean_hw, 2),
        "std_headway": round(float(arr.std()), 2),
    }


def compute_bunching_index(headways: list[float]) -> float:
    """Compute a 0-1 bunching index from a list of headways.

    0 = perfectly spaced, 1 = severe bunching.
    Uses coefficient of variation normalized to [0, 1].
    """
    if len(headways) < 2:
        return 0.0
    arr = np.array(headways, dtype=float)
    mean = arr.mean()
    if mean <= 0:
        return 1.0
    cv = arr.std() / mean
    # Normalize: CV of 0 = index 0, CV of 1+ = index ~1
    return min(cv, 1.0)
