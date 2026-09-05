import requests

def test_get_api_geocode_search_with_valid_address_query():
    base_url = "http://localhost:8000"
    endpoint = "/api/geocode/search"
    url = base_url + endpoint
    headers = {
        # No Authorization needed as per PRD
    }
    params = {
        "q": "10 Downing St, London"
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, dict), "Response JSON is not a dictionary"
        # Expecting at least one forward-geocode result matching query string in the results
        results = data.get("results") or data.get("features") or []
        assert isinstance(results, list), "Results are not a list"
        assert len(results) > 0, "No geocode results returned"
        # Optionally check if address or name fields match query roughly
        matched = any("10 Downing" in (res.get("address", "") if isinstance(res, dict) else "") or
                      "10 Downing" in (res.get("name", "") if isinstance(res, dict) else "")
                      for res in results)
        assert matched, "No geocode result matches the query address"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

test_get_api_geocode_search_with_valid_address_query()