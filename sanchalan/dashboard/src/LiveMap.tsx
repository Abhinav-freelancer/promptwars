import { MapContainer, TileLayer, CircleMarker, Popup, Polyline } from 'react-leaflet';
import { CorridorData } from './App';
import 'leaflet/dist/leaflet.css';

interface Props {
  corridors: Record<string, CorridorData>;
  selected: string | null;
  onSelect: (id: string) => void;
}

// Corridor center coordinates (Bengaluru MG Road area)
const CORRIDOR_COORDS: Record<string, [number, number]> = {
  mg_road_west:       [12.9750, 77.5900],
  mg_road_west_rev:   [12.9748, 77.5900],
  mg_road_central:    [12.9750, 77.5950],
  mg_road_central_rev:[12.9748, 77.5950],
  mg_road_east:       [12.9750, 77.6000],
  mg_road_east_rev:   [12.9748, 77.6000],
  brigade_road:       [12.9730, 77.5970],
  brigade_road_rev:   [12.9728, 77.5972],
};

// Road network lines for the map
const ROAD_SEGMENTS: [number, number][][] = [
  [[12.9750, 77.5860], [12.9750, 77.5920], [12.9750, 77.5980], [12.9750, 77.6040]],
  [[12.9750, 77.5970], [12.9730, 77.5970], [12.9710, 77.5970]],
];

const LEVEL_COLOR: Record<string, string> = {
  green: '#22c55e',
  amber: '#f59e0b',
  red: '#ef4444',
};

const LEVEL_RADIUS: Record<string, number> = {
  green: 10, amber: 14, red: 18,
};

export default function LiveMap({ corridors, selected, onSelect }: Props) {
  return (
    <div className="map-container">
      <MapContainer
        center={[12.9750, 77.5950]}
        zoom={15}
        style={{ width: '100%', height: '100%' }}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {/* Road network */}
        {ROAD_SEGMENTS.map((seg, i) => (
          <Polyline
            key={i}
            positions={seg}
            pathOptions={{ color: '#374151', weight: 6, opacity: 0.6 }}
          />
        ))}
        {/* Corridor markers */}
        {Object.entries(CORRIDOR_COORDS).map(([cid, pos]) => {
          const data = corridors[cid];
          const level = data?.crs_level || 'green';
          const isSelected = selected === cid;
          return (
            <CircleMarker
              key={cid}
              center={pos}
              radius={LEVEL_RADIUS[level] + (isSelected ? 4 : 0)}
              fillColor={LEVEL_COLOR[level]}
              fillOpacity={isSelected ? 0.9 : 0.7}
              color={isSelected ? '#ffffff' : LEVEL_COLOR[level]}
              weight={isSelected ? 3 : 2}
              eventHandlers={{
                click: () => onSelect(cid),
              }}
            >
              <Popup>
                <strong>{cid.replace(/_/g, ' ').toUpperCase()}</strong>
                <br />
                CRS: {data?.crs_score?.toFixed(2) || '—'} ({level})
                <br />
                Vehicles: {data?.vehicle_flow || 0}
                <br />
                Speed: {data?.mean_speed?.toFixed(1) || '—'} km/h
                <br />
                Buses: {data?.num_buses || 0}
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
      {/* Legend overlay */}
      <div className="map-legend">
        <div className="legend-title">Corridor Status</div>
        {Object.entries(LEVEL_COLOR).map(([level, color]) => (
          <div key={level} className="legend-item">
            <span className="legend-dot" style={{ background: color }} />
            {level.charAt(0).toUpperCase() + level.slice(1)}
          </div>
        ))}
      </div>
    </div>
  );
}
