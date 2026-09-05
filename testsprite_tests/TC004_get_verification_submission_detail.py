import requests

BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS_AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
TIMEOUT = 30


def test_get_verification_submission_detail():
    # Step 1: Get pending verification submissions to find a valid submission_id
    queue_url = f"{BASE_URL}/api/admin/verification/queue"
    try:
        response = requests.get(queue_url, headers=HEADERS_AUTH, timeout=TIMEOUT)
        assert response.status_code == 200, f"Failed to get queue: {response.status_code}"
        queue_data = response.json()
        assert isinstance(queue_data, list), "Queue response is not a list"
        assert len(queue_data) > 0, "No pending verification submissions found"

        submission_id = queue_data[0].get("id") or queue_data[0].get("submission_id")
        assert submission_id, "submission_id not found in queue item"
    except Exception as e:
        raise AssertionError(f"Setup to get verification submission failed: {e}")

    # Step 2: Call GET /api/admin/verification/{submission_id} with valid admin JWT
    detail_url = f"{BASE_URL}/api/admin/verification/{submission_id}"
    response = requests.get(detail_url, headers=HEADERS_AUTH, timeout=TIMEOUT)
    assert response.status_code == 200, f"Expected 200 but got {response.status_code} for admin authorized request"
    detail_data = response.json()
    assert isinstance(detail_data, dict), "Verification submission detail is not a dict"
    # Check presence of some expected keys - minimal check
    assert "id" in detail_data, "'id' field missing in submission detail"
    assert str(detail_data.get("id")) == str(submission_id), "submission_id mismatch in detail response"

    # Step 3: Call GET /api/admin/verification/{submission_id} without auth header - expect 403
    response_no_auth = requests.get(detail_url, timeout=TIMEOUT)
    assert response_no_auth.status_code == 403, f"Expected 403 but got {response_no_auth.status_code} for unauthorized request"


test_get_verification_submission_detail()