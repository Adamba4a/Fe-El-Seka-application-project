import requests

ADMIN_JWT = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjQ3NjgwLCJpYXQiOjE3ODg1NjEyODAsImVtYWlsIjoiYWRtaW5AdHJpcGx5eS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2MTI4MH1dLCJzZXNzaW9uX2lkIjoiZTZhNGE5MDMtZDBjMy00MWU5LWEyMGQtNzc1NjEwN2RkM2M0IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Ntg7e0ufpK5UYOQ73Ve63NQxVtxWS66NZ0pXZj03Mv2igmU-js51NCIACpMprr8xppT2dcHCqFVNE3ZldH0qnw"

def test_get_admin_moderation_queue_with_admin_auth():
    url = "http://localhost:8000/api/admin/moderation/queue"
    headers = {
        "Authorization": f"Bearer {ADMIN_JWT}"
    }
    timeout = 30

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        # Check response status code
        assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"
        # Check response body is a dict
        json_body = response.json()
        assert isinstance(json_body, dict), f"Expected response body to be a dict but got {type(json_body)}"
        # Check it contains the 'items' key which should be a list
        assert 'items' in json_body, "Response JSON does not contain 'items' key"
        assert isinstance(json_body['items'], list), f"Expected 'items' to be a list but got {type(json_body['items'])}"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"


test_get_admin_moderation_queue_with_admin_auth()