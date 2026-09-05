import requests

def test_get_admin_dashboard_overview_metrics():
    base_url = "http://localhost:8000"
    endpoint = "/api/admin/dashboard/overview"
    full_url = base_url + endpoint

    admin_token = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
    headers_with_auth = {
        "Authorization": f"Bearer {admin_token}"
    }
    headers_without_auth = {}

    timeout_seconds = 30

    # Test with valid admin JWT - expect 200 and validate response schema/contents
    try:
        response = requests.get(full_url, headers=headers_with_auth, timeout=timeout_seconds)
    except requests.RequestException as e:
        assert False, f"Request with admin JWT failed: {e}"
    assert response.status_code == 200, f"Expected status 200 but got {response.status_code}"

    json_data = None
    try:
        json_data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate that 'dashboard metrics and summary counts' fields exist and are correct types
    # The PRD does not specify exact field names, so check presence of keys typically expected
    # Example expected keys (adjust if needed):
    expected_keys = ["total_users", "total_rides", "pending_verifications", "summary_counts"]

    for key in expected_keys:
        assert key in json_data, f"Missing expected key '{key}' in dashboard overview response"

    # Check some nested structure type assertions if summary_counts exists
    if "summary_counts" in json_data:
        assert isinstance(json_data["summary_counts"], dict), "'summary_counts' should be a dict"

    # Test without admin JWT - expect 403 Forbidden
    try:
        response_no_auth = requests.get(full_url, headers=headers_without_auth, timeout=timeout_seconds)
    except requests.RequestException as e:
        assert False, f"Request without admin JWT failed: {e}"
    assert response_no_auth.status_code == 403, f"Expected status 403 but got {response_no_auth.status_code}"

test_get_admin_dashboard_overview_metrics()