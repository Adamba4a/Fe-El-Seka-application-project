import requests

BASE_URL = "http://localhost:8000"
DRIVER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjQ3NjgwLCJpYXQiOjE3ODg1NjEyODAsImVtYWlsIjoiYWRtaW5AdHJpcGx5eS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2MTI4MH1dLCJzZXNzaW9uX2lkIjoiZTZhNGE5MDMtZDBjMy00MWU5LWEyMGQtNzc1NjEwN2RkM2M0IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Ntg7e0ufpK5UYOQ73Ve63NQxVtxWS66NZ0pXZj03Mv2igmU-js51NCIACpMprr8xppT2dcHCqFVNE3ZldH0qnw"

def test_post_api_admin_moderation_review_and_resolve_dismiss():
    # Step 1: Create a fresh report as DRIVER
    create_report_url = f"{BASE_URL}/api/v1/reports"
    report_payload = {
        "ride_id": "4d10d5ae-dd04-41ad-9acd-58bbfa62ff78",
        "booking_id": "372bf8a9-b117-4b59-914f-63c22c5473c7",
        "reported_user_id": "9e5b16eb-2edc-48f5-9ca3-5f7d3b0f240f",
        "category": "other",
        "description": "TestSprite TC017 test report"
    }
    headers_driver = {
        "Authorization": f"Bearer {DRIVER_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    response = requests.post(create_report_url, json=report_payload, headers=headers_driver, timeout=30)
    assert response.status_code == 201, f"Failed to create report, status: {response.status_code}, body: {response.text}"
    resp_json = response.json()
    report_id = resp_json.get("report_id") or resp_json.get("id")
    assert report_id, f"report_id not found in response: {resp_json}"

    # Step 2: As ADMIN, mark report under review
    review_url = f"{BASE_URL}/api/admin/moderation/reports/{report_id}/review"
    headers_admin = {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Accept": "application/json"
    }
    response_review = requests.post(review_url, headers=headers_admin, timeout=30)
    assert response_review.status_code == 200, f"Failed to mark report under review, status: {response_review.status_code}, body: {response_review.text}"

    # Step 3: As ADMIN, resolve the report with dismiss action
    resolve_url = f"{BASE_URL}/api/admin/moderation/reports/{report_id}/resolve"
    resolve_payload = {
        "action": "dismiss",
        "reason": "TestSprite TC017 test: no action needed"
    }
    headers_admin_json = {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    response_resolve = requests.post(resolve_url, json=resolve_payload, headers=headers_admin_json, timeout=30)
    assert response_resolve.status_code == 200, f"Failed to resolve report with dismiss, status: {response_resolve.status_code}, body: {response_resolve.text}"

test_post_api_admin_moderation_review_and_resolve_dismiss()