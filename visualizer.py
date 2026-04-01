import os
import json
from groq import Groq
from dotenv import load_dotenv
from state import AgentState
from groq_utils import groq_chat_create

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def visualizer_agent(state: AgentState):
    """JSON segments with timings, layout, source URL or AI prompt."""
    print("\n--- VISUALIZER: segment + layout plan (Groq) ---")

    feedback = (state.get("last_feedback_by_agent") or {}).get("visualizer", "")
    fb_block = ""
    if feedback.strip():
        fb_block = f"""
FEEDBACK (align segments and timings; fix issues only):
{feedback}
"""

    imgs = state.get("source_images") or []
    source_images_str = "\n".join(imgs) if imgs else "(none — use AI prompts only)"

    prompt = f"""
You are a TV News Visual Director.
{fb_block}
NARRATION SCRIPT:
{state['narration_script']}

SOURCE IMAGES FROM THE ARTICLE (reuse aggressively when on-topic):
The list below is the only trusted photo pool. Prefer a real URL over an AI prompt whenever the image supports the beat.
- Use a different layout pattern across segments where possible (e.g. anchor_left + source_visual_right vs anchor_center vs anchor_left + graph_right).
- Across ALL segments where a source URL is relevant to the narration, assign source_image_url from this list. Do not use a source image for only one segment if multiple URLs apply to different beats.
- Only use ai_support_visual_prompt when no listed image fits that beat; keep prompts concrete and news-safe (no meta-instructions like "generate an image").

{source_images_str}

Produce 3-5 segments covering the full script. Total implied duration 60-120 seconds.
For each segment set exactly one of source_image_url OR ai_support_visual_prompt (never both null; never both filled).
Use MM:SS times, contiguous, non-overlapping, starting at 00:00.

Respond ONLY with valid JSON:
{{
  "video_duration_sec": <int 60-120>,
  "segments": [
    {{
      "segment_id": 1,
      "text": "<narration excerpt for this segment>",
      "start_time": "00:00",
      "end_time": "00:20",
      "layout": "anchor_left + source_visual_right",
      "source_image_url": "<url or null>",
      "ai_support_visual_prompt": "<description or null>"
    }}
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
        "segments": data.get("segments") or [],
        "video_duration_sec": int(data.get("video_duration_sec") or 60),
    }
