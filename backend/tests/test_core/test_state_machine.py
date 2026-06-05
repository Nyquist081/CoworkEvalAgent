import pytest
from src.core.state_machine import StateMachine
from src.core.schemas import RunStatus
from src.core.exceptions import StateTransitionError


class TestStateMachine:
    def test_valid_transition_sequence(self):
        sm = StateMachine()
        transitions = [
            RunStatus.PARSING_TRACE,
            RunStatus.EVALUATING_BASELINE,
            RunStatus.AWAITING_JUDGE,
            RunStatus.EVALUATING_JUDGE,
            RunStatus.COMPLETED,
        ]
        for status in transitions:
            sm.transition_to(status)
        assert sm.current == RunStatus.COMPLETED

    def test_can_transition_to_failed_from_any_state(self):
        fail_states = [
            RunStatus.PENDING,
            RunStatus.PARSING_TRACE,
            RunStatus.EVALUATING_BASELINE,
            RunStatus.AWAITING_JUDGE,
            RunStatus.EVALUATING_JUDGE,
        ]
        for from_state in fail_states:
            sm = StateMachine()
            sm.current = from_state
            sm.validate_transition(from_state, RunStatus.FAILED)
            sm.transition_to(RunStatus.FAILED)
            assert sm.current == RunStatus.FAILED

    def test_invalid_jump_rejected(self):
        sm = StateMachine()
        with pytest.raises(StateTransitionError):
            sm.validate_transition(RunStatus.PENDING, RunStatus.COMPLETED)

    def test_failed_is_terminal(self):
        sm = StateMachine()
        sm.transition_to(RunStatus.FAILED)
        with pytest.raises(StateTransitionError):
            sm.validate_transition(RunStatus.FAILED, RunStatus.PENDING)

    def test_completed_is_terminal(self):
        sm = StateMachine()
        sm.current = RunStatus.COMPLETED
        with pytest.raises(StateTransitionError):
            sm.validate_transition(RunStatus.COMPLETED, RunStatus.PENDING)

    def test_skip_judge_path(self):
        sm = StateMachine(judge_enabled=False)
        sm.transition_to(RunStatus.PARSING_TRACE)
        sm.transition_to(RunStatus.EVALUATING_BASELINE)
        sm.validate_transition(RunStatus.EVALUATING_BASELINE, RunStatus.COMPLETED)
        sm.transition_to(RunStatus.COMPLETED)
        assert sm.current == RunStatus.COMPLETED
