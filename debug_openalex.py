import requests
import json

MAILTO = "mailto:test@example.com"
HEADERS = {"User-Agent": MAILTO}

def test_citations():
    # 1. Test per-page limit
    print("Testing per-page=500...")
    url = "https://api.openalex.org/works?per-page=500"
    r = requests.get(url, headers=HEADERS)
    print(f"Status per-page=500: {r.status_code}") # Expect 403 or 400
    
    # 2. Test OR operator for cites
    print("\nTesting 'cites' with OR operator...")
    # Using some random highly cited works: W2741809807 (Einstein), W2033283250
    w1 = "W2741809807" 
    w2 = "W2033283250"
    url2 = f"https://api.openalex.org/works?filter=cites:{w1}|{w2}&per-page=10"
    r2 = requests.get(url2, headers=HEADERS)
    print(f"Status cites OR: {r2.status_code}")
    if r2.status_code == 200:
        print(f"Count: {len(r2.json()['results'])}")

if __name__ == "__main__":
    test_citations()
