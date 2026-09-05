import requests

def test_get_api_geocode_reverse_with_valid_lat_lng():
    base_url = "http://localhost:8000"
    endpoint = "/api/geocode/reverse"
    token = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Use valid latitude and longitude values (e.g., Cairo, Egypt)
    params = {
        "lat": 30.0444,
        "lng": 31.2357
    }

    try:
        response = requests.get(
            url=f"{base_url}{endpoint}",
            headers=headers,
            params=params,
            timeout=30
        )
    except requests.RequestException as e:
        assert False, f"Request to {endpoint} failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    json_data = response.json()
    assert isinstance(json_data, dict), "Response JSON should be a dictionary"
    # Assuming response has some address info, check keys presence
    assert "address" in json_data or "formatted_address" in json_data, "Response should contain resolved address"

test_get_api_geocode_reverse_with_valid_lat_lng()