from newspaper import Article
import trafilatura
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_with_curl_cffi(url: str):
    """Tier 1: Fetch HTML using curl_cffi (Chrome 110 impersonation)."""
    logger.info(f"Targeting {url} with curl_cffi (Chrome 110 impersonation)...")
    try:
        response = cffi_requests.get(url, impersonate="chrome110", timeout=15)
        logger.info(f"curl_cffi returned status {response.status_code}")
        return response.text, response.status_code
    except Exception as e:
        logger.error(f"curl_cffi fetch failed for {url}: {e}")
        return "", 0

def fetch_with_playwright_stealth(url: str) -> str:
    """Tier 2: Fetch rendered HTML using Playwright in full Stealth Mode."""
    logger.info(f"Falling back to Playwright Stealth for {url}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            # Apply advanced stealth patches
            stealth(page)
            
            # Navigate and settle
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3500) # Settle for Cloudflare/redirections
            
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        logger.error(f"Playwright Stealth fetch failed for {url}: {e}")
        return ""

def scrape_article(url: str) -> dict:
    """
    The 'God-Tier' Scraping Pipeline:
    1. Fast Strike: curl_cffi (Bypass TLS)
    2. Fast Parse: Trafilatura (Clean Text)
    3. Heavy Muscle: Playwright Stealth (Render JS)
    4. Guarded Fallback: Newspaper3k (Using pre-downloaded HTML)
    """
    
    # --- PHASE 1: Fast Strike (curl_cffi) ---
    html, status_code = fetch_with_curl_cffi(url)
    
    # ❌ HARD ABORT: Dead, Server Gone, or Gone Pages
    if status_code in [404, 410, 500, 502, 503, 504]:
        logger.error(f"Hard HTTP Error {status_code}. Aborting.")
        return build_error_dict(status_code)

    # 🔄 UPGRADE TO PLAYWRIGHT: Blocked (403/401/429) or empty HTML
    should_fallback = status_code in [401, 403, 429] or not html
    
    # --- PHASE 2: Fast Parse (Internal Trafilatura) ---
    content = None
    if not should_fallback:
        content = trafilatura.extract(html)
        # If text is too thin, it's likely a blank JS shell (React/Angular)
        if not content or len(content) < 500:
            should_fallback = True
            logger.info("Content thin or missing with curl_cffi. Escalating to Playwright...")

    # --- PHASE 3: Heavy Muscle (Playwright Stealth) ---
    if should_fallback:
        html = fetch_with_playwright_stealth(url)
        if html:
            status_code = 200 # <-- THE FIX: Playwright succeeded, clear the error code!
            content = trafilatura.extract(html)

    # --- PHASE 4: Metadata & Guarded Fallback ---
    title = ""
    images = []
    
    if html:
        # A. Quick Metadata extraction (Trafilatura)
        metadata = trafilatura.extract_metadata(html)
        if metadata:
            title = metadata.title
            if metadata.image: images.append(metadata.image)
        
        # B. Robust Fallback (Newspaper3k - SET HTML, NO DOWNLOAD)
        if not content or len(content) < 500 or not title:
            logger.info("Extraction thin. Final safety net: Newspaper3k...")
            article = Article(url)
            article.set_html(html) # <-- TRAP FIXED: No re-download
            article.parse()
            if not content or len(content) < 500:
                content = article.text
            if not title: title = article.title
            
            # Grab top images from Newspaper
            if article.top_image and article.top_image not in images:
                images.append(article.top_image)
            if article.images:
                for img in list(article.images)[:3]:
                    if img not in images: images.append(img)

    return {
        "title": title or "No Title Found",
        "text": content or "No content extracted.",
        "images": images,
        "status_code": status_code,
        "text_length": len(content) if content else 0
    }

def build_error_dict(status_code):
    return {
        "title": f"HTTP Error {status_code}",
        "text": f"ERROR: {status_code} Page Dead or Blocked.",
        "images": [],
        "status_code": status_code,
        "text_length": 0
    }
