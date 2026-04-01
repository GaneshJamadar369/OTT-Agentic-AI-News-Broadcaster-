import os
import json
from groq import Groq
from dotenv import load_dotenv
from state import AgentState
from groq_utils import groq_chat_create

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def tagger_agent(state: AgentState):
    """Per-segment headlines, subheads, top tags."""
    print("\n--- TAGGER: headlines and tags (Groq) ---")

    feedback = (state.get("last_feedback_by_agent") or {}).get("tagger", "")
    fb_block = ""
    if feedback.strip():
        fb_block = f"""
FEEDBACK (improve weak metrics; keep valid lines):
{feedback}
"""

    prompt = f"""
You are a TV chyron editor.
{fb_block}
NARRATION SCRIPT:
{state['narration_script']}

Build segment_tags with the SAME number of segments as the story beats you infer (3-5).
headline max 30 characters; subheadline max 50 characters.
top_tag must be one of: BREAKING, LIVE, DEVELOPING, UPDATE, LATEST, EXCLUSIVE, ANALYSIS.

JSON only:
{{
  "segment_tags": [
    {{"headline": "...", "subheadline": "...", "top_tag": "UPDATE"}}
  ]
}}
"""

<<<<<<< Current (Your changes)
    response = groq_chat_create(
        client,
=======
    response = client.chat.completions.create(
>>>>>>> Incoming (Background Agent changes)
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content or "{}")

    return {
        "segment_tags": data.get("segment_tags") or [],
    }
