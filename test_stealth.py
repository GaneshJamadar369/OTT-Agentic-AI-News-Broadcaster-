from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    Stealth(page)
    print('success')