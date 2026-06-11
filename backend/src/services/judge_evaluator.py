from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

from src.core.interfaces import BaseEvaluator, JudgeResultRepository
from src.core.schemas import (
    ScoreResult, QuestionItem, JudgeResult, JudgeVerdict, JudgeDimension,
    SkillCompliance, FatalViolation,
)
from src.infrastructure.llm_gateway import LLMClient
from src.infrastructure.trace_parser import TraceParser
from src.services.trace_condenser import TraceCondenser, CondensedTraceView

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are an expert agent evaluator. Your job is to review an agent's execution trace and provide a detailed, evidence-based assessment.

## CRITICAL: Task Relevance Check First
Before scoring, you MUST verify the trace is actually executing the assigned task:
- Read the "题目要求的输入文件" and "题目要求的输出目录" sections
- Check if the agent in the trace worked on THOSE files or completely different files
- If the trace is for a DIFFERENT task than what the question asks:
  * task_completion MUST be 0
  * execution_efficiency should still reflect the trace's objective quality
  * Explain the mismatch clearly in conclusion

## Scoring Rubric (0-100)

## Trace Integrity Boundary
If the user prompt contains "Trace 完整性诊断":
- failure_domain=harness means the observation/capture layer is incomplete.
- Missing or orphaned tool_result events MUST NOT be treated as agent tool failures.
- Do not penalize tool_accuracy only because a matching tool_result is absent.
- Judge only the behavior that is actually observable in the trace.
- If the missing observation prevents confident task-completion assessment, lower confidence in the explanation and state that the result is partially unverifiable.

## Condensed Trace Boundary
If the user prompt says judge_input_mode=condensed_trace:
- The raw trace is still the source for numeric metrics, trace integrity, and confidence.
- Condensed trace is used only for semantic judging.
- Preserved raw evidence steps are authoritative; chunk summaries are secondary.
- Do not invent missing details from summaries. If a scoring point needs evidence that is absent, say it is unverifiable.

### execution_efficiency (Action Efficiency)
- 90-100: Path is extremely streamlined, every action purposeful, zero wasted steps
- 75-89: Mostly efficient, minor redundancy (1-2 unnecessary actions)
- 60-74: Noticeable detours, 3+ redundant actions, inefficient tool usage patterns
- <60: Dead loops, extreme redundancy, repeatedly trying the same failing approach

### tool_accuracy (Tool Selection & Parameter Accuracy)
- 90-100: Optimal tool chosen every time, parameters precise on first attempt
- 75-89: Correct tools but occasional parameter adjustments needed
- 60-74: Multiple parameter construction failures, suboptimal tool choices
- <60: Consistently wrong tools, fundamentally incorrect approach

### thinking_efficiency (Context Understanding & Reasoning)
- 90-100: Perfect contextual reasoning, leverages all available information
- 75-89: Good reasoning, minor oversights in using error messages or results
- 60-74: Produces hallucinations, ignores error messages, misinterprets results
- <60: Completely ignores error logs, fabricates non-existent files or data

### task_completion (Result Quality & Intent Alignment)
- 90-100: Perfectly solves problem including edge cases, output is production-ready
- 75-89: Core functionality correct, minor edge cases missed
- 60-74: Surface-level completion but introduces new bugs or data issues
- <60: Completely deviates from user intent, fundamentally wrong output

## Critical Steps Analysis
Only list steps that are REDUNDANT or ERRONEOUS. Do NOT list normal steps.
For each problematic step, provide the full causal chain:
- observation: what went wrong
- context_chain: what led to this (前因) AND what resulted from this (后果)
- root_cause: the fundamental reason
- expected_action: what the agent should have done

## Fatal Rules
If any fatal_rules are provided, check each one. A fatal rule violation means the corresponding dimension score MUST be set to 0, regardless of other performance.

## Skill Compliance
If the question expects a Skill to be triggered:
- skill_invoked: Check if trace contains a tool_call for the Skill
- skill_read: Check if Skill content was actually read
- script_executed: If the Skill requires script execution, check if it was done
- Score: invoked(+3) + read(+3) + executed(+4), mapped to 0-100 linearly (0→0, 3→30, 6→60, 10→100)
"""


class JudgeEvaluator(BaseEvaluator):
    """LLM-based semantic evaluation engine. Performs 4-dimension scoring
    with step-level causal analysis, fatal rules checking, and Skill audit."""

    def __init__(
        self,
        judge_repo: JudgeResultRepository,
        llm_client: LLMClient,
        max_retries: int = 3,
        trace_condenser: TraceCondenser | None = None,
    ):
        self.judge_repo = judge_repo
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.trace_parser = TraceParser()
        self.trace_condenser = trace_condenser or TraceCondenser(llm_client)

    async def evaluate(
        self, run_id: UUID, question: QuestionItem, trace_data: list[dict]
    ) -> ScoreResult:
        trace_diagnostic = self.trace_parser.diagnose_integrity(trace_data)

        # Build user prompt with question context so judge can verify task relevance
        fatal_rules = question.eval_config.fatal_rules if question.eval_config else []
        skills_expected = question.skills if question.skills else ""

        # Load the question's actual task prompt from prompt_file
        question_prompt = ""
        if question.prompt_file:
            prompt_path = Path(question.prompt_file)
            if prompt_path.exists():
                question_prompt = prompt_path.read_text(encoding="utf-8")[:1000]

        judge_input_mode = "raw_trace"
        condensed_trace: CondensedTraceView | None = None
        if self.trace_condenser.should_condense(trace_data):
            condensed_trace = await self.trace_condenser.condense(
                trace_data,
                fatal_rules=fatal_rules,
                skills_expected=skills_expected,
            )
            trace_text = self._format_condensed_trace(condensed_trace)
            judge_input_mode = "condensed_trace"
        else:
            trace_text = self._format_trace(trace_data)

        user_prompt = self._build_user_prompt(
            question_id=question.question_id,
            question_name=question.question_name,
            trace_text=trace_text,
            fatal_rules=fatal_rules,
            skills_expected=skills_expected,
            question_prompt=question_prompt,
            expected_inputs=question.input_files,
            expected_output_dir=question.output_dir,
            trace_diagnostic=trace_diagnostic,
            judge_input_mode=judge_input_mode,
            condensed_trace=condensed_trace,
        )

        # Call LLM with retry
        verdict = None
        for attempt in range(self.max_retries):
            try:
                verdict = await self.llm_client.ask_structured_output(
                    system_prompt=JUDGE_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_model=JudgeVerdict,
                )
                break
            except Exception as e:
                logger.warning(f"Judge LLM attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2.0 * (2 ** attempt))

        if verdict is None:
            # All retries exhausted — return partial score from Skill compliance only
            return ScoreResult(
                run_id=run_id, question_id=question.question_id,
                t1_completion=0.0, t1_judge_only=0.0,
            )

        # Apply fatal rules: zero out violated dimensions
        dim_scores = {
            JudgeDimension.EXECUTION_EFFICIENCY: verdict.execution_efficiency.score,
            JudgeDimension.TOOL_ACCURACY: verdict.tool_accuracy.score,
            JudgeDimension.THINKING_EFFICIENCY: verdict.thinking_efficiency.score,
            JudgeDimension.TASK_COMPLETION: verdict.task_completion.score,
        }
        for fv in verdict.fatal_violations:
            if fv.dimension in dim_scores:
                dim_scores[fv.dimension] = 0

        # Apply Skill compliance weighting to tool_accuracy
        tool_score = dim_scores[JudgeDimension.TOOL_ACCURACY]
        if verdict.skill_compliance and skills_expected:
            tool_score = int(0.3 * tool_score + 0.7 * verdict.skill_compliance.score)

        # Persist JudgeResult
        judge_result = JudgeResult(
            run_id=run_id,
            question_id=question.question_id,
            execution_efficiency=dim_scores[JudgeDimension.EXECUTION_EFFICIENCY],
            tool_accuracy=tool_score,
            thinking_efficiency=dim_scores[JudgeDimension.THINKING_EFFICIENCY],
            task_completion=dim_scores[JudgeDimension.TASK_COMPLETION],
            conclusion=verdict.conclusion,
            critical_steps=verdict.critical_steps,
            evolution_suggestions=verdict.evolution_suggestions,
            skill_compliance=verdict.skill_compliance,
            fatal_violations=verdict.fatal_violations,
            raw_response=json.dumps(
                {
                    "verdict": verdict.model_dump(mode="json"),
                    "judge_input": {
                        "mode": judge_input_mode,
                        "compression_ratio": (
                            condensed_trace.compression_ratio if condensed_trace else 1.0
                        ),
                        "preserved_step_ids": (
                            condensed_trace.preserved_step_ids if condensed_trace else []
                        ),
                    },
                },
                ensure_ascii=False,
            ),
        )
        await self.judge_repo.save(judge_result)

        # Return judge-side score for fusion
        return ScoreResult(
            run_id=run_id,
            question_id=question.question_id,
            t1_judge_only=float(judge_result.task_completion),
            t1_completion=float(judge_result.task_completion),
        )

    def _format_trace(self, trace_data: list[dict]) -> str:
        lines = []
        lines.append(f"共 {len(trace_data)} 个步骤。每个步骤编号 (Step N) 是唯一标识。\n")
        for i, event in enumerate(trace_data, 1):
            lines.append(f"### Step {i}")
            lines.append(json.dumps(event, ensure_ascii=False))
            lines.append("")
        return "\n".join(lines)

    def _format_condensed_trace(self, condensed: CondensedTraceView) -> str:
        lines = [
            "judge_input_mode=condensed_trace",
            f"original_event_count={condensed.original_event_count}",
            f"original_char_count={condensed.original_char_count}",
            f"condensed_char_count={condensed.condensed_char_count}",
            f"compression_ratio={condensed.compression_ratio}",
            f"preserved_step_ids={condensed.preserved_step_ids}",
            "",
            "## 不可压缩关键原文证据",
            condensed.preserved_evidence_text or "无",
            "",
            "## 分块语义摘要",
        ]
        for summary in condensed.chunk_summaries:
            lines.append(json.dumps(summary.model_dump(), ensure_ascii=False, indent=2))
        return "\n".join(lines)

    def _build_user_prompt(
        self,
        question_id: str,
        question_name: str,
        trace_text: str,
        fatal_rules: list,
        skills_expected: str,
        question_prompt: str = "",
        expected_inputs: list[str] | None = None,
        expected_output_dir: str = "",
        trace_diagnostic: dict | None = None,
        judge_input_mode: str = "raw_trace",
        condensed_trace: CondensedTraceView | None = None,
    ) -> str:
        parts = [
            f"## 评测题目",
            f"题目 ID: {question_id}",
            f"题目名称: {question_name}",
            "",
        ]

        # CRITICAL: Include the actual task description so judge can verify relevance
        if question_prompt:
            parts.append(f"## 题目的任务要求（Agent 应该执行的任务）")
            parts.append(question_prompt)
            parts.append("")

        if expected_inputs:
            parts.append(f"## 题目要求的输入文件: {', '.join(expected_inputs)}")
            parts.append("请检查 Agent 是否操作了这些文件，还是操作了不相关的文件。")
            parts.append("")

        if expected_output_dir:
            parts.append(f"## 题目要求的输出目录: {expected_output_dir}")
            parts.append("")

        if trace_diagnostic and trace_diagnostic.get("integrity_status") != "ok":
            parts.append("## Trace 完整性诊断")
            parts.append(f"integrity_status: {trace_diagnostic.get('integrity_status')}")
            parts.append(f"failure_domain: {trace_diagnostic.get('failure_domain')}")
            parts.append(
                "affected_tool_call_ids: "
                + ", ".join(trace_diagnostic.get("affected_tool_call_ids") or [])
            )
            parts.append(f"scoring_policy: {trace_diagnostic.get('scoring_policy')}")
            parts.append(f"message: {trace_diagnostic.get('message')}")
            parts.append(
                "裁判约束: 这是观测链路问题，不得仅因缺失 tool_result 将其判定为 Agent 工具调用失败。"
            )
            parts.append("")

        parts.append("## Judge 输入模式")
        parts.append(f"judge_input_mode: {judge_input_mode}")
        if condensed_trace is not None:
            parts.append("raw_trace_metrics_source: raw_trace")
            parts.append("condensed_trace_used_for: judge_semantic_scoring")
            parts.append(f"compression_ratio: {condensed_trace.compression_ratio}")
            parts.append(f"preserved_step_ids: {condensed_trace.preserved_step_ids}")
            parts.append("裁判约束: 数值型过程指标、完整性、置信度来自原始 trace；压缩内容只用于语义判断。")
        parts.append("")

        # TASK RELEVANCE CHECK — the gate
        parts.append("## ⚠️ 任务相关性检查（最重要！先做这一步）")
        parts.append("首先判断 Trace 中的 Agent 是否在执行**这道题目要求的任务**：")
        parts.append("- 检查 Trace Step 1 的 user_question 是否与题目任务要求匹配")
        parts.append("- 检查 Agent 操作的文件是否与题目要求的输入文件相关")
        parts.append("- 如果 Trace 明显在执行另一个不相关的任务（例如题目要求分析告警但 Trace 在分析经营数据），")
        parts.append("  则 task_completion 必须判定为 0，并在 conclusion 中明确说明「Trace 与题目不匹配」")
        parts.append("")

        if skills_expected:
            parts.append(f"## 期望触发的 Skill: {skills_expected}")
            parts.append("请检查 Agent 是否调用了该 Skill、读取了内容、执行了必要脚本。")
            parts.append("")

        if fatal_rules:
            parts.append("## 致命规则 (Fatal Rules)")
            parts.append("以下规则触犯任意一条，对应维度直接判 0 分：")
            for fr in fatal_rules:
                parts.append(f"- [{fr.rule_id}] {fr.description} → 维度: {fr.dimension.value}")
            parts.append("")

        parts.append("## Agent 执行轨迹")
        parts.append(trace_text)
        return "\n".join(parts)
