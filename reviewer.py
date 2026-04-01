"""
Legacy module: monolithic reviewer replaced by evaluation.pipeline.evaluate_package_step
and per-agent rubrics in config/evaluation_rubric.yaml. Kept for import compatibility.
"""


def reviewer_agent(state):
    raise RuntimeError(
        "reviewer_agent is deprecated; the graph uses evaluate_package in main.py"
    )
