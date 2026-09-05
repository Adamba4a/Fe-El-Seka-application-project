import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

def post_resolve_report_with_admin_auth():
    session = requests.Session()
    session.headers.update(HEADERS)
    timeout = 30

    try:
        # Step 1: Get pending moderation items to obtain a valid report_id
        queue_url = f"{BASE_URL}/api/admin/moderation/queue"
        resp = session.get(queue_url, timeout=timeout)
        assert resp.status_code == 200, f"Expected 200 on queue retrieval but got {resp.status_code}"
        queue_data = resp.json()
        assert isinstance(queue_data, list), "Expected list of moderation items"

        # Find a report ID
        report_id = None
        for item in queue_data:
            if "report_id" in item:
                report_id = item["report_id"]
                break
            if "id" in item:
                # fallback: maybe the report_id is 'id'
                report_id = item["id"]
                break

        assert report_id is not None, "No report_id found in moderation queue to resolve"

        # Step 2: POST to resolve the report
        resolve_url = f"{BASE_URL}/api/admin/moderation/reports/{report_id}/resolve"
        resolve_resp = session.post(resolve_url, timeout=timeout)
        assert resolve_resp.status_code == 200, f"Expected 200 on resolve but got {resolve_resp.status_code}"

        resolved_outcome = resolve_resp.json()
        # We expect the resolved moderation outcome, verify keys presence or type
        assert isinstance(resolved_outcome, dict), "Expected JSON response with resolved moderation outcome"
        # Basic sanity check: outcome likely contains keys like status, message, or outcome
        assert any(key in resolved_outcome for key in ["status", "outcome", "message"]), \
            "Resolved outcome response missing expected keys"

    finally:
        # No resource created in this test, so no deletion needed
        session.close()

post_resolve_report_with_admin_auth()