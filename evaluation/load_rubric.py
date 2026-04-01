"""Load and validate evaluation_rubric.yaml and evaluation_policy.yaml."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict

import yaml

_CONFIG = "config"
_RUBRIC = "evaluation_rubric.yaml"
_POLICY = "evaluation_policy.yaml"


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_rubric_generated(root: Path) -> None:
    rubric_path = root / _CONFIG / _RUBRIC
    gen_script = root / "gen_rubric.py"
    if rubric_path.exists():
        return
    if gen_script.is_file():
        spec = importlib.util.spec_from_file_location("gen_rubric", gen_script)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.main()


def load_rubric() -> Dict[str, Any]:
    root = get_project_root()
    _ensure_rubric_generated(root)
    path = root / _CONFIG / _RUBRIC
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "agents" not in data:
        raise ValueError("Invalid evaluation_rubric.yaml: missing agents")
    return data


def load_policy() -> Dict[str, Any]:
    root = get_project_root()
    path = root / _CONFIG / _POLICY
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_metrics_for_agent(rubric: Dict[str, Any], agent: str) -> Dict[str, Any]:
    return rubric.get("agents", {}).get(agent, {})


def metric_ids_for_llm(rubric: Dict[str, Any], agent: str) -> list[str]:
    out = []
    for mid, meta in get_metrics_for_agent(rubric, agent).items():
        ev = meta.get("evaluator", "llm")
        if ev in ("llm", "hybrid"):
            out.append(mid)
    return out


def metric_ids_for_code(rubric: Dict[str, Any], agent: str) -> list[str]:
    out = []
    for mid, meta in get_metrics_for_agent(rubric, agent).items():
        if meta.get("evaluator") == "code":
            out.append(mid)
    return out
