import requests
import uuid

ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjQ3NjgwLCJpYXQiOjE3ODg1NjEyODAsImVtYWlsIjoiYWRtaW5AdHJpcGx5eS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2MTI4MH1dLCJzZXNzaW9uX2lkIjoiZTZhNGE5MDMtZDBjMy00MWU5LWEyMGQtNzc1NjEwN2RkM2M0IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Ntg7e0ufpK5UYOQ73Ve63NQxVtxWS66NZ0pXZj03Mv2igmU-js51NCIACpMprr8xppT2dcHCqFVNE3ZldH0qnw"

BASE_URL = "http://localhost:8000"


def test_post_api_admin_sponsored_groups_create_and_add_funds():
    headers = {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
    }

    random_suffix = uuid.uuid4().hex[:8]
    payload = {
        "name": f"TestSprite TC014 Sponsored Group {random_suffix}",
        "domains": [f"testsprite-tc014-{random_suffix}.edu"],
        "funded_balance_egp": "1000.00",
    }

    group_id = None
    try:
        create_response = requests.post(
            f"{BASE_URL}/api/admin/sponsored-groups",
            headers=headers,
            json=payload,
            timeout=30,
        )

        assert create_response.status_code in (200, 201), (
            f"Failed to create sponsored group: Status {create_response.status_code} - {create_response.text}"
        )

        json_create = create_response.json()
        group_id = json_create.get("id") or json_create.get("group_id")
        assert group_id, "Response JSON missing group 'id'"

        def get_balance(resp_json):
            for key in ("funded_balance_egp", "balance_egp", "balance", "current_balance"):
                if key in resp_json:
                    try:
                        return float(resp_json[key])
                    except (ValueError, TypeError):
                        continue
            return None

        initial_balance = get_balance(json_create)
        assert initial_balance is not None, "Initial sponsored group balance missing or not numeric"

        add_funds_payload = {"amount_egp": "500.00"}

        add_funds_resp = requests.post(
            f"{BASE_URL}/api/admin/sponsored-groups/{group_id}/add-funds",
            headers=headers,
            json=add_funds_payload,
            timeout=30,
        )

        assert add_funds_resp.status_code == 200, (
            f"Failed to add funds: Status {add_funds_resp.status_code} - {add_funds_resp.text}"
        )

        json_add_funds = add_funds_resp.json()

        added_balance = get_balance(json_add_funds)
        assert added_balance is not None, "Response missing balance after adding funds"
        assert added_balance >= (initial_balance + 500), (
            f"Sponsored group balance after adding funds not increased enough; "
            f"before: {initial_balance}, after: {added_balance}"
        )

    finally:
        if group_id:
            try:
                del_resp = requests.delete(
                    f"{BASE_URL}/api/admin/sponsored-groups/{group_id}",
                    headers=headers,
                    timeout=30,
                )
                assert del_resp.status_code in (200, 204), (
                    f"Failed to delete sponsored group in cleanup: "
                    f"Status {del_resp.status_code} - {del_resp.text}"
                )
            except Exception as cleanup_ex:
                raise cleanup_ex


test_post_api_admin_sponsored_groups_create_and_add_funds()
