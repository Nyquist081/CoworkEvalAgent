from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

from src.core.interfaces import BaseEvaluator, JudgeResultRepository
from src.core.schemas import (
    ScoreResult, QuestionItem, JudgeResult, JudgeVerdict, JudgeDimension,
    SkillCompliance, FatalViolation,
)
from src.infrastructure.llm_gateway import LLMClient

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are an expert agent evaluator. Your job is to review an agent's execution trace and provide a detailed, evidence-based assessment.

## Scoring Rubric (0-100)

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
    ):
        self.judge_repo = judge_repo
        self.llm_client = llm_client
        self.max_retries = max_retries

    async def evaluate(
        self, run_id: UUID, question: QuestionItem, trace_data: list[dict]
    ) -> ScoreResult:
        # Format trace as Step-numbered text
        trace_text = self._format_trace(trace_data)

        # Build user prompt
        fatal_rules = question.eval_config.fatal_rules if question.eval_config else []
        skills_expected = question.skills if question.skills else ""

        user_prompt = self._build_user_prompt(
            question_id=question.question_id,
            question_name=question.question_name,
            trace_text=trace_text,
            fatal_rules=fatal_rules,
            skills_expected=skills_expected,
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
            raw_response=verdict.model_dump_json(),
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

    def _build_user_prompt(
        self,
        question_id: str,
        question_name: str,
        trace_text: str,
        fatal_rules: list,
        skills_expected: str,
    ) -> str:
        parts = [
            f"## 评测任务",
            f"题目 ID: {question_id}",
            f"题目名称: {question_name}",
            "",
        ]

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
