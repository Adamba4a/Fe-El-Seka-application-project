import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}


def test_redeem_loyalty_points_with_sufficient_balance():
    # Step 1: Get current loyalty balance
    balance_resp = requests.get(
        f"{BASE_URL}/api/v1/loyalty/balance", headers=HEADERS, timeout=30
    )
    assert balance_resp.status_code == 200, f"Balance fetch failed: {balance_resp.text}"

    balance_data = balance_resp.json()
    # Try to find points key in common naming
    if "points" in balance_data and isinstance(balance_data["points"], int):
        current_points = balance_data["points"]
    elif "balance" in balance_data and isinstance(balance_data["balance"], int):
        current_points = balance_data["balance"]
    else:
        # fallback: check if any int field exists
        int_points = [v for v in balance_data.values() if isinstance(v, int)]
        assert int_points, "Invalid points in balance response"
        current_points = int_points[0]

    assert current_points > 0, "User has insufficient loyalty points to proceed with redemption"

    # Step 2: Get the loyalty catalog entries
    catalog_resp = requests.get(
        f"{BASE_URL}/api/v1/loyalty/catalog", headers=HEADERS, timeout=30
    )
    assert catalog_resp.status_code == 200, f"Catalog fetch failed: {catalog_resp.text}"

    catalog_entries = catalog_resp.json()
    assert isinstance(catalog_entries, list) and len(catalog_entries) > 0, "No catalog entries available"

    # Find a catalog entry that requires points <= current_points
    catalog_entry_to_redeem = None
    for entry in catalog_entries:
        # Schema of entry is assumed to have 'id' and 'points_required'
        points_required = entry.get("points_required")
        entry_id = entry.get("id")
        if (
            entry_id is not None
            and isinstance(points_required, int)
            and points_required <= current_points
        ):
            catalog_entry_to_redeem = entry
            break

    assert catalog_entry_to_redeem is not None, "No catalog entry found with redeemable points requirement"

    catalog_entry_id = catalog_entry_to_redeem["id"]
    points_required = catalog_entry_to_redeem["points_required"]

    # Step 3: Redeem loyalty points for the selected catalog entry
    redeem_resp = requests.post(
        f"{BASE_URL}/api/v1/loyalty/catalog/{catalog_entry_id}/redeem",
        headers=HEADERS,
        timeout=30
    )
    assert redeem_resp.status_code == 200, f"Redemption failed: {redeem_resp.text}"

    redeem_data = redeem_resp.json()
    # Validate some confirmation keys in redeem_data
    # Assuming response contains at least a confirmation message and deducted points
    assert "message" in redeem_data or "confirmation" in redeem_data, "Missing confirmation in redeem response"

    # Step 4: Confirm points deduction by fetching balance again
    balance_after_resp = requests.get(
        f"{BASE_URL}/api/v1/loyalty/balance", headers=HEADERS, timeout=30
    )
    assert balance_after_resp.status_code == 200, f"Balance fetch after redemption failed: {balance_after_resp.text}"

    balance_after_data = balance_after_resp.json()

    if "points" in balance_after_data and isinstance(balance_after_data["points"], int):
        points_after = balance_after_data["points"]
    elif "balance" in balance_after_data and isinstance(balance_after_data["balance"], int):
        points_after = balance_after_data["balance"]
    else:
        int_points_after = [v for v in balance_after_data.values() if isinstance(v, int)]
        assert int_points_after, "Invalid points in balance response after redemption"
        points_after = int_points_after[0]

    assert points_after == current_points - points_required or points_after <= current_points - points_required, (
        "Points after redemption did not decrease correctly"
    )


test_redeem_loyalty_points_with_sufficient_balance()
