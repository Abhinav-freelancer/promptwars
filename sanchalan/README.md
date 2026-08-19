# SANCHALAN - Predictive Coordination Layer

## Quick Start

### 1. Install SUMO (required)

```powershell
# Option A: winget (recommended)
winget install EclipseFoundation.SUMO

# Option B: manual download
# https://sumo.dlr.de/download.php → Windows 64-bit zip
# Extract to C:\Sumo and set SUMO_HOME=C:\Sumo

# After install, set the env var:
$env:SUMO_HOME = "C:\Program Files\Eclipse\Sumo"  # or your path
```

### 2. Build SUMO network

```powershell
cd sanchalan\simulation\network
netconvert -n sanchalan.nod.xml -e sanchalan.edg.xml -x sanchalan.con.xml -o sanchalan.net.xml
```

### 3. Install Python deps & start backend

```powershell
cd sanchalan
pip install -r requirements.txt
cd backend
python -c "from database import init_db, seed_corridors; init_db(); seed_corridors()"
python -m uvicorn main:app --reload --port 8000
```

### 4. Start dashboard

```powershell
cd sanchalan\dashboard
npm install
npm run dev
```

Open http://localhost:5173 — the dashboard connects via WebSocket to the backend.

### 5. Run the demo

1. Click **Start** in the header to begin the simulation
2. Watch corridors transition from green → amber → red as traffic builds
3. Click **Rain** to inject a weather event (increases CRS)
4. See recommendations appear in the right panel
5. Click a corridor marker on the map for detailed metrics

## Architecture

```
SUMO (simulation) → TraCI → FastAPI backend → SQLite DB
                                    ↓
                              React dashboard (WebSocket)
                              Recommendation engine
                              SMS notifications (Phase 5)
```

## Project Structure

```
sanchalan/
├── simulation/network/     SUMO network, routes, config
├── backend/                FastAPI + TraCI + ML + DB
│   ├── main.py            Server + simulation loop
│   ├── traci_client.py    SUMO control via TraCI
│   ├── prediction.py      CRS calculation
│   ├── recommendation.py  Rule-based action engine
│   └── database.py        SQLAlchemy models + DB
├── dashboard/              React + Leaflet frontend
├── requirements.txt
└── setup.bat              One-click setup
```
