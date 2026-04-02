import os
import json
from groq import Groq
from dotenv import load_dotenv
from state import AgentState
from groq_utils import groq_chat_create

load_dotenv()
_groq_keys = os.getenv("GROQ_API_KEY", "").split(",")
client = Groq(api_key=_groq_keys[0].strip() if _groq_keys else None)

def metadata_agent(state: AgentState):
    """Generates video category and SEO tags in parallel with the editor."""
    print("\n--- METADATA: category and SEO tags (Groq) ---")
    
    prompt = f"""
    You are a Broadcast Metadata Specialist.
    Based on the following News Story, provide:
    1. A single video category (e.g., Politics, Technology, World News, Finance, Sports).
    2. A list of 5-8 relevant SEO keywords.

    NEWS STORY:
    {state.get('article_text', '')}

    Respond ONLY with valid JSON:
    {{
      "video_category": "Category Name",
      "seo_tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
    }}
    """

    response = groq_chat_create(
        client,
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content or "{}")

    return {
        "video_category": data.get("video_category", "General News"),
        "seo_tags": data.get("seo_tags") or [],
    }
