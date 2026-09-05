import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}

def test_post_api_profiles_me_photo_upload_profile_photo():
    photo_upload_url = f"{BASE_URL}/api/profiles/me/photo"
    profile_me_url = f"{BASE_URL}/api/profiles/me"
    timeout = 30
    # Use a small valid image file content (a PNG 1x1 pixel)
    image_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
        b"\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {
        "file": ("profile.png", image_content, "image/png")
    }

    resp_upload = None
    try:
        resp_upload = requests.post(photo_upload_url, headers=HEADERS, files=files, timeout=timeout)
        assert resp_upload.status_code == 200, f"Expected 200 on photo upload but got {resp_upload.status_code}"
        json_upload = resp_upload.json()
        assert "photo_url" in json_upload and isinstance(json_upload["photo_url"], str) and json_upload["photo_url"], "Response missing valid photo_url"

        # Now get profile to verify photo has been updated/shown
        resp_profile = requests.get(profile_me_url, headers=HEADERS, timeout=timeout)
        assert resp_profile.status_code == 200, f"Expected 200 on getting profile but got {resp_profile.status_code}"
        json_profile = resp_profile.json()
        assert "photo_url" in json_profile and json_profile["photo_url"], "Profile data missing photo_url"
        assert json_profile["photo_url"] == json_upload["photo_url"], "Returned photo_url in profile does not match uploaded photo_url"
    finally:
        # Optional: no delete endpoint exists for photo; skipping cleanup as replacing photo replaces prior
        pass

test_post_api_profiles_me_photo_upload_profile_photo()