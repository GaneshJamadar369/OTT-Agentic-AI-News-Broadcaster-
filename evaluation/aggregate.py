"""Merge deterministic + LLM scores; apply policy; emit pass flags and surgical retry routing."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from evaluation.load_rubric import get_metrics_for_agent


def merge_metric_scores(
    rubric_agent: Dict[str, Any],
    deterministic: Dict[str, Dict[str, Any]],
    llm: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Full metric_id -> {score, evidence, fix, owner} per rubric evaluator type."""
    merged: Dict[str, Dict[str, Any]] = {}
    for mid, meta in rubric_agent.items():
        ev_type = meta.get("evaluator", "llm")
        # Default metadata from rubric
        default_owner = meta.get("owner", "system")
        base = {"score": 2, "evidence": "missing", "fix": "check pipeline", "owner": default_owner}

        if ev_type == "code":
            cell = deterministic.get(mid, base)
        elif ev_type == "llm":
            cell = llm.get(mid, base)
        else:
            cell = deterministic.get(mid) or llm.get(mid) or base

        # Ensure fix/owner are present even if the source missed them
        if "fix" not in cell:
            cell["fix"] = "refer to rubric metric name"
        if "owner" not in cell or not cell["owner"]:
            cell["owner"] = default_owner

        merged[mid] = cell
    return merged


def weighted_average(merged: Dict[str, Dict[str, Any]], rubric_agent: Dict[str, Any]) -> float:
    num = 0.0
    den = 0.0
    for mid, meta in rubric_agent.items():
        w = float(meta.get("weight", 1.0))
        cell = merged.get(mid)
        if not cell:
            continue
        num += float(cell.get("score", 0)) * w
        den += w
    return num / den if den > 0 else 0.0


def _critical_floor_for_metric(mid: str, policy: Dict[str, Any], default: int) -> float:
    ovr = policy.get("critical_metric_floor_overrides") or {}
    if mid in ovr:
        return float(ovr[mid])
    return float(default)


def agent_passes(
    merged: Dict[str, Dict[str, Any]],
    rubric_agent: Dict[str, Any],
    policy: Dict[str, Any],
    agent_name: str = "",
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Returns (pass, blocking_metric_reports)."""
    floor_crit = int(policy.get("critical_score_floor", 4))
    floor_nc = int(policy.get("min_score_per_metric", 3))
    min_by_metric = (policy.get("metric_minimum_scores") or {}).get(agent_name, {}) or {}
    blocking: List[Dict[str, Any]] = []

    for mid, meta in rubric_agent.items():
        cell = merged.get(mid)
        if not cell:
            blocking.append({"id": mid, "score": 0, "threshold": 2, "evidence": "missing cell", "fix": "rerun", "owner": agent_name})
            continue

        sc = int(cell.get("score", 0))
        thr = 0.0
        is_blocked = False

        if mid in min_by_metric:
            thr = float(min_by_metric[mid])
            if sc < thr:
                is_blocked = True
        elif meta.get("critical"):
            thr = _critical_floor_for_metric(mid, policy, floor_crit)
            if sc < thr:
                is_blocked = True
        else:
            thr = max(floor_nc, int(meta.get("min_score", 3)))
            if sc < thr:
                is_blocked = True

        if is_blocked:
            blocking.append({
                "id": mid,
                "score": sc,
                "threshold": thr,
                "evidence": cell.get("evidence"),
                "fix": cell.get("fix"),
                "owner": cell.get("owner") or agent_name
            })

    wa = weighted_average(merged, rubric_agent)
    thr_avg = float(policy.get("overall_pass_threshold_per_agent", 4.3))
    ok = (len(blocking) == 0) and (wa >= thr_avg)

    if not ok and not blocking and wa < thr_avg:
        blocking.append({
            "id": "weighted_average",
            "score": wa,
            "threshold": thr_avg,
            "evidence": "Average below threshold",
            "fix": "Improve the weakest overall metrics while preserving what already passes.",
            "owner": agent_name
        })

    return ok, blocking


def cross_passes(
    merged: Dict[str, Dict[str, Any]],
    rubric_cross: Dict[str, Any],
    policy: Dict[str, Any],
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Returns (pass, blocking_metric_reports) for cross-package logic."""
    floor_crit = int(policy.get("critical_score_floor", 4))
    floor_nc = int(policy.get("min_score_per_metric", 3))
    blocking: List[Dict[str, Any]] = []

    for mid, meta in rubric_cross.items():
        cell = merged.get(mid)
        if not cell:
            blocking.append({"id": mid, "score": 0, "threshold": 2, "evidence": "missing cell", "fix": "rerun", "owner": "system"})
            continue

        sc = int(cell.get("score", 0))
        thr = 0.0
        is_blocked = False

        if meta.get("critical"):
            thr = floor_crit
            if sc < thr:
                is_blocked = True
        else:
            thr = max(floor_nc, int(meta.get("min_score", 3)))
            if sc < thr:
                is_blocked = True

        if is_blocked:
            blocking.append({
                "id": mid,
                "score": sc,
                "threshold": thr,
                "evidence": cell.get("evidence"),
                "fix": cell.get("fix"),
                "owner": cell.get("owner") or "system"
            })

    wa = weighted_average(merged, rubric_cross)
    thr_avg = float(policy.get("overall_pass_threshold_cross_package", 4.5))
    ok = (len(blocking) == 0) and (wa >= thr_avg)

    if not ok and not blocking and wa < thr_avg:
        blocking.append({
            "id": "weighted_average_cross",
            "score": wa,
            "threshold": thr_avg,
            "evidence": "Global cross-package average below threshold",
            "fix": "Review alignment between narrative and visuals; ensure modality consistency.",
            "owner": "editor, visualizer, tagger"
        })

    return ok, blocking


def build_surgical_feedback_for_agent(
    agent_name: str,
    all_failures: List[Dict[str, Any]]
) -> str:
    """Filter failures by owner and build dense repair packets."""
    relevant = []
    for f in all_failures:
        owners = [o.strip().lower() for o in str(f.get("owner", "")).split(",")]
        if agent_name.lower() in owners:
            relevant.append(f)

    if not relevant:
        return ""

    lines = [f"\n--- SURGICAL REPAIR PACKET FOR {agent_name.upper()} ---"]
    for f in relevant:
        packet = {
            "metric": f["id"],
            "score": f["score"],
            "threshold": f["threshold"],
            "problem": f["evidence"],
            "fix": f["fix"],
            "preserve": ["segment_count", "timecode_structure", "factual_core"]
        }
        lines.append(json.dumps(packet, indent=2))

    return "\n".join(lines)


def route_by_blocking_metrics(all_failures: List[Dict[str, Any]]) -> str:
    """Surgical routing: Failures drive the route, with Editor-First priority."""
    if not all_failures:
        return "finalize"

    owners = set()
    for f in all_failures:
        fo = [o.strip().lower() for o in str(f.get("owner", "")).split(",")]
        owners.update(fo)

    if "system" in owners:
        # System failures (config, versions) are fatal and non-retryable for content agents
        return "abort"

    if "editor" in owners:
        # Editor first priority: visualizer depends on script
        return "retry_editor"

    if "visualizer" in owners or "tagger" in owners:
        return "retry_visuals"

    return "finalize"


def merge_agent_feedback(prev: str, new: str) -> str:
    p, n = (prev or "").strip(), (new or "").strip()
    if not n:
        return p
    if not p:
        return n
    if n in p:
        return p
    return p + "\n\n" + n


def feedback_for_parallel_fail(validation_errors: List[str]) -> str:
    return "FEEDBACK (deterministic sync):\n" + "\n".join(f"- {e}" for e in validation_errors)
