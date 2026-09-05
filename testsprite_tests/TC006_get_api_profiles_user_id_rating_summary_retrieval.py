import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
}

def test_get_api_profiles_user_id_rating_summary_retrieval():
    # Step 1: Get current user profile to obtain user_id
    try:
        response_me = requests.get(f"{BASE_URL}/api/profiles/me", headers=headers, timeout=30)
        response_me.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Failed to get current user's profile: {e}"
    user_data = response_me.json()
    user_id = user_data.get("id")
    assert user_id, "Current user's ID not found in profile response"

    # Step 2: GET rating summary for existing user_id, expect 200 with rating data
    try:
        response_rating = requests.get(f"{BASE_URL}/api/profiles/{user_id}/rating", headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request to get user rating summary failed: {e}"
    assert response_rating.status_code == 200, f"Expected 200, got {response_rating.status_code}"
    rating_data = response_rating.json()
    assert isinstance(rating_data, dict), "Rating summary response is not a JSON object"
    assert "average" in rating_data and rating_data["average"] is not None, "Rating summary missing 'average' field or it is null"
    assert "count" in rating_data and rating_data["count"] is not None, "Rating summary missing 'count' field or it is null"
    assert isinstance(rating_data.get("average"), (int, float)), "Rating 'average' is not a number"
    assert isinstance(rating_data.get("count"), int), "Rating 'count' is not an integer"

    # Step 3: GET rating summary for nonexistent user, expect error indicating not found
    invalid_user_id = "00000000-0000-0000-0000-000000000000"
    try:
        response_invalid = requests.get(f"{BASE_URL}/api/profiles/{invalid_user_id}/rating", headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request to get rating for nonexistent user failed: {e}"

    assert response_invalid.status_code in {400, 404}, f"Expected 400 or 404 for nonexistent user, got {response_invalid.status_code}"

    # Optionally check error message structure
    try:
        error_data = response_invalid.json()
        assert "detail" in error_data or "error" in error_data, "Error response missing detail or error message"
    except Exception:
        # If response is not JSON, still pass as status code is validated
        pass

test_get_api_profiles_user_id_rating_summary_retrieval()
