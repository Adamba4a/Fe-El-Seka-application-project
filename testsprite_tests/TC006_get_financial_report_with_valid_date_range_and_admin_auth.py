import requests

def test_get_financial_report_with_valid_date_range_and_admin_auth():
    base_url = "http://localhost:8000"
    endpoint = "/api/admin/financial/report"
    url = base_url + endpoint
    token = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    params = {
        "start_date": "2023-01-01",
        "end_date": "2023-12-31"
    }
    timeout = 30

    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"
        data = response.json()
        # Basic validation of expected financial report structure
        assert "total_revenue" in data, "Missing 'total_revenue' in response"
        assert "total_commission" in data, "Missing 'total_commission' in response"
        assert "net_revenue" in data, "Missing 'net_revenue' in response"
        # Verify financial values are reasonable
        assert isinstance(data["total_revenue"], (int, float)), "'total_revenue' should be numeric"
        assert isinstance(data["total_commission"], (int, float)), "'total_commission' should be numeric"
        assert isinstance(data["net_revenue"], (int, float)), "'net_revenue' should be numeric"
    except requests.exceptions.RequestException as e:
        assert False, f"Request failed: {e}"

test_get_financial_report_with_valid_date_range_and_admin_auth()