import os
import re
from groq import Groq
from dotenv import load_dotenv

from state import AgentState
from scraper_utils import scrape_article
from llm_utils import llm_chat_create


load_dotenv()
_groq_keys = os.getenv("GROQ_API_KEY", "").split(",")
client = Groq(api_key=_groq_keys[0].strip() if _groq_keys and _groq_keys[0].strip() else None)


def _has_required_blocks(text: str) -> bool:
    if not text:
        return False
    has_title = bool(re.search(r"TITLE:\s*.+", text, re.I))
    has_story = bool(re.search(r"STORY:\s*.+?(?=FACTS:|$)", text, re.I | re.S))
    has_facts = bool(re.search(r"FACTS:\s*.+", text, re.I | re.S))
    return has_title and has_story and has_facts


def _extract_title(text: str, fallback: str) -> str:
    if not text:
        return fallback
    m = re.search(r"TITLE:\s*(.+?)(?:\n|$)", text, re.I)
    if not m:
        return fallback
    title = m.group(1).strip()
    return title if title else fallback


def journalist_agent(state: AgentState):
    """
    Tiered scrape plus strict LLM refinement.
    Designed for strong source_faithfulness, balance_neutrality,
    numerical_fidelity, and deterministic schema checks.
    """
    print(f"\n--- JOURNALIST: extracting from {state['url']} ---")

    article_data = scrape_article(state["url"])
    raw_text = (article_data.get("text") or "").strip()
    source_title = (article_data.get("title") or "").strip()
    source_images = article_data.get("images") or []
    status = article_data.get("status_code", 200)

    journalist_runs = int(state.get("journalist_runs", 0)) + 1

    if status in (404, 410, 500, 502, 503, 504) or "ERROR:" in raw_text[:200]:
        print(f"\n[Journalist] Scrape failed or HTTP error. Stopping: {state['url']}")
        return {
            "article_title": f"HTTP {status}",
            "article_text": "ERROR: INVALID_CONTENT",
            "raw_article_text": raw_text,
            "source_images": [],
            "current_agent": "Journalist",
            "journalist_runs": journalist_runs,
        }

    if len(raw_text) < 400:
        print(f"\n[Journalist] Guardrail: thin content. Stopping: {state['url']}")
        return {
            "article_title": "Invalid Content (Thin Source)",
            "article_text": "ERROR: INVALID_CONTENT",
            "raw_article_text": raw_text,
            "source_images": [],
            "current_agent": "Journalist",
            "journalist_runs": journalist_runs,
        }

    feedback = (state.get("last_feedback_by_agent") or {}).get("journalist", "")
    fb_block = ""
    if feedback.strip():
        fb_block = f"""
PRIOR EVALUATION FAILURES TO FIX:
{feedback}

Fix only the failing issues above.
Preserve already-correct grounded facts.
"""

    prompt = f"""
You are a wire-service newsroom extraction agent.

Your job is to convert the scraped article into a strict, factual newsroom brief
for downstream TV-writing agents.

You must be:
- neutral
- precise
- fact-grounded
- non-speculative
- consistent with the source text

Do NOT invent, infer, exaggerate, dramatize, soften, or reinterpret facts.
If a fact is uncertain or missing, omit it rather than guessing.

{fb_block}
SOURCE TITLE:
{source_title}

SOURCE TEXT:
{raw_text[:22000]}

Return EXACTLY this structure and nothing else:

TITLE: <one-line neutral broadcast headline, 5-10 words, present tense if natural, no hype>
STORY: <exactly 5-7 sentences, concise, neutral, directly grounded in the source, suitable for downstream TV script writing>
FACTS:
1. <fact directly supported by the source text>
2. <fact directly supported by the source text>
3. <fact directly supported by the source text>
4. <fact directly supported by the source text>
5. <fact directly supported by the source text>

Rules:
- Every sentence must be supported by the source text above.
- Preserve names, numbers, dates, places, offices, counts, and quotes exactly when present.
- Do not add background knowledge from memory.
- Do not add interpretation, emotion, legal judgment, or geopolitical framing unless it is explicitly in the source text.
- Avoid loaded wording and avoid taking sides.
- Use explicit attribution (e.g., "President Trump claimed...", "According to the report...", "The address stated...") for all evaluative, speculative, or official statements.
- For speeches, press conferences, or military claims: attribute every contentious or operational claim to the speaker or source (e.g., "Trump said...", "The White House stated...", "State media reported..."). Reporting what an official said is not endorsement; keep verbs neutral ("said", "stated", "described") not triumphant or inflammatory.
- Where the source presents competing claims, reflect that structure without resolving who is right.
- No phrases like "this article", "according to the article", "as an AI", or "language model".
- STORY must not be bullet points.
- FACTS must be numbered lines.
- If the source text is noisy, still extract only grounded facts and omit uncertain material.
"""

    response = llm_chat_create(
        client,
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )

    extracted_content = (response.choices[0].message.content or "").strip()

    error_flags = [
        "404",
        "401",
        "Page Not Found",
        "Access Denied",
        "Not Found",
        "ERROR: INVALID_CONTENT",
    ]
    is_error_like = any(flag.lower() in extracted_content.lower() for flag in error_flags)

    if is_error_like or not _has_required_blocks(extracted_content):
        print(f"\n[Journalist] Guardrail: malformed or error-like LLM extraction. Stopping: {state['url']}")
        return {
            "article_title": source_title or "Invalid Content",
            "article_text": "ERROR: INVALID_CONTENT",
            "raw_article_text": raw_text,
            "source_images": source_images,
            "current_agent": "Journalist",
            "journalist_runs": journalist_runs,
        }

    refined_title = _extract_title(extracted_content, source_title or "Extracted Title")

    return {
        "article_title": refined_title,
        "article_text": extracted_content,
        "raw_article_text": raw_text,
        "source_images": source_images,
        "current_agent": "Journalist",
        "journalist_runs": journalist_runs,
    }