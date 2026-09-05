import requests
import uuid
import base64

BASE_URL = "http://localhost:8000"
DRIVER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjQ3NjgwLCJpYXQiOjE3ODg1NjEyODAsImVtYWlsIjoiYWRtaW5AdHJpcGx5eS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2MTI4MH1dLCJzZXNzaW9uX2lkIjoiZTZhNGE5MDMtZDBjMy00MWU5LWEyMGQtNzc1NjEwN2RkM2M0IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Ntg7e0ufpK5UYOQ73Ve63NQxVtxWS66NZ0pXZj03Mv2igmU-js51NCIACpMprr8xppT2dcHCqFVNE3ZldH0qnw"


def test_post_api_wallet_topup_submit_and_admin_approve():
    driver_headers = {
        "Authorization": f"Bearer {DRIVER_TOKEN}"
    }
    admin_headers = {
        "Authorization": f"Bearer {ADMIN_TOKEN}"
    }

    # Generate a unique random payment reference
    random_suffix = uuid.uuid4().hex
    payment_reference = f"TESTSPRITE-TC010-{random_suffix}"
    amount_egp = "300.00"

    # Prepare the screenshot file content (1x1 PNG, base64 decoded)
    png_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY"
        "42YAAAAASUVORK5CYII="
    )
    png_bytes = base64.b64decode(png_base64)

    files = {
        "screenshot": ("receipt.png", png_bytes, "image/png")
    }

    data = {
        "amount_egp": amount_egp,
        "payment_reference": payment_reference,
    }

    # Submit top-up request as DRIVER (multipart/form-data POST)
    try:
        resp = requests.post(
            f"{BASE_URL}/api/wallet/topup",
            headers=driver_headers,
            data=data,
            files=files,
            timeout=30,
        )
        assert resp.status_code == 201, f"Unexpected status code: {resp.status_code}, body: {resp.text}"
        resp_json = resp.json()
        assert "id" in resp_json, "Response JSON missing 'id'"
        topup_id = resp_json["id"]

        # Approve the top-up request as ADMIN
        approve_resp = requests.post(
            f"{BASE_URL}/api/admin/wallet-topup-requests/{topup_id}/approve",
            headers=admin_headers,
            timeout=30
        )
        assert approve_resp.status_code == 200, f"Unexpected status code for approve: {approve_resp.status_code}, body: {approve_resp.text}"
        approve_json = approve_resp.json()
        # Check that new_balance_egp is included and is numeric
        assert "new_balance_egp" in approve_json, "Approve response missing 'new_balance_egp'"
        assert isinstance(approve_json["new_balance_egp"], (int, float, str)), "'new_balance_egp' is not a number or string"

    finally:
        # Cleanup: Attempt to cancel/cancel the top-up if possible
        # If cancel endpoint exists, fallback to deleting or ignoring otherwise
        if 'topup_id' in locals():
            try:
                # Try to cancel the top-up request to clean up (may or may not be allowed)
                cancel_resp = requests.post(
                    f"{BASE_URL}/api/wallet/topup/{topup_id}/cancel",
                    headers=driver_headers,
                    timeout=10,
                )
                # Accept 200 or 404 or 204 as reasonable cleanup
                if cancel_resp.status_code not in [200, 204, 404]:
                    pass  # ignore cleanup issues
            except Exception:
                pass


test_post_api_wallet_topup_submit_and_admin_approve()