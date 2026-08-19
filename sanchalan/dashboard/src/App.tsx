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

export default function App() {
  const [simState, setSimState] = useState<SimState>(INITIAL_STATE);
  const [selectedCorridor, setSelectedCorridor] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [simRunning, setSimRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connectWs = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/live`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log('[WS] Connected');
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setSimState(data);
    };
    ws.onclose = () => {
      setConnected(false);
      console.log('[WS] Disconnected, reconnecting...');
      setTimeout(connectWs, 2000);
    };
    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connectWs();
    return () => wsRef.current?.close();
  }, [connectWs]);

  const toggleSim = async () => {
    const endpoint = simRunning ? '/api/sim/stop' : '/api/sim/start';
    await fetch(endpoint, { method: 'POST' });
    setSimRunning(!simRunning);
  };

  const approveRecommendation = async (recId: number) => {
    await fetch(`/api/recommendations/${recId}/approve`, { method: 'POST' });
  };

  const triggerRain = async (risk: number) => {
    await fetch(`/api/sim/weather?risk=${risk}`, { method: 'POST' });
  };

  const elapsed = Math.floor(simState.time_sec);
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;

  return (
    <div className="app">
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
