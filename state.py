from typing import TypedDict, List, Annotated
import operator

class AgentState(TypedDict):
    url: str

    article_title: str
    article_text: str
    source_images: List[str]

    narration_script: str

    segments: List[dict]
    segment_tags: List[dict]

    review_scores: dict
    review_feedback: str

    iterations: Annotated[int, operator.add]
    current_agent: str