import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}
TIMEOUT = 30

def test_admin_create_update_delete_loyalty_catalog_entry():
    session = requests.Session()
    session.headers.update(HEADERS)
    catalog_entry_id = None

    try:
        # Create a new catalog voucher (POST)
        create_payload = {
            "title": "Test Voucher",
            "description": "Discount voucher for testing",
            "points_required": 100,
            "valid_from": "2026-09-10T00:00:00Z",
            "valid_until": "2027-09-10T00:00:00Z",
            "max_redeemable": 10,
            "retired": False
        }
        create_response = session.post(
            f"{BASE_URL}/api/admin/loyalty/catalog",
            json=create_payload,
            timeout=TIMEOUT
        )
        assert create_response.status_code == 201, f"Expected status 201, got {create_response.status_code}"
        create_data = create_response.json()
        assert "id" in create_data and isinstance(create_data["id"], (int, str)), "Response missing catalog entry id"
        catalog_entry_id = create_data["id"]

        # Update the catalog voucher (PATCH)
        update_payload = {
            "description": "Updated discount voucher for testing",
            "points_required": 120,
            "max_redeemable": 5
        }
        update_response = session.patch(
            f"{BASE_URL}/api/admin/loyalty/catalog/{catalog_entry_id}",
            json=update_payload,
            timeout=TIMEOUT
        )
        assert update_response.status_code == 200, f"Expected status 200, got {update_response.status_code}"
        update_data = update_response.json()
        assert update_data.get("description") == update_payload["description"], "Description was not updated"
        assert update_data.get("points_required") == update_payload["points_required"], "Points_required was not updated"
        assert update_data.get("max_redeemable") == update_payload["max_redeemable"], "Max_redeemable was not updated"

        # Retire the catalog voucher (DELETE)
        delete_response = session.delete(
            f"{BASE_URL}/api/admin/loyalty/catalog/{catalog_entry_id}",
            timeout=TIMEOUT
        )
        assert delete_response.status_code in (200, 204), f"Expected status 200 or 204, got {delete_response.status_code}"

        # Confirm the catalog voucher is retired (not present)
        get_response = session.get(
            f"{BASE_URL}/api/admin/loyalty/catalog",
            timeout=TIMEOUT
        )
        assert get_response.status_code == 200, f"Expected status 200 on get catalog, got {get_response.status_code}"
        catalog_list = get_response.json()
        # catalog_list expected to be a list or dict containing entries; ensure our retired entry is absent
        if isinstance(catalog_list, dict) and "items" in catalog_list:
            entries = catalog_list["items"]
        elif isinstance(catalog_list, list):
            entries = catalog_list
        else:
            entries = []
        assert all(str(entry.get("id")) != str(catalog_entry_id) for entry in entries), "Retired catalog entry still present"

    finally:
        # Cleanup if not deleted
        if catalog_entry_id is not None:
            # Try to delete again if exists (ignore errors)
            session.delete(
                f"{BASE_URL}/api/admin/loyalty/catalog/{catalog_entry_id}",
                timeout=TIMEOUT
            )

test_admin_create_update_delete_loyalty_catalog_entry()