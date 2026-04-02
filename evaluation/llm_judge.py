"""LLM-as-judge: Groq, temperature 0, JSON scores + evidence per metric."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from groq import Groq
from dotenv import load_dotenv
from llm_utils import llm_chat_create
from evaluation.load_rubric import get_metrics_for_agent, metric_ids_for_llm

load_dotenv()
_client: Groq | None = None


def _client_groq() -> Groq:
    global _client
    if _client is None:
        _groq_keys = os.getenv("GROQ_API_KEY", "").split(",")
        _client = Groq(api_key=_groq_keys[0].strip() if _groq_keys else None)
    return _client


def _judge_prompt(agent: str, metric_ids: List[str], rubric: Dict[str, Any], context: str) -> str:
    defs = get_metrics_for_agent(rubric, agent)
    lines = []
    for mid in metric_ids:
        m = defs.get(mid, {})
        lines.append(f"- {mid}: {m.get('name', mid)} (critical={m.get('critical')})")
    rubric_block = "\n".join(lines)
    journalist_calibration = ""
    if agent == "journalist":
        journalist_calibration = """
Calibration (journalist only):
- Score 4 means "acceptable for broadcast": minor wording issues are still 4 if facts and structure are sound.
- Reserve 1–2 for clear fabrication, missing blocks, or unsafe content.
- For balance_neutrality: attributing official statements or quoted claims (e.g., "Trump said...", "Iranian state TV reported...") is correct wire-style reporting, not bias. Penalize only unattributed assertions, one-sided omission of attributed counterclaims present in the source, or loaded editorial language.
- For source_faithfulness: reward close paraphrase that preserves numbers/names; penalize only clear drift or invention.

"""
    return f"""You are an expert TV newsroom QA judge. Score each metric from 1 (poor) to 5 (excellent).
For any score below 5, you MUST provide a surgical fix suggestion.
{journalist_calibration}
Return ONLY valid JSON: an object mapping each metric_id to:
{{
  "score": <int 1-5>,
  "evidence": "<reason for score without including any 'FIX:' prefix or repair instructions>",
  "fix": "<one surgical actionable instruction to repair the defect found in the evidence above>",
  "owner": "<the agent most responsible (editor, visualizer, tagger, or system)>"
}}

Metrics to score:
{rubric_block}

Context (article, outputs, state):
{context[:28000]}

JSON object keys must be exactly: {json.dumps(metric_ids)}
"""


def run_llm_metrics(
    agent: str,
    rubric: Dict[str, Any],
    context: str,
    model: str = "llama-3.1-8b-instant",
) -> Dict[str, Dict[str, Any]]:
    ids = metric_ids_for_llm(rubric, agent)
    if not ids:
        return {}
    prompt = _judge_prompt(agent, ids, rubric, context)
    resp = llm_chat_create(
        _client_groq(),
        model=model,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    data = json.loads(raw)
    out: Dict[str, Dict[str, Any]] = {}
    defs = get_metrics_for_agent(rubric, agent)
    for mid in ids:
        cell = data.get(mid)
        default_owner = defs.get(mid, {}).get("owner", agent)
        if isinstance(cell, dict):
            sc = int(cell.get("score", 3))
            sc = max(1, min(5, sc))
            out[mid] = {
                "score": sc,
                "evidence": str(cell.get("evidence", ""))[:500],
                "fix": str(cell.get("fix", ""))[:500],
                "owner": str(cell.get("owner", default_owner)).lower() or default_owner,
            }
        else:
            out[mid] = {
                "score": 3,
                "evidence": "Judge returned malformed cell",
                "fix": "Retry evaluation",
                "owner": default_owner,
            }
    return out


def build_journalist_context(state: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "url": state.get("url"),
            "raw_article_excerpt": (state.get("raw_article_text") or "")[:12000],
            "journalist_output": (state.get("article_text") or "")[:12000],
        },
        ensure_ascii=False,
    )


def build_editor_context(state: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "journalist_article_text": (state.get("article_text") or "")[:10000],
            "narration_script": (state.get("narration_script") or "")[:8000],
        },
        ensure_ascii=False,
    )


def build_visualizer_context(state: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "narration_script": (state.get("narration_script") or "")[:6000],
            "source_images": state.get("source_images") or [],
            "video_duration_sec": state.get("video_duration_sec"),
            "segments": state.get("segments") or [],
        },
        ensure_ascii=False,
    )


def build_tagger_context(state: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "narration_script": (state.get("narration_script") or "")[:6000],
            "segment_tags": state.get("segment_tags") or [],
        },
        ensure_ascii=False,
    )


def build_cross_context(state: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "article_title": state.get("article_title"),
            "narration_script": (state.get("narration_script") or "")[:6000],
            "video_duration_sec": state.get("video_duration_sec"),
            "segments": state.get("segments") or [],
            "segment_tags": state.get("segment_tags") or [],
        },
        ensure_ascii=False,
    )
