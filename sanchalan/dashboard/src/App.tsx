import { useState, useEffect, useCallback, useRef } from 'react';
import LiveMap from './LiveMap';
import CorridorPanel from './CorridorPanel';
import RecommendationList from './RecommendationList';
import Header from './Header';
import './styles.css';

export interface CorridorData {
  vehicle_flow: number;
  mean_speed: number;
  num_buses: number;
  bus_headway_var: number;
  crs_score: number;
  crs_level: 'green' | 'amber' | 'red';
  explanation: string;
  type_counts: Record<string, number>;
}

export interface SignalData {
  id: string;
  phase: number;
  current_state: string;
  phase_duration: number;
}

export interface RecData {
  corridor_id: string;
  action_type: string;
  action_detail: string;
  priority: number;
}

export interface SimState {
  tick: number;
  time_sec: number;
  total_vehicles: number;
  weather_risk: number;
  institutional_flag: boolean;
  corridors: Record<string, CorridorData>;
  recommendations: RecData[];
  signals: Record<string, SignalData>;
}

const INITIAL_STATE: SimState = {
  tick: 0, time_sec: 0, total_vehicles: 0, weather_risk: 0,
  institutional_flag: false, corridors: {}, recommendations: [], signals: {},
};

const DEMO_STATE: SimState = {
  tick: 142, time_sec: 8520, total_vehicles: 87, weather_risk: 0.7,
  institutional_flag: false,
  corridors: {
    mg_road_west: {
      vehicle_flow: 14, mean_speed: 8.2, num_buses: 1, bus_headway_var: 12,
      crs_score: 0.78, crs_level: 'red',
      explanation: 'High congestion. Vehicle flow exceeds threshold with low speeds. Signal priority recommended.',
      type_counts: { car: 6, twowheeler: 5, auto: 2, bus: 1 },
    },
    mg_road_west_rev: {
      vehicle_flow: 11, mean_speed: 12.1, num_buses: 0, bus_headway_var: 0,
      crs_score: 0.35, crs_level: 'green',
      explanation: 'Normal traffic conditions. Flow and speed within acceptable ranges.',
      type_counts: { car: 4, twowheeler: 5, auto: 2, bus: 0 },
    },
    mg_road_central: {
      vehicle_flow: 18, mean_speed: 6.5, num_buses: 2, bus_headway_var: 28,
      crs_score: 0.85, crs_level: 'red',
      explanation: 'Critical congestion. Bus bunching detected (headway variance 28s). Immediate action needed.',
      type_counts: { car: 7, twowheeler: 6, auto: 3, bus: 2 },
    },
    mg_road_central_rev: {
      vehicle_flow: 9, mean_speed: 15.3, num_buses: 1, bus_headway_var: 5,
      crs_score: 0.32, crs_level: 'green',
      explanation: 'Stable traffic flow. Bus headway within normal range.',
      type_counts: { car: 3, twowheeler: 4, auto: 1, bus: 1 },
    },
    mg_road_east: {
      vehicle_flow: 10, mean_speed: 10.8, num_buses: 0, bus_headway_var: 0,
      crs_score: 0.48, crs_level: 'amber',
      explanation: 'Moderate congestion building. Monitor for further degradation.',
      type_counts: { car: 4, twowheeler: 4, auto: 2, bus: 0 },
    },
    mg_road_east_rev: {
      vehicle_flow: 8, mean_speed: 14.2, num_buses: 1, bus_headway_var: 8,
      crs_score: 0.28, crs_level: 'green',
      explanation: 'Light traffic. All metrics within normal operating range.',
      type_counts: { car: 3, twowheeler: 3, auto: 1, bus: 1 },
    },
    brigade_road: {
      vehicle_flow: 12, mean_speed: 7.9, num_buses: 1, bus_headway_var: 15,
      crs_score: 0.72, crs_level: 'red',
      explanation: 'Congestion due to rain effect. Speed reduced below threshold. Commuter advisory recommended.',
      type_counts: { car: 5, twowheeler: 4, auto: 2, bus: 1 },
    },
    brigade_road_rev: {
      vehicle_flow: 5, mean_speed: 18.0, num_buses: 0, bus_headway_var: 0,
      crs_score: 0.18, crs_level: 'green',
      explanation: 'Low traffic volume. Road operating well below capacity.',
      type_counts: { car: 2, twowheeler: 2, auto: 1, bus: 0 },
    },
  },
  recommendations: [
    { corridor_id: 'mg_road_central', action_type: 'signal_priority', action_detail: 'Extend green phase by 15s for eastbound flow at C_signal_2. CRS 0.85.', priority: 1 },
    { corridor_id: 'brigade_road', action_type: 'notify_only', action_detail: 'Commuter alert: Rain-related slowdown on Brigade Road. Consider alternate route.', priority: 2 },
    { corridor_id: 'mg_road_west', action_type: 'signal_priority', action_detail: 'Extend green phase by 10s at B_signal_1. Vehicle flow 14 with speed 8.2 km/h.', priority: 3 },
    { corridor_id: 'mg_road_central', action_type: 'bus_dispatch', action_detail: 'Dispatch backup bus to resolve headway gap on MG Road Central corridor.', priority: 2 },
  ],
  signals: {
    B_signal_1: { id: 'B_signal_1', phase: 2, current_state: 'GGrr', phase_duration: 30 },
    C_signal_2: { id: 'C_signal_2', phase: 1, current_state: 'rGGg', phase_duration: 25 },
    D_signal_3: { id: 'D_signal_3', phase: 3, current_state: 'gGGr', phase_duration: 35 },
    F_signal_4: { id: 'F_signal_4', phase: 0, current_state: 'Grrr', phase_duration: 20 },
  },
};

const API_URL = import.meta.env.VITE_API_URL || '';
const WS_URL = API_URL
  ? API_URL.replace('https', 'wss')
  : (window.location.protocol === 'https:' ? 'wss:' : 'ws:');

function getWsUrl() {
  if (API_URL) return `${WS_URL}${new URL(API_URL).pathname}`.replace(/\/$/, '') + '/ws/live';
  return `${WS_URL}//${window.location.host}/ws/live`;
}

function getApi(path: string) {
  return API_URL ? `${API_URL}${path}` : path;
}

export default function App() {
  const [simState, setSimState] = useState<SimState>(INITIAL_STATE);
  const [selectedCorridor, setSelectedCorridor] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [simRunning, setSimRunning] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connectWs = useCallback(() => {
    if (retryRef.current) { clearTimeout(retryRef.current); retryRef.current = null; }
    try {
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;
      ws.onopen = () => { setConnected(true); setDemoMode(false); };
      ws.onmessage = (event) => { setSimState(JSON.parse(event.data)); };
      ws.onclose = () => { setConnected(false); retryRef.current = setTimeout(connectWs, 2000); };
      ws.onerror = () => ws.close();
    } catch {
      retryRef.current = setTimeout(connectWs, 2000);
    }
  }, []);

  useEffect(() => {
    connectWs();
    return () => { wsRef.current?.close(); if (retryRef.current) clearTimeout(retryRef.current); };
  }, [connectWs]);

  useEffect(() => {
    if (connected) return;
    const timer = setTimeout(async () => {
      if (connected) return;
      try {
        const res = await fetch(getApi('/api/sim/status'));
        if (res.ok) {
          const data = await res.json();
          setSimState(data);
          setSimRunning(data.sim_running || false);
          return;
        }
      } catch { /* no backend */ }
      setDemoMode(true);
      setSimState(DEMO_STATE);
    }, 2500);
    return () => clearTimeout(timer);
  }, [connected]);

  const toggleSim = async () => {
    const endpoint = simRunning ? '/api/sim/stop' : '/api/sim/start';
    await fetch(getApi(endpoint), { method: 'POST' });
    setSimRunning(!simRunning);
  };

  const approveRecommendation = async (recId: number) => {
    await fetch(getApi(`/api/recommendations/${recId}/approve`), { method: 'POST' });
  };

  const triggerRain = async (risk: number) => {
    await fetch(getApi(`/api/sim/weather?risk=${risk}`), { method: 'POST' });
  };

  const elapsed = Math.floor(simState.time_sec);
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;

  return (
    <div className="app">
      {demoMode && (
        <div style={{
          background: '#f59e0b', color: '#000', textAlign: 'center',
          fontSize: 12, fontWeight: 600, padding: '4px 0',
        }}>
          DEMO MODE — Backend not connected. Showing sample data.
        </div>
      )}
      <Header
        connected={connected}
        simRunning={simRunning}
        tick={simState.tick}
        time={`${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`}
        totalVehicles={simState.total_vehicles}
        weatherRisk={simState.weather_risk}
        onToggleSim={toggleSim}
        onTriggerRain={triggerRain}
      />
      <div className="main-layout">
        <LiveMap
          corridors={simState.corridors}
          selected={selectedCorridor}
          onSelect={setSelectedCorridor}
        />
        <div className="side-panel">
          <CorridorPanel
            corridorId={selectedCorridor}
            data={selectedCorridor ? simState.corridors[selectedCorridor] : null}
            onApprove={approveRecommendation}
          />
          <RecommendationList
            recommendations={simState.recommendations}
            onApprove={approveRecommendation}
          />
        </div>
      </div>
    </div>
  );
}
