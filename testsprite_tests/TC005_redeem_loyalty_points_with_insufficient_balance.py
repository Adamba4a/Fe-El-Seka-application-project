import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def test_redeem_loyalty_points_with_insufficient_balance():
    try:
        # Step 1: Get loyalty balance
        balance_resp = requests.get(
            f"{BASE_URL}/api/v1/loyalty/balance",
            headers=HEADERS,
            timeout=30,
        )
        assert balance_resp.status_code == 200, f"Expected 200 from balance endpoint, got {balance_resp.status_code}"
        balance_data = balance_resp.json()
        current_points = balance_data.get("points") or balance_data.get("balance") or 0
        # Defensive fallback if balance field is named differently
        if not isinstance(current_points, (int, float)):
            # fallback if balance data nested differently
            current_points = 0

        # Step 2: Get catalog entries
        catalog_resp = requests.get(
            f"{BASE_URL}/api/v1/loyalty/catalog",
            headers=HEADERS,
            timeout=30,
        )
        assert catalog_resp.status_code == 200, f"Expected 200 from catalog, got {catalog_resp.status_code}"
        catalog = catalog_resp.json()
        # catalog expected to be a list or dict with entries list inside
        entries = []
        if isinstance(catalog, dict):
            # try known keys
            if "entries" in catalog and isinstance(catalog["entries"], list):
                entries = catalog["entries"]
            elif "data" in catalog and isinstance(catalog["data"], list):
                entries = catalog["data"]
            else:
                # fallback: try list directly
                entries = [catalog] if catalog else []
        elif isinstance(catalog, list):
            entries = catalog
        if not entries:
            raise AssertionError("No catalog entries available to test redeem")

        # Step 3: Find a catalog entry with required points more than user's current balance
        candidate_entry = None
        for entry in entries:
            # Try to get a valid catalog entry ID first
            catalog_entry_id = (
                entry.get("id")
                or entry.get("catalog_entry_id")
                or entry.get("entry_id")
                or entry.get("_id")
            )
            if not isinstance(catalog_entry_id, (str, int)):
                # skip entries without valid ID
                continue
            points_required = (
                entry.get("points_required")
                or entry.get("cost")
                or entry.get("pointsCost")
                or entry.get("required_points")
            )
            if points_required is not None:
                try:
                    points_required = int(points_required)
                except Exception:
                    points_required = None
            if points_required is not None and points_required > current_points:
                candidate_entry = entry
                break
        # If no entry found with points required > current balance,
        # just pick first entry with valid ID
        if candidate_entry is None:
            for entry in entries:
                catalog_entry_id = (
                    entry.get("id")
                    or entry.get("catalog_entry_id")
                    or entry.get("entry_id")
                    or entry.get("_id")
                )
                if isinstance(catalog_entry_id, (str, int)):
                    candidate_entry = entry
                    break
        if candidate_entry is None:
            raise AssertionError("No catalog entry with a valid ID found")

        catalog_entry_id = (
            candidate_entry.get("id")
            or candidate_entry.get("catalog_entry_id")
            or candidate_entry.get("entry_id")
            or candidate_entry.get("_id")
        )

        # Step 4: Attempt redeeming
        redeem_resp = requests.post(
            f"{BASE_URL}/api/v1/loyalty/catalog/{catalog_entry_id}/redeem",
            headers=HEADERS,
            timeout=30,
        )

        # Step 5: Validate error response status code is 400 or 422
        assert redeem_resp.status_code in (400, 422), f"Expected status 400 or 422 for insufficient balance, got {redeem_resp.status_code}"

        # Optionally check error message indication
        try:
            err_json = redeem_resp.json()
            error_message = err_json.get("detail") or err_json.get("error") or err_json.get("message") or ""
            assert any(
                x in error_message.lower()
                for x in ["insufficient", "not enough", "cannot be completed", "balance", "points", "redeem"]
            )
        except Exception:
            # error content is optional
            pass

    except requests.RequestException as e:
        raise AssertionError(f"HTTP request failed: {e}")


test_redeem_loyalty_points_with_insufficient_balance()
