from typing import TypedDict, List, Annotated, Dict, Any
import operator


class AgentState(TypedDict, total=False):
    url: str

    article_title: str
    article_text: str
    raw_article_text: str
    source_images: List[str]

    narration_script: str

    segments: List[dict]
    segment_tags: List[dict]
    video_duration_sec: int

    review_scores: dict
    review_feedback: str

    iterations: Annotated[int, operator.add]
    current_agent: str

    journalist_runs: int
    editor_runs: int
    packaging_runs: int

    evaluation_trace: List[Dict[str, Any]]
    evaluation_results: Dict[str, Any]
    last_feedback_by_agent: Dict[str, str]

    rubric_version: str
    policy_version: str

    parallel_validation_ok: bool
    parallel_validation_errors: List[str]

    package_evaluation_ok: bool
    package_route_hint: str

    rejection_reason: str
