"""SQLAlchemy database setup — SQLite for hackathon, PostGIS for production."""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///sanchalan.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Corridor(Base):
    __tablename__ = "corridors"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    lanes = Column(Integer, default=4)
    city_id = Column(String, default="bengaluru")


class CorridorFeature(Base):
    __tablename__ = "corridor_features"
    id = Column(Integer, primary_key=True, autoincrement=True)
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    ts = Column(DateTime, nullable=False)
    tick = Column(Integer, nullable=False)
    vehicle_flow = Column(Integer, default=0)
    car_count = Column(Integer, default=0)
    tw_count = Column(Integer, default=0)
    auto_count = Column(Integer, default=0)
    bus_count = Column(Integer, default=0)
    mean_speed = Column(Float, default=0.0)
    bus_headway_var = Column(Float, default=0.0)
    vehicle_occupancy_pct = Column(Float, default=0.0)
    capacity_ratio = Column(Float, default=0.0)
    weather_risk = Column(Float, default=0.0)
    institutional_flag = Column(Boolean, default=False)
    crs_score = Column(Float, default=0.0)
    confidence = Column(Float, default=1.0)


class Route(Base):
    __tablename__ = "routes"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    agency = Column(String, default="BMTC")
    gtfs_route_id = Column(String, nullable=True)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(String, nullable=False)
    route_id = Column(String, ForeignKey("routes.id"), nullable=True)
    ts = Column(DateTime, nullable=False)
    tick = Column(Integer, nullable=False)
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    occupancy_pct = Column(Float, default=0.0)
    speed = Column(Float, default=0.0)
    vtype = Column(String, default="car")
    passengers = Column(Integer, default=0)


class EventCalendar(Base):
    __tablename__ = "events_calendar"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=True)
    start_ts = Column(DateTime, nullable=False)
    end_ts = Column(DateTime, nullable=False)
    expected_load = Column(Float, default=0.5)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    ts = Column(DateTime, nullable=False)
    tick = Column(Integer, nullable=False)
    action_type = Column(String, nullable=False)
    action_detail = Column(Text, default="")
    status = Column(String, default="pending")
    approved_by = Column(String, nullable=True)
    ts_approved = Column(DateTime, nullable=True)
    crs_score = Column(Float, default=0.0)
    signal_ids_affected = Column(Text, default="")


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=True)
    channel = Column(String, nullable=False)
    recipient_ref = Column(String, default="demo")
    message = Column(Text, default="")
    ts_sent = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="sent")


def init_db():
    Base.metadata.create_all(engine)
    print("[DB] Tables created.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_corridors():
    """Insert corridor definitions into the database."""
    from config import CORRIDOR_GEO, CORRIDOR_LANES
    db = SessionLocal()
    existing = db.query(Corridor).count()
    if existing > 0:
        db.close()
        return
    for cid, geo in CORRIDOR_GEO.items():
        db.add(Corridor(
            id=cid, name=geo["name"],
            lat=geo["lat"], lon=geo["lon"],
            lanes=CORRIDOR_LANES.get(cid, 2),
        ))
    db.commit()
    db.close()
    print(f"[DB] Seeded {len(CORRIDOR_GEO)} corridors.")
