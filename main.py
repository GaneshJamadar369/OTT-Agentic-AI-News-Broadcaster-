import json
import os
from langgraph.graph import StateGraph, END
from langfuse.langchain import CallbackHandler

from state import AgentState
from journalist import journalist_agent
from editor import editor_agent
from visualizer import visualizer_agent
from tagger import tagger_agent
from metadata_agent import metadata_agent
from evaluation.load_rubric import load_policy, load_rubric
from evaluation.pipeline import evaluate_journalist_step, evaluate_package_step, validate_parallel_step
from errors import BroadcastRejectedError


def route_after_journalist_output(state: AgentState):
    if state.get("article_text") == "ERROR: INVALID_CONTENT":
        return "invalid"
    return "eval"


def route_after_journalist_eval(state: AgentState):
    res = (state.get("evaluation_results") or {}).get("journalist") or {}
    if res.get("pass"):
        print("[route] evaluate_journalist -> continue (PASS)")
        return "continue"
    policy = load_policy()
    max_r = int(policy.get("agent_max_retries", {}).get("journalist", 2))
    runs = int(state.get("journalist_runs") or 0)
    if runs < 1 + max_r:
        print(
            f"[route] evaluate_journalist -> retry journalist "
            f"(runs={runs}, max_retries={max_r}, blocking={res.get('blocking')})"
        )
        return "retry"
    print("[route] evaluate_journalist -> recover_best (budget exhausted)")
    return "recover"


def route_after_parallel(state: AgentState):
    if state.get("parallel_validation_ok"):
        print("[route] validate_parallel -> ok (deterministic sync PASS)")
        return "ok"
    policy = load_policy()
    max_r = int(policy.get("agent_max_retries", {}).get("visualizer", 2))
    pr = int(state.get("packaging_runs") or 0)
    errs = state.get("parallel_validation_errors") or []
    print(f"[route] validate_parallel FAIL: {errs}")
    
    if pr < 1 + max_r:
        # Check if the only failure is per-segment tag alignment
        only_tag_count = all("tag count" in e.lower() or "no tags" in e.lower() for e in errs)
        if only_tag_count:
            print(f"[route] validate_parallel -> retry_tagger_only (packaging_runs={pr}, max={max_r})")
            return "retry_tagger"
        print(f"[route] validate_parallel -> retry_visualizer (packaging_runs={pr}, max={max_r})")
        return "retry_visualizer"
    
    print("[route] validate_parallel -> reject_parallel (sync budget exhausted)")
    return "abort_sync"


def route_after_package(state: AgentState):
    if state.get("package_evaluation_ok"):
        print("[route] evaluate_package -> finalize (PASS)")
        return "finalize"
    policy = load_policy()
    max_g = int(policy.get("max_graph_iterations", 3))
    it = int(state.get("iterations") or 0)
    hint = state.get("package_route_hint") or "retry_visuals"
    rs = state.get("review_scores") or {}
    print(
        f"[route] evaluate_package FAIL: status={rs.get('status')} "
        f"iterations={it}/{max_g} hint={hint} "
        f"by_agent={rs.get('by_agent')}"
    )
    if it >= max_g:
        print("[route] evaluate_package -> recover_best (max graph iterations)")
        return "recover"
    max_e = int(policy.get("agent_max_retries", {}).get("editor", 2))
    max_v = int(policy.get("agent_max_retries", {}).get("visualizer", 2))
    er = int(state.get("editor_runs") or 0)
    pr = int(state.get("packaging_runs") or 0)
    if hint == "abort":
        print("[route] evaluate_package -> reject_package (FATAL SYSTEM FAILURE)")
        return "reject_package"
    if hint == "retry_editor" and er < 1 + max_e:
        print(f"[route] evaluate_package -> retry_editor (editor_runs={er}, max={max_e})")
        return "retry_editor"
    if hint == "retry_visuals" and pr < 1 + max_v:
        print(
            f"[route] evaluate_package -> retry_visuals (fork) "
            f"(packaging_runs={pr}, max={max_v})"
        )
        return "retry_visuals"
    print("[route] evaluate_package -> recover_best (retry budgets exhausted or invalid hint)")
    return "recover"


def visual_packaging_fork(state: AgentState):
    return {"packaging_runs": int(state.get("packaging_runs") or 0) + 1}


def evaluate_journalist_node(state: AgentState):
    return evaluate_journalist_step(dict(state))


def validate_parallel_node(state: AgentState):
    return validate_parallel_step(dict(state))


def evaluate_package_node(state: AgentState):
    return evaluate_package_step(dict(state))


def parallel_fork(state: AgentState):
    return {}

def rollback_best_journalist_node(state: AgentState):
    print("[recovery] Rolling back to best journalist iteration (Best-of-N)")
    return state.get("best_journalist_state") or {}

def rollback_best_package_node(state: AgentState):
    print("[recovery] Rolling back to best package iteration (Best-of-N)")
    return state.get("best_package_state") or {}

def repair_tagger_node(state: AgentState):
    print("[repair] Retrying tagger for current segments (surgical count fix)")
    return tagger_agent(state)

def final_assembler(state: AgentState):
    segments = state.get("segments") or []
    tags = state.get("segment_tags") or []
    for i, seg in enumerate(segments):
        if i < len(tags):
            seg.update(tags[i])
    return {"segments": segments}


def reject_after_journalist(state: AgentState):
    snap = {
        "evaluation_results": state.get("evaluation_results"),
        "review_scores": state.get("review_scores"),
        "evaluation_trace": state.get("evaluation_trace"),
    }
    raise BroadcastRejectedError(
        "BROADCAST REJECTED: journalist evaluation failed after max retries (rubric thresholds not met).",
        evaluation_snapshot=snap,
    )


def reject_after_parallel(state: AgentState):
    snap = {
        "parallel_validation_errors": state.get("parallel_validation_errors"),
        "evaluation_trace": state.get("evaluation_trace"),
    }
    raise BroadcastRejectedError(
        "BROADCAST REJECTED: visualizer/tagger deterministic sync failed after max packaging retries.",
        evaluation_snapshot=snap,
    )


def reject_after_package(state: AgentState):
    snap = {
        "evaluation_results": state.get("evaluation_results"),
        "review_scores": state.get("review_scores"),
        "evaluation_trace": state.get("evaluation_trace"),
    }
    raise BroadcastRejectedError(
        "BROADCAST REJECTED: package evaluation failed after max graph iterations or retry budgets exhausted. "
        f"iterations={state.get('iterations')} package_ok={state.get('package_evaluation_ok')}",
        evaluation_snapshot=snap,
    )


workflow = StateGraph(AgentState)

workflow.add_node("journalist", journalist_agent)
workflow.add_node("evaluate_journalist", evaluate_journalist_node)
workflow.add_node("parallel_fork", parallel_fork)
workflow.add_node("editor", editor_agent)
workflow.add_node("metadata_agent", metadata_agent)
workflow.add_node("visual_packaging_fork", visual_packaging_fork)
workflow.add_node("visualizer", visualizer_agent)
workflow.add_node("tagger", tagger_agent)
workflow.add_node("validate_parallel", validate_parallel_node)
workflow.add_node("evaluate_package", evaluate_package_node)
workflow.add_node("final_assembler", final_assembler)
workflow.add_node("rollback_journalist", rollback_best_journalist_node)
workflow.add_node("rollback_package", rollback_best_package_node)
workflow.add_node("repair_tagger", repair_tagger_node)
workflow.add_node("reject_journalist", reject_after_journalist)
workflow.add_node("reject_parallel", reject_after_parallel)
workflow.add_node("reject_package", reject_after_package)

workflow.set_entry_point("journalist")

workflow.add_conditional_edges(
    "journalist",
    route_after_journalist_output,
    {"invalid": END, "eval": "evaluate_journalist"},
)

workflow.add_conditional_edges(
    "evaluate_journalist",
    route_after_journalist_eval,
    {"continue": "parallel_fork", "retry": "journalist", "recover": "rollback_journalist", "abort": "reject_journalist"},
)

workflow.add_edge("rollback_journalist", "parallel_fork")

workflow.add_edge("parallel_fork", "editor")
workflow.add_edge("parallel_fork", "metadata_agent")

workflow.add_edge("editor", "visual_packaging_fork")
workflow.add_edge("metadata_agent", "visual_packaging_fork")

workflow.add_edge("visual_packaging_fork", "visualizer")
workflow.add_edge("visualizer", "tagger")
workflow.add_edge("tagger", "validate_parallel")

workflow.add_conditional_edges(
    "validate_parallel",
    route_after_parallel,
    {
        "ok": "evaluate_package",
        "retry_tagger": "repair_tagger",
        "retry_visualizer": "visual_packaging_fork",
        "abort_sync": "reject_parallel"
    },
)

workflow.add_edge("repair_tagger", "validate_parallel")

workflow.add_conditional_edges(
    "evaluate_package",
    route_after_package,
    {
        "finalize": "final_assembler",
        "retry_editor": "editor",
        "retry_visuals": "visual_packaging_fork",
        "recover": "rollback_package",
        "reject_package": "reject_package",
    },
)

workflow.add_edge("rollback_package", "final_assembler")

workflow.add_edge("final_assembler", END)

app = workflow.compile()


def run_industry_pipeline(url: str):
    print("Starting news screenplay pipeline (LangGraph + rubric evaluation).")

    rubric = load_rubric()
    policy = load_policy()
    rv, pv = str(rubric.get("version", "?")), str(policy.get("version", "?"))

    langfuse_handler = CallbackHandler()

    inputs: dict = {
        "url": url,
        "iterations": 0,
        "journalist_runs": 0,
        "editor_runs": 0,
        "packaging_runs": 0,
        "evaluation_trace": [],
        "rubric_version": str(rv),
        "policy_version": str(pv),
    }

    try:
        final_state = app.invoke(
            inputs,
            config={"callbacks": [langfuse_handler]},
        )
    except BroadcastRejectedError as exc:
        print("\n", str(exc))
        snap = getattr(exc, "evaluation_snapshot", None) or {}
        try:
            with open("evaluation_report.json", "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
            print("Saved: evaluation_report.json (rejection snapshot)")
        except OSError:
            pass
        raise

    if final_state.get("article_text") == "ERROR: INVALID_CONTENT":
        print("\nPipeline halted: invalid or blocked content.")
        return None

    print_human_screenplay(final_state)

    out = {
        "article_url": url,
        "source_title": final_state.get("article_title"),
        "video_duration_sec": final_state.get("video_duration_sec", 60),
        "segments": final_state.get("segments") or [],
        "evaluation_results": final_state.get("evaluation_results"),
        "evaluation_trace": final_state.get("evaluation_trace"),
        "rubric_version": final_state.get("rubric_version"),
        "policy_version": final_state.get("policy_version"),
        "review_scores": final_state.get("review_scores"),
        "video_category": final_state.get("video_category"),
        "seo_tags": final_state.get("seo_tags"),
    }

    with open("final_broadcast_plan.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open("evaluation_report.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "evaluation_trace": final_state.get("evaluation_trace"),
                "evaluation_results": final_state.get("evaluation_results"),
                "review_scores": final_state.get("review_scores"),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("\nSaved: final_broadcast_plan.json, evaluation_report.json")
    return out


def print_human_screenplay(state: dict):
    review = state.get("review_scores") or {}
    print("\n" + "=" * 80)
    print(f"PRODUCTION SCREENPLAY: {state.get('article_title', 'News Update')}")
    print(f"CATEGORY: {state.get('video_category', 'N/A')} | TAGS: {', '.join(state.get('seo_tags', []))}")
    print("=" * 80)
    for seg in state.get("segments") or []:
        sid = seg.get("segment_id", "?")
        print(
            f"\n[SCENE {sid} | {seg.get('start_time', '00:00')}-{seg.get('end_time', '00:00')}]"
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
