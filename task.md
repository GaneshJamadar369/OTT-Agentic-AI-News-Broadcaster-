# Task: News Pipeline Retry Refactor (Industrial-Grade)

The objective is to implement surgical, metric-level retry routing, capture structured repair signals (fix/owner) from the LLM judge, and ensure feedback is precisely distributed to the responsible agents.

- [x] Researched `aggregate.py`, `llm_judge.py`, and `rubric.yaml`
- [x] Defined structured Failure Object schema (`fix`, `owner`)
- [x] Implemented logic to inject `owner` metadata from rubric
- [x] Updated `llm_judge.py` prompt for surgical repair packets
- [x] Refactored `aggregate.py` for metric-aware routing (Editor-First priority)
- [x] Integrated surgical feedback distribution in `pipeline.py`
- [x] Updated `main.py` to handle `abort` (system) vs `retry` (content)
- [x] Verified overall average includes `cross_package` scores
- [x] Validated Journalist length control alignment