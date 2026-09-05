import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}
TIMEOUT = 30


def test_get_wallet_topup_settings_returns_limits_for_driver():
    url = f"{BASE_URL}/api/wallet/topup/settings"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request to {url} failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Check for keys that specify top-up limits according to typical API
    assert ('min_amount' in data and 'max_amount' in data) or ('min_topup' in data and 'max_topup' in data), \
        "Response must contain min and max top-up limit fields"

    # Determine keys for min and max limits
    if 'min_amount' in data and 'max_amount' in data:
        min_limit = data['min_amount']
        max_limit = data['max_amount']
    else:
        min_limit = data['min_topup']
        max_limit = data['max_topup']

    assert isinstance(min_limit, (int, float)), "min limit should be a number"
    assert isinstance(max_limit, (int, float)), "max limit should be a number"
    assert max_limit >= min_limit, "max limit should be >= min limit"

    # Optional: currency field check if present
    if "currency" in data:
        assert isinstance(data["currency"], str) and len(data["currency"]) > 0, "'currency' should be a non-empty string"

    # Optional additional keys validation if present
    if "rules" in data:
        assert isinstance(data["rules"], (dict, list)), "'rules' should be dict or list if present"


test_get_wallet_topup_settings_returns_limits_for_driver()
