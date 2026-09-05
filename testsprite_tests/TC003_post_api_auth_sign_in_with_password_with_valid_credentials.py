import requests

def test_post_api_auth_sign_in_with_password_with_valid_credentials():
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/auth/sign-in-with-password"
    json_data = {
        "email": "testsprite.drive+4f241358@example.com",
        "password": "password"
    }
    try:
        response = requests.post(url, json=json_data, timeout=30)
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        json_resp = response.json()
        # Assert presence of session tokens in response
        assert "access_token" in json_resp or "accessToken" in json_resp, "access token missing in response"
        assert "refresh_token" in json_resp or "refreshToken" in json_resp, "refresh token missing in response"
        # Optionally check for user or session id in response
        assert "user" in json_resp or "session" in json_resp or "session_id" in json_resp, "user/session info missing in response"
    except requests.Timeout:
        assert False, "Request timed out"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

test_post_api_auth_sign_in_with_password_with_valid_credentials()