"""SANCHALAN FastAPI backend — Full pipeline (Phases 1-5)."""

import asyncio
import warnings
from contextlib import asynccontextmanager
from datetime import datetime

warnings.filterwarnings("ignore", category=DeprecationWarning, module="traci")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from traci_client import client as traci_client
from database import (
    init_db, seed_corridors, get_db, SessionLocal,
    Corridor, CorridorFeature, Recommendation, Notification,
)
from prediction import compute_crs
from recommendation import generate_recommendations
from notification import notify_corridor_red, send_sms
from collections import defaultdict, deque

# Lazy imports for ML (may not be available)
ml_forecaster = None
ml_bunching = None

def _load_ml():
    global ml_forecaster, ml_bunching
    try:
        from ml import forecaster as _f
        ml_forecaster = _f
    except Exception as e:
        print(f"[ML] Could not load forecaster: {e}")
    try:
        from ml import bunching as _b
        ml_bunching = _b
    except Exception as e:
        print(f"[ML] Could not load bunching predictor: {e}")


# Shared state
sim_running = False
sim_speed = 1.0
sim_weather_risk = 0.0
sim_institutional_flag = False
latest_snapshot = None
latest_crs = {}
latest_recommendations = {}
latest_bunching = {}
ws_clients: list[WebSocket] = []
# Per-corridor headway history for bunching prediction (last 20 readings)
headway_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_corridors()
    _load_ml()
    asyncio.create_task(sim_loop())
    yield
    traci_client.stop()


app = FastAPI(
    title="SANCHALAN — Predictive Coordination Layer",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── REST API ────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    return {
        "status": "running",
        "sim_tick": traci_client.tick,
        "sim_running": sim_running,
        "active_ws_clients": len(ws_clients),
    }


@app.get("/api/corridors")
def list_corridors():
    db = SessionLocal()
    corridors = db.query(Corridor).all()
    db.close()
    return [
        {"id": c.id, "name": c.name, "lat": c.lat, "lon": c.lon, "lanes": c.lanes}
        for c in corridors
    ]


@app.get("/api/corridors/{corridor_id}/recommendation")
def get_recommendation(corridor_id: str):
    crs_data = latest_crs.get(corridor_id)
    if not crs_data:
        return {"corridor_id": corridor_id, "error": "no data yet"}

    ml_prediction = None
    if ml_forecaster and latest_snapshot:
        cm = latest_snapshot.corridors.get(corridor_id)
        if cm:
            ml_prediction = ml_forecaster.predict_crs_risk({
                "vehicle_flow": cm.vehicle_flow,
                "mean_speed": cm.mean_speed,
                "bus_headway_var": cm.bus_headway_var,
                "capacity_ratio": cm.capacity_ratio,
                "bus_count": cm.num_buses,
                "weather_risk": latest_snapshot.weather_risk,
                "crs_score": crs_data.crs_score,
            })

    bunching = latest_bunching.get(corridor_id)

    recs = latest_recommendations.get(corridor_id, [])
    return {
        "corridor_id": corridor_id,
        "crs_score": crs_data.crs_score,
        "crs_level": crs_data.level,
        "confidence": crs_data.confidence,
        "explanation": crs_data.explanation,
        "ml_prediction": ml_prediction,
        "bunching_prediction": bunching,
        "actions": [
            {
                "action_type": r.action_type,
                "action_detail": r.action_detail,
                "priority": r.priority,
                "signal_ids_affected": r.signal_ids_affected,
            }
            for r in recs
        ],
    }


@app.get("/api/corridors/{corridor_id}/forecast")
def get_forecast(corridor_id: str):
    crs_data = latest_crs.get(corridor_id)
    if not crs_data:
        return {"corridor_id": corridor_id, "error": "no data yet"}
    return {
        "corridor_id": corridor_id,
        "crs_score": crs_data.crs_score,
        "crs_level": crs_data.level,
        "confidence": crs_data.confidence,
        "explanation": crs_data.explanation,
        "vehicle_factor": crs_data.vehicle_factor,
        "bus_factor": crs_data.bus_factor,
        "weather_factor": crs_data.weather_factor,
        "institutional_factor": crs_data.institutional_factor,
    }


@app.get("/api/corridors/{corridor_id}/explain")
def get_explain(corridor_id: str):
    crs_data = latest_crs.get(corridor_id)
    if not crs_data:
        return {"corridor_id": corridor_id, "error": "no data yet"}
    snapshot = latest_snapshot
    corr_data = snapshot.corridors.get(corridor_id) if snapshot else None
    return {
        "corridor_id": corridor_id,
        "crs_score": crs_data.crs_score,
        "level": crs_data.level,
        "vehicle_flow": corr_data.vehicle_flow if corr_data else 0,
        "mean_speed_ms": round(corr_data.mean_speed, 2) if corr_data else 0,
        "mean_speed_kmh": round(corr_data.mean_speed * 3.6, 1) if corr_data else 0,
        "num_buses": corr_data.num_buses if corr_data else 0,
        "bus_headway_var": round(corr_data.bus_headway_var, 1) if corr_data else 0,
        "capacity_ratio": round(corr_data.capacity_ratio, 3) if corr_data else 0,
        "vehicle_types": corr_data.type_counts if corr_data else {},
        "weather_risk": snapshot.weather_risk if snapshot else 0,
        "institutional_peak": snapshot.institutional_flag if snapshot else False,
        "explanation": crs_data.explanation,
    }


@app.get("/api/corridors/{corridor_id}/features")
def get_features(corridor_id: str, limit: int = 20):
    db = SessionLocal()
    rows = (
        db.query(CorridorFeature)
        .filter(CorridorFeature.corridor_id == corridor_id)
        .order_by(CorridorFeature.id.desc())
        .limit(limit)
        .all()
    )
    db.close()
    return [
        {
            "tick": r.tick, "ts": r.ts.isoformat() if r.ts else None,
            "vehicle_flow": r.vehicle_flow, "crs_score": r.crs_score,
            "mean_speed": r.mean_speed, "bus_headway_var": r.bus_headway_var,
            "capacity_ratio": r.capacity_ratio, "confidence": r.confidence,
        }
        for r in reversed(rows)
    ]


@app.get("/api/corridors/{corridor_id}/history")
def get_history(corridor_id: str, limit: int = 100):
    db = SessionLocal()
    rows = (
        db.query(CorridorFeature)
        .filter(CorridorFeature.corridor_id == corridor_id)
        .order_by(CorridorFeature.id.desc())
        .limit(limit)
        .all()
    )
    db.close()
    return [
        {
            "tick": r.tick, "crs_score": r.crs_score,
            "vehicle_flow": r.vehicle_flow, "mean_speed": r.mean_speed,
            "bus_headway_var": r.bus_headway_var,
        }
        for r in reversed(rows)
    ]


@app.get("/api/recommendations")
def list_recommendations(limit: int = 20):
    db = SessionLocal()
    recs = db.query(Recommendation).order_by(Recommendation.id.desc()).limit(limit).all()
    db.close()
    return [
        {
            "id": r.id, "corridor_id": r.corridor_id,
            "action_type": r.action_type, "action_detail": r.action_detail,
            "status": r.status, "crs_score": r.crs_score, "tick": r.tick,
        }
        for r in recs
    ]


@app.post("/api/recommendations/{rec_id}/approve")
def approve_recommendation(rec_id: int):
    db = SessionLocal()
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        db.close()
        return {"error": "not found"}
    rec.status = "approved"
    rec.approved_by = "operator"
    rec.ts_approved = datetime.utcnow()
    db.commit()
    result = _execute_action(rec)
    db.close()
    return {"id": rec_id, "status": "approved", "execution": result}


@app.post("/api/sim/start")
def sim_start():
    global sim_running
    traci_client.start()
    sim_running = True
    return {"status": "started", "sim_tick": traci_client.tick, "sim_running": sim_running}


@app.post("/api/sim/stop")
def sim_stop():
    global sim_running
    sim_running = False
    traci_client.stop()
    return {"status": "stopped"}


@app.post("/api/sim/step")
def sim_step(n: int = 10):
    global latest_snapshot, latest_crs, latest_recommendations, latest_bunching
    if not traci_client.running:
        traci_client.start()
    for _ in range(n):
        snapshot = traci_client.step(
            weather_risk=sim_weather_risk,
            institutional_flag=sim_institutional_flag,
        )
    latest_snapshot = snapshot
    _process_snapshot(snapshot)
    return {"sim_tick": snapshot.tick, "steps": n, "total_vehicles": snapshot.total_vehicles}


@app.post("/api/sim/weather")
def set_weather(risk: float):
    global sim_weather_risk
    sim_weather_risk = max(0.0, min(risk, 1.0))
    return {"weather_risk": sim_weather_risk}


@app.post("/api/sim/institutional")
def set_institutional(active: bool):
    global sim_institutional_flag
    sim_institutional_flag = active
    return {"institutional_flag": sim_institutional_flag}


@app.post("/api/sim/speed")
def set_speed(speed: float):
    global sim_speed
    sim_speed = max(0.1, min(speed, 10.0))
    return {"sim_speed": sim_speed}


@app.get("/api/sim/snapshot")
def get_snapshot():
    if not latest_snapshot:
        return {"error": "no snapshot yet"}
    corridors = {}
    for cid, cm in latest_snapshot.corridors.items():
        corridors[cid] = {
            "vehicle_flow": cm.vehicle_flow, "type_counts": cm.type_counts,
            "mean_speed": round(cm.mean_speed, 2), "num_buses": cm.num_buses,
            "bus_headway_var": round(cm.bus_headway_var, 1),
            "capacity_ratio": round(cm.capacity_ratio, 3),
        }
    return {
        "tick": latest_snapshot.tick, "time_sec": latest_snapshot.time_sec,
        "total_vehicles": latest_snapshot.total_vehicles,
        "weather_risk": latest_snapshot.weather_risk,
        "institutional_flag": latest_snapshot.institutional_flag,
        "corridors": corridors, "signals": latest_snapshot.signals,
    }


@app.get("/api/vehicles")
def get_vehicles():
    if not latest_snapshot:
        return {"error": "no snapshot yet"}
    all_vehicles = []
    for cid, cm in latest_snapshot.corridors.items():
        for v in cm.all_vehicles:
            all_vehicles.append({**v, "corridor_id": cid})
    return {"count": len(all_vehicles), "vehicles": all_vehicles}


@app.post("/api/ml/train")
def train_ml_model():
    if not ml_forecaster:
        return {"error": "ML forecaster not loaded"}
    db = SessionLocal()
    report = ml_forecaster.maybe_retrain(db, CorridorFeature, min_rows=50)
    db.close()
    if report is None:
        return {"status": "skipped", "reason": "insufficient data or class imbalance"}
    return {"status": "trained", "report": report}


@app.post("/api/notify/test")
def test_notification():
    result = send_sms("SANCHALAN test notification from API")
    return result


# ─── WebSocket ────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        pass
    finally:
        if websocket in ws_clients:
            ws_clients.remove(websocket)


# ─── Simulation Loop ─────────────────────────────────────────────

async def sim_loop():
    global latest_snapshot, latest_crs, latest_recommendations, sim_running

    while True:
        await asyncio.sleep(sim_speed)
        if not sim_running:
            continue

        snapshot = traci_client.step(
            weather_risk=sim_weather_risk,
            institutional_flag=sim_institutional_flag,
        )
        latest_snapshot = snapshot
        _process_snapshot(snapshot)

        # Broadcast to WebSocket clients
        ws_payload = _build_ws_payload(snapshot, latest_crs, latest_recommendations)
        disconnected = []
        for ws in ws_clients:
            try:
                await ws.send_json(ws_payload)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            ws_clients.remove(ws)


def _process_snapshot(snapshot):
    """Compute CRS, generate recommendations, persist to DB, trigger notifications."""
    global latest_crs, latest_recommendations, latest_bunching

    crs_results = {}
    recs_results = {}
    bunching_results = {}
    db = SessionLocal()
    newly_red = []

    for cid, cm in snapshot.corridors.items():
        crs = compute_crs(
            vehicle_flow=cm.vehicle_flow,
            capacity_ratio=cm.capacity_ratio,
            mean_speed=cm.mean_speed,
            bus_headway_var=cm.bus_headway_var,
            num_buses=cm.num_buses,
            weather_risk=snapshot.weather_risk,
            institutional_flag=snapshot.institutional_flag,
        )
        crs_results[cid] = crs

        # Track headway history and run bunching predictor
        headway_history[cid].append(cm.bus_headway_var)
        if ml_bunching and len(headway_history[cid]) >= 3:
            bunching_results[cid] = ml_bunching.predict_headway_gap(
                list(headway_history[cid])
            )

        db.add(CorridorFeature(
            corridor_id=cid, ts=datetime.utcnow(), tick=snapshot.tick,
            vehicle_flow=cm.vehicle_flow,
            car_count=cm.type_counts.get("car", 0),
            tw_count=cm.type_counts.get("twowheeler", 0),
            auto_count=cm.type_counts.get("auto", 0),
            bus_count=cm.num_buses,
            mean_speed=cm.mean_speed,
            bus_headway_var=cm.bus_headway_var,
            vehicle_occupancy_pct=cm.vehicle_occupancy_pct,
            capacity_ratio=cm.capacity_ratio,
            weather_risk=snapshot.weather_risk,
            institutional_flag=snapshot.institutional_flag,
            crs_score=crs.crs_score,
            confidence=crs.confidence,
        ))

        if crs.level in ("amber", "red"):
            nearby_max = max(
                (v.crs_score for k, v in crs_results.items() if k != cid),
                default=0.0,
            )
            recs = generate_recommendations(
                corridor_id=cid, crs_score=crs.crs_score, crs_level=crs.level,
                num_buses=cm.num_buses, bus_headway_var=cm.bus_headway_var,
                vehicle_flow=cm.vehicle_flow, nearby_corridor_risk=nearby_max,
            )
            recs_results[cid] = recs

            for rec in recs:
                db.add(Recommendation(
                    corridor_id=rec.corridor_id, ts=rec.ts, tick=snapshot.tick,
                    action_type=rec.action_type, action_detail=rec.action_detail,
                    status="pending", crs_score=crs.crs_score,
                    signal_ids_affected=",".join(rec.signal_ids_affected),
                ))

            # Phase 5: Trigger notification on newly red corridors
            prev = latest_crs.get(cid)
            if crs.level == "red" and (not prev or prev.level != "red"):
                newly_red.append((cid, crs.crs_score, recs))

    db.commit()
    db.close()
    latest_crs = crs_results
    latest_recommendations = recs_results
    latest_bunching = bunching_results

    # Send SMS for newly red corridors
    for cid, score, recs in newly_red:
        rec_dicts = [{"action_type": r.action_type} for r in recs]
        notify_result = notify_corridor_red(cid, score, rec_dicts)
        print(f"[NOTIFY] {cid}: {notify_result['notification']['status']}")


def _build_ws_payload(snapshot, crs_results, recs_results):
    corridors = {}
    for cid, cm in snapshot.corridors.items():
        crs = crs_results.get(cid)
        corridors[cid] = {
            "vehicle_flow": cm.vehicle_flow,
            "mean_speed": round(cm.mean_speed * 3.6, 1),
            "num_buses": cm.num_buses,
            "bus_headway_var": round(cm.bus_headway_var, 1),
            "crs_score": crs.crs_score if crs else 0,
            "crs_level": crs.level if crs else "green",
            "explanation": crs.explanation if crs else "",
            "type_counts": cm.type_counts,
        }

    recs_list = []
    for cid, recs in recs_results.items():
        for rec in recs:
            recs_list.append({
                "corridor_id": rec.corridor_id,
                "action_type": rec.action_type,
                "action_detail": rec.action_detail,
                "priority": rec.priority,
            })

    return {
        "tick": snapshot.tick, "time_sec": snapshot.time_sec,
        "total_vehicles": snapshot.total_vehicles,
        "weather_risk": snapshot.weather_risk,
        "institutional_flag": snapshot.institutional_flag,
        "corridors": corridors, "recommendations": recs_list,
        "signals": snapshot.signals,
    }


def _execute_action(rec: Recommendation) -> dict:
    if rec.action_type == "signal_priority":
        affected = [s.strip() for s in rec.signal_ids_affected.split(",") if s.strip()]
        results = []
        for sid in affected:
            ok = traci_client.apply_signal_priority(sid, green_duration=40)
            results.append({"signal": sid, "extended": ok})
        return {"signal_priority": results}

    elif rec.action_type == "bus_dispatch":
        vid = traci_client.inject_bus("bus_route_1_wb")
        return {"bus_dispatched": vid is not None, "vehicle_id": vid}

    elif rec.action_type == "notify_only":
        result = notify_corridor_red(rec.corridor_id, rec.crs_score, [{"action_type": "notify_only"}])
        db = SessionLocal()
        db.add(Notification(
            recommendation_id=rec.id, channel="sms",
            message=rec.action_detail,
            status=result["notification"]["status"],
        ))
        db.commit()
        db.close()
        return {"notification": result["notification"]}

    return {"unknown_action": rec.action_type}
