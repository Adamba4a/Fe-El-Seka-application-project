import requests
import time

BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
TIMEOUT = 30

def test_tc006_reject_verification_submission():
    headers_admin = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    headers_no_auth = {}
    
    # Step 1: Get a pending verification submission_id
    try:
        resp_queue = requests.get(f"{BASE_URL}/api/admin/verification/queue", headers=headers_admin, timeout=TIMEOUT)
        assert resp_queue.status_code == 200, f"Expected 200 from verification queue, got {resp_queue.status_code}"
        submissions = resp_queue.json()
        assert isinstance(submissions, list), "Submissions should be a list"
        assert len(submissions) > 0, "No pending verification submissions available to test reject"
        submission_id = submissions[0].get("id") or submissions[0].get("submission_id")
        assert submission_id, "Submission ID not found in pending submissions"
    except Exception as e:
        raise AssertionError(f"Failed to obtain submission_id for test: {e}")
    
    # Step 2: Reject the verification submission with valid admin JWT
    try:
        url_reject = f"{BASE_URL}/api/admin/verification/{submission_id}/reject"
        resp_reject = requests.post(url_reject, headers=headers_admin, timeout=TIMEOUT)
        assert resp_reject.status_code == 200, f"Expected 200 on rejecting submission, got {resp_reject.status_code}"
        # Since FCM push notifications are mocked/skipped locally, we validate only status code
    except Exception as e:
        raise AssertionError(f"Reject request with admin token failed: {e}")
    
    # Step 3: Reject with no auth header - expect 403 Forbidden
    try:
        url_reject = f"{BASE_URL}/api/admin/verification/{submission_id}/reject"
        resp_reject_no_auth = requests.post(url_reject, headers=headers_no_auth, timeout=TIMEOUT)
        assert resp_reject_no_auth.status_code == 403, f"Expected 403 forbidden without auth, got {resp_reject_no_auth.status_code}"
    except Exception as e:
        raise AssertionError(f"Reject request without auth did not return 403: {e}")

test_tc006_reject_verification_submission()