import requests
from datetime import datetime, timedelta
import uuid

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_post_ride_with_nested_origin_destination_coordinates():
    # Prepare a sample vehicle_id by creating a dummy ride first if needed. Since no vehicle_id is provided,
    # simulate a call to get an existing vehicle_id or use a placeholder.
    # For this test, we will assume the active vehicle_id is known and fixed UUID.
    # If it was unknown, here we'd create or fetch it first.
    vehicle_id = "d2f0e4e6-4a0b-4d3c-8420-fcb9f5aa3c47"  # Replace with valid active vehicle_id in test env if known
    
    # Use departure_datetime in future to ensure validity
    departure_datetime = (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0).isoformat() + "Z"
    
    payload = {
        "origin": {
            "coordinates": {
                "lat": 30.0444,
                "lng": 31.2357
            },
            "address": "Cairo, Egypt"
        },
        "destination": {
            "coordinates": {
                "lat": 29.9914,
                "lng": 31.1536
            },
            "address": "Giza, Egypt"
        },
        "departure_datetime": departure_datetime,
        "total_seats": 3,
        "vehicle_id": vehicle_id
    }

    ride_id = None
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/rides",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        # Validate status 200 or 503 due to local OSRM limitation
        # The PRD states it reliably returns 503 locally when OSRM is not configured
        assert response.status_code in (200, 503), f"Unexpected status code: {response.status_code}"
        
        if response.status_code == 503:
            # Verify error content if OSRM unavailable
            body = response.json()
            assert "error" in body and body["error"] == "route_intelligence_unavailable"
            return  # stop test here because ride not created
        
        data = response.json()
        
        # Ride created successfully
        # Validate required fields in response
        assert "id" in data and isinstance(data["id"], str)
        ride_id = data["id"]
        assert "origin" in data and "coordinates" in data["origin"]
        assert "destination" in data and "coordinates" in data["destination"]
        assert "departure_datetime" in data
        assert data["departure_datetime"] == departure_datetime or data["departure_datetime"].startswith(departure_datetime[:19])
        assert "total_seats" in data and data["total_seats"] == 3
        assert "vehicle_id" in data and data["vehicle_id"] == vehicle_id
        assert "fare" in data and isinstance(data["fare"], (int, float))
        assert "route" in data  # computed route present
        
        # Additional check: coordinates correctness
        assert data["origin"]["coordinates"]["lat"] == payload["origin"]["coordinates"]["lat"]
        assert data["origin"]["coordinates"]["lng"] == payload["origin"]["coordinates"]["lng"]
        assert data["destination"]["coordinates"]["lat"] == payload["destination"]["coordinates"]["lat"]
        assert data["destination"]["coordinates"]["lng"] == payload["destination"]["coordinates"]["lng"]
    finally:
        # Cleanup if ride was created
        if ride_id:
            try:
                del_response = requests.delete(
                    f"{BASE_URL}/api/v1/rides/{ride_id}",
                    headers=HEADERS,
                    timeout=30
                )
                # It's acceptable if delete is not supported or gives 404,
                # just ignore any delete errors here.
            except Exception:
                pass


test_post_ride_with_nested_origin_destination_coordinates()