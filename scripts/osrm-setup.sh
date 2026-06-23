#!/usr/bin/env bash
# One-time OSRM routing graph build for Egypt.
# Run from the repository root before starting the stack for the first time.
# Prerequisites: Docker must be running.
#
# Usage: bash scripts/osrm-setup.sh

set -euo pipefail

DATA_DIR="$(cd "$(dirname "$0")/.." && pwd)/osrm-data"
OSM_FILE="egypt-latest.osm.pbf"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend:v5.27.1"
DOWNLOAD_URL="https://download.geofabrik.de/africa/egypt-latest.osm.pbf"

mkdir -p "$DATA_DIR"

if [ ! -f "$DATA_DIR/$OSM_FILE" ]; then
    echo "[osrm-setup] Downloading Egypt OSM extract (~80MB)..."
    curl -L --progress-bar -o "$DATA_DIR/$OSM_FILE" "$DOWNLOAD_URL"
else
    echo "[osrm-setup] OSM extract already present, skipping download."
fi

echo "[osrm-setup] Extracting road network (car profile)..."
docker run --rm -v "$DATA_DIR:/data" "$OSRM_IMAGE" \
    osrm-extract -p /opt/car.lua /data/"$OSM_FILE"

echo "[osrm-setup] Contracting graph (CH algorithm — this takes a few minutes)..."
docker run --rm -v "$DATA_DIR:/data" "$OSRM_IMAGE" \
    osrm-contract /data/egypt-latest.osrm

echo "[osrm-setup] Done. Routing graph is ready in osrm-data/."
echo "[osrm-setup] Start the full stack with: docker compose up"
