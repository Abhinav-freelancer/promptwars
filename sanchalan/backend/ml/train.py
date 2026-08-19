"""Training data generator — runs SUMO under varied synthetic scenarios
to produce labeled corridor_features rows for the XGBoost forecaster.

Usage:
    python -m ml.train          # generate data + train model
    python -m ml.train --data   # generate data only
    python -m ml.train --train  # train only (requires existing data)
"""

import os
import sys
import warnings
import argparse
from datetime import datetime
from collections import defaultdict

warnings.filterwarnings("ignore", category=DeprecationWarning)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import traci
from config import SUMO_BIN, SUMO_CFG, ALL_CORRIDOR_EDGES, CORRIDOR_LANES, LANE_CAPACITY, SIGNAL_IDS
from database import init_db, SessionLocal, CorridorFeature
from prediction import compute_crs, RED_THRESHOLD

SCENARIOS = [
    {"weather": 0.0, "institutional": False, "label": "normal"},
    {"weather": 0.0, "institutional": True, "label": "institutional_peak"},
    {"weather": 0.5, "institutional": False, "label": "light_rain"},
    {"weather": 0.8, "institutional": False, "label": "heavy_rain"},
    {"weather": 0.9, "institutional": True, "label": "rain_peak_combined"},
    {"weather": 0.3, "institutional": False, "label": "moderate_rain"},
    {"weather": 0.0, "institutional": True, "label": "morning_rush"},
    {"weather": 0.6, "institutional": True, "label": "evening_storm_rush"},
]


def run_scenario(scenario: dict, ticks: int = 300) -> list[dict]:
    """Run a single scenario via TraCI and return per-corridor per-tick feature rows."""
    rows = []

    cmd = [
        SUMO_BIN, "-c", SUMO_CFG,
        "--no-step-log", "--duration-log.disable",
        "--start", "--quit-on-end", "--xml-validation", "never",
    ]
    traci.start(cmd, numRetries=5)

    try:
        for tick in range(ticks):
            traci.simulationStep()

            for corr_id, edges in ALL_CORRIDOR_EDGES.items():
                type_counts = {}
                total_speed = 0.0
                edge_count = 0
                bus_ids = []

                for edge_id in edges:
                    veh_ids = traci.edge.getLastStepVehicleIDs(edge_id)
                    for vid in veh_ids:
                        try:
                            vtype = traci.vehicle.getTypeID(vid)
                            speed = traci.vehicle.getSpeed(vid)
                            max_speed = traci.vehicle.getMaxSpeed(vid)
                            if vtype == "bus":
                                bus_ids.append(vid)
                            type_counts[vtype] = type_counts.get(vtype, 0) + 1
                            total_speed += speed
                            edge_count += 1
                        except Exception:
                            continue

                veh_count = sum(type_counts.values())
                mean_speed = total_speed / max(edge_count, 1)
                lanes = CORRIDOR_LANES.get(corr_id, 2)
                capacity = sum(LANE_CAPACITY.get(t, 0.1) * c for t, c in type_counts.items()) * lanes

                headway_var = 0.0
                if len(bus_ids) >= 2:
                    positions = []
                    for bid in bus_ids:
                        try:
                            positions.append(traci.vehicle.getLanePosition(bid))
                        except Exception:
                            continue
                    if len(positions) >= 2:
                        positions.sort()
                        headways = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
                        mean_hw = sum(headways) / len(headways)
                        headway_var = sum((h - mean_hw) ** 2 for h in headways) / len(headways)

                crs = compute_crs(
                    vehicle_flow=veh_count,
                    capacity_ratio=min(capacity, 1.0),
                    mean_speed=mean_speed,
                    bus_headway_var=headway_var,
                    num_buses=len(bus_ids),
                    weather_risk=scenario["weather"],
                    institutional_flag=scenario["institutional"],
                )

                rows.append({
                    "corridor_id": corr_id,
                    "tick": tick,
                    "vehicle_flow": veh_count,
                    "car_count": type_counts.get("car", 0),
                    "tw_count": type_counts.get("twowheeler", 0),
                    "auto_count": type_counts.get("auto", 0),
                    "bus_count": len(bus_ids),
                    "mean_speed": mean_speed,
                    "bus_headway_var": headway_var,
                    "capacity_ratio": min(capacity, 1.0),
                    "weather_risk": scenario["weather"],
                    "institutional_flag": scenario["institutional"],
                    "crs_score": crs.crs_score,
                })
    finally:
        traci.close()

    return rows


def generate_all_data(ticks_per_scenario: int = 300):
    """Run all scenarios and save to DB."""
    init_db()
    db = SessionLocal()

    total_rows = 0
    for i, scenario in enumerate(SCENARIOS):
        print(f"[TRAIN] Scenario {i + 1}/{len(SCENARIOS)}: {scenario['label']} "
              f"(weather={scenario['weather']}, institutional={scenario['institutional']})")
        rows = run_scenario(scenario, ticks=ticks_per_scenario)

        for r in rows:
            db.add(CorridorFeature(
                corridor_id=r["corridor_id"],
                ts=datetime.utcnow(),
                tick=r["tick"],
                vehicle_flow=r["vehicle_flow"],
                car_count=r["car_count"],
                tw_count=r["tw_count"],
                auto_count=r["auto_count"],
                bus_count=r["bus_count"],
                mean_speed=r["mean_speed"],
                bus_headway_var=r["bus_headway_var"],
                vehicle_occupancy_pct=0.0,
                capacity_ratio=r["capacity_ratio"],
                weather_risk=r["weather_risk"],
                institutional_flag=r["institutional_flag"],
                crs_score=r["crs_score"],
                confidence=1.0,
            ))
            total_rows += 1

        db.commit()
        print(f"  -> {len(rows)} rows saved")

    db.close()
    print(f"\n[TRAIN] Total: {total_rows} rows generated across {len(SCENARIOS)} scenarios")
    return total_rows


def train_and_evaluate():
    """Train the XGBoost model and run backtest."""
    from ml.forecaster import generate_training_data, train_model, MODEL_PATH

    db = SessionLocal()
    count = db.query(CorridorFeature).count()
    print(f"\n[TRAIN] DB has {count} corridor_features rows")

    if count < 30:
        print("[TRAIN] Not enough data. Run with --data first.")
        db.close()
        return None

    X, y = generate_training_data(db, CorridorFeature, red_threshold=RED_THRESHOLD, horizon=20)
    db.close()

    if X is None:
        print("[TRAIN] No training data generated.")
        return None

    print(f"[TRAIN] Features: {X.shape[0]} samples, {X.shape[1]} features")
    pos_rate = y.mean()
    print(f"[TRAIN] Positive rate (CRS crosses red within 20 ticks): {pos_rate:.1%}")

    if pos_rate < 0.05 or pos_rate > 0.95:
        print("[TRAIN] Severe class imbalance. Retrying with relaxed threshold (0.50) and horizon (30)...")
        db2 = SessionLocal()
        X2, y2 = generate_training_data(db2, CorridorFeature, red_threshold=0.50, horizon=30)
        db2.close()
        if X2 is not None and len(X2) > 30:
            pr2 = y2.mean()
            print(f"[TRAIN] Relaxed: {len(X2)} samples, {pr2:.1%} positive")
            if 0.05 <= pr2 <= 0.95:
                X, y = X2, y2
                pos_rate = pr2
            else:
                print("[TRAIN] Still imbalanced, proceeding anyway...")
        else:
            print("[TRAIN] No valid data with relaxed threshold either.")

    model, report = train_model(X, y)

    print("\n[TRAIN] === Backtest Results (80/20 split) ===")
    print(f"  Precision (red):  {report.get('1', {}).get('precision', 0):.3f}")
    print(f"  Recall (red):     {report.get('1', {}).get('recall', 0):.3f}")
    print(f"  F1 (red):         {report.get('1', {}).get('f1-score', 0):.3f}")
    print(f"  Accuracy:         {report.get('accuracy', 0):.3f}")
    print(f"\n[TRAIN] Model saved to {MODEL_PATH}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate training data and/or train model")
    parser.add_argument("--data", action="store_true", help="Generate synthetic training data only")
    parser.add_argument("--train", action="store_true", help="Train the XGBoost model only")
    parser.add_argument("--ticks", type=int, default=300, help="Ticks per scenario (default: 300)")
    args = parser.parse_args()

    if args.data:
        generate_all_data(ticks_per_scenario=args.ticks)
    elif args.train:
        train_and_evaluate()
    else:
        generate_all_data(ticks_per_scenario=args.ticks)
        train_and_evaluate()
