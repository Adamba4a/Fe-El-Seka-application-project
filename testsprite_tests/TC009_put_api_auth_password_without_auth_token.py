import requests

def test_put_api_auth_password_without_auth_token():
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/auth/password"
    payload = {
        "password": "NewPassword123!"
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.put(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 401, (
        f"Expected status code 401 Unauthorized, got {response.status_code}, response: {response.text}"
    )

test_put_api_auth_password_without_auth_token()