# Implementation journey (0–100%)

This document describes how the LOQO pipeline evolved and how the pieces fit together. It is aligned with the **current codebase**, not with aspirational marketing claims.

---

## Phase 0–25%: Single-purpose flow

**Goal:** From one URL, produce usable article text and a readable story.

**Approach:** Early experiments often chained one LLM step after another or scraped naively. Problems: noisy HTML inflated tokens, failed pages still produced “stories,” and runtime stacked serially.

**Where it landed:** `scraper_utils.py` centralizes fetch and extract (requests → trafilatura → Playwright if needed → newspaper3k). `journalist.py` runs an LLM pass to normalize title/story/facts and applies **guardrails** so obviously bad or tiny inputs become `ERROR: INVALID_CONTENT` instead of a fake newscast.

---

## Phase 25–50%: Editor and structured segments

**Goal:** A single **anchor narration** (about one to two minutes spoken) instead of a flat summary.

**Approach:** `editor.py` constrains length and broadcast tone in the prompt. Segmentation and visuals were split out so the editor does not need to output final JSON for every field.

**Where it landed:** `narration_script` in state feeds downstream agents only after a successful journalist step.

---

## Phase 50–75%: Parallel visual packaging

**Requirement (see `task.md`):** At least one **parallel** stage after scripting.

**Approach:** Two nodes consume the same narration:

- **`visualizer.py`** – JSON with `segments` (ids, times, layout, `text`, image URL or AI prompt, `video_duration_sec`).
- **`tagger.py`** – JSON `segment_tags` (headline, subheadline, top_tag per segment).

They run in parallel after a shared **fork** node (`visual_packaging_fork` in `main.py`) so both **initial runs** and **visual retries** schedule **both** branches. Without that fork, routing a retry only to `visualizer` would leave tags from an older pass attached to new segments.

**Where it landed:** `main.py` wires `editor → visual_packaging_fork → (visualizer | tagger) → reviewer`.

---

## Phase 75–100%: Reviewer, targeted retries, merge

**Goal:** Do not accept the first draft blindly; cap retries (e.g. three).

**Approach:** `reviewer.py` returns structured JSON: scores, `overall_average`, `status`, `failure_type`, `feedback`. On **FAIL**, state increments `iterations` via the reducer-friendly update in the reviewer return value.

**Router logic (`should_continue`):**

- **PASS** → `final_assembler` → END.
- **FAIL** and `iterations >= 3` → finalize with the latest package (no more loops).
- **`failure_type`** `visualizer` or `tagger` → retry **visual packaging fork** (both agents).
- Else → **retry editor** (script only).

**Merge:** `final_assembler` zips `segment_tags[i]` into `segments[i]` so one list is written to JSON and printed on the CLI.

**Observability:** Langfuse `CallbackHandler` is attached at invoke time for traceability when keys are set.

---

## Design choices (concise)

| Topic | Decision |
|--------|-----------|
| State typing | `TypedDict` + `Annotated[int, operator.add]` for `iterations` |
| Segment shape | `List[dict]` in state; strict runtime schema enforced by LLM JSON modes and downstream consumers |
| Scraper vs LLM | Scraper supplies ground text; LLM in journalist refines but can be cut for stricter grounding if needed |
| Retry scope | Editor-only vs full visual branch, driven by reviewer `failure_type` |

---

## Graph summary

1. **journalist** → optional **END** on invalid content.  
2. **editor** → **visual_packaging_fork** → **visualizer** ∥ **tagger**.  
3. **reviewer** → **finalize** | **retry_editor** | **retry_visuals** (back to fork).  
4. **final_assembler** → **END**.

This matches the Mermaid diagram in `README.md`.
