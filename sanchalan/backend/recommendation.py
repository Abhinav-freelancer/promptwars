"""Rule-based recommendation engine (Section 12 — not ML, deliberately)."""

from dataclasses import dataclass, field
from datetime import datetime
from prediction import RED_THRESHOLD


@dataclass
class Recommendation:
    corridor_id: str
    action_type: str  # signal_priority, bus_dispatch, notify_only, reroute_advisory
    action_detail: str
    priority: int  # 1=highest
    signal_ids_affected: list = field(default_factory=list)
    ts: datetime = field(default_factory=datetime.utcnow)


def generate_recommendations(
    corridor_id: str,
    crs_score: float,
    crs_level: str,
    num_buses: int,
    bus_headway_var: float,
    vehicle_flow: int,
    nearby_corridor_risk: float = 0.0,
) -> list[Recommendation]:
    recs = []

    if crs_level == "red":
        # Priority 1: Signal priority for buses on this corridor
        recs.append(Recommendation(
            corridor_id=corridor_id,
            action_type="signal_priority",
            action_detail=(
                f"Extend green phase by 15s at signals on {corridor_id} "
                f"to prioritise bus flow (CRS: {crs_score:.2f})"
            ),
            priority=1,
            signal_ids_affected=_corridor_signals(corridor_id),
        ))

        # Priority 2: Dispatch extra bus if bunching is severe
        if bus_headway_var > 800 or num_buses < 2:
            recs.append(Recommendation(
                corridor_id=corridor_id,
                action_type="bus_dispatch",
                action_detail=(
                    f"Dispatch 1 extra bus from depot to route serving {corridor_id} "
                    f"(headway variance: {bus_headway_var:.0f}, {num_buses} buses active)"
                ),
                priority=2,
            ))

        # Priority 3: Notify commuters
        recs.append(Recommendation(
            corridor_id=corridor_id,
            action_type="notify_only",
            action_detail=(
                f"Send SMS/IVR advisory: '{corridor_id.replace('_', ' ').title()}' corridor "
                f"expected severe congestion in 15-20 min. Use alternate route."
            ),
            priority=3,
        ))

    elif crs_level == "amber":
        # Signal priority if no adjacent corridor at risk
        if nearby_corridor_risk < RED_THRESHOLD:
            recs.append(Recommendation(
                corridor_id=corridor_id,
                action_type="signal_priority",
                action_detail=(
                    f"Extend green phase by 10s at signals on {corridor_id} "
                    f"(CRS: {crs_score:.2f}, amber alert)"
                ),
                priority=1,
                signal_ids_affected=_corridor_signals(corridor_id),
            ))

        # Recommend dispatch only if bus bunching is borderline
        if bus_headway_var > 500:
            recs.append(Recommendation(
                corridor_id=corridor_id,
                action_type="bus_dispatch",
                action_detail=(
                    f"Stage 1 standby: prepare extra bus at depot for {corridor_id} "
                    f"(headway variance rising: {bus_headway_var:.0f})"
                ),
                priority=2,
            ))

        # Lighter notification
        recs.append(Recommendation(
            corridor_id=corridor_id,
            action_type="notify_only",
            action_detail=(
                f"Push notification via partner apps: "
                f"'{corridor_id.replace('_', ' ').title()}' congestion building. "
                f"Consider departing 10 min early."
            ),
            priority=3,
        ))

    # Green: no action needed
    return recs


def _corridor_signals(corridor_id: str) -> list[str]:
    """Map corridor to the traffic light IDs it contains."""
    mapping = {
        "mg_road_west": ["B_signal_1"],
        "mg_road_central": ["B_signal_1", "C_signal_2", "D_signal_3"],
        "mg_road_east": ["D_signal_3"],
        "brigade_road": ["C_signal_2", "F_signal_4"],
        "mg_road_west_rev": ["B_signal_1"],
        "mg_road_central_rev": ["B_signal_1", "C_signal_2", "D_signal_3"],
        "mg_road_east_rev": ["D_signal_3"],
        "brigade_road_rev": ["C_signal_2", "F_signal_4"],
    }
    return mapping.get(corridor_id, [])
