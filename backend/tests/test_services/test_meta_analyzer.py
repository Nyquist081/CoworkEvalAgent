import pytest
from uuid import uuid4
from src.services.meta_analyzer import MetaAnalyzer
from src.core.schemas import ScoreResult, JudgeResult


class TestPassRates:
    def test_pass_at_k_at_least_one(self):
        analyzer = MetaAnalyzer(pass_threshold=60)
        scores = {
            "q-001": [
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=80),
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=30),
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=50),
            ],
            "q-002": [
                ScoreResult(run_id=uuid4(), question_id="q-002", t1_completion=20),
            ],
        }
        result = analyzer.compute_pass_rates(scores, k=3)

        # q-001: at least 1 pass among 3 → pass@3 ✓
        # q-002: only 1 execution at 0.2 → pass@3 ✗
        assert result["pass_at_k"] == 1
        assert result["pass_power_k"] == 0
        assert result["pass_at_k_pct"] == 50.0
        assert result["total_questions"] == 2

    def test_pass_power_k_all_pass(self):
        analyzer = MetaAnalyzer(pass_threshold=60)
        scores = {
            "q-001": [
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=80),
                ScoreResult(run_id=uuid4(), question_id="q-001", t1_completion=90),
            ],
        }
        result = analyzer.compute_pass_rates(scores, k=2)
        assert result["pass_at_k"] == 1
        assert result["pass_power_k"] == 1
        assert result["pp_gap"] == 0.0

    def test_empty_scores(self):
        analyzer = MetaAnalyzer()
        result = analyzer.compute_pass_rates({}, k=3)
        assert result["total_questions"] == 0
        assert result["pass_at_k_pct"] == 0.0

    def test_empty_pass_rates_do_not_crash(self):
        analyzer = MetaAnalyzer()
        result = analyzer.compute_pass_rates({})
        assert result["total_questions"] == 0
        assert result["pass_at_k_pct"] == 0.0
        assert result["pass_power_k_pct"] == 0.0
        assert result["k"] == 0
        assert result["threshold"] == 60.0

    def test_group_scores_by_question_sorts_attempts(self):
        run_id = uuid4()
        scores = [
            ScoreResult(run_id=run_id, question_id="q-1", attempt_index=2, t1_completion=30),
            ScoreResult(run_id=run_id, question_id="q-1", attempt_index=1, t1_completion=80),
            ScoreResult(run_id=run_id, question_id="q-2", attempt_index=1, t1_completion=90),
        ]

        grouped = MetaAnalyzer.group_scores_by_question(scores)

        assert [s.attempt_index for s in grouped["q-1"]] == [1, 2]
        assert list(grouped.keys()) == ["q-1", "q-2"]


class TestCommonIssuesInput:
    def test_build_summaries(self):
        analyzer = MetaAnalyzer()
        judge_results = [
            JudgeResult(
                run_id=uuid4(), question_id="q-001",
                execution_efficiency=65, tool_accuracy=80,
                thinking_efficiency=70, task_completion=75,
                conclusion="Needs better error handling",
            ),
        ]
        summaries = analyzer.build_common_issues_input(judge_results)
        assert len(summaries) == 1
        assert summaries[0]["question_id"] == "q-001"
        assert "execution_efficiency" in summaries[0]["deductions"]

    def test_extract_common_issues_from_judge_results(self):
        from src.core.schemas import CriticalStep, EvolutionSuggestion

        run_id = uuid4()
        judge_results = [
            JudgeResult(
                run_id=run_id,
                question_id="q-1",
                execution_efficiency=60,
                tool_accuracy=80,
                thinking_efficiency=70,
                task_completion=75,
                conclusion="存在重复读取文件的问题",
                critical_steps=[
                    CriticalStep(
                        step_id="Step 3",
                        assessment="REDUNDANT",
                        observation="重复读取同一 Excel 文件",
                        context_chain="前因是未缓存表结构, 后果是多消耗步骤",
                        root_cause="缺少中间结果复用",
                        expected_action="复用已读取的表结构",
                    )
                ],
                evolution_suggestions=[
                    EvolutionSuggestion(type="execution_path", suggestion="读取文件后缓存列名")
                ],
            )
        ]

        result = MetaAnalyzer().extract_common_issues(judge_results)

        assert result["status"] == "extracted"
        assert result["summary"]
        assert result["common_issues"][0]["question_ids"] == ["q-1"]
        assert result["improvement_suggestions"][0]["suggestion"] == "读取文件后缓存列名"
