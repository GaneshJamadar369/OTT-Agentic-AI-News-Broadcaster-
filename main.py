import os
import json
from langgraph.graph import StateGraph, END
from langfuse.langchain import CallbackHandler
from state import AgentState
from journalist import journalist_agent
from editor import editor_agent
from visualizer import visualizer_agent
from tagger import tagger_agent
from reviewer import reviewer_agent

def should_start_narrating(state: AgentState):
    """End the graph early when extraction failed the journalist guardrails."""
    if state.get("article_text") == "ERROR: INVALID_CONTENT":
        return "end"
    return "continue"

def should_continue(state: AgentState):
    """After review: finalize, retry script only, or re-run visual packaging (both branches)."""
    review = state.get("review_scores", {})
    if review.get("status") == "PASS":
        return "finalize"
    
    # Max iterations stop
    if state.get("iterations", 0) >= 3:
        print("Max retries reached. Finalizing current version.")
        return "finalize"
    
    # Targeted Routing
    failure = review.get("failure_type", "editor").lower()
    if failure == "visualizer" or failure == "tagger":
        return "retry_visuals"
    else:
        return "retry_editor"

# Fork node: editor and retries both need visualizer + tagger in parallel.
def visual_packaging_fork(state: AgentState):
    return {}


# 2. Define the Final Assembler Node
def final_assembler(state: AgentState):
    """
    Merges segment rows from the visualizer with headline fields from the tagger.
    """
    segments = state.get("segments", [])
    tags = state.get("segment_tags", [])
    
    # Merge tagging data into the segment dictionaries
    for i, seg in enumerate(segments):
        if i < len(tags):
            seg.update(tags[i])
            
    return {"segments": segments}

# LangGraph workflow
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("journalist", journalist_agent)
workflow.add_node("editor", editor_agent)
workflow.add_node("visual_packaging_fork", visual_packaging_fork)
workflow.add_node("visualizer", visualizer_agent)
workflow.add_node("tagger", tagger_agent)
workflow.add_node("reviewer", reviewer_agent)
workflow.add_node("final_assembler", final_assembler)

# Set Entry Point
workflow.set_entry_point("journalist")

# Standard Sequential Flow
workflow.add_conditional_edges(
    "journalist",
    should_start_narrating,
    {
        "continue": "editor",
        "end": END
    }
)

# Parallel step: one fork so retries can re-run both branches together.
workflow.add_edge("editor", "visual_packaging_fork")
workflow.add_edge("visual_packaging_fork", "visualizer")
workflow.add_edge("visual_packaging_fork", "tagger")

# Re-Sync Parallel Nodes into the Reviewer
workflow.add_edge("visualizer", "reviewer")
workflow.add_edge("tagger", "reviewer")

# Reviewer routing: pass, cap retries at 3, else editor vs visual packaging fork.
workflow.add_conditional_edges(
    "reviewer",
    should_continue,
    {
        "finalize": "final_assembler",
        "retry_editor": "editor",
        "retry_visuals": "visual_packaging_fork",
    },
)

# Connect Final Assembler to the END
workflow.add_edge("final_assembler", END)

# Compiled graph (invoke with config.callbacks for Langfuse when configured).
app = workflow.compile()

def run_industry_pipeline(url):
    print("Starting news screenplay pipeline (LangGraph).")
    
    # Initialize the Langfuse tracker
    langfuse_handler = CallbackHandler()
    
    inputs = {
        "url": url, 
        "iterations": 0
    }
    
    # Run the graph!
    final_state = app.invoke(
        inputs,
        config={"callbacks": [langfuse_handler]}
    )
    
    # Check for Kill Switch activation
    if final_state.get("article_text") == "ERROR: INVALID_CONTENT":
        print("\nPipeline halted: invalid or blocked content. No screenplay generated.")
        return
    
    # Print Human-Readable Production Script
    print_human_screenplay(final_state)
    
    # Structured output for downstream video tooling
    output_schema = {
        "article_url": url,
        "source_title": final_state.get("article_title"),
        "video_duration_sec": final_state.get("video_duration_sec", 60),
        "segments": final_state.get("segments", [])
    }
    
    with open("final_broadcast_plan.json", "w", encoding="utf-8") as f:
        json.dump(output_schema, f, ensure_ascii=False, indent=2)
    print("\nSaved: final_broadcast_plan.json")


def print_human_screenplay(state):
    review = state.get("review_scores") or {}
    print("\n" + "=" * 80)
    print(f"PRODUCTION SCREENPLAY: {state.get('article_title', 'News Update')}")
    print("=" * 80)
    for seg in state.get("segments", []):
        print(
            f"\n[SCENE {seg['segment_id']} | "
            f"{seg.get('start_time', '00:00')}-{seg.get('end_time', '00:00')}]"
        )
        print(f"HEADLINE: {str(seg.get('headline', 'N/A')).upper()}")
        print(f"SUBTEXT:  {seg.get('subheadline', 'N/A')}")
        print(f"LAYOUT:   {seg.get('layout', 'N/A')}")
        print(f"VISUAL:   {seg.get('source_image_url') or seg.get('ai_support_visual_prompt')}")
        print(f"AUDIO:    {seg.get('text', '')}")
    print("\n" + "=" * 80)
    print(
        f"REVIEW: {review.get('status', 'N/A')} | "
        f"SCORE: {review.get('overall_average', 'N/A')}"
    )


if __name__ == "__main__":
    print("\n--- LOQO: News URL to broadcast screenplay ---")
    user_url = input("Please enter a news article URL: ").strip()
    if user_url:
        run_industry_pipeline(user_url)
    else:
        print("No URL provided. Exiting.")
