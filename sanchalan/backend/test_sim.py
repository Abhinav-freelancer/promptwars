"""Test TraCI + SUMO + CRS + Recommendations with rain event."""
import os
import sys
import warnings
warnings.filterwarnings("ignore")

os.environ["SUMO_HOME"] = r"C:\Users\abhinav s\AppData\Local\Sumo\sumo-1.27.1"
sys.path.insert(0, os.path.dirname(__file__))

from traci_client import client
from prediction import compute_crs
from recommendation import generate_recommendations

client.start()
print("Running 400 steps with rain event at t=100...")

for i in range(400):
    weather = 0.7 if i >= 100 else 0.0  # Rain starts at t=100
    snap = client.step(weather_risk=weather, institutional_flag=False)
    c = snap.corridors.get("mg_road_central")
    if c:
        crs = compute_crs(
            vehicle_flow=c.vehicle_flow, capacity_ratio=c.capacity_ratio,
            mean_speed=c.mean_speed, bus_headway_var=c.bus_headway_var,
            num_buses=c.num_buses, weather_risk=weather, institutional_flag=False,
        )
        if crs.level != "green" or i % 50 == 0:
            recs = generate_recommendations(
                corridor_id="mg_road_central", crs_score=crs.crs_score,
                crs_level=crs.level, num_buses=c.num_buses,
                bus_headway_var=c.bus_headway_var, vehicle_flow=c.vehicle_flow,
            )
            rec_str = ", ".join(r.action_type for r in recs) if recs else "none"
            print(f"  t={i:3d}: veh={snap.total_vehicles:3d} central={c.vehicle_flow:2d} "
                  f"spd={c.mean_speed:.1f} buses={c.num_buses} "
                  f"CRS={crs.crs_score:.3f} [{crs.level.upper():5s}] recs=[{rec_str}]")

client.stop()
print("Done!")
