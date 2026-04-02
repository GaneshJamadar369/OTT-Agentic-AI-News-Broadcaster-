import os
from groq import Groq
from dotenv import load_dotenv
from state import AgentState
from llm_utils import llm_chat_create

load_dotenv()
_groq_keys = os.getenv("GROQ_API_KEY", "").split(",")
client = Groq(api_key=_groq_keys[0].strip() if _groq_keys else None)


def editor_agent(state: AgentState):
    """Broadcast narration 160–320 words; consumes metric-level FEEDBACK on retries."""
    print("\n--- EDITOR: writing narration (Groq) ---")

    feedback = (state.get("last_feedback_by_agent") or {}).get("editor", "")
    fb_block = ""
    if feedback.strip():
        fb_block = f"""
FEEDBACK (fix these issues; preserve strong parts):
{feedback}
"""

    prompt = f"""
You are a Senior TV News Producer. Use only facts supported by the research package below.
{fb_block}
RESEARCH PACKAGE:
{state['article_text']}

TASK: Write one continuous TV news narration (no bullet points, no numbered lists).
Constraints:
- Length: 160 to 320 words (strict).
- Structure: strong hook, 3-4 story beats in paragraphs, professional close.
- Tone: broadcast, urgent but accurate; no jokes on serious topics.
- Never say "this article", "this script", or "according to the report" meta-phrases.
- Temperature: write for live anchor read-aloud.
"""

    response = llm_chat_create(
        client,
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "narration_script": response.choices[0].message.content or "",
        "current_agent": "Editor",
        "editor_runs": state.get("editor_runs", 0) + 1,
    }
