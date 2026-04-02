"""One-off generator for config/evaluation_rubric.yaml — run if rubric structure changes."""
import yaml

RUBRIC_VERSION = "1.0.0"

# (metric_id, name, group, weight, critical, min_score, evaluator)
JOURNALIST = [
    ("source_faithfulness", "Source faithfulness vs scrape", "domain", 2.5, True, 4, "llm"),
    ("key_fact_coverage", "Key fact coverage (5W+H)", "domain", 2.5, True, 4, "llm"),
    ("lead_clarity", "Lead clarity", "domain", 1.5, False, 3, "llm"),
    ("context_background", "Context and background", "domain", 1.5, False, 3, "llm"),
    ("balance_neutrality", "Balance and neutrality", "domain", 1.5, False, 3, "llm"),
    ("temporal_accuracy", "Temporal accuracy", "domain", 1.5, False, 3, "llm"),
    ("numerical_fidelity", "Numerical fidelity", "domain", 2.0, True, 4, "llm"),
    ("named_entity_accuracy", "Named entity accuracy", "domain", 2.0, True, 4, "llm"),
    ("quote_integrity", "Quote integrity", "domain", 1.5, False, 3, "llm"),
    ("story_completeness", "Story completeness", "domain", 1.5, False, 3, "llm"),
    ("redundancy_control", "Redundancy control", "domain", 1.0, False, 3, "llm"),
    ("grammar_quality", "Language and grammar quality", "domain", 1.5, False, 3, "llm"),
    ("instruction_adherence", "TITLE/STORY/FACTS structure", "prompting", 2.0, True, 4, "code"),
    ("length_control", "STORY length window", "prompting", 1.5, False, 3, "code"),
    ("facts_structure_quality", "FACTS list structure", "prompting", 1.5, False, 3, "llm"),
    ("forbidden_phrases", "No meta-phrasing", "prompting", 2.0, True, 4, "code"),
    ("encoding_sanity", "Encoding sanity", "prompting", 1.0, False, 3, "code"),
    ("safety_compliance", "Safety and compliance", "prompting", 1.5, False, 3, "llm"),
    ("deterministic_schema_validity", "Schema blocks present", "prompting", 2.5, True, 4, "code"),
    ("language_detection", "Language matches policy", "prompting", 1.0, False, 3, "code"),
    ("error_handling_discipline", "Error handling discipline", "prompting", 1.5, False, 3, "llm"),
    ("latency_budget", "Token/latency discipline", "prompting", 0.5, False, 3, "llm"),
]

EDITOR = [
    ("hook_strength", "Hook strength", "domain", 2.5, True, 4, "llm"),
    ("story_structure", "Story structure", "domain", 2.5, True, 4, "llm"),
    ("beat_clarity", "Beat clarity", "domain", 2.0, False, 3, "llm"),
    ("factual_consistency_with_journalist", "Factual consistency vs journalist", "domain", 3.0, True, 4, "llm"),
    ("tone_appropriateness", "Tone appropriateness", "domain", 1.5, False, 3, "llm"),
    ("pacing_suitability", "Pacing suitability", "domain", 1.5, False, 3, "llm"),
    ("clarity_simplicity", "Clarity and simplicity", "domain", 1.5, False, 3, "llm"),
    ("avoid_sensationalism", "Avoid sensationalism", "domain", 1.5, False, 3, "llm"),
    ("audience_orientation", "Audience orientation", "domain", 1.0, False, 3, "llm"),
    ("redundancy_repetition", "Redundancy control", "domain", 1.0, False, 3, "llm"),
    ("transition_smoothness", "Transition smoothness", "domain", 1.0, False, 3, "llm"),
    ("pronunciation_friendliness", "Pronunciation friendliness", "domain", 1.0, False, 3, "llm"),
    ("word_count_adherence", "Word count 160–320", "prompting", 3.0, True, 4, "code"),
    ("no_bullet_lists", "No bullet/numbered lists", "prompting", 2.0, True, 4, "code"),
    ("section_presence", "Recognizable beats/paragraphs", "prompting", 1.0, False, 3, "llm"),
    ("instruction_adherence", "Instruction adherence", "prompting", 1.5, False, 3, "llm"),
    ("no_meta_text", "No meta-text", "prompting", 2.0, True, 4, "code"),
    ("profanity_safety", "Profanity / safety", "prompting", 1.5, False, 3, "llm"),
    ("format_stability_retries", "Format stability on retry", "prompting", 1.0, False, 3, "llm"),
    ("language_style_match", "Language style match", "prompting", 1.0, False, 3, "llm"),
    ("token_budget_adherence", "Token budget", "prompting", 0.5, False, 3, "llm"),
    ("prompt_responsiveness", "Responsiveness to feedback", "prompting", 1.5, False, 3, "llm"),
]

VISUALIZER = [
    ("segment_count", "Segment count 3–5", "domain", 2.0, True, 4, "code"),
    ("beat_alignment", "Beat alignment", "domain", 2.5, True, 4, "llm"),
    ("timecode_coverage_continuity", "Timecode coverage", "domain", 2.5, True, 4, "code"),
    ("layout_variety_purpose", "Layout variety with purpose", "domain", 1.5, False, 3, "llm"),
    ("visual_story_match", "Visual-story match", "domain", 2.5, True, 4, "llm"),
    ("use_of_source_images", "Use of source images", "domain", 1.5, False, 3, "llm"),
    ("emotional_tone_alignment", "Emotional tone alignment", "domain", 1.5, False, 3, "llm"),
    ("avoid_misleading_visuals", "Avoid misleading visuals", "domain", 1.5, False, 3, "llm"),
    ("transition_logic", "Transition logic", "domain", 1.0, False, 3, "llm"),
    ("chyron_readability", "Chyron readability", "domain", 1.0, False, 3, "llm"),
    ("shot_diversity", "Shot diversity", "domain", 1.0, False, 3, "llm"),
    ("crisis_treatment", "Crisis sensitivity", "domain", 1.5, False, 3, "llm"),
    ("localization_appropriateness", "Localization", "domain", 1.0, False, 3, "llm"),
    ("json_schema_validity", "JSON schema validity", "prompting", 3.0, True, 4, "code"),
    ("time_format_correctness", "Time format MM:SS", "prompting", 2.0, True, 4, "code"),
    ("monotonic_timecodes", "Monotonic non-overlapping times", "prompting", 2.5, True, 4, "code"),
    ("duration_word_consistency", "Duration vs word rate", "prompting", 1.5, False, 3, "code"),
    ("null_handling_visual", "Exactly one of URL or AI prompt", "prompting", 2.0, True, 4, "code"),
    ("prompt_completeness", "AI prompt completeness", "prompting", 1.5, False, 3, "llm"),
    ("cross_check_tagger_count", "Segment count vs tagger", "prompting", 2.5, True, 4, "code"),
    ("no_meta_in_prompts", "No meta instructions in prompts", "prompting", 1.5, False, 3, "llm"),
    ("visual_safety_filter", "Visual safety", "prompting", 1.5, False, 3, "llm"),
    ("prompt_length_cap", "Prompt length cap", "prompting", 1.0, False, 3, "code"),
]

TAGGER = [
    ("segment_alignment", "Segment alignment", "domain", 2.5, True, 4, "llm"),
    ("headline_punch", "Headline punch", "domain", 2.0, True, 4, "llm"),
    ("subheadline_clarity", "Subheadline clarity", "domain", 1.5, False, 3, "llm"),
    ("tag_appropriateness", "Tag appropriateness", "domain", 2.0, True, 4, "llm"),
    ("avoid_clickbait", "Avoid clickbait", "domain", 1.5, False, 3, "llm"),
    ("consistency_with_narration", "Consistency with narration", "domain", 2.0, True, 4, "llm"),
    ("style_guide_adherence", "Style guide adherence", "domain", 1.0, False, 3, "llm"),
    ("diversity_across_segments", "Diversity across segments", "domain", 1.0, False, 3, "llm"),
    ("localization_wording", "Localization wording", "domain", 1.0, False, 3, "llm"),
    ("sensitivity_tragedies", "Sensitivity for tragedies", "domain", 1.5, False, 3, "llm"),
    ("screen_fit", "Screen-fit", "domain", 1.0, False, 3, "llm"),
    ("redundancy_control_subheadline", "Subheadline adds value", "domain", 1.0, False, 3, "llm"),
    ("json_schema_validity", "JSON schema validity", "prompting", 2.5, True, 4, "code"),
    ("char_limits", "Char limits", "prompting", 2.5, True, 4, "code"),
    ("tag_vocabulary", "Tag vocabulary", "prompting", 2.0, True, 4, "code"),
    ("no_meta_text", "No meta labels in strings", "prompting", 1.5, False, 3, "code"),
    ("safe_language", "Safe language", "prompting", 1.5, False, 3, "llm"),
    ("response_format_stability", "JSON stability", "prompting", 1.0, False, 3, "llm"),
    ("segment_count_equality", "len(tags)==len(segments)", "prompting", 3.0, True, 4, "code"),
    ("prompt_responsiveness", "Responsiveness to feedback", "prompting", 1.0, False, 3, "llm"),
    ("language_correctness", "Spelling/grammar", "prompting", 1.0, False, 3, "llm"),
    ("no_emoji_informal", "No emoji/informal markers", "prompting", 1.5, False, 3, "code"),
]

CROSS = [
    ("global_story_coherence", "Global story coherence", "domain", 2.5, True, 4, "llm"),
    ("temporal_alignment", "Temporal alignment", "domain", 1.5, False, 3, "llm"),
    ("narration_visual_rhythm", "Narration-visual rhythm", "domain", 1.5, False, 3, "llm"),
    ("duration_fit", "Duration fit", "domain", 2.0, True, 4, "llm"),
    ("coverage_completeness", "Coverage completeness", "domain", 2.0, True, 4, "llm"),
    ("redundancy_across_modalities", "Redundancy across modalities", "domain", 1.0, False, 3, "llm"),
    ("overall_engagement", "Overall engagement", "domain", 1.5, False, 3, "llm"),
    ("ethics_safety", "Ethics and safety", "domain", 2.0, True, 4, "llm"),
    ("no_schema_drift_retries", "Schema stability across retries", "prompting", 1.0, False, 3, "llm"),
    ("traceability_reproducibility", "Traceability", "prompting", 1.0, False, 3, "llm"),
    ("deterministic_evaluation_settings", "Judge settings (temp0, JSON)", "prompting", 1.5, False, 3, "code"),
    ("policy_respecting_routing", "Policy-respecting routing", "prompting", 1.5, False, 3, "code"),
    ("cost_latency_budget", "Cost/latency budget", "prompting", 0.5, False, 3, "llm"),
    ("fallback_graceful_failure", "Graceful failure after max retries", "prompting", 1.0, False, 3, "llm"),
    ("versioned_rubrics", "Rubric/policy version recorded", "prompting", 1.0, False, 3, "code"),
]


def build_agent_block(rows):
    d = {}
    for mid, name, group, weight, critical, min_score, ev in rows:
        d[mid] = {
            "name": name,
            "group": group,
            "weight": weight,
            "critical": critical,
            "min_score": min_score,
            "evaluator": ev,
        }
    return d


def main():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    out = {
        "version": RUBRIC_VERSION,
        "agents": {
            "journalist": build_agent_block(JOURNALIST),
            "editor": build_agent_block(EDITOR),
            "visualizer": build_agent_block(VISUALIZER),
            "tagger": build_agent_block(TAGGER),
            "cross_package": build_agent_block(CROSS),
        },
    }
    path = root / "config" / "evaluation_rubric.yaml"
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Auto-generated by scripts/generate_evaluation_rubric.py\n")
        yaml.dump(out, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print("Wrote", path)


if __name__ == "__main__":
    main()
