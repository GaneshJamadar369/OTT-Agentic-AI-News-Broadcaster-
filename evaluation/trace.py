"""Append evaluation rounds and compute simple deltas for audit."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


def append_trace(
    trace: Optional[List[Dict[str, Any]]],
    round_name: str,
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    t = deepcopy(trace) if trace else []
    prev = t[-1]["payload"] if t else None
    delta: Dict[str, Any] = {}
    if prev and "weighted_averages" in payload and "weighted_averages" in prev:
        for k, v in payload.get("weighted_averages", {}).items():
            if k in prev.get("weighted_averages", {}):
                delta[k] = round(v - prev["weighted_averages"][k], 3)
    entry = {
        "round": round_name,
        "payload": payload,
        "delta_vs_previous": delta,
    }
    t.append(entry)
    return t
