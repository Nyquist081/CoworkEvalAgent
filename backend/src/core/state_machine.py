from __future__ import annotations
from src.core.schemas import RunStatus
from src.core.exceptions import StateTransitionError


_VALID_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.PENDING: {RunStatus.PARSING_TRACE, RunStatus.FAILED},
    RunStatus.PARSING_TRACE: {RunStatus.EVALUATING_BASELINE, RunStatus.FAILED},
    RunStatus.EVALUATING_BASELINE: {RunStatus.AWAITING_JUDGE, RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.AWAITING_JUDGE: {RunStatus.EVALUATING_JUDGE, RunStatus.FAILED},
    RunStatus.EVALUATING_JUDGE: {RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
}

_VALID_TRANSITIONS_NO_JUDGE = dict(_VALID_TRANSITIONS)
_VALID_TRANSITIONS_NO_JUDGE[RunStatus.EVALUATING_BASELINE] = {RunStatus.COMPLETED, RunStatus.FAILED}


class StateMachine:
    def __init__(self, current: RunStatus = RunStatus.PENDING, judge_enabled: bool = True):
        self.current = current
        self.judge_enabled = judge_enabled
        self._transitions = _VALID_TRANSITIONS if judge_enabled else _VALID_TRANSITIONS_NO_JUDGE

    def validate_transition(self, from_status: RunStatus, to_status: RunStatus) -> None:
        allowed = self._transitions.get(from_status, set())
        if to_status not in allowed:
            raise StateTransitionError(
                from_status=from_status.value,
                to_status=to_status.value,
                reason=f"Allowed next states from {from_status.value}: {[s.value for s in allowed]}"
            )

    def transition_to(self, to_status: RunStatus) -> None:
        self.validate_transition(self.current, to_status)
        self.current = to_status
