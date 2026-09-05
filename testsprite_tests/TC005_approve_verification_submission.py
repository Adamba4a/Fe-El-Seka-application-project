import requests

BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
NON_ADMIN_TOKEN = ADMIN_TOKEN  # Provided token is non-admin for testing 403 case on non-admin token
TIMEOUT = 30

def test_approve_verification_submission():
    headers_admin = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    headers_non_admin = {"Authorization": f"Bearer {NON_ADMIN_TOKEN}"}

    # Step 1: Get pending verification submissions to obtain a valid submission_id
    try:
        resp_queue = requests.get(f"{BASE_URL}/api/admin/verification/queue", headers=headers_admin, timeout=TIMEOUT)
        assert resp_queue.status_code == 200, f"Failed to get verification queue: {resp_queue.status_code}"
        queue_data = resp_queue.json()
        assert isinstance(queue_data, list), "Verification queue response is not a list"
        assert len(queue_data) > 0, "No pending verification submissions available to approve"
        submission_id = queue_data[0].get("id") or queue_data[0].get("submission_id")
        assert submission_id, "submission_id not found in verification queue item"
    except AssertionError:
        # If queue is empty or error, cannot proceed with approve test
        raise
    except Exception as e:
        raise RuntimeError(f"Exception while fetching verification submissions: {e}")

    # Step 2: Approve submission with admin JWT - Expect 200
    try:
        resp_approve = requests.post(
            f"{BASE_URL}/api/admin/verification/{submission_id}/approve",
            headers=headers_admin,
            timeout=TIMEOUT
        )
        assert resp_approve.status_code == 200, f"Approve API call did not return 200, got {resp_approve.status_code}"
        # Assuming response is JSON and contains some confirmation or updated status
        resp_json = resp_approve.json()
        assert "id" in resp_json and (resp_json["id"] == submission_id or str(resp_json["id"]) == str(submission_id)), "Response ID mismatch after approving"
    except Exception as e:
        raise RuntimeError(f"Exception during approval with admin token: {e}")

    # Step 3: Approve submission with non-admin token - Expect 403 Forbidden
    try:
        resp_non_admin = requests.post(
            f"{BASE_URL}/api/admin/verification/{submission_id}/approve",
            headers=headers_non_admin,
            timeout=TIMEOUT
        )
        assert resp_non_admin.status_code == 403, f"Non-admin approval did not return 403, got {resp_non_admin.status_code}"
    except Exception as e:
        raise RuntimeError(f"Exception during approval with non-admin token: {e}")

test_approve_verification_submission()