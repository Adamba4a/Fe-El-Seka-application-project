import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
TIMEOUT = 30


def test_put_api_profiles_me_update_current_user_profile():
    updated_profile_payload = {
        "display_name": "Updated Test Display Name",
        "role": "driver"
    }

    # Send PUT request to update profile
    put_response = requests.put(
        f"{BASE_URL}/api/profiles/me",
        headers=HEADERS,
        json=updated_profile_payload,
        timeout=TIMEOUT,
    )
    try:
        # Assert status code 200
        assert put_response.status_code == 200, f"PUT /api/profiles/me failed: {put_response.status_code} {put_response.text}"

        updated_profile = put_response.json()
        # Assert response contains the updated fields with expected values
        assert "display_name" in updated_profile and updated_profile["display_name"] == updated_profile_payload["display_name"], "Display name not updated correctly"
        assert "role" in updated_profile and updated_profile["role"] == updated_profile_payload["role"], "Role not updated correctly"

        # Send GET request to retrieve profile and verify changes persisted
        get_response = requests.get(
            f"{BASE_URL}/api/profiles/me",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        assert get_response.status_code == 200, f"GET /api/profiles/me failed: {get_response.status_code} {get_response.text}"

        profile_data = get_response.json()
        assert "display_name" in profile_data and profile_data["display_name"] == updated_profile_payload["display_name"], "Display name not persisted after update"
        assert "role" in profile_data and profile_data["role"] == updated_profile_payload["role"], "Role not persisted after update"

    finally:
        # Optional: no rollback because no original profile data was fetched; 
        # relying on test environment reset or manual cleanup if needed.
        pass


test_put_api_profiles_me_update_current_user_profile()