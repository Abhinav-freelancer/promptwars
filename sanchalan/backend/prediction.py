"""CRS (Congestion Risk Score) calculation per Section 8.2 of the design doc."""

import math
from dataclasses import dataclass


@dataclass
class CRSCalculation:
    crs_score: float
    confidence: float
    vehicle_factor: float
    bus_factor: float
    weather_factor: float
    institutional_factor: float
    level: str  # green, amber, red
    explanation: str


# Weights: vehicle_flow + bus bunching dominate (per prompt Phase 2)
W1 = 0.60  # vehicle flow vs capacity
W2 = 0.40  # bus bunching (1 - OnTimeBusIndex)
# Weather/institutional are additive modifiers (not separate weights)
WEATHER_MODIFIER = 0.10  # adds up to 0.10 to CRS
INSTITUTIONAL_MODIFIER = 0.15  # adds up to 0.15 to CRS

# Thresholds (prompt Phase 2 spec)
RED_THRESHOLD = 0.70
AMBER_THRESHOLD = 0.40


def compute_crs(
    vehicle_flow: int,
    capacity_ratio: float,
    mean_speed: float,
    bus_headway_var: float,
    num_buses: int,
    weather_risk: float,
    institutional_flag: bool,
    confidence: float = 1.0,
) -> CRSCalculation:
    # Vehicle factor: flow relative to capacity
    # Normalize: high flow + low speed = high congestion risk
    speed_factor = 1.0 - min(mean_speed / 13.89, 1.0)  # 13.89 m/s = 50 km/h free flow
    flow_factor = min(vehicle_flow / 30.0, 1.0)  # 30 vehicles = high density on this corridor
    vehicle_factor = 0.5 * speed_factor + 0.5 * flow_factor

    # Bus bunching factor: headway variance → OnTimeBusIndex
    # Headway variance of 0 = perfect spacing = index 1.0 = factor 0
    # Variance > 1000 = severe bunching = index ~0 = factor ~1.0
    if num_buses < 2:
        bus_factor = 0.3  # insufficient data, moderate default
    else:
        on_time_index = 1.0 / (1.0 + bus_headway_var / 500.0)
        bus_factor = 1.0 - on_time_index

    # Weather factor: direct mapping
    weather_factor = min(max(weather_risk, 0.0), 1.0)

    # Institutional peak
    institutional_factor = 1.0 if institutional_flag else 0.0

    crs = W1 * vehicle_factor + W2 * bus_factor
    # Additive modifiers (not weighted, just push CRS up)
    crs += WEATHER_MODIFIER * weather_factor
    crs += INSTITUTIONAL_MODIFIER * institutional_factor
    crs = min(max(crs, 0.0), 1.0)

    if crs >= RED_THRESHOLD:
        level = "red"
    elif crs >= AMBER_THRESHOLD:
        level = "amber"
    else:
        level = "green"

    # Build human-readable explanation
    parts = []
    if vehicle_factor > 0.6:
        parts.append(f"High vehicle density ({vehicle_flow} vehicles, {mean_speed:.1f} m/s avg)")
    if bus_factor > 0.5 and num_buses >= 2:
        parts.append(f"Bus bunching detected (headway variance: {bus_headway_var:.0f})")
    if weather_factor > 0.3:
        parts.append(f"Weather risk elevated ({weather_factor:.0%})")
    if institutional_factor > 0:
        parts.append("Institutional peak active")

    explanation = "; ".join(parts) if parts else "Normal conditions"

    return CRSCalculation(
        crs_score=round(crs, 4),
        confidence=confidence,
        vehicle_factor=round(vehicle_factor, 4),
        bus_factor=round(bus_factor, 4),
        weather_factor=round(weather_factor, 4),
        institutional_factor=round(institutional_factor, 4),
        level=level,
        explanation=explanation,
    )
