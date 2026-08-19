FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        sumo sumo-tools sumo-doc \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY sanchalan/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sanchalan/simulation/ ./simulation/
COPY sanchalan/backend/ ./backend/
COPY sanchalan/backend/ml/crs_forecaster.pkl ./backend/ml/crs_forecaster.pkl

ENV SUMO_HOME=/usr/share/sumo
ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
