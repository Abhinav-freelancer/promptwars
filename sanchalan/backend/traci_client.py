"""TraCI client wrapper for SUMO simulation control."""

import os
import sys
import warnings
from dataclasses import dataclass, field

import traci
from traci.exceptions import TraCIException

from config import (
    SUMO_BIN, SUMO_CFG, ALL_CORRIDOR_EDGES, CORRIDOR_LANES,
    LANE_CAPACITY, SIGNAL_IDS,
)


@dataclass
class CorridorMetrics:
    corridor_id: str
    vehicle_flow: int = 0
    type_counts: dict = field(default_factory=dict)
    mean_speed: float = 0.0
    num_buses: int = 0
    bus_headway_var: float = 0.0
    vehicle_occupancy_pct: float = 0.0
    capacity_ratio: float = 0.0
    all_vehicles: list = field(default_factory=list)


@dataclass
class SimulationSnapshot:
    tick: int
    time_sec: float
    corridors: dict
    signals: dict
    total_vehicles: int = 0
    weather_risk: float = 0.0
    institutional_flag: bool = False


class TraCIClient:
    def __init__(self):
        self.running = False
        self.tick = 0
        self.start_time = 0.0

    def start(self):
        if self.running:
            return
        cmd = [SUMO_BIN, "-c", SUMO_CFG, "--no-step-log",
               "--duration-log.disable", "--start", "--quit-on-end",
               "--xml-validation", "never"]
        print(f"[TraCI] Starting SUMO: {SUMO_BIN}")
        traci.start(cmd, numRetries=10)
        self.running = True
        self.tick = 0
        self.start_time = 0.0
        print("[TraCI] Connected.")

    def stop(self):
        if self.running:
            try:
                traci.close()
            except TraCIException:
                pass
            self.running = False
            print("[TraCI] Stopped.")

    def step(self, weather_risk: float = 0.0, institutional_flag: bool = False) -> SimulationSnapshot:
        if not self.running:
            self.start()
        traci.simulationStep()
        self.tick += 1

        corridors = {}
        total_vehicles = 0

        for corr_id, edges in ALL_CORRIDOR_EDGES.items():
            type_counts = {}
            total_speed = 0.0
            edge_count = 0
            all_vehicles = []
            bus_ids = []

            for edge_id in edges:
                veh_ids = traci.edge.getLastStepVehicleIDs(edge_id)
                for vid in veh_ids:
                    try:
                        vtype = traci.vehicle.getTypeID(vid)
                        speed = traci.vehicle.getSpeed(vid)
                        pos = traci.vehicle.getLanePosition(vid)
                        # Use speed ratio as proxy for occupancy
                        max_speed = traci.vehicle.getMaxSpeed(vid)
                        occ = (1.0 - speed / max_speed) if max_speed > 0 else 0.0
                        passengers = 0
                        if vtype == "bus":
                            bus_ids.append(vid)
                            try:
                                passengers = traci.vehicle.getPersonNumber(vid)
                            except (TraCIException, AttributeError):
                                passengers = 20
                        type_counts[vtype] = type_counts.get(vtype, 0) + 1
                        total_speed += speed
                        edge_count += 1
                        all_vehicles.append({
                            "id": vid, "type": vtype,
                            "lane_position": pos, "speed": speed,
                            "occupancy": occ, "passengers": passengers,
                        })
                    except TraCIException:
                        continue

            veh_count = sum(type_counts.values())
            total_vehicles += veh_count

            mean_speed = total_speed / max(edge_count, 1)
            lanes = CORRIDOR_LANES.get(corr_id, 2)
            capacity = sum(LANE_CAPACITY.get(t, 0.1) * c for t, c in type_counts.items()) * lanes

            headway_var = self._headway_variance(bus_ids)
            occ_pct = self._avg_occupancy(all_vehicles)

            corridors[corr_id] = CorridorMetrics(
                corridor_id=corr_id,
                vehicle_flow=veh_count,
                type_counts=type_counts,
                mean_speed=mean_speed,
                num_buses=len(bus_ids),
                bus_headway_var=headway_var,
                vehicle_occupancy_pct=occ_pct,
                capacity_ratio=min(capacity, 1.0),
                all_vehicles=all_vehicles,
            )

        signals = {}
        for tl_id in SIGNAL_IDS:
            signals[tl_id] = self._get_signal_state(tl_id)

        return SimulationSnapshot(
            tick=self.tick,
            time_sec=self.tick * 1.0,
            corridors=corridors,
            signals=signals,
            total_vehicles=total_vehicles,
            weather_risk=weather_risk,
            institutional_flag=institutional_flag,
        )

    def _get_signal_state(self, tl_id: str) -> dict:
        """Get traffic light phase info."""
        try:
            phase = traci.trafficlight.getPhase(tl_id)
            duration = traci.trafficlight.getPhaseDuration(tl_id)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                program = traci.trafficlight.getCompleteRedYellowGreenDefinition(tl_id)
            n_phases = len(program[0].phases) if program else 0
            current_state = program[0].phases[phase].state if program and phase < n_phases else "???"
            return {
                "id": tl_id,
                "phase": phase,
                "phase_duration": duration,
                "current_state": current_state,
                "total_phases": n_phases,
            }
        except (TraCIException, IndexError):
            return {"id": tl_id, "phase": -1, "phase_duration": 0, "current_state": "unknown", "total_phases": 0}

    def apply_signal_priority(self, signal_id: str, green_duration: int = 30):
        """Extend green phase for a signal (simulates BATCS priority)."""
        if not self.running:
            return False
        try:
            traci.trafficlight.setPhaseDuration(signal_id, green_duration)
            return True
        except TraCIException:
            return False

    def inject_bus(self, route_id: str, vtype: str = "bus", depart_pos: str = "random"):
        """Inject an extra bus into the simulation."""
        if not self.running:
            return None
        try:
            veh_id = f"injected_bus_{self.tick}"
            traci.vehicle.add(veh_id, route_id, typeID=vtype, departPos=depart_pos)
            return veh_id
        except TraCIException:
            return None

    def get_tripinfo(self) -> dict:
        """Get simulation-level statistics."""
        if not self.running:
            return {}
        try:
            return {
                "loaded": traci.simulation.getLoadedNumber(),
                "running": traci.simulation.getSubscriptionResults() or {},
                "min_duration": traci.simulation.getMinExpectedNumber(),
            }
        except TraCIException:
            return {}

    @staticmethod
    def _headway_variance(bus_ids: list) -> float:
        if len(bus_ids) < 2:
            return 0.0
        positions = []
        for bid in bus_ids:
            try:
                positions.append(traci.vehicle.getLanePosition(bid))
            except TraCIException:
                continue
        if len(positions) < 2:
            return 0.0
        positions.sort()
        headways = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
        mean_hw = sum(headways) / len(headways)
        return sum((h - mean_hw) ** 2 for h in headways) / len(headways)

    @staticmethod
    def _avg_occupancy(vehicles: list) -> float:
        if not vehicles:
            return 0.0
        total_occ = sum(v.get("occupancy", 0) for v in vehicles)
        return total_occ / len(vehicles)


# Module-level singleton
client = TraCIClient()
