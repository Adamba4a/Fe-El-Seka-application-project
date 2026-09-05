import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_ride_with_flat_origin_data_validation_error():
    url = f"{BASE_URL}/api/v1/rides"
    # Payload with flat origin data missing nested coordinates to cause validation error
    payload = {
        "origin": {
            "address": "Cairo, Egypt"
            # Coordinates missing intentionally
        },
        "destination": {
            "coordinates": {"lat": 30.0444, "lng": 31.2357},
            "address": "Giza, Egypt"
        },
        "departure_datetime": "2026-09-10T08:00:00Z",
        "total_seats": 3,
        "vehicle_id": "00000000-0000-0000-0000-000000000001"
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request to post ride failed with exception: {e}"

    assert response.status_code == 422, f"Expected 422 validation error, got {response.status_code}"
    # Confirm error message indicates validation failure for coordinates
    json_resp = {}
    try:
        json_resp = response.json()
    except Exception:
        assert False, "Response is not valid JSON"

    if isinstance(json_resp, dict) and "detail" in json_resp:
        error_detail = json_resp.get("detail", "")
    else:
        # Fallback: search for known validation error indications in any top-level string or list
        error_detail = []
        if isinstance(json_resp, dict):
            for k, v in json_resp.items():
                if isinstance(v, (str, list)):
                    error_detail.append(v)
        else:
            error_detail = [str(json_resp)]

    assert error_detail, "Response JSON missing 'detail' or equivalent for validation errors"
    # We do not rely on exact message; just check presence of coordinate mention or validation keywords
    validation_error_found = any(
        "coordinates" in str(detail).lower()
        or "origin" in str(detail).lower()
        or "missing" in str(detail).lower()
        or "field required" in str(detail).lower()
        or "value_error" in str(detail).lower()
        for detail in (error_detail if isinstance(error_detail, list) else [error_detail])
    )
    assert validation_error_found, f"Validation error for 'coordinates' not found in response detail: {error_detail}"

test_post_ride_with_flat_origin_data_validation_error()
