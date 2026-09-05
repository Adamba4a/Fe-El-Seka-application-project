import requests
from io import BytesIO

BASE_URL = "http://localhost:8000"
DRIVER_ID = "2b61b48e-1ec2-4cb3-b2c1-750d0f563bd6"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoiYWRtaW5AdmVyaWZpY2F0aW9uLmV4YW1wbGUuY29tIiwicGhvbmUiOiIiLCJyb2wiOiJhZG1pbiIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzg4NTQ5Mzg0fV0sInNlc3Npb25faWQiOiJhZG1pbi1zZXNzaW9uLWlkIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.o3ZtG6sbHrW1LgG3txajEyoWW_i61Qv9-QZzdf3aOQ46iEA1yTHy5ax5Cnu8Cjcif2cP3rPJCbmeZCJfYTdjVKA"

DRIVER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImRyaXZlciIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzg4NTQ5Mzg0fV0sInNlc3Npb25faWQiOiJkcml2ZXItc2Vzc2lvbi1pZCIsImlzX2Fub255bW91cyI6ZmFsc2V9.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS_DRIVER = {
    "Authorization": f"Bearer {DRIVER_TOKEN}",
}

HEADERS_ADMIN = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
}

# Small valid PNG binary data (1x1 px transparent)
SMALL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
    b"\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82"
)


def post_api_verification_reject_lock_cycle_and_admin_unlock():
    session = requests.Session()
    submission_ids = []

    def submit_verification():
        url = f"{BASE_URL}/api/verification/submit"
        files = {
            "front_id": ("front.png", BytesIO(SMALL_PNG_BYTES), "image/png"),
            "back_id": ("back.png", BytesIO(SMALL_PNG_BYTES), "image/png"),
            "selfie": ("selfie.png", BytesIO(SMALL_PNG_BYTES), "image/png"),
        }
        data = {"submission_type": "driver_id_license"}
        response = session.post(
            url,
            headers=HEADERS_DRIVER,
            files=files,
            data=data,
            timeout=30,
        )
        return response

    def admin_reject(submission_id):
        url = f"{BASE_URL}/api/admin/verification/{submission_id}/reject"
        response = session.post(url, headers=HEADERS_ADMIN, timeout=30)
        return response

    def admin_unlock_user(user_id):
        url = f"{BASE_URL}/api/admin/verification/users/{user_id}/unlock"
        response = session.post(url, headers=HEADERS_ADMIN, timeout=30)
        return response

    # Perform exactly 3 submit+reject cycles
    for cycle in range(1, 4):
        # Submit verification
        submit_resp = submit_verification()
        # On first two cycles, expect 201 Created
        if cycle <= 2:
            assert submit_resp.status_code == 201, f"Cycle {cycle}: Expected 201 Created on submit, got {submit_resp.status_code}, response: {submit_resp.text}"
        # On 3rd submit, depending on lock logic, might still accept submission but lock triggered after reject
        # The problem wants to check that after 3rd reject, user is locked, so assume submit returns 201 on 3rd too
        else:
            # To allow test to proceed, accept 201 here too
            assert submit_resp.status_code == 201, f"Cycle {cycle}: Expected 201 Created on submit, got {submit_resp.status_code}, response: {submit_resp.text}"

        submit_data = submit_resp.json()
        submission_id = submit_data.get("id")
        assert submission_id, f"Cycle {cycle}: Submission ID missing in response: {submit_resp.text}"
        submission_ids.append(submission_id)

        # Admin reject the submission
        reject_resp = admin_reject(submission_id)
        assert reject_resp.status_code == 200, f"Cycle {cycle}: Expected 200 OK on admin reject, got {reject_resp.status_code}, response: {reject_resp.text}"

    # After the 3rd rejection, user should be locked from submission.
    # To verify user is locked, attempt a submit again and expect failure (e.g. 4xx).
    locked_submit_resp = submit_verification()
    # Assuming locked user cannot submit again, expect a 4xx error like 403 or 423 or similar.
    assert locked_submit_resp.status_code >= 400, f"Expected error on submit after 3rd rejection lock, got {locked_submit_resp.status_code}, response: {locked_submit_resp.text}"

    # Admin can unlock user via the unlock endpoint
    unlock_resp = admin_unlock_user(DRIVER_ID)
    assert unlock_resp.status_code == 200, f"Expected 200 OK on admin unlock, got {unlock_resp.status_code}, response: {unlock_resp.text}"

    # After unlock, the user should be able to submit again successfully
    post_unlock_submit_resp = submit_verification()
    assert post_unlock_submit_resp.status_code == 201, f"Expected 201 Created on submit after unlock, got {post_unlock_submit_resp.status_code}, response: {post_unlock_submit_resp.text}"

    print("TC020 passed.")


post_api_verification_reject_lock_cycle_and_admin_unlock()