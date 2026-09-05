import requests
import uuid

BASE_URL = "http://localhost:8000"
DRIVER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjQ3NjgwLCJpYXQiOjE3ODg1NjEyODAsImVtYWlsIjoiYWRtaW5AdHJpcGx5eS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2MTI4MH1dLCJzZXNzaW9uX2lkIjoiZTZhNGE5MDMtZDBjMy00MWU5LWEyMGQtNzc1NjEwN2RkM2M0IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Ntg7e0ufpK5UYOQ73Ve63NQxVtxWS66NZ0pXZj03Mv2igmU-js51NCIACpMprr8xppT2dcHCqFVNE3ZldH0qnw"
DRIVER_ID = "2b61b48e-1ec2-4cb3-b2c1-750d0f563bd6"
TIMEOUT = 30

def test_post_api_wallet_topup_submit_and_admin_reject():
    # Prepare headers
    driver_headers = {
        "Authorization": f"Bearer {DRIVER_TOKEN}",
    }
    admin_headers = {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
    }

    # Prepare multipart form data for wallet top-up submission
    random_suffix = uuid.uuid4().hex
    amount_egp = "50.00"
    payment_reference = f"TESTSPRITE-TC011-{random_suffix}"
    screenshot_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\xdac`\x00\x00\x00"
        b"\x02\x00\x01\xe2!\xbc33\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    files = {
        "amount_egp": (None, amount_egp),
        "payment_reference": (None, payment_reference),
        "screenshot": ("receipt.png", screenshot_bytes, "image/png"),
    }

    # Submit wallet top-up request as driver
    topup_submit_url = f"{BASE_URL}/api/wallet/topup"
    resp = requests.post(topup_submit_url, headers=driver_headers, files=files, timeout=TIMEOUT)
    assert resp.status_code == 201, f"Expected 201 from wallet top-up submit, got {resp.status_code}"
    resp_json = resp.json()
    assert "id" in resp_json, "Response missing 'id' field after wallet top-up submit"
    request_id = resp_json["id"]

    try:
        # Admin rejects the wallet top-up request
        reject_url = f"{BASE_URL}/api/admin/wallet-topup-requests/{request_id}/reject"
        reject_payload = {"reason": "TestSprite TC011 test rejection"}
        reject_resp = requests.post(reject_url, headers=admin_headers, json=reject_payload, timeout=TIMEOUT)
        assert reject_resp.status_code == 200, f"Expected 200 from admin reject top-up, got {reject_resp.status_code}"

        # Admin unlocks the driver top-up capability
        unlock_url = f"{BASE_URL}/api/admin/wallet-topup-requests/drivers/{DRIVER_ID}/unlock"
        unlock_resp = requests.post(unlock_url, headers=admin_headers, timeout=TIMEOUT)
        assert unlock_resp.status_code == 200, f"Expected 200 from admin unlocking driver, got {unlock_resp.status_code}"

    finally:
        # Cleanup: attempt to cancel the top-up request if it still exists and not rejected
        # (The PRD doesn't define an admin endpoint to delete topup requests, so cancellation is by driver)
        cancel_url = f"{BASE_URL}/api/wallet/topup/{request_id}/cancel"
        # Cancel only if request still exists and cancelable
        cancel_resp = requests.post(cancel_url, headers=driver_headers, timeout=TIMEOUT)
        # Either 200 for successful cancel or 404/400 if already processed or not found; no assertion needed

test_post_api_wallet_topup_submit_and_admin_reject()