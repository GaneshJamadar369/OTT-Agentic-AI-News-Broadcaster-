"""Pipeline-level errors surfaced to CLI / Streamlit instead of silent bad outputs."""


class BroadcastRejectedError(RuntimeError):
    """Raised when evaluation fails after max retries or graph iteration cap."""

    def __init__(self, message: str, evaluation_snapshot: dict | None = None):
        super().__init__(message)
        self.evaluation_snapshot = evaluation_snapshot or {}
