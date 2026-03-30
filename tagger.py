import os
import json
from groq import Groq
from dotenv import load_dotenv
from state import AgentState

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def tagger_agent(state: AgentState):
    """Headlines, subheadlines, and top tags per segment (runs parallel to visualizer)."""
    print("\n--- TAGGER IS GENERATING HEADLINES & TAGS (via GROQ) ---")
    
    prompt = f"""
    You are a TV News Editor. Given this narration script:
    {state['narration_script']}
    
    Break the script into segments (should match the story's visual flow).
    For each segment, provide:
    1. A punchy Main Headline (max 30 chars).
    2. A descriptive Subheadline (max 50 chars).
    3. A Top Tag (e.g., 'BREAKING', 'LIVE', 'DEVELOPING', 'UPDATE').

    IMPORTANT: You MUST respond ONLY in valid JSON format like this:
    {{
      "segment_tags": [
        {{
          "headline": "...",
          "subheadline": "...",
          "top_tag": "..."
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
        "segment_tags": data["segment_tags"]
    }
