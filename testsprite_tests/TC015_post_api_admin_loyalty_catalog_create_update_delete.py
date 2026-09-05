import requests
import uuid

BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjQ3NjgwLCJpYXQiOjE3ODg1NjEyODAsImVtYWlsIjoiYWRtaW5AdHJpcGx5eS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2MTI4MH1dLCJzZXNzaW9uX2lkIjoiZTZhNGE5MDMtZDBjMy00MWU5LWEyMGQtNzc1NjEwN2RkM2M0IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Ntg7e0ufpK5UYOQ73Ve63NQxVtxWS66NZ0pXZj03Mv2igmU-js51NCIACpMprr8xppT2dcHCqFVNE3ZldH0qnw"
HEADERS = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}
TIMEOUT = 30

def test_post_api_admin_loyalty_catalog_create_update_delete():
    # Generate a random suffix for uniqueness
    random_suffix = str(uuid.uuid4())
    created_id = None
    try:
        # Create a loyalty catalog entry
        create_payload = {
            "title": f"TestSprite TC015 Voucher {random_suffix}",
            "description": "Disposable voucher for TestSprite CUD test.",
            "audience": "passenger",
            "point_cost": 10,
            "fulfillment_mode": "instant"
        }
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/loyalty/catalog",
            json=create_payload,
            headers=HEADERS,
            timeout=TIMEOUT
        )
        assert create_resp.status_code in (200, 201), f"Expected 201 or 200 on create, got {create_resp.status_code}"
        create_json = create_resp.json()
        assert "id" in create_json, "Response missing 'id' on create"
        created_id = create_json["id"]

        # Update the loyalty catalog entry via PATCH
        update_payload = {
            "point_cost": 20
        }
        patch_resp = requests.patch(
            f"{BASE_URL}/api/admin/loyalty/catalog/{created_id}",
            json=update_payload,
            headers=HEADERS,
            timeout=TIMEOUT
        )
        assert patch_resp.status_code == 200, f"Expected 200 on patch, got {patch_resp.status_code}"

        # Delete the loyalty catalog entry
        delete_resp = requests.delete(
            f"{BASE_URL}/api/admin/loyalty/catalog/{created_id}",
            headers=HEADERS,
            timeout=TIMEOUT
        )
        assert delete_resp.status_code in (200, 204), f"Expected 200 or 204 on delete, got {delete_resp.status_code}"
        created_id = None  # Deleted successfully, no need to cleanup further

    finally:
        # Cleanup in case of failure before delete
        if created_id is not None:
            try:
                _ = requests.delete(
                    f"{BASE_URL}/api/admin/loyalty/catalog/{created_id}",
                    headers=HEADERS,
                    timeout=TIMEOUT
                )
            except Exception:
                pass

test_post_api_admin_loyalty_catalog_create_update_delete()
