import os
import json
from groq import Groq
from dotenv import load_dotenv
from state import AgentState

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def reviewer_agent(state: AgentState):
    print("\n--- REVIEWER: scoring package (Groq) ---")
    
    # Context includes the narration, visual segments, and tags
    review_context = {
        "article_title": state['article_title'],
        "script": state['narration_script'],
        "segments": state['segments'],
        "tags": state['segment_tags']
    }

    prompt = f"""
    You are a Critical News Consultant. Evaluate this broadcast package against these criteria:
    {json.dumps(review_context)}

    Main Evaluation Criteria (Score 1-5):
    1. Story Structure & Flow (Start, Middle, End closure)
    2. Hook & Engagement (Opening interest)
    3. Narration Quality (Professional, easy to speak)
    4. Visual Planning (Relevant visuals, correct timing/layouts)
    5. Headline/Tag Quality (Short, punchy, matches segment)

    PASS RULE: Overall average must be 4.0 or higher, and NO single score below 3.

    Provide your response in JSON format:
    {{
      "scores": {{
        "structure": 0,
        "hook": 0,
        "narration": 0,
        "visuals": 0,
        "headlines": 0
      }},
      "overall_average": 0.0,
      "status": "PASS or FAIL",
      "failure_type": "None, editor, visualizer, or tagger",
      "feedback": "Detailed reason why it passed or failed"
    }}

    IMPORTANT: If status is FAIL, set 'failure_type' to the most problematic agent:
    - 'editor': If structure, hook, or narration is weak.
    - 'visualizer': If visual planning or timing is bad.
    - 'tagger': If headlines/tags are weak.
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    review_results = json.loads(response.choices[0].message.content)
    
    # If we failed, we increment the iteration counter
    update = {
        "review_scores": review_results,
        "current_agent": "Reviewer"
    }
    
    if review_results.get("status") == "FAIL":
        update["iterations"] = 1 # Reducer adds this to the total
        
    return update