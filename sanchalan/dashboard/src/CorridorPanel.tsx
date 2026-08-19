import { CorridorData } from './App';

interface Props {
  corridorId: string | null;
  data: CorridorData | null;
  onApprove: (recId: number) => void;
}

const LEVEL_BG: Record<string, string> = {
  green: 'rgba(34, 197, 94, 0.15)',
  amber: 'rgba(245, 158, 11, 0.15)',
  red: 'rgba(239, 68, 68, 0.15)',
};

const LEVEL_BORDER: Record<string, string> = {
  green: '#22c55e',
  amber: '#f59e0b',
  red: '#ef4444',
};

export default function CorridorPanel({ corridorId, data, onApprove }: Props) {
  if (!corridorId || !data) {
    return (
      <div className="panel corridor-panel">
        <div className="panel-placeholder">
          Select a corridor on the map to view details
        </div>
      </div>
    );
  }

  const level = data.crs_level;
  const typeEntries = Object.entries(data.type_counts);

  return (
    <div
      className="panel corridor-panel"
      style={{
        background: LEVEL_BG[level],
        borderColor: LEVEL_BORDER[level],
      }}
    >
      <div className="panel-header">
        <h3>{corridorId.replace(/_/g, ' ').toUpperCase()}</h3>
        <span className={`crs-badge crs-${level}`}>
          CRS {data.crs_score.toFixed(2)}
        </span>
      </div>

      <div className="metric-grid">
        <MetricCard label="Vehicles" value={data.vehicle_flow.toString()} />
        <MetricCard label="Avg Speed" value={`${data.mean_speed.toFixed(0)} km/h`} />
        <MetricCard label="Buses" value={data.num_buses.toString()} />
        <MetricCard label="Headway Var" value={data.bus_headway_var.toFixed(0)} />
      </div>

      {typeEntries.length > 0 && (
        <div className="vehicle-breakdown">
          <h4>Traffic Composition</h4>
          <div className="type-bars">
            {typeEntries.map(([type, count]) => {
              const total = typeEntries.reduce((s, [, c]) => s + c, 0);
              const pct = total > 0 ? (count / total) * 100 : 0;
              return (
                <div key={type} className="type-bar-row">
                  <span className="type-label">{type}</span>
                  <div className="type-bar">
                    <div
                      className={`type-fill type-${type}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="type-count">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="explanation">
        <strong>Analysis:</strong> {data.explanation}
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}
