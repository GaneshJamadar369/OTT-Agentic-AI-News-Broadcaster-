from scraper_utils import scrape_article
import json

# Test URLs
url_static = "https://www.bbc.com/news/articles/cvg5g3pjy06o"
url_js_heavy = "https://vcl.stanford.edu/projects/scriptease/" # Example JS heavy or complex page

def test_scraper(url):
    print(f"\n--- Testing Scraper for: {url} ---")
    result = scrape_article(url)
    print(f"TITLE: {result['title']}")
    print(f"TEXT LENGTH: {result['text_length']}")
    print(f"IMAGES FOUND: {len(result['images'])}")
    if result['images']:
        print(f"FIRST IMAGE: {result['images'][0]}")
    else:
        print("NO IMAGES FOUND")
    print(f"SAMPLE TEXT: {result['text'][:200]}...")

if __name__ == "__main__":
    test_scraper(url_static)
    test_scraper(url_js_heavy)
