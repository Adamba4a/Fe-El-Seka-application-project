import requests

BASE_URL = "http://localhost:8000"
ENDPOINT = "/api/v1/users/me/device-tokens"
TIMEOUT = 30

def test_post_users_me_device_tokens_without_authentication():
    url = f"{BASE_URL}{ENDPOINT}"
    payload = {
        "device_token": "example.device.token"
    }
    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 401, f"Expected 401 Unauthorized, got {response.status_code}"
    # Optionally assert response content for unauthorized message if available
    try:
        resp_json = response.json()
        assert "detail" in resp_json or "error" in resp_json, "Response JSON should contain error details"
    except ValueError:
        pass  # Response is not JSON, ignore

test_post_users_me_device_tokens_without_authentication()