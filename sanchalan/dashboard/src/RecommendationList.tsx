import { RecData } from './App';

interface Props {
  recommendations: RecData[];
  onApprove: (recId: number) => void;
}

const ACTION_ICONS: Record<string, string> = {
  signal_priority: '\u{1F6A6}',
  bus_dispatch: '\u{1F68C}',
  notify_only: '\u{1F4E1}',
  reroute_advisory: '\u{1F500}',
};

const ACTION_LABELS: Record<string, string> = {
  signal_priority: 'Signal Priority',
  bus_dispatch: 'Bus Dispatch',
  notify_only: 'Commuter Alert',
  reroute_advisory: 'Reroute Advisory',
};

export default function RecommendationList({ recommendations, onApprove }: Props) {
  return (
    <div className="panel recommendation-panel">
      <div className="panel-header">
        <h3>Active Recommendations</h3>
        <span className="rec-count">{recommendations.length}</span>
      </div>
      {recommendations.length === 0 ? (
        <div className="panel-placeholder">
          No active recommendations. All corridors operating normally.
        </div>
      ) : (
        <div className="rec-list">
          {recommendations.map((rec, idx) => (
            <div key={idx} className={`rec-item rec-${rec.action_type}`}>
              <div className="rec-icon">
                {ACTION_ICONS[rec.action_type] || '\u{2699}'}
              </div>
              <div className="rec-body">
                <div className="rec-type">
                  {ACTION_LABELS[rec.action_type] || rec.action_type}
                </div>
                <div className="rec-corridor">
                  {rec.corridor_id.replace(/_/g, ' ')}
                </div>
                <div className="rec-detail">{rec.action_detail}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
