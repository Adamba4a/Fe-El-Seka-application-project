import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_api_verification_submit_verification_documents():
    url = f"{BASE_URL}/api/verification"

    # Since PRD specifies required fields, empty {} is invalid payload, expect 422

    # Test invalid payloads including empty payload
    invalid_payloads = [
        {},  # empty payload
        {"unexpected_field": "value"},  # unexpected field
        None,  # null payload
        "string instead of json",  # invalid type
    ]

    for idx, payload in enumerate(invalid_payloads, 1):
        if payload is None:
            # Sending empty body (null payload)
            resp = requests.post(url, headers=HEADERS, timeout=30)
        elif isinstance(payload, str):
            # Sending invalid json payload as string
            resp = requests.post(url, data=payload, headers=HEADERS, timeout=30)
        else:
            resp = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        try:
            assert resp.status_code == 422, f"Invalid payload #{idx} expected 422, got {resp.status_code}"
            json_resp = resp.json()
            assert "detail" in json_resp, f"Invalid payload #{idx} missing 'detail' in response"
        except Exception as e:
            raise AssertionError(f"Invalid payload #{idx} validation failed: {e}")

    # Since no valid example payload is available from PRD, do not test a valid payload here


test_post_api_verification_submit_verification_documents()
