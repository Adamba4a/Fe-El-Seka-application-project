import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def test_admin_fulfill_loyalty_redemption_request():
    redemption_request_id = None
    try:
        # Step 1: Get pending loyalty redemption requests
        queue_url = f"{BASE_URL}/api/admin/loyalty/queue"
        resp_queue = requests.get(queue_url, headers=HEADERS, timeout=30)
        assert resp_queue.status_code == 200, f"Expected 200, got {resp_queue.status_code}"
        queue_data = resp_queue.json()
        assert isinstance(queue_data, list), "Queue response should be a list"

        # If no pending requests, cannot fulfill; skip test but fail gracefully
        if not queue_data:
            raise Exception("No pending loyalty redemption requests available to fulfill")

        # Use the first pending redemption request id
        redemption_request_id = queue_data[0].get("id") or queue_data[0].get("redemption_request_id")
        assert redemption_request_id is not None, "redemption_request_id not found in queue item"

        # Step 2: Fulfill the loyalty redemption request
        fulfill_url = f"{BASE_URL}/api/admin/loyalty/queue/{redemption_request_id}/fulfill"
        resp_fulfill = requests.post(fulfill_url, headers=HEADERS, timeout=30)
        assert resp_fulfill.status_code == 200, f"Expected 200, got {resp_fulfill.status_code}"
        resp_json = resp_fulfill.json()
        # Confirm the response indicates successful fulfillment
        assert "fulfilled" in resp_json or "status" in resp_json or "message" in resp_json, \
            "Fulfillment confirmation keys missing in response"

    except requests.RequestException as e:
        raise AssertionError(f"HTTP request failed: {e}")
    except Exception as ex:
        raise AssertionError(f"Test failed: {ex}")

test_admin_fulfill_loyalty_redemption_request()