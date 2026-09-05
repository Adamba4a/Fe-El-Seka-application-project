import requests
from io import BytesIO

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

# Bearer token for the driver user
DRIVER_TOKEN = (
    "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03N"
    "TBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWls"
    "IjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm"
    "92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cn"
    "VlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdG"
    "FtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5v"
    "bnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
)

# Bearer token for the admin user
ADMIN_TOKEN = (
    "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwM"
    "zAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoiYWRtaW5AZXhhbXBl"
    "LmNvbSIsInBob25lIjoiIiwiaHR0cDovL2xvY2FsaG9zdDo4MDAwL2FwaS9hZG1pbi91c2Vycy81N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04N"
    "zY3MTg3ZDIwMyIsInJvbGUiOiJhZG1pbiIsImFhbCI6ImFhbDEiLCJhbXIiOlsidG9rZW4iXSwic2Vzc2lvbl9pZCI6IjE5YjYxNjJhOC02OGI"
    "wLTRkMzQtOTdjMS0zZTgxMmU1MDNkZmUiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.uQZIcnODvWcUfNdLgUKN1IvQN_fZ6g44Wo8XdJJlIZ33ZsQ"
    "49X75DW0BLzjAGAObpu6NSAZUEUbcAqhIJz_HIbnAg"
)


def test_post_api_verification_submit_and_admin_approve():
    headers_driver = {"Authorization": f"Bearer {DRIVER_TOKEN}"}
    headers_admin = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

    # Prepare small valid PNG bytes for all three files: front_id, back_id, selfie
    # 1x1 transparent PNG pixel
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f"
        b"\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc#\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    files = {
        "front_id": ("front.png", BytesIO(png_bytes), "image/png"),
        "back_id": ("back.png", BytesIO(png_bytes), "image/png"),
        "selfie": ("selfie.png", BytesIO(png_bytes), "image/png"),
    }

    try:
        # Step 1: Driver submits verification documents
        submit_response = requests.post(
            f"{BASE_URL}/api/verification/submit",
            headers=headers_driver,
            files=files,
            timeout=TIMEOUT,
        )
        assert submit_response.status_code == 201, f"Expected 201 Created, got {submit_response.status_code}"
        submit_json = submit_response.json()
        # Assuming the response contains a unique submission ID as 'id' or similar:
        submission_id = submit_json.get("id") or submit_json.get("submission_id")
        assert submission_id, "Submission ID missing in response"

        # Step 2: Admin approves the verification submission
        approve_response = requests.post(
            f"{BASE_URL}/api/admin/verification/{submission_id}/approve",
            headers=headers_admin,
            timeout=TIMEOUT,
        )
        assert approve_response.status_code == 200, f"Expected 200 OK on approve, got {approve_response.status_code}"

    finally:
        # No deletion endpoint provided in the PRD for verification submissions
        pass


test_post_api_verification_submit_and_admin_approve()
