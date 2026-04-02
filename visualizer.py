import os
import json
from groq import Groq
from dotenv import load_dotenv
from state import AgentState
from groq_utils import groq_chat_create

load_dotenv()
_groq_keys = os.getenv("GROQ_API_KEY", "").split(",")
client = Groq(api_key=_groq_keys[0].strip() if _groq_keys else None)


def visualizer_agent(state: AgentState):
    """Plan 4 TV-style segments with timings, layout, and either a source URL or AI prompt."""
    print("\n--- VISUALIZER: segment + layout plan (Groq) ---")

    feedback = (state.get("last_feedback_by_agent") or {}).get("visualizer", "")
    fb_block = ""
    if feedback.strip():
        fb_block = f"""
FEEDBACK FROM PREVIOUS REVIEW (fix only these issues, keep good parts stable):
{feedback}
"""

    imgs = state.get("source_images") or []
    source_images_str = "\n".join(imgs) if imgs else "(none — use AI prompts only)"

    prompt = f"""
You are a senior TV News Visual Director for a 1–2 minute broadcast.

Your job: take the NARRATION SCRIPT and break it into exactly FOUR on-air segments
that feel like a real TV package. Each segment must have:
- a contiguous excerpt of the narration (do NOT invent new narration),
- start and end times,
- a layout choice,
- EITHER a source image URL from the list OR an AI support visual prompt (never both).

{fb_block}
NARRATION SCRIPT (full, final anchor read):
{state['narration_script']}

SOURCE IMAGES FROM THE ARTICLE (trusted photo pool):
Use these URLs wherever they naturally match a beat. Prefer real URLs over AI prompts.
Only use an AI prompt when none of these images fit that segment.
{source_images_str}

SEGMENT DESIGN RULES (VERY IMPORTANT):

1) EXACTLY 4 SEGMENTS, IN ORDER
   - Segment 1: OPENING / HOOK (introduce story, location, main actors)
   - Segment 2: CONTEXT & DETAILS (what happened, how, key facts)
   - Segment 3: IMPACT & DEVELOPMENTS (responses, casualties, international angle, etc.)
   - Segment 4: CLOSING & WHAT'S NEXT (current status + forward-looking line)

   Split the narration into 4 contiguous chunks in this order.
   The "text" field for each segment MUST be copied from the script (full sentences),
   not rewritten summaries.

2) TIMING & DURATION
   - video_duration_sec must be an integer between 75 and 105.
   - Use MM:SS timestamps.
   - start_time must begin at "00:00" for segment 1.
   - Times must be strictly increasing and non-overlapping.
   - The end_time of segment 4 should be very close to video_duration_sec.
   - Aim for a natural anchor cadence: roughly 2–3 spoken words per second
     inside each segment (no auctioneer speed, no extremely slow pauses).

3) LAYOUT VARIETY
   Use only these layout strings:
   - "anchor_left + source_visual_right"
   - "anchor_left + ai_support_visual_right"
   - "anchor_center + full_frame_visual"
   - "anchor_left + graph_right"

   Do NOT use the same layout for all segments.
   At least TWO different layouts must appear, and avoid repeating the exact same
   layout more than twice in a row.

4) SOURCE IMAGE VS AI PROMPT (CRITICAL)
   - For each segment, set EXACTLY ONE of:
       * source_image_url: "<one of the trusted URLs above>"
       * ai_support_visual_prompt: "<concrete visual description>"
   - NEVER leave both null, NEVER fill both at the same time.
   - If a source image clearly matches the narration for that segment, USE IT.
     Example: if the narration mentions "White House address", prefer a source image
     showing the speaker / White House.
   - Only use ai_support_visual_prompt when no source image fits that beat.
   - AI prompts must be concrete, safe and visual only. Do NOT include meta text
     like "generate an image" or "a picture of". Just describe the scene.

5) SEGMENT TEXT QUALITY
   - text should be 1–3 short sentences copied from the narration that fit the beat.
   - Do not repeat the exact same sentences across multiple segments.
   - Make sure the four texts together cover the whole story from open to close.

RESPOND ONLY WITH A VALID JSON OBJECT. NO extra commentary, no Markdown.

JSON SCHEMA (EXAMPLE SHAPE ONLY, NOT VALUES):

{{
  "video_duration_sec": 90,
  "segments": [
    {{
      "segment_id": 1,
      "text": "<excerpt from narration for opening>",
      "start_time": "00:00",
      "end_time": "00:20",
      "layout": "anchor_left + source_visual_right",
      "source_image_url": "<one URL from the list above or null>",
      "ai_support_visual_prompt": "<prompt or null>"
    }},
    {{
      "segment_id": 2,
      "text": "<excerpt from narration for context>",
      "start_time": "00:20",
      "end_time": "00:40",
      "layout": "anchor_left + ai_support_visual_right",
      "source_image_url": null,
      "ai_support_visual_prompt": "<prompt>"
    }},
    {{
      "segment_id": 3,
      "text": "<excerpt from narration for developments>",
      "start_time": "00:40",
      "end_time": "01:05",
      "layout": "anchor_center + full_frame_visual",
      "source_image_url": "<url or null>",
      "ai_support_visual_prompt": "<prompt or null>"
    }},
    {{
      "segment_id": 4,
      "text": "<excerpt from narration for closing>",
      "start_time": "01:05",
      "end_time": "01:30",
      "layout": "anchor_left + graph_right",
      "source_image_url": "<url or null>",
      "ai_support_visual_prompt": "<prompt or null>"
    }}
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
        "segments": data.get("segments") or [],
        "video_duration_sec": int(data.get("video_duration_sec") or 90),
    }
