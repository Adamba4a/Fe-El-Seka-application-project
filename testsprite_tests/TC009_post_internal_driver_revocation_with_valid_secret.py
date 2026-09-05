import requests

def test_post_internal_driver_revocation_with_valid_secret():
    url = "http://localhost:8000/api/v1/internal/driver-revocation"
    headers = {
        "X-Webhook-Secret": "a59ca77cbed50b91a108377020a600571309ddc70302fc4dc1126ede2e924c67",
        "Content-Type": "application/json"
    }
    payload = {
        "driver_id": "2b61b48e-1ec2-4cb3-b2c1-750d0f563bd6",
        "revocation_type": "suspend"
    }
    timeout = 30

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

test_post_internal_driver_revocation_with_valid_secret()