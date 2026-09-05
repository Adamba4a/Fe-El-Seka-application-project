import requests

BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
PASSENGER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImY3MTI0MjZiLTg1ZjUtNGJkZi1hZmNhLTBkYTcwMGQ4M2Y2ZSIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiJlMDQ2ZjY2Yy1hODIyLTQ5NmUtOTkzNi0xNDQ2NTQ4YWQ0OTAifQ.UyzTpWiiiNf6kLjOgFkoNQZ55F0n5RMI_9yQml_J7s-vFqyFvqNqHRKxqPCxWzdlT0KzfE0mZjytDDXknYoEyQ"

HEADERS_ADMIN = {
    "Authorization": f"Bearer {ADMIN_TOKEN}"
}

HEADERS_NON_ADMIN = {
    "Authorization": f"Bearer {PASSENGER_TOKEN}"
}

TIMEOUT = 30


def test_admin_rides_visibility_and_feature_toggling():
    # 1. Verify GET /api/admin/rides returns 200 with admin JWT and includes markup and fair-price fields
    get_rides_url = f"{BASE_URL}/api/admin/rides"
    res_admin = requests.get(get_rides_url, headers=HEADERS_ADMIN, timeout=TIMEOUT)
    assert res_admin.status_code == 200, f"Expected 200 OK with admin JWT but got {res_admin.status_code}"
    rides_data = res_admin.json()
    assert isinstance(rides_data, list), "Expected response to be a list of rides"
    assert len(rides_data) > 0, "Expected at least one ride in rides list"
    # Check at least one ride includes 'markup' and 'fair_price' fields
    ride = rides_data[0]
    assert "markup" in ride, "'markup' field missing in ride data"
    assert "fair_price" in ride, "'fair_price' field missing in ride data"
    ride_id = ride.get("id") or ride.get("ride_id")
    assert ride_id, "Ride ID not found in ride data for feature/unfeature tests"

    # 2. Verify GET /api/admin/rides returns 403 without admin JWT (no auth header)
    res_unauth = requests.get(get_rides_url, timeout=TIMEOUT)
    assert res_unauth.status_code == 403, f"Expected 403 forbidden without admin JWT but got {res_unauth.status_code}"

    # 3. Verify GET /api/admin/rides returns 403 with non-admin token
    res_non_admin = requests.get(get_rides_url, headers=HEADERS_NON_ADMIN, timeout=TIMEOUT)
    assert res_non_admin.status_code == 403, f"Expected 403 forbidden with non-admin token but got {res_non_admin.status_code}"

    # 4. Verify POST /api/admin/rides/{ride_id}/feature marks ride as featured and returns 200 with admin JWT
    feature_url = f"{BASE_URL}/api/admin/rides/{ride_id}/feature"
    res_feature = requests.post(feature_url, headers=HEADERS_ADMIN, timeout=TIMEOUT)
    assert res_feature.status_code == 200, f"Expected 200 OK on feature ride but got {res_feature.status_code}"

    # 5. Verify POST /api/admin/rides/{ride_id}/feature returns 403 with non-admin token
    res_feature_non_admin = requests.post(feature_url, headers=HEADERS_NON_ADMIN, timeout=TIMEOUT)
    assert res_feature_non_admin.status_code == 403, f"Expected 403 forbidden on feature ride with non-admin token but got {res_feature_non_admin.status_code}"

    # 6. Verify POST /api/admin/rides/{ride_id}/unfeature removes featured status and returns 200 with admin JWT
    unfeature_url = f"{BASE_URL}/api/admin/rides/{ride_id}/unfeature"
    res_unfeature = requests.post(unfeature_url, headers=HEADERS_ADMIN, timeout=TIMEOUT)
    assert res_unfeature.status_code == 200, f"Expected 200 OK on unfeature ride but got {res_unfeature.status_code}"

    # 7. Verify POST /api/admin/rides/{ride_id}/unfeature returns 403 with non-admin token
    res_unfeature_non_admin = requests.post(unfeature_url, headers=HEADERS_NON_ADMIN, timeout=TIMEOUT)
    assert res_unfeature_non_admin.status_code == 403, f"Expected 403 forbidden on unfeature ride with non-admin token but got {res_unfeature_non_admin.status_code}"


test_admin_rides_visibility_and_feature_toggling()