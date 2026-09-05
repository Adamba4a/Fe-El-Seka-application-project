import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtM WE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def test_post_wallet_withdrawals_creates_withdrawal_request():
    url = f"{BASE_URL}/api/wallet/withdrawals"
    # Define valid payload fields as per PRD for withdrawal request
    payload = {
        "amount_egp": 10.0,  # Required field, positive amount in EGP
        "payout_reference": "Test payout reference"
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    # The expected success status codes are 200 or 201 indicating creation.
    assert response.status_code in (200, 201), f"Unexpected status code: {response.status_code}, response: {response.text}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate response contains created withdrawal request info
    assert "id" in data, f"Response JSON missing 'id': {data}"
    assert "amount_egp" in data, f"Response JSON missing 'amount_egp': {data}"
    try:
        assert float(data["amount_egp"]) == payload["amount_egp"], f"Withdrawal amount_egp mismatch: sent {payload['amount_egp']} vs received {data['amount_egp']}"
    except (ValueError, TypeError):
        assert False, f"Invalid amount_egp type in response: {data['amount_egp']}"


test_post_wallet_withdrawals_creates_withdrawal_request()
