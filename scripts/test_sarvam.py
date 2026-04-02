"""
Simple test script for Sarvam AI provider integration.
"""
import os
import sys

# Add parent directory to sys.path to find llm_utils
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from dotenv import load_dotenv
from llm_utils import llm_chat_create

def test_sarvam():
    load_dotenv()
    
    print("Testing LLM Provider Chain (Sarvam Specifically)...")
    
    messages = [
        {"role": "user", "content": "Hello Sarvam! Answer 'NAMASTE' if you hear me. love u"}
    ]
    
    try:
        # We can bypass Groq/Gemini by calling the internal helper for a clean test
        from llm_utils import _sarvam_fallback_create
        
        response = _sarvam_fallback_create(
            messages=messages,
            temperature=0
        )
        
        if response:
            print("\n--- RESPONSE INFO ---")
            print(f"Provider: {getattr(response, 'provider', 'Unknown')}")
            print(f"Model: {getattr(response, 'model', 'Unknown')}")
            print(f"Content: {response.choices[0].message.content}")
        else:
            print("\n--- SARVAM SKIPPED (No API Key or Other Error) ---")
        
    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    test_sarvam()
