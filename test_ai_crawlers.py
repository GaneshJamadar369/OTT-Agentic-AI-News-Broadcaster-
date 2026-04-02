import sys
import os
import json
import requests
import logging
import codecs
import asyncio
import nest_asyncio
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate
from scraper_utils import scrape_article
from sarvam_utils import sarvam_chat_create

# Async Setup
nest_asyncio.apply()

# Suppress noisy logs
load_dotenv()
logging.getLogger("scraper_utils").setLevel(logging.WARNING)
logging.getLogger("crawl4ai").setLevel(logging.WARNING)

# API Keys
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY") or os.getenv("SARVAM_API")

# High-Security News Targets (The "Hard" URLs)
TEST_URLS = [
    {
        "name": "NDTV (Security Block)",
        "url": "https://www.ndtv.com/world-news/iran-war-news-if-you-kill-our-leaders-well-attack-us-firms-like-google-meta-iran-11292804"
    },
    {
        "name": "India Today (Agentic Test)",
        "url": "https://www.indiatoday.in/world-news/story/shelly-kittleson-us-journalist-iraq-kidnapped-baghdad-isis-2889814-2026-03-31"
    },
    {
        "name": "Hindustan Times (Bot Protection)",
        "url": "https://www.hindustantimes.com/india-news/political-vultures-vs-pm-run-by-trump-modi-rahul-exchange-fire-over-west-asia-war-impact-on-india-101774968354620.html"
    }
]

def score_and_critique_llm(url, text):
    """Quality audit using Sarvam."""
    if not text or len(text) < 200:
        return 0, "Blocked / No Content Found."
    if not SARVAM_API_KEY:
        return 0, "Missing SARVAM_API_KEY."
    
    prompt = f"""
    Analyze the quality of this news extraction from: {url}
    
    TEXT:
    {text[:2500]}
    
    You are an AI Architect. Rate the extraction (0-10) based on:
    1. 'Knowledge Completeness' (Did it get the main story facts?)
    2. 'Cleanliness' (Is it free of ads/links?)
    3. 'Broadcast Readiness' (Is it clean for a news script?)
    
    Return ONLY JSON:
    {{
        "score": (0-10),
        "summary": (Professional critique for a senior mentor)
    }}
    """
    try:
        response = sarvam_chat_create(
            None,
            messages=[{"role": "user", "content": prompt}],
            model=os.getenv("SARVAM_MODEL", "sarvam-105b"),
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data["score"], data["summary"]
    except:
        return 0, "Audit Error."

def test_jina(url):
    try:
        response = requests.get(f"https://r.jina.ai/{url}", timeout=15)
        return response.text if response.status_code == 200 else ""
    except: return ""

def test_tavily(url):
    if not TAVILY_API_KEY: return ""
    try:
        res = requests.post("https://api.tavily.com/extract", json={"api_key": TAVILY_API_KEY, "urls": [url]}, timeout=15)
        return res.json().get("results", [{}])[0].get("raw_content", "")
    except: return ""

async def test_crawl4ai(url):
    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            return result.markdown
    except Exception as e:
        return ""

def test_scrapegraph(url):
    # ScrapeGraphAI config in this benchmark was Groq-specific; skipped in Sarvam-only mode.
    return "Skipped (Sarvam-only benchmark mode)."

def run_benchmarks():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n🚀 Running 'The Ultimate Crawler Battle' on {len(TEST_URLS)} targets...")
    
    table_data = []

    for item in TEST_URLS:
        print(f"   ➤ Analyzing: {item['name']}...")
        
        # 1. Local God-Tier Scraper (Offline Stealth)
        local_scrape = scrape_article(item['url']).get("text", "")
        local_score, local_critique = score_and_critique_llm(item['url'], local_scrape)
        table_data.append([item['name'], "Local God-Tier", len(local_scrape), f"{local_score}/10", local_critique])

        # 2. Jina AI Reader (API Proxy)
        jina_scrape = test_jina(item['url'])
        jina_score, jina_critique = score_and_critique_llm(item['url'], jina_scrape)
        table_data.append(["", "Jina AI Reader", len(jina_scrape), f"{jina_score}/10", jina_critique])

        # 3. Tavily AI Extract (Managed Search)
        tavily_scrape = test_tavily(item['url'])
        tavily_score, tavily_critique = score_and_critique_llm(item['url'], tavily_scrape)
        table_data.append(["", "Tavily AI", len(tavily_scrape), f"{tavily_score}/10", tavily_critique])

        # 4. Crawl4AI (Open Source / Sync)
        c4ai_scrape = asyncio.run(test_crawl4ai(item['url']))
        c4ai_score, c4ai_critique = score_and_critique_llm(item['url'], c4ai_scrape or "")
        table_data.append(["", "Crawl4AI (OS)", len(c4ai_scrape or ""), f"{c4ai_score}/10", c4ai_critique])

        # 5. ScrapeGraphAI (Agentic - HT/India Today)
        sg_scrape = test_scrapegraph(item['url'])
        sg_score, sg_critique = score_and_critique_llm(item['url'], sg_scrape)
        table_data.append(["", "ScrapeGraphAI", len(sg_scrape), f"{sg_score}/10", sg_critique])

        table_data.append(["-"*15, "-"*15, "-"*10, "-"*10, "-"*30])

    # Show Final Table
    headers = ["News Site", "Crawler Type", "Chars", "Quality Score", "Architectural Critique"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid"))

    # Save Markdown Report
    output_file = "ELITE_CRAWLER_BENCHMARK.md"
    md_content = f"# LOQO AI: The Ultimate Crawler Comparison\n"
    md_content += f"**Generated on:** `{timestamp}`\n\n"
    md_content += tabulate(table_data, headers=headers, tablefmt="github")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    print(f"\n✅ Benchmarking Complete! Full report saved to: {output_file}")

if __name__ == "__main__":
    run_benchmarks()
