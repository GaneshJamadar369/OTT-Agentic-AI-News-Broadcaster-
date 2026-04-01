"""Merge deterministic + LLM scores; apply policy; emit pass flags and retry routing."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from evaluation.load_rubric import get_metrics_for_agent


def merge_metric_scores(
    rubric_agent: Dict[str, Any],
    deterministic: Dict[str, Dict[str, Any]],
    llm: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Full metric_id -> {score, evidence} per rubric evaluator type."""
    merged: Dict[str, Dict[str, Any]] = {}
    for mid, meta in rubric_agent.items():
        ev = meta.get("evaluator", "llm")
        if ev == "code":
            merged[mid] = deterministic.get(mid, {"score": 2, "evidence": "missing deterministic evaluation"})
        elif ev == "llm":
            merged[mid] = llm.get(mid, {"score": 2, "evidence": "missing LLM evaluation"})
        else:
            merged[mid] = deterministic.get(mid) or llm.get(mid) or {"score": 2, "evidence": "missing hybrid evaluation"}
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
) -> Tuple[bool, List[str]]:
    """Returns (pass, blocking_metric_ids)."""
    floor_crit = int(policy.get("critical_score_floor", 4))
    floor_nc = int(policy.get("min_score_per_metric", 3))
    min_by_metric = (policy.get("metric_minimum_scores") or {}).get(agent_name, {}) or {}
    blocking: List[str] = []
    for mid, meta in rubric_agent.items():
        cell = merged.get(mid)
        if not cell:
            blocking.append(mid)
            continue
        sc = int(cell.get("score", 0))
        if mid in min_by_metric and sc < float(min_by_metric[mid]):
            blocking.append(mid)
            continue
        if meta.get("critical"):
            cf = _critical_floor_for_metric(mid, policy, floor_crit)
            if float(sc) < cf:
                blocking.append(mid)
            continue
        if not meta.get("critical") and sc < max(floor_nc, int(meta.get("min_score", 3))):
            blocking.append(mid)
    thr = float(policy.get("overall_pass_threshold_per_agent", 4.3))
    wa = weighted_average(merged, rubric_agent)
    ok = (len(blocking) == 0) and (wa >= thr)
    if not ok and not blocking and wa < thr:
        blocking.append("weighted_average")
    return ok, blocking if not ok else []


def cross_passes(
    merged: Dict[str, Dict[str, Any]],
    rubric_cross: Dict[str, Any],
    policy: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    floor_crit = int(policy.get("critical_score_floor", 4))
    floor_nc = int(policy.get("min_score_per_metric", 3))
    blocking: List[str] = []
    for mid, meta in rubric_cross.items():
        cell = merged.get(mid)
        if not cell:
            blocking.append(mid)
            continue
        sc = int(cell.get("score", 0))
        if meta.get("critical") and sc < floor_crit:
            blocking.append(mid)
        elif not meta.get("critical") and sc < max(floor_nc, int(meta.get("min_score", 3))):
            blocking.append(mid)
    thr = float(policy.get("overall_pass_threshold_cross_package", 4.5))
    wa = weighted_average(merged, rubric_cross)
    ok = (len(blocking) == 0) and (wa >= thr)
    if not ok and not blocking and wa < thr:
        blocking.append("weighted_average_cross")
    return ok, blocking if not ok else []


def build_feedback_block(
    agent: str,
    merged: Dict[str, Dict[str, Any]],
    rubric_agent: Dict[str, Any],
    passed: bool,
    blocking_ids: List[str] | None = None,
) -> str:
    if passed:
        return ""
    ids = blocking_ids if blocking_ids is not None else []
    if not ids:
        for mid, meta in rubric_agent.items():
            cell = merged.get(mid)
            if not cell:
                ids.append(mid)
                continue
            sc = int(cell.get("score", 0))
            crit = meta.get("critical")
            min_sc = int(meta.get("min_score", 3))
            bad = (crit and sc < 4) or (not crit and sc < min_sc)
            if bad:
                ids.append(mid)
    return format_blocking_metrics_feedback(agent, merged, rubric_agent, ids)


def format_blocking_metrics_feedback(
    agent: str,
    merged: Dict[str, Dict[str, Any]],
    rubric_agent: Dict[str, Any],
    blocking_ids: List[str],
) -> str:
    """HR-facing retry text: metric id, score, judge evidence, concrete FIX line."""
    lines = [
        f"{agent} — BLOCKING METRICS (fix each; keep what already passes):",
    ]
    any_line = False
    for mid in blocking_ids:
        if mid in ("weighted_average", "weighted_average_cross"):
            continue
        cell = merged.get(mid) or {}
        sc = cell.get("score", "?")
        ev = (cell.get("evidence") or "")[:400]
        title = (rubric_agent.get(mid) or {}).get("name", mid)
        lines.append(
            f"- {mid} scored {sc}/5 — {title}\n"
            f"  REASON: {ev}\n"
            f"  FIX: Raise this dimension to meet policy; revise output accordingly."
        )
        any_line = True
    if not any_line and blocking_ids:
        lines.append(
            "- Weighted average below threshold: improve the weakest scored metrics above the floor "
            "and re-balance the bundle."
        )
    return "\n".join(lines)


def merge_agent_feedback(prev: str, new: str) -> str:
    p, n = (prev or "").strip(), (new or "").strip()
    if not n:
        return p
    if not p:
        return n
    return p + "\n\n---\n\n" + n


def decide_package_retry_route(
    editor_ok: bool,
    visualizer_ok: bool,
    tagger_ok: bool,
    cross_ok: bool,
) -> str:
    """Return routing key for LangGraph conditional."""
    if not editor_ok:
        return "retry_editor"
    if not visualizer_ok or not tagger_ok:
        return "retry_visuals"
    if not cross_ok:
        return "retry_visuals"
    return "finalize"


def feedback_for_parallel_fail(validation_errors: List[str]) -> str:
    return "FEEDBACK (deterministic sync):\n" + "\n".join(f"- {e}" for e in validation_errors)
