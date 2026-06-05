"""CoworkEval CLI — one command to evaluate, compare, and serve."""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock

import click
from src.core.schemas import Manifest, QuestionItem, EvalConfig
from src.infrastructure.trace_parser import TraceParser
from src.infrastructure.claude_code_adapter import ClaudeCodeAdapter
from src.infrastructure.llm_gateway import LLMClient
from src.services.baseline_evaluator import BaselineEvaluator
from src.services.judge_evaluator import JudgeEvaluator
from src.services.fusion_service import FusionService
from src.evaluator.result_comparator import ResultComparator


@click.group()
def cli():
    """CoworkEval — Agent 评测基座 CLI"""


@cli.command()
@click.argument("manifest_path", type=click.Path(exists=True))
def register(manifest_path):
    """注册评测集 Manifest"""
    m = Manifest.model_validate(json.loads(Path(manifest_path).read_text()))
    click.echo(f"✅ 已注册: {m.benchmark_id}")
    click.echo(f"   版本: {m.version}")
    click.echo(f"   题目数: {m.total_questions}")
    for q in m.questions:
        click.echo(f"   - {q.question_id}: {q.question_name} [{q.difficulty}]")


@cli.command()
@click.option("--trace", "-t", required=True, help="Trace JSONL 文件路径")
@click.option("--question", "-q", default=None, help="题目ID (可选，从trace文件名推断)")
@click.option("--baseline-tools", default=10, help="基准工具调用次数")
@click.option("--baseline-tokens", default=500000, help="基准Token数")
@click.option("--baseline-rounds", default=10, help="基准轮次")
@click.option("--baseline-time", default=50000, help="基准耗时(ms)")
@click.option("--baseline-cost", default=2.0, help="基准成本(USD)")
@click.option("--judge/--no-judge", default=False, help="启用裁判模型评测")
def evaluate(trace, question, baseline_tools, baseline_tokens, baseline_rounds,
             baseline_time, baseline_cost, judge):
    """评测一个 Trace 文件"""
    async def _run():
        parser = TraceParser()
        trace_data = await parser.parse(trace)
        metrics = parser.extract_metrics(trace_data)

        qid = question or Path(trace).stem
        q = QuestionItem(
            question_id=qid, question_name=qid,
            category="通用", difficulty="中等",
            prompt_file="", output_dir="",
            eval_config=EvalConfig(),
            baseline_tool_count=baseline_tools,
            baseline_tokens=baseline_tokens,
            baseline_rounds=baseline_rounds,
            baseline_time_ms=baseline_time,
            baseline_cost_usd=baseline_cost,
        )

        # Baseline scoring
        repo = AsyncMock(); repo.save = AsyncMock()
        evaluator = BaselineEvaluator(score_repo=repo, comparator=ResultComparator())
        score = await evaluator.evaluate(run_id=uuid4(), question=q, trace_data=trace_data)

        click.echo(f"\n📊 {qid}")
        click.echo(f"   实际指标: {metrics['total_tool_calls']}工具 {metrics['total_tokens']}tokens "
                    f"{metrics['duration_ms']}ms ${metrics['cost_usd']:.4f}")
        click.echo(f"   {'─'*45}")
        click.echo(f"   T2 工具准确率: {score.t2_accuracy or 0:>6.1f}  "
                    f"({metrics['success_tool_calls']}/{metrics['total_tool_calls']} 成功)")
        click.echo(f"   T3 工具效率:   {score.t3_efficiency or 0:>6.1f}  "
                    f"(baseline={baseline_tools})")
        click.echo(f"   T4 思考效率:   {score.t4_thinking or 0:>6.1f}")
        click.echo(f"   E  E2E性能:    {score.e_performance or 0:>6.1f}")
        click.echo(f"   C  成本效率:   {score.c_cost or 0:>6.1f}")
        click.echo(f"   综合总分:      {score.overall_score or 0:>6.1f}")

        if judge:
            click.echo("\n🧠 裁判模型评测中...")
            try:
                llm = LLMClient()
                jrepo = AsyncMock(); jrepo.save = AsyncMock()
                jeval = JudgeEvaluator(judge_repo=jrepo, llm_client=llm)
                await jeval.evaluate(run_id=uuid4(), question=q, trace_data=trace_data)
                jr = jrepo.save.call_args[0][0]
                click.echo(f"   执行效率: {jr.execution_efficiency}/100")
                click.echo(f"   工具准确性: {jr.tool_accuracy}/100")
                click.echo(f"   思考效率: {jr.thinking_efficiency}/100")
                click.echo(f"   任务完成度: {jr.task_completion}/100")
                click.echo(f"   {jr.conclusion[:150]}")

                fusion = FusionService()
                fused = await fusion.fuse(score, jr)
                click.echo(f"\n   融合后总分: {fused.overall_score:.1f}")
            except Exception as e:
                click.echo(f"   ⚠️  裁判模型不可用: {e}")

    asyncio.run(_run())


@cli.command()
@click.option("--baseline", "-b", required=True, help="Baseline Trace 文件")
@click.option("--actual", "-a", required=True, help="实测 Trace 文件")
def compare(baseline, actual):
    """对比两个 Trace（Baseline vs 实测）"""
    async def _run():
        parser = TraceParser()
        b_trace = await parser.parse(baseline)
        a_trace = await parser.parse(actual)
        b_m = parser.extract_metrics(b_trace)
        a_m = parser.extract_metrics(a_trace)

        click.echo(f"\n🏆 A/B 对比")
        click.echo(f"   {'指标':<20} {'Baseline':>12} {'实测':>12} {'变化':>10}")
        click.echo(f"   {'─'*20} {'─'*12} {'─'*12} {'─'*10}")

        dims = [
            ("工具调用", b_m["total_tool_calls"], a_m["total_tool_calls"], ""),
            ("成功率", f"{b_m['tool_success_rate']:.0f}%", f"{a_m['tool_success_rate']:.0f}%", ""),
            ("Token", b_m["total_tokens"], a_m["total_tokens"], ""),
            ("耗时(ms)", b_m["duration_ms"], a_m["duration_ms"], ""),
            ("成本(USD)", f"${b_m['cost_usd']:.4f}", f"${a_m['cost_usd']:.4f}", ""),
        ]

        for name, bv, av, _ in dims:
            if isinstance(bv, (int, float)) and isinstance(av, (int, float)):
                delta = (av - bv) / bv * 100 if bv else 0
                arrow = "↓" if delta < 0 else "↑" if delta > 0 else "→"
                click.echo(f"   {name:<20} {str(bv):>12} {str(av):>12} {arrow}{abs(delta):>8.1f}%")
            else:
                click.echo(f"   {name:<20} {str(bv):>12} {str(av):>12}")

    asyncio.run(_run())


@cli.command()
@click.option("--session", "-s", required=True, help="Claude Code session JSONL 路径")
def segments(session):
    """列出 Claude Code 会话中的任务段"""
    adapter = ClaudeCodeAdapter()
    segs = adapter.list_task_segments(session)
    click.echo(f"\n📋 会话任务段 ({len(segs)} 个):")
    for s in segs:
        click.echo(f"   [{s['segment_index']}] {s['summary'][:100]}...")


@cli.command()
@click.option("--session", "-s", required=True, help="Claude Code session JSONL 路径")
@click.option("--segment", "-n", type=int, required=True, help="任务段序号")
@click.option("--output", "-o", default="baseline", help="输出文件名前缀")
def extract(session, segment, output):
    """从 Claude Code 会话中提取任务段为 Trace"""
    adapter = ClaudeCodeAdapter()
    baseline = adapter.save_baseline_trace(session, segment, output)
    click.echo(f"✅ Trace 已保存: {baseline['baseline_trace_file']}")
    click.echo(f"   tool_count={baseline['baseline_tool_count']} "
                f"tokens={baseline['baseline_tokens']} "
                f"time={baseline['baseline_time_ms']}ms "
                f"cost=${baseline['baseline_cost_usd']:.4f}")


@cli.command()
@click.option("--port", "-p", default=8000, help="端口号")
def serve(port):
    """启动 Web 界面"""
    import uvicorn
    click.echo(f"🚀 CoworkEval Web: http://localhost:{port}")
    click.echo(f"   API 文档: http://localhost:{port}/docs")
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    cli()
