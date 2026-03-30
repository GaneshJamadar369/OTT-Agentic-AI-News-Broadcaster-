from newspaper import Article
import requests
import trafilatura
from playwright.sync_api import sync_playwright
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_with_requests(url: str) -> str:
    """Fetch raw HTML using requests."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.warning(f"Requests returned status {response.status_code} for {url}")
        return response.text
    except Exception as e:
        logger.error(f"Requests fetch failed for {url}: {e}")
        return ""

def fetch_with_playwright(url: str) -> str:
    """Fetch rendered HTML using Playwright (fallback for JS-heavy sites)."""
    logger.info(f"Falling back to Playwright for {url}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        logger.error(f"Playwright fetch failed for {url}: {e}")
        return ""

def scrape_article(url: str) -> dict:
    """
    Tiered scraping pipeline:
    1. Fetch HTML (Requests -> Playwright fallback).
    2. Extract Content (Trafilatura -> Newspaper3k fallback).
    """
    # 1. Fetch HTML
    html = fetch_with_requests(url)
    
    # Check if requests was sufficient (rough check on HTML size or trafilatura result)
    content = trafilatura.extract(html) if html else None
    
    if not content or len(content) < 500:
        logger.info("Content too short or missing with requests. Trying Playwright...")
        html = fetch_with_playwright(url)
        content = trafilatura.extract(html) if html else None

    # 2. Extract Title and Images
    title = ""
    images = []
    
    if html:
        # Use Trafilatura for metadata first
        metadata = trafilatura.extract_metadata(html)
        if metadata:
            title = metadata.title
            if metadata.image:
                images.append(metadata.image)
        
        # Fallback to Newspaper3k for extraction if trafilatura failed or was thin
        if not content or len(content) < 500:
            logger.info("Trafilatura failed to extract meaningful text. Falling back to Newspaper3k...")
            article = Article(url)
            article.set_html(html)
            article.parse()
            content = article.text
            if not title: title = article.title
            if not images and article.top_image:
                images.append(article.top_image)
            if article.images:
                # Add a few more images if available
                more_images = list(article.images)[:3]
                for img in more_images:
                    if img not in images: images.append(img)

    return {
        "title": title or "No Title Found",
        "text": content or "No content extracted.",
        "images": images,
        "html_length": len(html) if html else 0,
        "text_length": len(content) if content else 0
    }
