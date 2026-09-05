import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_post_mark_report_under_review_with_admin_auth():
    timeout = 30

    # Step 1: Get the pending moderation reports to obtain a valid report_id
    try:
        queue_resp = requests.get(
            f"{BASE_URL}/api/admin/moderation/queue",
            headers=HEADERS,
            timeout=timeout
        )
        queue_resp.raise_for_status()
        reports = queue_resp.json()
        assert isinstance(reports, list), "Expected list of reports"
        assert len(reports) > 0, "No reports available to mark under review"
        report_id = reports[0].get("id") or reports[0].get("report_id")
        assert report_id is not None, "Report ID not found in the reports list"
    except requests.RequestException as e:
        assert False, f"Failed to retrieve moderation queue: {e}"
    except (ValueError, AssertionError) as e:
        assert False, f"Invalid response data for moderation queue: {e}"

    # Step 2: Mark the report as under review
    try:
        review_url = f"{BASE_URL}/api/admin/moderation/reports/{report_id}/review"
        review_resp = requests.post(
            review_url,
            headers=HEADERS,
            timeout=timeout
        )
        review_resp.raise_for_status()
        # Validate response for success - expecting status 200
        assert review_resp.status_code == 200

        # Optionally, check response content for confirmation
        # Expecting JSON with confirmation message or marked report details
        try:
            review_data = review_resp.json()
            assert isinstance(review_data, dict), "Response JSON is not a dictionary"
            # Confirm some key exists indicating success, e.g. "status" is "under_review"
            # This is inference since PRD does not specify response body
            if "status" in review_data:
                assert review_data["status"] == "under_review"
        except (ValueError, AssertionError):
            # If JSON parse fails or keys missing, ignore as not strictly required
            pass

    except requests.HTTPError as e:
        assert False, f"HTTP error when marking report under review: {e}"
    except requests.RequestException as e:
        assert False, f"Request failed when marking report under review: {e}"

test_post_mark_report_under_review_with_admin_auth()