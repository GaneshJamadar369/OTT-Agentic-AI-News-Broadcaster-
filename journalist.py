import os
import re
from groq import Groq
from dotenv import load_dotenv
from state import AgentState
from scraper_utils import scrape_article
from groq_utils import groq_chat_create

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def journalist_agent(state: AgentState):
    """Tiered scrape plus structured LLM refinement; stores raw article text for faithfulness checks."""
    print(f"\n--- JOURNALIST: extracting from {state['url']} ---")

    article_data = scrape_article(state["url"])
    raw_text = article_data.get("text") or ""
    status = article_data.get("status_code", 200)

    if status in (404, 410, 500, 502, 503, 504) or "ERROR:" in (raw_text or "")[:200]:
        print(f"\n[Journalist] Scrape failed or HTTP error. Stopping: {state['url']}")
        return {
            "article_title": f"HTTP {status}",
            "article_text": "ERROR: INVALID_CONTENT",
            "raw_article_text": raw_text,
            "source_images": [],
            "current_agent": "Journalist",
            "journalist_runs": state.get("journalist_runs", 0) + 1,
        }

    feedback = (state.get("last_feedback_by_agent") or {}).get("journalist", "")
    fb_block = ""
    if feedback.strip():
        fb_block = f"""
FEEDBACK FROM PRIOR EVALUATION (address these issues only; keep correct parts):
{feedback}
"""

    prompt = f"""
You are a professional News Researcher. Do not invent facts not present in the source text.
{fb_block}
SOURCE TITLE: {article_data['title']}
SOURCE TEXT:
{raw_text[:25000]}

Refine into this exact structure (no extra preamble):
TITLE: [Concise headline]
STORY: [3-5 paragraphs, core narrative for downstream TV writing]
FACTS: [Bullet or numbered key facts: who, what, when, where, why]

Rules:
- Every fact must appear in the source text above.
- If uncertain, omit rather than guess.
- No phrases like "this article" or "as an AI".
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    extracted_content = response.choices[0].message.content or ""

    error_flags = ["404", "401", "Page Not Found", "Access Denied", "Not Found"]
    is_error = any(flag in extracted_content for flag in error_flags)

    if is_error or len(raw_text) < 400:
        print(f"\n[Journalist] Guardrail: thin or error-like content. Stopping: {state['url']}")
        return {
            "article_title": "Invalid Content (404/Thin)",
            "article_text": "ERROR: INVALID_CONTENT",
            "raw_article_text": raw_text,
            "source_images": [],
            "current_agent": "Journalist",
            "journalist_runs": state.get("journalist_runs", 0) + 1,
        }

    title_m = re.search(r"TITLE:\s*(.+?)(?:\n|$)", extracted_content, re.I)
    refined_title = title_m.group(1).strip() if title_m else (article_data["title"] or "Extracted Title")

    return {
        "article_title": refined_title,
        "article_text": extracted_content,
        "raw_article_text": raw_text,
        "source_images": article_data.get("images") or [],
        "current_agent": "Journalist",
        "journalist_runs": state.get("journalist_runs", 0) + 1,
    }
