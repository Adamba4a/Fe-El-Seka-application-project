import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}

def test_get_api_v1_reports_mine_list_reports():
    url = f"{BASE_URL}/api/v1/reports/mine"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        assert isinstance(data, dict), "Response data should be a dict"
        # If response contains a list of reports, check the first item
        reports = None
        for key, value in data.items():
            if isinstance(value, list):
                reports = value
                break
        if reports:
            sample_report = reports[0]
            assert isinstance(sample_report, dict), "Each report should be a dict"
            assert "id" in sample_report, "Report should have an 'id' field"
            assert "created_at" in sample_report or "createdAt" in sample_report, "Report should have a creation timestamp"
    except requests.HTTPError as http_err:
        assert False, f"HTTP error occurred: {http_err}"
    except requests.RequestException as req_err:
        assert False, f"Request error occurred: {req_err}"
    except ValueError:
        assert False, "Response is not valid JSON"

test_get_api_v1_reports_mine_list_reports()
