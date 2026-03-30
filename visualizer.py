import os
import json
from groq import Groq
from dotenv import load_dotenv
from state import AgentState

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def visualizer_agent(state: AgentState):
    """
    The Visualizer Agent: Plans the timing, layout, and visual prompts for each segment.
    Uses source images if available.
    """
    print("\n--- VISUALIZER IS PLANNING THE SCREENPLAY SEGMENTS (via GROQ) ---")
    
    source_images_str = "\n".join(state.get("source_images", []))
    
    prompt = f"""
    You are a TV News Visual Director. Take this narration script:
    {state['narration_script']}
    
    And these source images from the article:
    {source_images_str}
    
    Break this script into 3-5 logical segments.
    For EACH segment, provide:
    1. The portion of the script text.
    2. Start time and End time (e.g., "00:00" to "00:12"). Ensure the total duration is 60-120s.
    3. A 'Layout' (e.g., 'anchor_left + source_visual_right', 'fullscreen_ai_visual', 'anchor_center').
    4. A 'Visual Plan': 
       - If a source image is relevant, use its URL.
       - If not, describe a detailed AI Image Prompt (e.g., 'Realistic news-style shot of a crowded Indian market, smoke in distance, 4k').

    IMPORTANT: You MUST respond ONLY in valid JSON format like this:
    {{
      "video_duration_sec": 75,
      "segments": [
        {{
          "segment_id": 1,
          "text": "...",
          "start_time": "00:00",
          "end_time": "00:12",
          "layout": "...",
          "source_image_url": "url_or_null",
          "ai_support_visual_prompt": "description_or_null"
        }}
      ]
    }}
    """
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    data = json.loads(response.choices[0].message.content)
    
    return {
        "segments": data["segments"],
        "video_duration_sec": data.get("video_duration_sec", 60)
    }