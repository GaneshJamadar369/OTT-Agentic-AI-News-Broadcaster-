import os
from groq import Groq
from dotenv import load_dotenv
from state import AgentState
from scraper_utils import scrape_article

# Load dependencies
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def journalist_agent(state: AgentState):
    """
    The Journalist Agent: Fetches the article content using the tiered scraper 
    and uses an LLM to professionally summarize it.
    """
    print(f"\n--- JOURNALIST IS EXTRACTING CONTENT FROM: {state['url']} ---")
    
    # 1. Programmatic Scraping (Requests + Playwright + Trafilatura)
    article_data = scrape_article(state['url'])
    
    # 2. Use LLM to format/refine the extracted content
    prompt = f"""
    You are a professional News Researcher. 
    Review the following extracted article content:
    
    TITLE: {article_data['title']}
    TEXT: {article_data['text']}
    
    Refine and return the following in a structured format:
    1. A punchy Article Title.
    2. The core story (3-5 detailed paragraphs for narration).
    3. Key facts (names, dates, locations).
    
    Format the output as follows:
    TITLE: [Refined Title]
    STORY: [Refined Story]
    FACTS: [Key Facts]
    """
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    
    extracted_content = response.choices[0].message.content
    
    # KILL SWITCH: Detect 404, 401, or trivial text (Sidebar Hallucinations)
    error_flags = ["404", "401", "Page Not Found", "Access Denied", "Not Found"]
    is_error = any(flag in extracted_content for flag in error_flags)
    
    if is_error or len(article_data['text']) < 400:
        print(f"\n[Journalist] Guardrail: thin or error-like content. Stopping: {state['url']}")
        return {
            "article_title": "Invalid Content (404/Thin)",
            "article_text": "ERROR: INVALID_CONTENT",
            "source_images": [],
            "current_agent": "Journalist"
        }
    
    return {
        "article_title": article_data['title'] or "Extracted Title",
        "article_text": extracted_content,
        "source_images": article_data['images'],
        "current_agent": "Journalist"
    }