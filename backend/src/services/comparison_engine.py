from __future__ import annotations
from uuid import UUID

from src.core.schemas import ScoreResult


class ComparisonEngine:
    """Computes multi-version comparison data for frontend charts."""

    def radar_data(self, runs: dict[str, list[ScoreResult]]) -> dict:
        """Build radar chart data for multiple runs.

        Args:
            runs: run_label → list of ScoreResults

        Returns:
            {"dimensions": ["T1","T2","T3","T4","E","C"],
             "series": [{"label": "v1.0", "values": [75,80,90,70,85,95]}, ...]}
        """
        dimensions = ["T1", "T2", "T3", "T4", "E", "C"]
        series = []
        for label, scores in runs.items():
            if not scores:
                continue
            n = len(scores)
            values = [
                round(sum(s.t1_completion or 0 for s in scores) / n, 1),
                round(sum(s.t2_accuracy or 0 for s in scores) / n, 1),
                round(sum(s.t3_efficiency or 0 for s in scores) / n, 1),
                round(sum(s.t4_thinking or 0 for s in scores) / n, 1),
                round(sum(s.e_performance or 0 for s in scores) / n, 1),
                round(sum(s.c_cost or 0 for s in scores) / n, 1),
            ]
            series.append({"label": label, "values": values})
        return {"dimensions": dimensions, "series": series}

    def heatmap_data(
        self, scores: list[ScoreResult], categories: dict[str, str] | None = None
    ) -> dict:
        """Build heatmap data: question × dimension → score.

        Returns:
            {"questions": ["q-001",...], "dimensions": ["T1",...],
             "data": [[75,80,...], [60,70,...], ...]}
        """
        dims = ["T1", "T2", "T3", "T4", "E", "C"]
        questions = []
        data = []
        for s in scores:
            questions.append(s.question_id)
            data.append([
                round(s.t1_completion or 0, 1),
                round(s.t2_accuracy or 0, 1),
                round(s.t3_efficiency or 0, 1),
                round(s.t4_thinking or 0, 1),
                round(s.e_performance or 0, 1),
                round(s.c_cost or 0, 1),
            ])
        return {"questions": questions, "dimensions": dims, "data": data}

    def trend_data(self, run_sequences: list[dict]) -> dict:
        """Build trend line data for a version sequence.

        Args:
            run_sequences: [{"label": "v1.0", "overall": 78.5, "pass_at_k_pct": 75.0,
                             "pass_power_k_pct": 50.0, "pass_pp_gap": 25.0}, ...]
        """
        labels = []
        overalls = []
        pass_at_ks = []
        pass_power_ks = []
        for rs in run_sequences:
            labels.append(rs["label"])
            overalls.append(rs.get("overall", 0))
            pass_at_ks.append(rs.get("pass_at_k_pct", 0))
            pass_power_ks.append(rs.get("pass_power_k_pct", 0))
        return {
            "labels": labels,
            "overall_scores": overalls,
            "pass_at_k_pcts": pass_at_ks,
            "pass_power_k_pcts": pass_power_ks,
        }

    def pass_rate_comparison(
        self, run_pass_rates: dict[str, dict]
    ) -> dict:
        """Compare pass@k/pass^k across runs.

        Args:
            run_pass_rates: run_label → pass_rate_dict (from MetaAnalyzer)

        Returns:
            {"runs": [{"label": "v1.0", "pass_at_k_pct": 75.0,
                       "pass_power_k_pct": 50.0, "pp_gap": 25.0}, ...]}
        """
        runs = []
        for label, pr in run_pass_rates.items():
            runs.append({
                "label": label,
                "pass_at_k_pct": pr.get("pass_at_k_pct", 0),
                "pass_power_k_pct": pr.get("pass_power_k_pct", 0),
                "pp_gap": pr.get("pp_gap", 0),
                "k": pr.get("k", 0),
                "threshold": pr.get("threshold", 0.6),
            })
        return {"runs": runs}

    def observability_comparison(self, runs: dict[str, list[ScoreResult]]) -> dict:
        """Compare harness trace observability separately from agent quality."""
        summaries = []
        for label, scores in runs.items():
            total_tool_calls = sum(s.actual_tool_calls for s in scores)
            observed_tool_results = sum(s.observed_tool_results for s in scores)
            missing_tool_results = sum(s.missing_tool_results for s in scores)
            trace_observability_rate = (
                observed_tool_results / total_tool_calls * 100
                if total_tool_calls > 0 else 100.0
            )
            observed_denominator = max(observed_tool_results, 0)
            agent_tool_success_rate = (
                sum(s.actual_success_calls for s in scores) / observed_denominator * 100
                if observed_denominator > 0 else 100.0
            )
            validity = "valid" if missing_tool_results == 0 else "trace_incomplete"
            summaries.append({
                "label": label,
                "actual_tool_calls": total_tool_calls,
                "observed_tool_results": observed_tool_results,
                "missing_tool_results": missing_tool_results,
                "agent_tool_success_rate": round(agent_tool_success_rate, 1),
                "trace_observability_rate": round(trace_observability_rate, 1),
                "evaluation_validity": validity,
                "can_claim_winner": validity == "valid",
            })
        return {"runs": summaries}
