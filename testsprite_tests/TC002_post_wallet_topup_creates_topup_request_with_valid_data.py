import requests
from requests.exceptions import RequestException

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_post_wallet_topup_creates_topup_request_with_valid_data():
    url = f"{BASE_URL}/api/wallet/topup"
    payload = {
        "amount": 100.0,
        "reference_data": {"notes": "Test top-up reference"}
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        # Validate status code 200 or 201 (created)
        assert response.status_code in (200, 201), f"Unexpected status code: {response.status_code}"
        # Validate response body contains an id and matches amount and reference_data
        assert "id" in data, "Response JSON missing 'id'"
        assert isinstance(data["id"], (int, str)), "'id' should be int or str"
        assert "amount" in data, "Response JSON missing 'amount'"
        assert float(data["amount"]) == payload["amount"], f"Amount mismatch: expected {payload['amount']} got {data['amount']}"
        assert "reference_data" in data, "Response JSON missing 'reference_data'"
        assert data["reference_data"] == payload["reference_data"], f"Reference_data mismatch: expected {payload['reference_data']} got {data['reference_data']}"
    except RequestException as e:
        assert False, f"Request failed: {e}"
    except AssertionError as e:
        assert False, f"Assertion failed: {e}"

test_post_wallet_topup_creates_topup_request_with_valid_data()
