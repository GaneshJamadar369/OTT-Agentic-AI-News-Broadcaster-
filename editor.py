import os
from groq import Groq
from dotenv import load_dotenv
from state import AgentState

# Load dependencies
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def editor_agent(state: AgentState):
    """
    The Editor Agent: Writes a broadcast script (60-120s) with clear story beats.
    Target word count: 160-320 words.
    """
    print("\n--- EDITOR IS WRITING THE BROADCAST SCRIPT (via GROQ) ---")
    
    prompt = f"""
    You are a Senior TV News Producer. Use these facts from the article: 
    {state['article_text']}
    
    TASK: Write a 1-2 minute TV News Narration Script.
    Constraints:
    - Length: Exactly 160 to 320 words (approx 60-120s at speaking speed).
    - Tone: Professional, urgent, and conversational (broadcast style).
    - Structure:
        1. THE HOOK: A punchy lead that spreads interest.
        2. THE MEAT: 3-4 distinct 'beats' or paragraphs with factual depth.
        3. THE CLOSE: A professional sign-off or closing thought.
    - Avoid: Robotic phrasing or bulleted lists in the final script.
    """
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return {
        "narration_script": response.choices[0].message.content,
        "current_agent": "Editor"
    }