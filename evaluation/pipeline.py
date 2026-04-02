"""Evaluation pipeline steps invoked from LangGraph nodes."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from evaluation.aggregate import (
    agent_passes,
    build_surgical_feedback_for_agent,
    cross_passes,
    merge_agent_feedback,
    merge_metric_scores,
    route_by_blocking_metrics,
    weighted_average,
)
from evaluation.deterministic_checks import (
    check_cross_package_code,
    check_editor_deterministic,
    check_journalist_deterministic,
    check_tagger_deterministic,
    check_visualizer_deterministic,
)
from evaluation.llm_judge import (
    build_cross_context,
    build_editor_context,
    build_journalist_context,
    build_tagger_context,
    build_visualizer_context,
    run_llm_metrics,
)
from evaluation.load_rubric import get_metrics_for_agent, load_policy, load_rubric
from evaluation.trace import append_trace


def _versions(rubric: Dict[str, Any], policy: Dict[str, Any]) -> Tuple[str, str]:
    return str(rubric.get("version", "unknown")), str(policy.get("version", "unknown"))


def evaluate_journalist_step(state: Dict[str, Any]) -> Dict[str, Any]:
    rubric = load_rubric()
    policy = load_policy()
    rv, pv = _versions(rubric, policy)
    agent = "journalist"
    r_ag = get_metrics_for_agent(rubric, agent)
    det = check_journalist_deterministic(state)
    llm = run_llm_metrics(agent, rubric, build_journalist_context(state))
    merged = merge_metric_scores(r_ag, det, llm)
    ok, blocking_reports = agent_passes(merged, r_ag, policy, agent_name="journalist")
    wa = weighted_average(merged, r_ag)
    
    # Surgical feedback for journalist
    fb = build_surgical_feedback_for_agent(agent, blocking_reports)
    
    payload = {
        "agent": agent,
        "pass": ok,
        "weighted_average": wa,
        "blocking": [f["id"] for f in blocking_reports],
        "blocking_reports": blocking_reports,
        "merged_scores": merged,
    }
    trace = append_trace(state.get("evaluation_trace"), "evaluate_journalist", {"weighted_averages": {agent: wa}, "pass": ok})
    er = dict(state.get("evaluation_results") or {})
    er["journalist"] = payload
    
    # Best-of-N Tracking
    best_scr = state.get("best_journalist_score") or 0.0
    best_st = state.get("best_journalist_state") or {}
    if wa > best_scr:
        best_scr = wa
        best_st = {
            "article_title": state.get("article_title"),
            "article_text": state.get("article_text"),
            "raw_article_text": state.get("raw_article_text"),
            "source_images": state.get("source_images"),
        }
        
    out: Dict[str, Any] = {
        "evaluation_results": er,
        "evaluation_trace": trace,
        "rubric_version": rv,
        "policy_version": pv,
        "best_journalist_score": best_scr,
        "best_journalist_state": best_st,
        "review_scores": {
            "status": "PASS" if ok else "FAIL",
            "overall_average": wa,
            "agent": agent,
            "blocking_metrics": [f["id"] for f in blocking_reports],
        },
    }
    if fb:
        lf = state.get("last_feedback_by_agent") or {}
        lf = {**lf, agent: fb}
        out["last_feedback_by_agent"] = lf
    return out


def validate_parallel_step(state: Dict[str, Any]) -> Dict[str, Any]:
    # This remains mostly deterministic but feeds into surgical feedback later
    segs = state.get("segments") or []
    tags = state.get("segment_tags") or []
    errors: List[str] = []
    policy = load_policy()
    vd = state.get("video_duration_sec")
    if not isinstance(segs, list) or not segs:
        errors.append("Visualizer produced no segments")
    if not isinstance(tags, list) or not tags:
        errors.append("Tagger produced no tags")
    if len(segs) != len(tags):
        errors.append(f"Segment count {len(segs)} != tag count {len(tags)}")
    vd_min = policy.get("video_duration_min", 60)
    vd_max = policy.get("video_duration_max", 120)
    if isinstance(vd, int) and not (vd_min <= vd <= vd_max):
        errors.append(f"video_duration_sec {vd} not in [{vd_min},{vd_max}]")
    
    ok = len(errors) == 0
    out: Dict[str, Any] = {
        "parallel_validation_ok": ok,
        "parallel_validation_errors": errors,
    }
    if not ok:
        # Deterministic errors distributed to both
        fb = "FEEDBACK (deterministic sync):\n" + "\n".join(f"- {e}" for e in errors)
        lf = dict(state.get("last_feedback_by_agent") or {})
        lf["visualizer"] = merge_agent_feedback(lf.get("visualizer", ""), fb)
        lf["tagger"] = merge_agent_feedback(lf.get("tagger", ""), fb)
        out["last_feedback_by_agent"] = lf
    return out


def evaluate_package_step(state: Dict[str, Any]) -> Dict[str, Any]:
    rubric = load_rubric()
    policy = load_policy()
    rv, pv = _versions(rubric, policy)
    agents = ["editor", "visualizer", "tagger"]
    results: Dict[str, Any] = {}
    was: Dict[str, float] = {}
    all_failures: List[Dict[str, Any]] = []

    # 1. Editor
    det_ed = check_editor_deterministic(state)
    llm_ed = run_llm_metrics("editor", rubric, build_editor_context(state))
    r_ed = get_metrics_for_agent(rubric, "editor")
    m_ed = merge_metric_scores(r_ed, det_ed, llm_ed)
    ok_ed, bl_ed = agent_passes(m_ed, r_ed, policy, agent_name="editor")
    results["editor"] = {"pass": ok_ed, "merged": m_ed, "blocking": [f["id"] for f in bl_ed], "wa": weighted_average(m_ed, r_ed)}
    was["editor"] = results["editor"]["wa"]
    all_failures.extend(bl_ed)

    # 2. Visualizer
    det_v = check_visualizer_deterministic(state, len(state.get("segment_tags") or []))
    llm_v = run_llm_metrics("visualizer", rubric, build_visualizer_context(state))
    r_v = get_metrics_for_agent(rubric, "visualizer")
    m_v = merge_metric_scores(r_v, det_v, llm_v)
    ok_v, bl_v = agent_passes(m_v, r_v, policy, agent_name="visualizer")
    results["visualizer"] = {"pass": ok_v, "merged": m_v, "blocking": [f["id"] for f in bl_v], "wa": weighted_average(m_v, r_v)}
    was["visualizer"] = results["visualizer"]["wa"]
    all_failures.extend(bl_v)

    # 3. Tagger
    det_t = check_tagger_deterministic(state, len(state.get("segments") or []))
    llm_t = run_llm_metrics("tagger", rubric, build_tagger_context(state))
    r_t = get_metrics_for_agent(rubric, "tagger")
    m_t = merge_metric_scores(r_t, det_t, llm_t)
    ok_t, bl_t = agent_passes(m_t, r_t, policy, agent_name="tagger")
    results["tagger"] = {"pass": ok_t, "merged": m_t, "blocking": [f["id"] for f in bl_t], "wa": weighted_average(m_t, r_t)}
    was["tagger"] = results["tagger"]["wa"]
    all_failures.extend(bl_t)

    # 4. Cross-Package
    st_cross = {**state, "rubric_version": rv, "policy_version": pv}
    det_x = check_cross_package_code(st_cross)
    llm_x = run_llm_metrics("cross_package", rubric, build_cross_context(state))
    r_x = get_metrics_for_agent(rubric, "cross_package")
    m_x = merge_metric_scores(r_x, det_x, llm_x)
    ok_x, bl_x = cross_passes(m_x, r_x, policy)
    results["cross_package"] = {"pass": ok_x, "merged": m_x, "blocking": [f["id"] for f in bl_x], "wa": weighted_average(m_x, r_x)}
    was["cross_package"] = results["cross_package"]["wa"]
    all_failures.extend(bl_x)

    # Coarse booleans for legacy flow if needed, but routing is now surgical
    package_ok = (len(all_failures) == 0)
    route = route_by_blocking_metrics(all_failures)

    # Distribute surgical feedback packets
    lf = dict(state.get("last_feedback_by_agent") or {})
    for a in ["editor", "visualizer", "tagger"]:
        surgical_fb = build_surgical_feedback_for_agent(a, all_failures)
        if surgical_fb:
            lf[a] = merge_agent_feedback(lf.get(a, ""), surgical_fb)

    # Visible average includes cross-package (Truthful Analytics)
    overall = sum(was.values()) / len(was)
    
    trace = append_trace(
        state.get("evaluation_trace"),
        "evaluate_package",
        {"weighted_averages": was, "pass": package_ok},
    )

    er = dict(state.get("evaluation_results") or {})
    er["package"] = results
    
    # Best-of-N Tracking
    best_scr = state.get("best_package_score") or 0.0
    best_st = state.get("best_package_state") or {}
    if overall > best_scr:
        best_scr = overall
        best_st = {
            "narration_script": state.get("narration_script"),
            "segments": state.get("segments"),
            "segment_tags": state.get("segment_tags"),
            "video_duration_sec": state.get("video_duration_sec"),
            "video_category": state.get("video_category"),
            "seo_tags": state.get("seo_tags"),
        }
        
    out: Dict[str, Any] = {
        "evaluation_results": er,
        "evaluation_trace": trace,
        "package_evaluation_ok": package_ok,
        "package_route_hint": route,
        "rubric_version": rv,
        "policy_version": pv,
        "best_package_score": best_scr,
        "best_package_state": best_st,
        "review_scores": {
            "status": "PASS" if package_ok else "FAIL",
            "overall_average": overall,
            "by_agent": was,
            "cross_package_average": was.get("cross_package"),
            "all_blocking": [f["id"] for f in all_failures],
        },
        "last_feedback_by_agent": lf,
    }
    
    if not package_ok:
        # Prevent runaway loops if system issues detected
        if route == "abort":
            out["iterations"] = 99  # Signal LangGraph to stop
        else:
            out["iterations"] = 1
            
    return out
