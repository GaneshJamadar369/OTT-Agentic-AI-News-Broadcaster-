# LOQO News OTT — Strict multi-agent evaluation (project report)

## Purpose

This document summarizes the **rubric-driven evaluation and retry** layer added to the LOQO broadcast screenplay pipeline. The full research-backed metric definitions and design rationale live in **`docs/STRICT_EVALUATION_SPEC.md`** (canonical copy of the long-form evaluation design).

**Repository URL (placeholder):** `https://github.com/YOUR_ORG/loqo-news-ott` — replace when the remote is published.

---

## Methodology

1. **Config-first:** `config/evaluation_rubric.yaml` lists per-agent metrics (`domain` vs `prompting`), weights, `critical` flags, `min_score`, and `evaluator` (`code` or `llm`). `config/evaluation_policy.yaml` holds global thresholds, retry budgets, and structural limits (word counts, segment counts, tag vocabulary).
2. **Deterministic before LLM:** Programmatic checks run first (JSON shape, timecodes, word counts, alignment). Parallel packaging must pass **`validate_parallel`** before **`evaluate_package`** runs expensive judges.
3. **LLM judges:** Groq (`llama-3.3-70b-versatile`), **temperature 0**, **`response_format: json_object`**, one JSON object per agent with `{metric_id: {score, evidence}}`.
4. **Aggregation:** `evaluation/aggregate.py` merges code + LLM scores per rubric, computes weighted averages, applies **critical floor** (default 4 on critical metrics) and **per-agent** / **cross-package** thresholds.
5. **Routing:** Retry targets come from **`package_route_hint`** (`retry_editor` vs `retry_visuals`) derived from which agent bundles failed—not from parsing natural-language `failure_type`. Parallel validation failures set shared feedback for **visualizer** and **tagger**.
6. **Trace:** `evaluation_trace` records rounds (`evaluate_journalist`, `evaluate_package`) with deltas between weighted averages for audit.

---

## Policy table (hard rules)

| Rule | Value |
|------|--------|
| Critical metric fail | Any **critical** metric with score below **4** (see `critical_score_floor`) fails that agent bundle |
| Non-critical floor | `min_score_per_metric` (default 3), per-metric `min_score` in rubric |
| Per-agent pass | Weighted average at or above **`overall_pass_threshold_per_agent`** (default **4.3**) |
| Cross-package pass | Weighted average at or above **`overall_pass_threshold_cross_package`** (default **4.5**) |
| Graph rounds | `max_graph_iterations` (**3**); package step may still finalize on last round when iterations cap |
| Retries | `agent_max_retries` per role in YAML (e.g. journalist/editor/visualizer/tagger **2**) |

---

## Metric appendix

Metrics are generated into **`config/evaluation_rubric.yaml`** by **`gen_rubric.py`** (do not hand-edit the YAML; regenerate). Approximate counts per bundle:

| Agent | Metrics |
|-------|---------|
| journalist | ~22 |
| editor | ~22 |
| visualizer | ~23 |
| tagger | ~22 |
| cross_package | ~15 |

For human-readable names, groups, and evaluator types, open the YAML or run:

`python gen_rubric.py`

---

## Artifacts

| File | Contents |
|------|----------|
| `final_broadcast_plan.json` | Segments plus `evaluation_results`, `evaluation_trace`, versions |
| `evaluation_report.json` | Trace plus evaluation results plus `review_scores` snapshot |

---

## Limitations

- Judge variance remains possible even at temperature 0; deterministic gates reduce but do not eliminate it.
- Strict thresholds (4.3 / 4.5) will often yield **FAIL** until retries; final outputs may still be produced when the graph hits iteration or retry limits (see `main.py` routing).
- Legacy **`reviewer.py`** is deprecated; orchestration uses **`evaluation/`** only.

---

## References

- `docs/STRICT_EVALUATION_SPEC.md` — full spec
- `config/evaluation_policy.yaml`, `config/evaluation_rubric.yaml`
- `task.md` — original product constraints
