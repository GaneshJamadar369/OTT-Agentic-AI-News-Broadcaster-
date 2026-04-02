import os
import json
from groq import Groq
from dotenv import load_dotenv
from state import AgentState
from groq_utils import groq_chat_create

load_dotenv()
_groq_keys = os.getenv("GROQ_API_KEY", "").split(",")
client = Groq(api_key=_groq_keys[0].strip() if _groq_keys else None)


def tagger_agent(state: AgentState):
    """Per-segment headlines, subheads, top tags, strictly aligned with visualizer segments."""
    print("\n--- TAGGER: headlines and tags (Groq) ---")

    segments = state.get("segments") or []
    segments_summary = "\n".join([
        f"Segment {s['segment_id']} ({s['start_time']}-{s['end_time']}): {s['text'][:100]}..."
        for s in segments
    ])

    feedback = (state.get("last_feedback_by_agent") or {}).get("tagger", "")
    fb_block = ""
    if feedback.strip():
        fb_block = f"\nFEEDBACK (improve weak metrics):\n{feedback}\n"

    prompt = f"""
    You are a TV chyron editor.
    {fb_block}
    NARRATION SCRIPT:
    {state['narration_script']}

    STRICT SEGMENT TEMPLATE:
    Below are the segments defined by the visual director. 
    You MUST provide exactly one set of tags for each segment ID listed below, in order.
    
    {segments_summary}

    Rules:
    - headline max 25 characters.
    - subheadline max 45 characters.
    - top_tag must be one of: BREAKING, LIVE, DEVELOPING, UPDATE, LATEST, EXCLUSIVE, ANALYSIS.
    - Respond with a JSON array 'segment_tags' containing exactly {len(segments)} objects.

    JSON only:
    {{
      "segment_tags": [
        {{"segment_id": 1, "headline": "...", "subheadline": "...", "top_tag": "UPDATE"}}
      ]
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
        "segment_tags": data.get("segment_tags") or [],
    }
