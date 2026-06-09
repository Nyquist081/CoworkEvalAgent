from __future__ import annotations
from typing import Optional


class CoworkEvalError(Exception):
    """Base exception for all CoworkEval errors."""
    pass


class IncompleteTraceError(CoworkEvalError):
    """Raised when JSONL trace is missing the final result record."""
    def __init__(self, message: str, question_id: Optional[str] = None):
        super().__init__(message)
        self.question_id = question_id


class TraceIntegrityError(CoworkEvalError):
    """Raised when trace events cannot be matched into a reliable execution chain."""
    def __init__(self, message: str, question_id: Optional[str] = None):
        super().__init__(message)
        self.question_id = question_id


class EvaluationError(CoworkEvalError):
    """Raised when an evaluation step fails unrecoverably."""
    def __init__(self, message: str, run_id: Optional[str] = None):
        super().__init__(message)
        self.run_id = run_id


class StateTransitionError(CoworkEvalError):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, from_status: str, to_status: str, reason: str):
        super().__init__(f"Cannot transition from {from_status} to {to_status}: {reason}")
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
