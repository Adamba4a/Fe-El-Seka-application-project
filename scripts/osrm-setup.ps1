# One-time OSRM routing graph build for Egypt.
# Run from the repository root before starting the stack for the first time.
# Prerequisites: Docker Desktop must be running.
#
# Usage (from repo root):  .\scripts\osrm-setup.ps1

$ErrorActionPreference = "Stop"

$RepoRoot    = Split-Path $PSScriptRoot -Parent
$DataDir     = Join-Path $RepoRoot "osrm-data"
$OsmFile     = "egypt-latest.osm.pbf"
$OsrmImage   = "ghcr.io/project-osrm/osrm-backend:v5.27.1"
$DownloadUrl = "https://download.geofabrik.de/africa/egypt-latest.osm.pbf"
$OsmPath     = Join-Path $DataDir $OsmFile

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

# Docker Desktop on Windows needs forward-slash paths for volume mounts
$DockerDataDir = $DataDir.Replace('\', '/')

if (-not (Test-Path $OsmPath)) {
    Write-Host "[osrm-setup] Downloading Egypt OSM extract (~80MB)..."
    curl.exe -L --progress-bar -o $OsmPath $DownloadUrl
} else {
    Write-Host "[osrm-setup] OSM extract already present, skipping download."
}

Write-Host "[osrm-setup] Extracting road network (car profile)..."
docker run --rm -v "${DockerDataDir}:/data" $OsrmImage osrm-extract -p /opt/car.lua "/data/$OsmFile"

Write-Host "[osrm-setup] Contracting graph (CH algorithm - takes a few minutes)..."
docker run --rm -v "${DockerDataDir}:/data" $OsrmImage osrm-contract /data/egypt-latest.osrm

Write-Host "[osrm-setup] Done. Start OSRM with:"
Write-Host "  docker compose --profile osrm up osrm"
