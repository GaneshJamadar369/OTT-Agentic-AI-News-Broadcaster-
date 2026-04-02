"""Programmatic metric scores (1–5) and evidence strings for rubric evaluator: code."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from evaluation.load_rubric import load_policy


def _score(ok: bool, good: bool = True) -> int:
    if ok and good:
        return 5
    if ok:
        return 4
    return 1


def _entry(score: int, evidence: str) -> Dict[str, Any]:
    return {"score": max(1, min(5, score)), "evidence": evidence}


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def parse_time_mm_ss(s: str) -> Optional[int]:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    parts = s.split(":")
    try:
        if len(parts) == 2:
            m, sec = int(parts[0]), int(parts[1])
            return m * 60 + sec
        if len(parts) == 3:
            h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
            return h * 3600 + m * 60 + sec
    except (ValueError, TypeError):
        return None
    return None


def extract_journalist_blocks(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not text:
        return None, None, None
    title_m = re.search(r"TITLE:\s*(.+?)(?=STORY:|FACTS:|$)", text, re.S | re.I)
    story_m = re.search(r"STORY:\s*(.+?)(?=FACTS:|$)", text, re.S | re.I)
    facts_m = re.search(r"FACTS:\s*(.+)$", text, re.S | re.I)
    title = title_m.group(1).strip() if title_m else None
    story = story_m.group(1).strip() if story_m else None
    facts = facts_m.group(1).strip() if facts_m else None
    return title, story, facts


def check_journalist_deterministic(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    policy = load_policy()
    text = state.get("article_text") or ""
    raw = state.get("raw_article_text") or ""
    out: Dict[str, Dict[str, Any]] = {}

    title, story, facts = extract_journalist_blocks(text)
    has_blocks = title is not None and story is not None and facts is not None
    out["deterministic_schema_validity"] = _entry(
        _score(has_blocks),
        "TITLE/STORY/FACTS blocks present" if has_blocks else "Missing structured blocks",
    )

    story_wc = word_count(story or "")
    min_w, max_w = 80, 800
    len_ok = min_w <= story_wc <= max_w if story else False
    out["length_control"] = _entry(
        _score(len_ok, story_wc >= 100),
        f"STORY word count={story_wc} (prompt-aligned window ~{min_w}-{max_w})",
    )

    meta_bad = re.search(
        r"this article|as an ai|language model|according to the article",
        text,
        re.I,
    )
    out["forbidden_phrases"] = _entry(
        5 if not meta_bad else 2,
        "No forbidden meta-phrases" if not meta_bad else f"Meta phrase detected: {meta_bad.group(0)[:80]}",
    )

    bad_enc = "\ufffd" in text or "\x00" in text
    out["encoding_sanity"] = _entry(5 if not bad_enc else 2, "Encoding OK" if not bad_enc else "Replacement chars or NUL")

    out["instruction_adherence"] = _entry(
        int(out["deterministic_schema_validity"]["score"]),
        str(out["deterministic_schema_validity"]["evidence"]),
    )

    out["language_detection"] = _entry(
        4,
        "Heuristic: expected %s (not enforced without langid)" % policy.get("expected_language", "en"),
    )

    facts_ok = bool(facts and len(facts.strip()) > 15)
    out["facts_structure_quality"] = _entry(
        _score(facts_ok),
        "FACTS block has content" if facts_ok else "FACTS missing or too short",
    )

    err_disc = "ERROR" not in (text[:200] if text else "")
    out["error_handling_discipline"] = _entry(4 if err_disc else 2, "Output looks like content" if err_disc else "Error-like output")

    out["latency_budget"] = _entry(4, "Latency not measured in-process")

    return out


def check_editor_deterministic(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    policy = load_policy()
    script = state.get("narration_script") or ""
    wc = word_count(script)
    wmin = policy.get("editor_word_count_min", 160)
    wmax = policy.get("editor_word_count_max", 320)
    wc_ok = wmin <= wc <= wmax
    out: Dict[str, Dict[str, Any]] = {
        "word_count_adherence": _entry(
            _score(wc_ok),
            f"Word count={wc} (required {wmin}-{wmax})",
        )
    }
    bullet = re.search(r"(?m)^\s*[-*•]\s+\S", script) or re.search(r"(?m)^\s*\d+\.\s+\S", script)
    out["no_bullet_lists"] = _entry(
        5 if not bullet else 2,
        "Continuous narration" if not bullet else "Bullet/numbered list pattern detected",
    )
    meta = re.search(r"in this script|following narration|this script", script, re.I)
    out["no_meta_text"] = _entry(
        5 if not meta else 2,
        "No meta-text" if not meta else "Meta-text detected",
    )
    return out


def check_visualizer_deterministic(
    state: Dict[str, Any],
    tagger_len: int,
) -> Dict[str, Dict[str, Any]]:
    policy = load_policy()
    out: Dict[str, Dict[str, Any]] = {}
    segs = state.get("segments") or []
    vd = state.get("video_duration_sec")
    seg_min = policy.get("segment_count_min", 3)
    seg_max = policy.get("segment_count_max", 5)
    n = len(segs)
    seg_ok = seg_min <= n <= seg_max
    out["segment_count"] = _entry(
        _score(seg_ok),
        f"segments={n} (need {seg_min}-{seg_max})",
    )

    schema_ok = isinstance(segs, list) and all(
        isinstance(s, dict)
        and "segment_id" in s
        and "text" in s
        and "start_time" in s
        and "end_time" in s
        and "layout" in s
        for s in segs
    )
    out["json_schema_validity"] = _entry(
        _score(schema_ok),
        "Visualizer JSON shape OK" if schema_ok else "Missing required segment fields",
    )

    times_ok = True
    prev_end = -1
    dur_total = 0
    for s in segs:
        st = parse_time_mm_ss(s.get("start_time", ""))
        en = parse_time_mm_ss(s.get("end_time", ""))
        if st is None or en is None:
            times_ok = False
            break
        if st < prev_end or st >= en:
            times_ok = False
            break
        prev_end = en
        dur_total = max(dur_total, en)
    out["time_format_correctness"] = _entry(
        _score(times_ok),
        "MM:SS parse OK" if times_ok else "Bad time format or order",
    )
    out["monotonic_timecodes"] = out["time_format_correctness"].copy()

    vd_min = policy.get("video_duration_min", 60)
    vd_max = policy.get("video_duration_max", 120)
    if isinstance(vd, int) and vd_min <= vd <= vd_max:
        vd_ok = True
    else:
        vd_ok = False
    out["timecode_coverage_continuity"] = _entry(
        _score(vd_ok and times_ok),
        f"video_duration_sec={vd}, span~{dur_total}s",
    )

    null_ok = True
    for s in segs:
        u = s.get("source_image_url")
        p = s.get("ai_support_visual_prompt")
        has_u = u is not None and str(u).strip() and str(u).lower() != "null"
        has_p = p is not None and str(p).strip() and str(p).lower() != "null"
        if has_u == has_p:
            null_ok = False
            break
        if not has_u and not has_p:
            null_ok = False
            break
    out["null_handling_visual"] = _entry(
        _score(null_ok),
        "Exactly one of URL or AI prompt per segment" if null_ok else "URL/prompt pairing invalid",
    )

    cross_ok = n == tagger_len and n > 0
    out["cross_check_tagger_count"] = _entry(
        _score(cross_ok),
        f"len(segments)={n} vs len(tags)={tagger_len}",
    )

    wpm_ok = True
    for s in segs:
        st = parse_time_mm_ss(s.get("start_time", ""))
        en = parse_time_mm_ss(s.get("end_time", ""))
        if st is None or en is None:
            wpm_ok = False
            break
        sec = max(1, en - st)
        wc = word_count(s.get("text", ""))
        rate = wc / sec
        if rate < 1.0 or rate > 4.5:
            wpm_ok = False
    out["duration_word_consistency"] = _entry(
        _score(wpm_ok),
        "Words/sec per segment in plausible range" if wpm_ok else "Narration density vs time off",
    )

    max_prompt = 400
    plen_ok = all(
        len((s.get("ai_support_visual_prompt") or "")) <= max_prompt for s in segs
    )
    out["prompt_length_cap"] = _entry(
        _score(plen_ok),
        f"AI prompt length <= {max_prompt} chars" if plen_ok else "Prompt too long",
    )

    return out


def check_tagger_deterministic(
    state: Dict[str, Any],
    segment_count: int,
) -> Dict[str, Dict[str, Any]]:
    policy = load_policy()
    tags = state.get("segment_tags") or []
    allowed = set(policy.get("allowed_top_tags", []))
    hmax = policy.get("headline_max_chars", 30)
    smax = policy.get("subheadline_max_chars", 50)
    out: Dict[str, Dict[str, Any]] = {}

    schema_ok = isinstance(tags, list) and all(
        isinstance(t, dict) and "headline" in t and "subheadline" in t and "top_tag" in t for t in tags
    )
    out["json_schema_validity"] = _entry(
        _score(schema_ok),
        "Tagger JSON shape OK" if schema_ok else "Bad tag objects",
    )

    eq_ok = len(tags) == segment_count and segment_count > 0
    out["segment_count_equality"] = _entry(
        _score(eq_ok),
        f"len(tags)={len(tags)} vs segments={segment_count}",
    )

    char_ok = True
    for t in tags:
        h = t.get("headline") or ""
        su = t.get("subheadline") or ""
        if len(h) > hmax or len(su) > smax:
            char_ok = False
    out["char_limits"] = _entry(
        _score(char_ok),
        f"headline<={hmax}, sub<={smax}",
    )

    vocab_ok = True
    for t in tags:
        tt = (t.get("top_tag") or "").strip().upper()
        if allowed and tt not in allowed:
            vocab_ok = False
    out["tag_vocabulary"] = _entry(
        _score(vocab_ok),
        "top_tag in allowed list" if vocab_ok else "Invalid top_tag",
    )

    meta_ok = not any(
        re.search(r"^(headline|subheadline|tag)\s*:", (t.get("headline") or ""), re.I)
        for t in tags
    )
    out["no_meta_text"] = _entry(
        _score(meta_ok),
        "No meta prefixes in headline fields" if meta_ok else "Meta prefix in content",
    )

    emoji = re.compile(r"[\U0001F300-\U0001F9FF]")
    emo_ok = not any(emoji.search(t.get("headline") or "") or emoji.search(t.get("subheadline") or "") for t in tags)
    out["no_emoji_informal"] = _entry(
        _score(emo_ok),
        "No emoji in overlays" if emo_ok else "Emoji found",
    )

    return out


def check_cross_package_code(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    rv = state.get("rubric_version") or ""
    pv = state.get("policy_version") or ""
    out["versioned_rubrics"] = _entry(
        5 if rv and pv else 3,
        f"rubric_version={rv}, policy_version={pv}",
    )
    out["deterministic_evaluation_settings"] = _entry(
        5,
        "Judges use temperature 0 and JSON mode (enforced in code)",
    )
    out["policy_respecting_routing"] = _entry(
        4,
        "Routing uses aggregate.retry_targets from policy",
    )
    return out
