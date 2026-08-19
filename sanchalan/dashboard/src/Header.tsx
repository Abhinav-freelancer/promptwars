interface Props {
  connected: boolean;
  simRunning: boolean;
  tick: number;
  time: string;
  totalVehicles: number;
  weatherRisk: number;
  onToggleSim: () => void;
  onTriggerRain: (risk: number) => void;
}

export default function Header({
  connected, simRunning, tick, time, totalVehicles,
  weatherRisk, onToggleSim, onTriggerRain,
}: Props) {
  return (
    <header className="header">
      <div className="header-left">
        <div className="logo">
          <span className="logo-hindi">{ '\u0938\u0902\u091A\u093E\u0932\u0928' }</span>
          <span className="logo-en">SANCHALAN</span>
        </div>
        <div className="header-subtitle">
          Predictive Coordination Layer
        </div>
      </div>
      <div className="header-center">
        <div className="stat">
          <span className="stat-label">Tick</span>
          <span className="stat-value">{tick}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Elapsed</span>
          <span className="stat-value">{time}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Vehicles</span>
          <span className="stat-value">{totalVehicles}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Weather</span>
          <span className="stat-value">
            {weatherRisk > 0.5 ? '\u{1F327}' : weatherRisk > 0 ? '\u{1F326}' : '\u{2600}'}
            {(weatherRisk * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      <div className="header-right">
        <button
          className={`btn btn-sim ${simRunning ? 'running' : ''}`}
          onClick={onToggleSim}
        >
          {simRunning ? '\u{23F8} Pause' : '\u{25B6} Start'}
        </button>
        <button
          className="btn btn-rain"
          onClick={() => onTriggerRain(weatherRisk > 0 ? 0 : 0.7)}
        >
          {weatherRisk > 0 ? '\u{2600} Clear' : '\u{1F327} Rain'}
        </button>
        <div className={`status-dot ${connected ? 'online' : 'offline'}`} />
      </div>
    </header>
  );
}
