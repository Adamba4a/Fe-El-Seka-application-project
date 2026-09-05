import requests

BASE_URL = "http://localhost:8000"

DRIVER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
PASSENGER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI5ZTViMTZlYi0yZWRjLTQ4ZjUtOWNhMy01ZjdkM2IwZjI0MGYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjUwNzg1LCJpYXQiOjE3ODg1NjQzODUsImVtYWlsIjoidGVzdHNwcml0ZS5wYXNzZW5nZXIrNjAwNDdAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2NDM4NX1dLCJzZXNzaW9uX2lkIjoiYzY3ODRmNTEtZTRlMS00ZmYyLTg1ZDYtM2IxYjcyMGVlOWNjIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.LvxYiCpc9BcMinXo0lYWMDCMu6-C9L1ZO5hEDnpxoXKMUa0LowW9NdamiYISGn86U0DjCK_s-EDkBQRSHhzZKQ"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjQ3NjgwLCJpYXQiOjE3ODg1NjEyODAsImVtYWlsIjoiYWRtaW5AdHJpcGx5eS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2MTI4MH1dLCJzZXNzaW9uX2lkIjoiZTZhNGE5MDMtZDBjMy00MWU5LWEyMGQtNzc1NjEwN2RkM2M0IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Ntg7e0ufpK5UYOQ73Ve63NQxVtxWS66NZ0pXZj03Mv2igmU-js51NCIACpMprr8xppT2dcHCqFVNE3ZldH0qnw"

HEADERS_DRIVER = {
    "Authorization": f"Bearer {DRIVER_TOKEN}",
    "Content-Type": "application/json"
}

HEADERS_ADMIN = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}

PASSENGER_ID = "9e5b16eb-2edc-48f5-9ca3-5f7d3b0f240f"


def test_post_api_admin_moderation_review_resolve_suspend_and_reinstate():
    # Step 1: Create a fresh report as DRIVER
    report_payload = {
        "ride_id": "4d10d5ae-dd04-41ad-9acd-58bbfa62ff78",
        "booking_id": "372bf8a9-b117-4b59-914f-63c22c5473c7",
        "reported_user_id": PASSENGER_ID,
        "category": "other",
        "description": "TestSprite TC018 test report"
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/reports",
            json=report_payload,
            headers=HEADERS_DRIVER,
            timeout=30
        )
        assert resp.status_code == 201, f"Unexpected status creating report: {resp.status_code} - {resp.text}"
        report_data = resp.json()
        report_id = report_data.get("report_id")
        assert report_id is not None, "report_id not in response"

        # Step 2: As ADMIN, mark the report as under review
        review_resp = requests.post(
            f"{BASE_URL}/api/admin/moderation/reports/{report_id}/review",
            headers=HEADERS_ADMIN,
            timeout=30
        )
        assert review_resp.status_code == 200, f"Unexpected status on review: {review_resp.status_code} - {review_resp.text}"

        # Step 3: As ADMIN, resolve the report with action "suspend"
        resolve_payload = {
            "action": "suspend",
            "reason": "TestSprite TC018 test: suspend for reinstate verification"
        }
        resolve_resp = requests.post(
            f"{BASE_URL}/api/admin/moderation/reports/{report_id}/resolve",
            json=resolve_payload,
            headers=HEADERS_ADMIN,
            timeout=30
        )
        assert resolve_resp.status_code == 200, f"Unexpected status on resolve suspend: {resolve_resp.status_code} - {resolve_resp.text}"

        # Step 4: As ADMIN, reinstate the suspended user - this must always run to clean up
        reinstate_payload = {
            "reason": "TestSprite TC018 test: reinstating after test suspension"
        }
        reinstate_resp = requests.post(
            f"{BASE_URL}/api/admin/moderation/users/{PASSENGER_ID}/reinstate",
            json=reinstate_payload,
            headers=HEADERS_ADMIN,
            timeout=30
        )
        assert reinstate_resp.status_code == 200, f"Unexpected status on reinstate: {reinstate_resp.status_code} - {reinstate_resp.text}"

    except Exception:
        # If an exception occurred, try to reinstate to clean up
        try:
            requests.post(
                f"{BASE_URL}/api/admin/moderation/users/{PASSENGER_ID}/reinstate",
                json={"reason": "TestSprite TC018 failed test cleanup reinstatement"},
                headers=HEADERS_ADMIN,
                timeout=30
            )
        except Exception:
            pass
        raise


test_post_api_admin_moderation_review_resolve_suspend_and_reinstate()