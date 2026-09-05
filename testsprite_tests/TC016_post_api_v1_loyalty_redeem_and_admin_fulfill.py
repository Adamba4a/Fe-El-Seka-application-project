import requests
import uuid

BASE_URL = "http://localhost:8000"

DRIVER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
PASSENGER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI5ZTViMTZlYi0yZWRjLTQ4ZjUtOWNhMy01ZjdkM2IwZjI0MGYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjUwNzg1LCJpYXQiOjE3ODg1NjQzODUsImVtYWlsIjoidGVzdHNwcml0ZS5wYXNzZW5nZXIrNjAwNDdAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2NDM4NX1dLCJzZXNzaW9uX2lkIjoiYzY3ODRmNTEtZTRlMS00ZmYyLTg1ZDYtM2IxYjcyMGVlOWNjIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.LvxYiCpc9BcMinXo0lYWMDCMu6-C9L1ZO5hEDnpxoXKMUa0LowW9NdamiYISGn86U0DjCK_s-EDkBQRSHhzZKQ"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjQ3NjgwLCJpYXQiOjE3ODg1NjEyODAsImVtYWlsIjoiYWRtaW5AdHJpcGx5eS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2MTI4MH1dLCJzZXNzaW9uX2lkIjoiZTZhNGE5MDMtZDBjMy00MWU5LWEyMGQtNzc1NjEwN2RkM2M0IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Ntg7e0ufpK5UYOQ73Ve63NQxVtxWS66NZ0pXZj03Mv2igmU-js51NCIACpMprr8xppT2dcHCqFVNE3ZldH0qnw"

def test_post_api_v1_loyalty_redeem_and_admin_fulfill():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    timeout = 30

    admin_headers = {
        "Authorization": f"Bearer {ADMIN_TOKEN}"
    }
    passenger_headers = {
        "Authorization": f"Bearer {PASSENGER_TOKEN}"
    }

    # Step 1: As ADMIN, create a loyalty catalog entry with manual fulfillment
    random_suffix = uuid.uuid4().hex
    catalog_entry_payload = {
        "title": f"TestSprite TC016 Redeem Voucher {random_suffix}",
        "description": "Disposable voucher for TestSprite redemption test.",
        "audience": "passenger",
        "point_cost": 10,
        "fulfillment_mode": "manual"
    }
    resp_create = session.post(
        f"{BASE_URL}/api/admin/loyalty/catalog",
        headers=admin_headers,
        json=catalog_entry_payload,
        timeout=timeout,
    )
    assert resp_create.status_code in (200, 201), f"Expected 200 or 201, got {resp_create.status_code}, body: {resp_create.text}"
    data_create = resp_create.json()
    assert "id" in data_create, "Response JSON missing 'id'"
    catalog_entry_id = data_create["id"]

    try:
        # Step 2: As PASSENGER, confirm sufficient loyalty points balance (optional but recommended)
        resp_balance = session.get(
            f"{BASE_URL}/api/v1/loyalty/balance",
            headers=passenger_headers,
            timeout=timeout,
        )
        assert resp_balance.status_code == 200, f"Expected 200 on balance, got {resp_balance.status_code}, body: {resp_balance.text}"
        balance_data = resp_balance.json()
        # Extract points balance with flexibility if shape varies
        points_balance = None
        if isinstance(balance_data, dict):
            for key in ["points", "balance", "points_balance"]:
                if key in balance_data and isinstance(balance_data[key], (int, float)):
                    points_balance = balance_data[key]
                    break
            # fallback in nested keys or direct int/float data
            if points_balance is None:
                for v in balance_data.values():
                    if isinstance(v, (int, float)):
                        points_balance = v
                        break
        assert points_balance is not None and points_balance >= 10, f"Passenger has insufficient points ({points_balance}), requires at least 10"

        # Step 3: As PASSENGER, redeem the catalog entry
        redeem_url = f"{BASE_URL}/api/v1/loyalty/catalog/{catalog_entry_id}/redeem"
        resp_redeem = session.post(
            redeem_url,
            headers=passenger_headers,
            json={},  # empty JSON body as specified
            timeout=timeout,
        )
        assert resp_redeem.status_code in [200, 201], f"Expected 200 or 201 from redeem, got {resp_redeem.status_code}, body: {resp_redeem.text}"
        redeem_data = resp_redeem.json()
        assert "redemption_request_id" in redeem_data, "Response JSON missing 'redemption_request_id'"
        redemption_request_id = redeem_data["redemption_request_id"]

        # Step 4: As ADMIN, fulfill the redemption request
        fulfill_url = f"{BASE_URL}/api/admin/loyalty/queue/{redemption_request_id}/fulfill"
        resp_fulfill = session.post(
            fulfill_url,
            headers=admin_headers,
            timeout=timeout,
        )
        assert resp_fulfill.status_code == 200, f"Expected 200 from fulfillment, got {resp_fulfill.status_code}, body: {resp_fulfill.text}"

    finally:
        # Cleanup: Attempt to delete the created catalog entry
        del_url = f"{BASE_URL}/api/admin/loyalty/catalog/{catalog_entry_id}"
        try:
            resp_delete = session.delete(
                del_url,
                headers=admin_headers,
                timeout=timeout,
            )
            # Accept 200 or 204 or 202 as success for deletion
            assert resp_delete.status_code in (200, 202, 204), f"Failed to delete catalog entry, status: {resp_delete.status_code}, body: {resp_delete.text}"
        except Exception:
            # Ignore exceptions during cleanup
            pass

test_post_api_v1_loyalty_redeem_and_admin_fulfill()
