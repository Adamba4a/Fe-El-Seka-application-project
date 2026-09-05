import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json"
}
TIMEOUT = 30

def test_get_wallet_topup_returns_driver_topup_history():
    url = f"{BASE_URL}/api/wallet/topup"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"HTTP request failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate response is a dict containing a list of top-up requests
    assert isinstance(data, dict), f"Expected response to be a dict, got {type(data)}"

    # The key containing the top-up requests list might be 'topup_requests' or 'items'
    # We check for common expected key names
    if 'topup_requests' in data:
        topup_list = data['topup_requests']
    elif 'items' in data:
        topup_list = data['items']
    else:
        # fallback: try to find any list value
        lists = [v for v in data.values() if isinstance(v, list)]
        assert lists, "No list found in response data for top-up requests"
        topup_list = lists[0]

    assert isinstance(topup_list, list), f"Expected a list of top-up requests, got {type(topup_list)}"

    # If there are any top-up requests, check expected fields in first element
    if topup_list:
        first = topup_list[0]
        assert isinstance(first, dict), "Each top-up request should be a dictionary"
        expected_keys = {"id", "amount", "reference", "status", "created_at"}
        missing_keys = expected_keys - first.keys()
        assert not missing_keys, f"Missing expected keys in top-up request: {missing_keys}"

test_get_wallet_topup_returns_driver_topup_history()
