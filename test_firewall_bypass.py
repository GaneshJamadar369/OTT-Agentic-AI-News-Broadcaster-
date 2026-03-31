import requests
import trafilatura
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL = "https://www.ndtv.com/world-news/us-iran-war-us-boots-on-the-ground-american-troop-movements-middle-east-11285015?pfrom=home-ndtvworld_world_top_scroll"

def test_jina():
    print("\n--- Testing Solution: Jina AI Reader ---")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        jina_url = f"https://r.jina.ai/{URL}"
        response = requests.get(jina_url, headers=headers, timeout=20)
        print(f"Status: {response.status_code}")
        content = trafilatura.extract(response.text)
        print(f"Content length: {len(content) if content else 0}")
        return len(content) if content else 0
    except Exception as e:
        print(f"Error: {e}")
        return 0

def test_curl_cffi():
    print("\n--- Testing Solution: curl_cffi ---")
    try:
        response = cffi_requests.get(URL, impersonate="chrome110", timeout=15)
        print(f"Status: {response.status_code}")
        content = trafilatura.extract(response.text)
        print(f"Content length: {len(content) if content else 0}")
        return len(content) if content else 0
    except Exception as e:
        print(f"Error: {e}")
        return 0

def test_playwright_stealth():
    print("\n--- Testing Solution: Playwright Stealth Library ---")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0")
            page = context.new_page()
            stealth(page)
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3500)
            html = page.content()
            content = trafilatura.extract(html)
            print(f"Content length: {len(content) if content else 0}")
            browser.close()
            return len(content) if content else 0
    except Exception as e:
        print(f"Error: {e}")
        return 0

if __name__ == "__main__":
    results = {
        "Jina AI": test_jina(),
        "curl_cffi": test_curl_cffi(),
        "Playwright Stealth": test_playwright_stealth()
    }
    print("\n" + "="*30)
    print("FINAL RESULTS")
    print("="*30)
    for name, score in results.items():
        print(f"{name}: {score} chars extracted")
