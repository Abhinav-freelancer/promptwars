"""SUMO configuration constants."""

import os

SUMO_HOME = os.environ.get("SUMO_HOME", r"C:\Users\abhinav s\AppData\Local\Sumo\sumo-1.27.1")
SUMO_BIN = os.environ.get("SUMO_BIN", os.path.join(SUMO_HOME, "bin", "sumo.exe"))
SUMO_CFG = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "simulation", "network", "sanchalan.sumocfg"))

CORRIDOR_EDGES = {
    "mg_road_west": ["A_to_B"],
    "mg_road_central": ["B_to_C", "C_to_D"],
    "mg_road_east": ["D_to_E"],
    "brigade_road": ["C_to_F", "F_to_G"],
}

CORRIDOR_EDGES_REV = {
    "mg_road_west_rev": ["B_to_A"],
    "mg_road_central_rev": ["C_to_B", "D_to_C"],
    "mg_road_east_rev": ["E_to_D"],
    "brigade_road_rev": ["F_to_C", "G_to_F"],
}

ALL_CORRIDOR_EDGES = {**CORRIDOR_EDGES, **CORRIDOR_EDGES_REV}

CORRIDOR_GEO = {
    "mg_road_west": {"lat": 12.9750, "lon": 77.5900, "name": "MG Road West"},
    "mg_road_central": {"lat": 12.9750, "lon": 77.5950, "name": "MG Road Central"},
    "mg_road_east": {"lat": 12.9750, "lon": 77.6000, "name": "MG Road East"},
    "brigade_road": {"lat": 12.9730, "lon": 77.5970, "name": "Brigade Road"},
    "mg_road_west_rev": {"lat": 12.9750, "lon": 77.5900, "name": "MG Road West (Rev)"},
    "mg_road_central_rev": {"lat": 12.9750, "lon": 77.5950, "name": "MG Road Central (Rev)"},
    "mg_road_east_rev": {"lat": 12.9750, "lon": 77.6000, "name": "MG Road East (Rev)"},
    "brigade_road_rev": {"lat": 12.9730, "lon": 77.5970, "name": "Brigade Road (Rev)"},
}

CORRIDOR_LANES = {
    "mg_road_west": 4, "mg_road_central": 4, "mg_road_east": 4, "brigade_road": 2,
    "mg_road_west_rev": 4, "mg_road_central_rev": 4, "mg_road_east_rev": 4, "brigade_road_rev": 2,
}

LANE_CAPACITY = {"car": 0.25, "twowheeler": 0.40, "auto": 0.20, "bus": 0.08}

SIGNAL_IDS = ["B_signal_1", "C_signal_2", "D_signal_3", "F_signal_4"]
